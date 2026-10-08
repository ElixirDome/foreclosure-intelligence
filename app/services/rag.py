"""
Phase 11 RAG — multi-source investment analysis.

Flow:
  Question
    → multi-source retriever
       (documents, properties, evidence, comparables, valuations, deal signals)
    → context pack
    → synthesizer (deterministic structured analysis and/or LLM)
    → Answer + citations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.services.multi_retriever import (
    ContextItem,
    MultiSourceContext,
    build_multi_source_context,
    looks_like_investment_question,
)
from app.services.retrieval import RetrievedChunk, retrieve


@dataclass
class Citation:
    kind: str
    source_id: str
    title: str
    excerpt: str
    score: float
    document_id: int | None = None
    chunk_id: int | None = None
    page_number: int | None = None
    property_id: int | None = None
    filename: str | None = None
    source_name: str | None = None


@dataclass
class StructuredAnalysis:
    summary: str
    strengths: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    due_diligence: list[str] = field(default_factory=list)
    recommendation: str = ""
    deal_score: float | None = None
    deal_rating: str | None = None


@dataclass
class RAGAnswer:
    question: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    structured: StructuredAnalysis | None = None
    context_kinds: list[str] = field(default_factory=list)
    property_ids: list[int] = field(default_factory=list)
    document_ids: list[int] = field(default_factory=list)
    chunks_used: int = 0
    method: str = "multi_source"
    mode: str = "hybrid"


def _citations_from_context(ctx: MultiSourceContext) -> list[Citation]:
    citations: list[Citation] = []
    for item in ctx.items:
        meta = item.metadata or {}
        citations.append(
            Citation(
                kind=item.kind,
                source_id=item.source_id,
                title=item.title,
                excerpt=item.text[:400],
                score=item.score,
                document_id=meta.get("document_id"),
                chunk_id=meta.get("chunk_id"),
                page_number=meta.get("page_number"),
                property_id=meta.get("property_id"),
                filename=meta.get("filename"),
                source_name=meta.get("source_name"),
            )
        )
    return citations


def _structured_from_context(ctx: MultiSourceContext) -> StructuredAnalysis:
    """Deterministic synthesis when no LLM is available."""
    strengths: list[str] = []
    risks: list[str] = []
    diligence: list[str] = []
    deal_score = None
    deal_rating = None
    recommendation = "Insufficient data for a firm recommendation."

    deals = ctx.by_kind("deal")
    if deals:
        top = deals[0]
        deal_score = top.metadata.get("deal_score")
        deal_rating = top.metadata.get("deal_rating")
        for line in top.text.splitlines():
            line = line.strip()
            if line.startswith("+"):
                strengths.append(line[1:].strip())
            elif line.startswith("-"):
                risks.append(line[1:].strip())

    vals = ctx.by_kind("valuation")
    if vals:
        strengths.append(
            f"Valuation on file: {vals[0].metadata.get('estimated_value')}"
        )
        conf = vals[0].metadata.get("confidence")
        if conf is not None and conf < 0.5:
            risks.append("Valuation confidence is low")

    comps = ctx.by_kind("comparable")
    if len(comps) >= 3:
        strengths.append(f"{len(comps)} market comparables in context")
    elif ctx.property_ids and not comps:
        risks.append("No market comparables retrieved for this property")
        diligence.append("Gather local sale comparables before bidding")

    props = ctx.by_kind("property")
    for p in props:
        lower = p.text.lower()
        if "foreclosure_status: sold" in lower:
            risks.append("Auction status is sold")
        if "foreclosure_status: cancelled" in lower:
            risks.append("Auction status is cancelled")
        if "opening_bid:" in p.text and "estimated_value: None" in p.text:
            risks.append("Opening bid present without estimated market value")
            diligence.append("Commission an independent valuation")

    docs = ctx.by_kind("document")
    if docs:
        diligence.append("Review cited auction-notice pages in full")
    else:
        risks.append("No auction-notice document chunks retrieved")
        diligence.append("Ingest the sale notice PDF/OCR before deciding")

    evidence = ctx.by_kind("evidence")
    if evidence:
        strengths.append(f"{len(evidence)} field-level evidence records linked")
    else:
        diligence.append("Confirm key fields against source documents")

    if deal_score is not None:
        if deal_score >= 70:
            recommendation = (
                f"Deal score {deal_score:.0f}/100 suggests a potentially "
                f"attractive opportunity, subject to due diligence."
            )
        elif deal_score >= 40:
            recommendation = (
                f"Deal score {deal_score:.0f}/100 is mixed — proceed only "
                f"after validating valuation and legal risk."
            )
        else:
            recommendation = (
                f"Deal score {deal_score:.0f}/100 is weak — high caution advised."
            )
    elif props and docs:
        recommendation = (
            "Property and document context exist, but deal scoring is "
            "incomplete (missing valuation and/or comparables)."
        )

    summary_parts = []
    if props:
        summary_parts.append(f"Analyzed {len(props)} property record(s).")
    if docs:
        summary_parts.append(f"Retrieved {len(docs)} document excerpt(s).")
    if comps:
        summary_parts.append(f"Included {len(comps)} comparable(s).")
    if deal_score is not None:
        summary_parts.append(
            f"Deal score {deal_score:.0f}"
            + (f" ({deal_rating})" if deal_rating else "")
            + "."
        )
    if not summary_parts:
        summary_parts.append(
            "Limited multi-source context was available for this question."
        )

    def uniq(seq: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for s in seq:
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        return out

    return StructuredAnalysis(
        summary=" ".join(summary_parts),
        strengths=uniq(strengths)[:8],
        risks=uniq(risks)[:8],
        due_diligence=uniq(diligence)[:8],
        recommendation=recommendation,
        deal_score=deal_score,
        deal_rating=deal_rating,
    )


def _format_structured_answer(
    question: str,
    analysis: StructuredAnalysis,
    ctx: MultiSourceContext,
) -> str:
    lines = [
        f"Question: {question}",
        "",
        analysis.summary,
        "",
    ]
    if analysis.deal_score is not None:
        rating = f" ({analysis.deal_rating})" if analysis.deal_rating else ""
        lines.append(f"Deal score: {analysis.deal_score:.0f}/100{rating}")
        lines.append("")
    if analysis.strengths:
        lines.append("Strengths:")
        lines.extend(f"  + {s}" for s in analysis.strengths)
        lines.append("")
    if analysis.risks:
        lines.append("Risks:")
        lines.extend(f"  - {r}" for r in analysis.risks)
        lines.append("")
    if analysis.due_diligence:
        lines.append("Due diligence:")
        lines.extend(f"  · {d}" for d in analysis.due_diligence)
        lines.append("")
    lines.append(f"Recommendation: {analysis.recommendation}")
    lines.append("")
    lines.append("Evidence sources used:")
    kinds = sorted({i.kind for i in ctx.items})
    lines.append("  " + ", ".join(kinds) if kinds else "  (none)")
    for i, item in enumerate(ctx.items[:5], start=1):
        snippet = item.text.replace("\n", " ")[:160]
        lines.append(f"  [{i}] ({item.kind}) {item.title}: {snippet}")
    return "\n".join(lines)


def _llm_synthesize(
    question: str,
    ctx: MultiSourceContext,
    provider: Any,
) -> str:
    context = ctx.as_prompt_blocks()
    prompt = f"""You are a foreclosure investment analyst.

Answer the investor question using ONLY the multi-source evidence below.
Sources may include auction documents, property records, field evidence,
market comparables, valuations, and deal scores.

Rules:
- Do not invent numbers, legal conclusions, or missing comparables.
- If evidence is incomplete, say what is missing.
- Cite sources by their [number].
- For investment questions, cover opportunity, risks, and due diligence.

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
    raise RuntimeError("provider does not support generation")


def _legacy_document_only_answer(
    question: str,
    chunks: list[RetrievedChunk],
) -> str:
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
    return "\n".join(lines)


def answer_question(
    db: Session,
    question: str,
    *,
    mode: str = "hybrid",
    document_id: int | None = None,
    property_id: int | None = None,
    limit: int = 6,
    provider: Any | None = None,
    multi_source: bool | None = None,
) -> RAGAnswer:
    """
    Answer a question with multi-source RAG.

    multi_source:
      None  → auto (on for investment-style questions or when property_id set)
      True  → always multi-source
      False → document-chunk RAG only (legacy)
    """
    if multi_source is None:
        multi_source = (
            property_id is not None
            or looks_like_investment_question(question)
        )

    if not multi_source:
        chunks = retrieve(
            db,
            question,
            mode=mode,
            document_id=document_id,
            limit=limit,
        )
        citations = [
            Citation(
                kind="document",
                source_id=f"chunk:{c.chunk_id}",
                title=c.filename or f"document {c.document_id}",
                excerpt=c.text[:400],
                score=c.score,
                document_id=c.document_id,
                chunk_id=c.chunk_id,
                page_number=c.page_number,
                filename=c.filename,
                source_name=c.source_name,
            )
            for c in chunks
        ]
        if provider is not None and chunks:
            try:
                ctx = MultiSourceContext(question=question)
                ctx.items = [
                    ContextItem(
                        kind="document",
                        source_id=f"chunk:{c.chunk_id}",
                        title=c.filename or "",
                        text=c.text,
                        score=c.score,
                        metadata={
                            "document_id": c.document_id,
                            "chunk_id": c.chunk_id,
                            "page_number": c.page_number,
                        },
                    )
                    for c in chunks
                ]
                text = _llm_synthesize(question, ctx, provider)
                method = "llm_document"
            except Exception:
                text = _legacy_document_only_answer(question, chunks)
                method = "extractive_document"
        else:
            text = _legacy_document_only_answer(question, chunks)
            method = "extractive_document"

        return RAGAnswer(
            question=question,
            answer=text,
            citations=citations,
            structured=None,
            context_kinds=["document"] if chunks else [],
            property_ids=[],
            document_ids=sorted({c.document_id for c in chunks}),
            chunks_used=len(chunks),
            method=method,
            mode=mode,
        )

    ctx = build_multi_source_context(
        db,
        question,
        property_id=property_id,
        document_id=document_id,
        mode=mode,
        doc_limit=limit,
    )
    analysis = _structured_from_context(ctx)
    citations = _citations_from_context(ctx)
    kinds = sorted({i.kind for i in ctx.items})

    if provider is not None and ctx.items:
        try:
            text = _llm_synthesize(question, ctx, provider)
            method = "llm_multi_source"
        except Exception:
            text = _format_structured_answer(question, analysis, ctx)
            method = "structured_multi_source_fallback"
    else:
        text = _format_structured_answer(question, analysis, ctx)
        method = "structured_multi_source"

    return RAGAnswer(
        question=question,
        answer=text,
        citations=citations,
        structured=analysis,
        context_kinds=kinds,
        property_ids=ctx.property_ids,
        document_ids=ctx.document_ids,
        chunks_used=len(ctx.by_kind("document")),
        method=method,
        mode=mode,
    )


def analyze_investment(
    db: Session,
    *,
    property_id: int,
    question: str | None = None,
    provider: Any | None = None,
    mode: str = "hybrid",
) -> RAGAnswer:
    """
    Convenience entry: 'Is this property a good investment?'
    Forces multi-source retrieval anchored on the property.
    """
    q = question or (
        f"Is property {property_id} a good foreclosure investment? "
        "Summarize opportunity, risks, comparables, valuation, and recommendation."
    )
    return answer_question(
        db,
        q,
        mode=mode,
        property_id=property_id,
        multi_source=True,
        provider=provider,
        limit=8,
    )
