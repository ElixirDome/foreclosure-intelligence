"""
Multi-source retriever for investment RAG (Phase 11).

Gathers context from:
  - Document chunks (auction notices, PDFs)
  - Properties (structured inventory)
  - Evidence (field-level provenance)
  - Market comparables
  - Valuations
  - Deal intelligence signals
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import (
    Document,
    DocumentChunk,
    Evidence,
    MarketComparable,
    Property,
    PropertyDocument,
    PropertyValuation,
)
from app.services.deal_intelligence import (
    DealIntelligence,
    build_deal_intelligence,
)
from app.services.embeddings import tokenize
from app.services.retrieval import RetrievedChunk, retrieve


SourceKind = Literal[
    "document",
    "property",
    "evidence",
    "comparable",
    "valuation",
    "deal",
]


@dataclass
class ContextItem:
    kind: SourceKind
    source_id: str
    title: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MultiSourceContext:
    question: str
    items: list[ContextItem] = field(default_factory=list)
    property_ids: list[int] = field(default_factory=list)
    document_ids: list[int] = field(default_factory=list)

    def by_kind(self, kind: SourceKind) -> list[ContextItem]:
        return [i for i in self.items if i.kind == kind]

    def as_prompt_blocks(self, max_chars: int = 12000) -> str:
        blocks: list[str] = []
        used = 0
        for i, item in enumerate(self.items, start=1):
            block = (
                f"[{i}] kind={item.kind} id={item.source_id} "
                f"score={item.score:.3f}\n"
                f"title: {item.title}\n"
                f"{item.text}"
            )
            if used + len(block) > max_chars:
                break
            blocks.append(block)
            used += len(block)
        return "\n\n".join(blocks)


_INVESTMENT_HINTS = re.compile(
    r"\b(invest|investment|good deal|worth|buy|bid|risk|return|"
    r"discount|comparable|valuation|recommend|should i)\b",
    re.I,
)


def looks_like_investment_question(question: str) -> bool:
    return bool(_INVESTMENT_HINTS.search(question or ""))


def _score_text_match(query: str, text: str) -> float:
    q = set(tokenize(query))
    if not q or not text:
        return 0.0
    t = set(tokenize(text))
    if not t:
        return 0.0
    overlap = q & t
    if not overlap:
        if query.lower().strip() in text.lower():
            return 0.3
        return 0.0
    return min(1.0, len(overlap) / len(q))


def _property_blob(prop: Property) -> str:
    parts = [
        f"Property #{prop.id}",
        f"address: {prop.address}",
        f"city: {prop.city}",
        f"locality: {prop.locality}",
        f"type: {prop.property_type}",
        f"area_sqft: {prop.area_sqft}",
        f"opening_bid: {prop.opening_bid}",
        f"estimated_value: {prop.estimated_value}",
        f"auction_date: {prop.auction_date}",
        f"foreclosure_status: {prop.foreclosure_status}",
        f"survey_number: {prop.survey_number}",
    ]
    return "\n".join(str(p) for p in parts if not str(p).endswith(": None"))


def retrieve_document_context(
    db: Session,
    question: str,
    *,
    document_id: int | None = None,
    property_id: int | None = None,
    limit: int = 6,
    mode: str = "hybrid",
) -> list[ContextItem]:
    doc_ids: list[int] | None = None
    if property_id is not None:
        links = (
            db.query(PropertyDocument)
            .filter(PropertyDocument.property_id == property_id)
            .all()
        )
        doc_ids = [link.document_id for link in links]
        if not doc_ids:
            return []

    items: list[ContextItem] = []

    if doc_ids is not None:
        for did in doc_ids:
            chunks = retrieve(
                db,
                question,
                mode=mode,
                document_id=did,
                limit=max(2, limit // max(len(doc_ids), 1)),
            )
            for c in chunks:
                items.append(_chunk_to_item(c))
    else:
        chunks = retrieve(
            db,
            question,
            mode=mode,
            document_id=document_id,
            limit=limit,
        )
        for c in chunks:
            items.append(_chunk_to_item(c))

    items.sort(key=lambda x: x.score, reverse=True)
    return items[:limit]


def _chunk_to_item(c: RetrievedChunk) -> ContextItem:
    return ContextItem(
        kind="document",
        source_id=f"chunk:{c.chunk_id}",
        title=c.filename or c.document_title or f"document {c.document_id}",
        text=c.text,
        score=c.score,
        metadata={
            "document_id": c.document_id,
            "chunk_id": c.chunk_id,
            "page_number": c.page_number,
            "source_name": c.source_name,
            "filename": c.filename,
        },
    )


def retrieve_property_context(
    db: Session,
    question: str,
    *,
    property_id: int | None = None,
    limit: int = 5,
) -> list[ContextItem]:
    if property_id is not None:
        prop = db.query(Property).filter(Property.id == property_id).first()
        if prop is None:
            return []
        return [
            ContextItem(
                kind="property",
                source_id=f"property:{prop.id}",
                title=prop.address,
                text=_property_blob(prop),
                score=1.0,
                metadata={"property_id": prop.id},
            )
        ]

    props = db.query(Property).order_by(Property.id.desc()).limit(200).all()
    scored: list[ContextItem] = []
    for prop in props:
        blob = _property_blob(prop)
        score = _score_text_match(question, blob)
        if score <= 0:
            continue
        scored.append(
            ContextItem(
                kind="property",
                source_id=f"property:{prop.id}",
                title=prop.address or f"property {prop.id}",
                text=blob,
                score=score,
                metadata={"property_id": prop.id},
            )
        )
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:limit]


def retrieve_evidence_context(
    db: Session,
    *,
    property_ids: list[int],
    limit: int = 20,
) -> list[ContextItem]:
    if not property_ids:
        return []

    rows = (
        db.query(Evidence)
        .filter(Evidence.property_id.in_(property_ids))
        .order_by(Evidence.id)
        .limit(limit)
        .all()
    )
    items: list[ContextItem] = []
    for e in rows:
        text = (
            f"field={e.field}\nvalue={e.value}\n"
            f"page={e.page_number}\nsource={e.source_text}\n"
            f"method={e.extraction_method}\nconfidence={e.confidence}"
        )
        items.append(
            ContextItem(
                kind="evidence",
                source_id=f"evidence:{e.id}",
                title=f"{e.field} = {e.value}",
                text=text,
                score=0.85,
                metadata={
                    "property_id": e.property_id,
                    "document_id": e.document_id,
                    "document_chunk_id": e.document_chunk_id,
                    "field": e.field,
                    "page_number": e.page_number,
                },
            )
        )
    return items


def retrieve_comparable_context(
    db: Session,
    question: str,
    *,
    property_id: int | None = None,
    limit: int = 8,
) -> list[ContextItem]:
    q = db.query(MarketComparable)
    city = None
    prop_type = None
    if property_id is not None:
        prop = db.query(Property).filter(Property.id == property_id).first()
        if prop is not None:
            city = prop.city
            prop_type = prop.property_type
            if city:
                q = q.filter(MarketComparable.city == city)
            if prop_type:
                q = q.filter(MarketComparable.property_type == prop_type)

    comps = q.order_by(MarketComparable.id.desc()).limit(100).all()
    scored: list[ContextItem] = []
    for c in comps:
        blob = (
            f"Comparable #{c.id}\n"
            f"address: {c.address}\n"
            f"city: {c.city}\n"
            f"locality: {c.locality}\n"
            f"type: {c.property_type}\n"
            f"area_sqft: {c.area_sqft}\n"
            f"sale_price: {c.sale_price}\n"
            f"sale_date: {c.sale_date}\n"
            f"source: {c.source}"
        )
        # Prefer city-matched comps even without query overlap
        base = 0.4 if (city and c.city == city) else 0.0
        score = max(base, _score_text_match(question, blob))
        if score <= 0 and property_id is None:
            continue
        if score <= 0 and property_id is not None:
            score = 0.35
        scored.append(
            ContextItem(
                kind="comparable",
                source_id=f"comparable:{c.id}",
                title=c.address,
                text=blob,
                score=score,
                metadata={
                    "comparable_id": c.id,
                    "sale_price": float(c.sale_price),
                    "area_sqft": c.area_sqft,
                    "city": c.city,
                },
            )
        )
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:limit]


def retrieve_valuation_context(
    db: Session,
    *,
    property_ids: list[int],
    limit: int = 10,
) -> list[ContextItem]:
    if not property_ids:
        return []
    rows = (
        db.query(PropertyValuation)
        .filter(PropertyValuation.property_id.in_(property_ids))
        .order_by(PropertyValuation.id.desc())
        .limit(limit)
        .all()
    )
    items = []
    for v in rows:
        text = (
            f"Valuation #{v.id} for property {v.property_id}\n"
            f"estimated_value: {v.estimated_value}\n"
            f"method: {v.valuation_method}\n"
            f"source: {v.source}\n"
            f"confidence: {v.confidence}\n"
            f"date: {v.valuation_date}"
        )
        items.append(
            ContextItem(
                kind="valuation",
                source_id=f"valuation:{v.id}",
                title=f"valuation {v.estimated_value}",
                text=text,
                score=0.9,
                metadata={
                    "property_id": v.property_id,
                    "estimated_value": float(v.estimated_value),
                    "confidence": (
                        float(v.confidence) if v.confidence is not None else None
                    ),
                },
            )
        )
    return items


def retrieve_deal_context(
    db: Session,
    *,
    property_ids: list[int],
) -> list[ContextItem]:
    items: list[ContextItem] = []
    for pid in property_ids:
        deal = build_deal_intelligence(db, pid)
        if deal is None:
            continue
        factors = "\n".join(
            f"{f.direction} {f.label}" for f in deal.factors
        )
        text = (
            f"Deal intelligence for property {pid}\n"
            f"score: {deal.deal_score}\n"
            f"rating: {deal.deal_rating}\n"
            f"discount_%: {deal.discount_percentage}\n"
            f"discount_amount: {deal.discount_amount}\n"
            f"price_per_sqft: {deal.price_per_sqft}\n"
            f"risk_level: {deal.risk_level}\n"
            f"opening_bid: {deal.opening_bid}\n"
            f"estimated_value: {deal.estimated_value}\n"
            f"comparables_used: {deal.comparable_count}\n"
            f"factors:\n{factors}\n"
            f"explanation:\n{deal.explanation}"
        )
        items.append(
            ContextItem(
                kind="deal",
                source_id=f"deal:{pid}",
                title=f"deal score {deal.deal_score}",
                text=text,
                score=1.0,
                metadata={
                    "property_id": pid,
                    "deal_score": deal.deal_score,
                    "deal_rating": deal.deal_rating,
                },
            )
        )
    return items


def build_multi_source_context(
    db: Session,
    question: str,
    *,
    property_id: int | None = None,
    document_id: int | None = None,
    mode: str = "hybrid",
    include_documents: bool = True,
    include_properties: bool = True,
    include_evidence: bool = True,
    include_comparables: bool = True,
    include_valuations: bool = True,
    include_deals: bool = True,
    doc_limit: int = 6,
    property_limit: int = 5,
    comparable_limit: int = 8,
) -> MultiSourceContext:
    """
    Assemble a unified context pack for RAG synthesis.
    """
    ctx = MultiSourceContext(question=question)
    items: list[ContextItem] = []

    if include_documents:
        items.extend(
            retrieve_document_context(
                db,
                question,
                document_id=document_id,
                property_id=property_id,
                limit=doc_limit,
                mode=mode,
            )
        )

    if include_properties:
        items.extend(
            retrieve_property_context(
                db,
                question,
                property_id=property_id,
                limit=property_limit,
            )
        )

    property_ids: list[int] = []
    if property_id is not None:
        property_ids = [property_id]
    else:
        property_ids = [
            i.metadata["property_id"]
            for i in items
            if i.kind == "property" and "property_id" in i.metadata
        ]

    if include_evidence and property_ids:
        items.extend(
            retrieve_evidence_context(db, property_ids=property_ids)
        )

    if include_comparables:
        # Prefer comps for the top property match
        pid = property_id or (property_ids[0] if property_ids else None)
        items.extend(
            retrieve_comparable_context(
                db,
                question,
                property_id=pid,
                limit=comparable_limit,
            )
        )

    if include_valuations and property_ids:
        items.extend(
            retrieve_valuation_context(db, property_ids=property_ids)
        )

    if include_deals and property_ids:
        items.extend(retrieve_deal_context(db, property_ids=property_ids))

    # Stable ranking: kind priority then score
    kind_boost = {
        "deal": 0.15,
        "valuation": 0.12,
        "property": 0.1,
        "evidence": 0.08,
        "document": 0.05,
        "comparable": 0.05,
    }
    items.sort(
        key=lambda x: x.score + kind_boost.get(x.kind, 0.0),
        reverse=True,
    )

    ctx.items = items
    ctx.property_ids = sorted(set(property_ids))
    ctx.document_ids = sorted(
        {
            i.metadata["document_id"]
            for i in items
            if i.kind == "document" and "document_id" in i.metadata
        }
    )
    return ctx
