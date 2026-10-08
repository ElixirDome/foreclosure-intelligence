"""
Chunk retrieval: keyword, vector, and hybrid (Phases 3–5).

No external vector DB required. Vectors live on chunk.metadata_json["embedding"]
when indexed; keyword search works immediately on chunk.text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk
from app.services.embeddings import cosine_similarity, embed_text, tokenize


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    chunk_index: int
    page_number: int | None
    text: str
    score: float
    method: str  # keyword | vector | hybrid
    document_title: str | None = None
    source_name: str | None = None
    filename: str | None = None


def _keyword_score(query: str, text: str) -> float:
    q_tokens = set(tokenize(query))
    if not q_tokens:
        return 0.0

    t_tokens = tokenize(text)
    if not t_tokens:
        return 0.0

    t_set = set(t_tokens)
    overlap = q_tokens & t_set
    if not overlap:
        # Phrase bonus: full query substring
        if query.lower().strip() in text.lower():
            return 0.35
        return 0.0

    recall = len(overlap) / len(q_tokens)
    precision = len(overlap) / max(len(t_set), 1)
    # Favor denser matches of query terms
    score = (0.7 * recall) + (0.3 * min(precision * 5, 1.0))

    # Boost exact phrase
    if query.lower().strip() in text.lower():
        score = min(1.0, score + 0.25)

    # Numeric boost (reserve prices, plot numbers)
    for token in q_tokens:
        if re.search(rf"\b{re.escape(token)}\b", text, re.IGNORECASE):
            if any(c.isdigit() for c in token):
                score = min(1.0, score + 0.1)

    return min(1.0, score)


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


def keyword_search(
    db: Session,
    query: str,
    *,
    document_id: int | None = None,
    limit: int = 8,
) -> list[RetrievedChunk]:
    q = (
        db.query(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
    )
    if document_id is not None:
        q = q.filter(DocumentChunk.document_id == document_id)

    scored: list[RetrievedChunk] = []
    for chunk, doc in q.all():
        score = _keyword_score(query, chunk.text)
        if score <= 0:
            continue
        scored.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                text=chunk.text,
                score=score,
                method="keyword",
                document_title=doc.title,
                source_name=doc.source_name,
                filename=doc.filename,
            )
        )

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:limit]


def vector_search(
    db: Session,
    query: str,
    *,
    document_id: int | None = None,
    limit: int = 8,
    min_score: float = 0.05,
) -> list[RetrievedChunk]:
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

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:limit]


def hybrid_search(
    db: Session,
    query: str,
    *,
    document_id: int | None = None,
    limit: int = 8,
    keyword_weight: float = 0.55,
    vector_weight: float = 0.45,
) -> list[RetrievedChunk]:
    """
    Combine keyword + vector scores (Phase 5).

    Same chunk appearing in both lists is merged with a weighted score.
    """
    kw = {
        r.chunk_id: r
        for r in keyword_search(
            db, query, document_id=document_id, limit=limit * 3
        )
    }
    vec = {
        r.chunk_id: r
        for r in vector_search(
            db, query, document_id=document_id, limit=limit * 3
        )
    }

    all_ids = set(kw) | set(vec)
    merged: list[RetrievedChunk] = []

    for cid in all_ids:
        k = kw.get(cid)
        v = vec.get(cid)
        base = k or v
        assert base is not None
        k_score = k.score if k else 0.0
        v_score = v.score if v else 0.0
        score = (keyword_weight * k_score) + (vector_weight * v_score)
        merged.append(
            RetrievedChunk(
                chunk_id=base.chunk_id,
                document_id=base.document_id,
                chunk_index=base.chunk_index,
                page_number=base.page_number,
                text=base.text,
                score=score,
                method="hybrid",
                document_title=base.document_title,
                source_name=base.source_name,
                filename=base.filename,
            )
        )

    merged.sort(key=lambda r: r.score, reverse=True)
    return merged[:limit]


def retrieve(
    db: Session,
    query: str,
    *,
    mode: str = "hybrid",
    document_id: int | None = None,
    limit: int = 8,
) -> list[RetrievedChunk]:
    mode = (mode or "hybrid").lower()
    if mode == "keyword":
        return keyword_search(db, query, document_id=document_id, limit=limit)
    if mode == "vector":
        return vector_search(db, query, document_id=document_id, limit=limit)
    return hybrid_search(db, query, document_id=document_id, limit=limit)
