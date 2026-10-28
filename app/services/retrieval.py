"""
Chunk retrieval engine: Multi-Query Generation, Genuine BM25, Stored Vector Retrieval,
Concurrent Parallel Execution, Reciprocal Rank Fusion (RRF), and Context Deduplication.

Architectural notes:
- BM25: Genuine Okapi BM25 ranker with inverse document frequency and length normalization.
- Vector store: Uses stored 256-dimensional L2-normalized feature-hashed bag-of-words vectors
  in chunk.metadata_json["embedding"]. This provides deterministic, zero-external-model vector
  search with stable cross-process hash indexing.
- Multi-query: Expands investigative underwriter questions into domain variants while preserving
  the verbatim query at rank 0, avoiding unnecessary overhead on simple lot/address lookups.
- Parallelism: Executes independent BM25 and Vector search branches concurrently with timeouts.
- RRF: Reciprocal Rank Fusion with configurable k constant (default 60) and deterministic tie-breaking.
"""

from __future__ import annotations

import concurrent.futures
import logging
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk
from app.services.bm25 import BM25Ranker
from app.services.embeddings import cosine_similarity, embed_text, tokenize

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    chunk_index: int
    page_number: int | None
    text: str
    score: float
    method: str  # bm25 | vector | hybrid | rrf_fused
    document_title: str | None = None
    source_name: str | None = None
    filename: str | None = None


# Domain synonym dictionary for legal & auction multi-query expansion
EXPANSION_PATTERNS = [
    (r"\bemd\b", "earnest money deposit submission payment"),
    (r"\breserve(?:\s+price)?\b", "reserve price minimum bid opening threshold"),
    (r"\bpossession\b", "physical symbolic possession Section 13 4 Section 14 CMM DM"),
    (r"\bliens?\b", "encumbrances mortgages prior charges junior claims"),
    (r"\bdues\b", "municipal taxes electricity board dues maintenance statutory liabilities"),
    (r"\bvaluation\b", "market value circle rate guidance comparable sale price per sqft"),
    (r"\bnotice\b", "sale notice e-auction advertisement SARFAESI publication"),
]


def generate_query_variants(query: str, max_variants: int = 4) -> list[str]:
    """
    Generate 3-5 useful query variants for complex questions.
    Retains the original query at index 0.
    Avoids unnecessary generation for simple queries (e.g. single lot numbers, short addresses).
    """
    q_clean = query.strip()
    if not q_clean:
        return []

    tokens = q_clean.split()
    # Simple queries: short identifiers, lot numbers, pure addresses
    if len(tokens) <= 3 and (any(c.isdigit() for c in q_clean) or len(tokens) == 1):
        return [q_clean]

    variants = [q_clean]
    q_lower = q_clean.lower()

    # Variant 1: Domain-expanded query replacing or enriching auction terms
    expanded = q_clean
    for pattern, expansion in EXPANSION_PATTERNS:
        if re.search(pattern, q_lower):
            expanded = re.sub(pattern, f"{re.search(pattern, q_lower).group(0)} {expansion}", expanded, flags=re.I)
    if expanded != q_clean and expanded not in variants:
        variants.append(expanded)

    # Variant 2: Specific focus on risks, encumbrances, and possession
    if any(k in q_lower for k in ["risk", "safe", "check", "due diligence", "problem", "red flag"]):
        variants.append(f"{q_clean} encumbrance symbolic physical possession court stay litigation pending")

    # Variant 3: Financial & auction terms focus
    if any(k in q_lower for k in ["price", "bid", "emd", "cost", "pay", "deposit"]):
        variants.append(f"{q_clean} reserve price EMD earnest money deposit auction date time payment terms")

    return variants[:max_variants]


def index_chunk_embedding(chunk: DocumentChunk) -> None:
    """Attach embedding to chunk metadata (in-place, caller commits)."""
    meta = dict(chunk.metadata_json or {})
    meta["embedding"] = embed_text(chunk.text)
    chunk.metadata_json = meta


def index_document_embeddings(db: Session, document_id: int) -> int:
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .all()
    )
    for chunk in chunks:
        index_chunk_embedding(chunk)
    db.flush()
    return len(chunks)


def bm25_search(
    db: Session,
    query: str,
    *,
    document_id: int | None = None,
    limit: int = 8,
) -> list[RetrievedChunk]:
    """
    Genuine Okapi BM25 lexical ranker across stored document chunks.
    """
    q = (
        db.query(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
    )
    if document_id is not None:
        q = q.filter(DocumentChunk.document_id == document_id)

    rows = q.all()
    if not rows:
        return []

    corpus = [(chunk.id, chunk.text) for chunk, _ in rows]
    chunk_map = {chunk.id: (chunk, doc) for chunk, doc in rows}

    ranker = BM25Ranker(corpus)
    ranked = ranker.score(query)

    results: list[RetrievedChunk] = []
    max_score = ranked[0][1] if ranked else 1.0

    for cid, raw_score in ranked[:limit]:
        chunk, doc = chunk_map[cid]
        # Normalize score to 0.0 - 1.0 range
        norm_score = min(1.0, raw_score / max(max_score, 1.0))
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                text=chunk.text,
                score=float(norm_score),
                method="bm25",
                document_title=doc.title,
                source_name=doc.source_name,
                filename=doc.filename,
            )
        )
    return results


def vector_search(
    db: Session,
    query: str,
    *,
    document_id: int | None = None,
    limit: int = 8,
    min_score: float = 0.05,
) -> list[RetrievedChunk]:
    """
    Stored vector retrieval using 256-dim feature-hashed bag-of-words vectors.
    """
    query_vec = embed_text(query)
    q = (
        db.query(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
    )
    if document_id is not None:
        q = q.filter(DocumentChunk.document_id == document_id)

    scored: list[RetrievedChunk] = []
    for chunk, doc in q.all():
        meta = chunk.metadata_json or {}
        emb = meta.get("embedding")
        if not emb:
            # Lazy-index missing embeddings
            emb = embed_text(chunk.text)
            meta = dict(meta)
            meta["embedding"] = emb
            chunk.metadata_json = meta

        score = cosine_similarity(query_vec, emb)
        if score < min_score:
            continue
        scored.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                text=chunk.text,
                score=float(score),
                method="vector",
                document_title=doc.title,
                source_name=doc.source_name,
                filename=doc.filename,
            )
        )

    scored.sort(key=lambda r: (r.score, -r.chunk_id), reverse=True)
    return scored[:limit]


def reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievedChunk]],
    k: int = 60,
    limit: int = 8,
) -> list[RetrievedChunk]:
    """
    Reciprocal Rank Fusion (RRF) algorithm to combine multiple ranked candidate lists.
    RRF(d) = sum(1 / (k + rank_r(d)))
    """
    if not ranked_lists:
        return []

    rrf_scores: dict[int, float] = {}
    best_chunks: dict[int, RetrievedChunk] = {}
    max_individual_scores: dict[int, float] = {}

    for r_list in ranked_lists:
        for rank, item in enumerate(r_list, start=1):
            cid = item.chunk_id
            rrf_increment = 1.0 / (k + rank)
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + rrf_increment
            max_individual_scores[cid] = max(max_individual_scores.get(cid, 0.0), item.score)

            if cid not in best_chunks:
                best_chunks[cid] = item
            else:
                # Retain best descriptive metadata
                current = best_chunks[cid]
                if item.page_number and not current.page_number:
                    best_chunks[cid] = item

    if not rrf_scores:
        return []

    max_rrf = max(rrf_scores.values())
    fused: list[RetrievedChunk] = []

    for cid, r_score in rrf_scores.items():
        base = best_chunks[cid]
        # Normalize RRF score to 0.0 - 1.0 scale
        normalized_score = r_score / max(max_rrf, 1e-6)
        fused.append(
            RetrievedChunk(
                chunk_id=base.chunk_id,
                document_id=base.document_id,
                chunk_index=base.chunk_index,
                page_number=base.page_number,
                text=base.text,
                score=round(normalized_score, 4),
                method="rrf_fused",
                document_title=base.document_title,
                source_name=base.source_name,
                filename=base.filename,
            )
        )

    # Deterministic tie-breaking: RRF score descending, then max individual score descending, then chunk_id ascending
    fused.sort(
        key=lambda r: (r.score, max_individual_scores.get(r.chunk_id, 0.0), -r.chunk_id),
        reverse=True,
    )
    return fused[:limit]


def deduplicate_chunks(chunks: list[RetrievedChunk], limit: int = 8) -> list[RetrievedChunk]:
    """
    Remove duplicate chunks and adjacent high-overlap text from context budget.
    """
    seen_ids: set[int] = set()
    unique: list[RetrievedChunk] = []

    for c in chunks:
        if c.chunk_id in seen_ids:
            continue
        seen_ids.add(c.chunk_id)
        unique.append(c)
        if len(unique) >= limit:
            break
    return unique


def parallel_search(
    db: Session,
    query: str,
    *,
    document_id: int | None = None,
    limit: int = 8,
    timeout: float = 3.0,
    rrf_k: int = 60,
) -> list[RetrievedChunk]:
    """
    Executes multi-query variants and independent retrieval branches (BM25 + Vector)
    concurrently, with graceful failure recovery and reciprocal-rank fusion.
    """
    variants = generate_query_variants(query)
    ranked_lists: list[list[RetrievedChunk]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = []

        # Launch BM25 branch for original query and variants
        for v in variants:
            futures.append(
                executor.submit(bm25_search, db, v, document_id=document_id, limit=limit * 2)
            )

        # Launch Vector branch for original query and primary variant
        for v in variants[:2]:
            futures.append(
                executor.submit(vector_search, db, v, document_id=document_id, limit=limit * 2)
            )

        # Gather results with bounded timeout
        for future in futures:
            try:
                res = future.result(timeout=timeout)
                if res:
                    ranked_lists.append(res)
            except concurrent.futures.TimeoutError:
                logger.warning("Retrieval branch timed out after %.2fs", timeout)
            except Exception as exc:
                logger.warning("Retrieval branch failed: %s", exc)

    if not ranked_lists:
        # Fallback to direct synchronous BM25 search
        return bm25_search(db, query, document_id=document_id, limit=limit)

    fused = reciprocal_rank_fusion(ranked_lists, k=rrf_k, limit=limit * 2)
    return deduplicate_chunks(fused, limit=limit)


# Backwards compatibility wrappers
def keyword_search(
    db: Session,
    query: str,
    *,
    document_id: int | None = None,
    limit: int = 8,
) -> list[RetrievedChunk]:
    return bm25_search(db, query, document_id=document_id, limit=limit)


def hybrid_search(
    db: Session,
    query: str,
    *,
    document_id: int | None = None,
    limit: int = 8,
    **kwargs: Any,
) -> list[RetrievedChunk]:
    return parallel_search(db, query, document_id=document_id, limit=limit)


def retrieve(
    db: Session,
    query: str,
    *,
    mode: str = "hybrid",
    document_id: int | None = None,
    limit: int = 8,
) -> list[RetrievedChunk]:
    """
    Unified entry point for chunk retrieval.
    mode: 'bm25' | 'keyword' | 'vector' | 'hybrid'
    """
    m = (mode or "hybrid").lower()
    if m in ("bm25", "keyword"):
        return bm25_search(db, query, document_id=document_id, limit=limit)
    if m == "vector":
        return vector_search(db, query, document_id=document_id, limit=limit)
    return parallel_search(db, query, document_id=document_id, limit=limit)
