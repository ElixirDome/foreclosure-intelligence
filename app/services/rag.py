"""
RAG pipeline (Phase 11).

  Question → retrieve chunks → (optional) LLM answer + citations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.services.retrieval import RetrievedChunk, retrieve


@dataclass
class Citation:
    document_id: int
    chunk_id: int
    page_number: int | None
    filename: str | None
    source_name: str | None
    excerpt: str
    score: float


@dataclass
class RAGAnswer:
    question: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    chunks_used: int = 0
    method: str = "extractive"
    mode: str = "hybrid"


def _extractive_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    """Answer without an LLM: return the best matching evidence."""
    if not chunks:
        return (
            "No relevant document evidence was found for this question. "
            "Ingest auction notices first, then retry."
        )

    top = chunks[0]
    lines = [
        f"Based on document evidence (score={top.score:.2f}):",
        "",
        top.text.strip()[:1200],
    ]
    if top.page_number:
        lines.append("")
        lines.append(
            f"[Source: document_id={top.document_id}, "
            f"page={top.page_number}, chunk={top.chunk_index}]"
        )
    if len(chunks) > 1:
        lines.append("")
        lines.append("Additional supporting excerpts:")
        for c in chunks[1:3]:
            snippet = c.text.strip().replace("\n", " ")[:240]
            lines.append(f"- (p.{c.page_number}) {snippet}")
    return "\n".join(lines)


def _llm_answer(
    question: str,
    chunks: list[RetrievedChunk],
    provider: Any,
) -> str:
    context_blocks = []
    for i, c in enumerate(chunks, start=1):
        context_blocks.append(
            f"[{i}] document_id={c.document_id} page={c.page_number}\n{c.text}"
        )
    context = "\n\n".join(context_blocks)
    prompt = f"""You are a foreclosure auction analyst.
Answer the question using ONLY the evidence below.
If the evidence is insufficient, say so.
Cite evidence by [number].

QUESTION:
{question}

EVIDENCE:
{context}
"""
    if hasattr(provider, "generate_raw"):
        return provider.generate_raw(prompt)
    if hasattr(provider, "generate"):
        result = provider.generate(prompt)
        return getattr(result, "summary", str(result))
    return _extractive_answer(question, chunks)


def answer_question(
    db: Session,
    question: str,
    *,
    mode: str = "hybrid",
    document_id: int | None = None,
    limit: int = 6,
    provider: Any | None = None,
) -> RAGAnswer:
    chunks = retrieve(
        db,
        question,
        mode=mode,
        document_id=document_id,
        limit=limit,
    )

    citations = [
        Citation(
            document_id=c.document_id,
            chunk_id=c.chunk_id,
            page_number=c.page_number,
            filename=c.filename,
            source_name=c.source_name,
            excerpt=c.text[:400],
            score=c.score,
        )
        for c in chunks
    ]

    if provider is not None and chunks:
        try:
            text = _llm_answer(question, chunks, provider)
            method = "llm"
        except Exception:
            text = _extractive_answer(question, chunks)
            method = "extractive_fallback"
    else:
        text = _extractive_answer(question, chunks)
        method = "extractive"

    return RAGAnswer(
        question=question,
        answer=text,
        citations=citations,
        chunks_used=len(chunks),
        method=method,
        mode=mode,
    )
