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
        """Render numbered, readable evidence blocks for grounded synthesis."""
        blocks: list[str] = []
        used = 0
        for i, item in enumerate(self.items, start=1):
            meta = item.metadata or {}
            source_parts = []
            if meta.get("source_name"):
                source_parts.append(str(meta["source_name"]))
            if meta.get("filename") and meta.get("filename") != item.title:
                source_parts.append(str(meta["filename"]))
            if meta.get("page_number"):
                source_parts.append(f"page {meta['page_number']}")
            source_label = f" ({', '.join(source_parts)})" if source_parts else ""
            header = f"[{i}] {item.title}{source_label}\n"
            block = header + item.text.strip()
            if used + len(block) > max_chars:
                remaining = max_chars - used
                if remaining > len(header) + 60:
                    allowance = remaining - len(header) - 20
                    blocks.append(header + item.text[:allowance].rstrip() + "…")
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


def _property_metadata(prop: Property) -> dict[str, Any]:
    valuations = [
        valuation
        for valuation in prop.valuations
        if valuation.source == "market_comparables"
        and valuation.valuation_method == "residential_comparable_sales"
    ]
    latest = max(valuations, key=lambda item: item.id) if valuations else None
    return {
        "property_id": prop.id,
        "foreclosure_status": prop.foreclosure_status,
        "reserve_price": prop.reserve_price,
        "opening_bid": prop.opening_bid,
        "estimated_value": latest.estimated_value if latest else None,
        "valuation_confidence": latest.confidence if latest else None,
    }


def _property_blob(prop: Property) -> str:
    meta = _property_metadata(prop)
    parts = [
        f"Property {prop.id}: {prop.address}",
        f"Location: {', '.join(part for part in [prop.locality, prop.city] if part)}",
        f"Property type: {prop.property_type}",
        f"Area: {prop.area_sqft} square feet" if prop.area_sqft is not None else None,
        f"Opening bid: ₹{prop.opening_bid:,.0f}" if prop.opening_bid is not None else None,
        f"Bank reserve price: ₹{prop.reserve_price:,.0f}" if prop.reserve_price is not None else None,
        f"Earnest money deposit (EMD): ₹{prop.emd:,.0f}" if prop.emd is not None else None,
        f"Comparable-based market estimate: ₹{meta['estimated_value']:,.0f}" if meta["estimated_value"] is not None else "No automated comparable-based market estimate is recorded",
        f"Valuation confidence: {float(meta['valuation_confidence']):.0%}" if meta["valuation_confidence"] is not None else None,
        f"Auction date: {prop.auction_date}" if prop.auction_date else None,
        f"Auction status: {prop.foreclosure_status}" if prop.foreclosure_status else None,
        f"Survey number: {prop.survey_number}" if prop.survey_number else None,
    ]
    return "\n".join(part for part in parts if part)


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
        chunks = retrieve(
            db,
            question,
            mode=mode,
            document_ids=doc_ids,
            limit=max(limit * 3, limit),
        )
        items.extend(_chunk_to_item(c) for c in chunks)
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
                metadata=_property_metadata(prop),
            )
        ]

    # Search the full inventory for matching address/location/survey terms.
    # The former latest-200 scan made older matching properties invisible.
    stopwords = {
        "the", "and", "for", "with", "this", "that", "what", "where",
        "when", "which", "does", "from", "about", "show", "find", "list",
        "all", "property", "properties", "investment", "good", "deal",
        "please", "tell", "give", "have", "there", "their", "into",
    }
    terms = [
        token for token in tokenize(question)
        if len(token) >= 3 and token not in stopwords
    ][:10]
    predicates = []
    for term in terms:
        pattern = f"%{term}%"
        predicates.extend([
            Property.address.ilike(pattern),
            Property.city.ilike(pattern),
            Property.locality.ilike(pattern),
            Property.survey_number.ilike(pattern),
        ])
    for property_number in re.findall(
        r"\b(?:property|lot|plot)\s*#?\s*(\d+)\b",
        question,
        re.IGNORECASE,
    ):
        predicates.append(Property.id == int(property_number))
    if not predicates:
        return []

    props = (
        db.query(Property)
        .filter(or_(*predicates))
        .order_by(Property.id.desc())
        .limit(1000)
        .all()
    )
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
                metadata=_property_metadata(prop),
            )
        )
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:limit]


def retrieve_evidence_context(
    db: Session,
    *,
    property_ids: list[int],
    question: str | None = None,
    limit: int = 20,
) -> list[ContextItem]:
    if not property_ids:
        return []

    # Rank the complete evidence set before applying the context limit.
    rows = (
        db.query(Evidence)
        .filter(Evidence.property_id.in_(property_ids))
        .order_by(Evidence.id.desc())
        .all()
    )
    items: list[ContextItem] = []
    for e in rows:
        text = (
            f"Extracted fact: {e.field} is {e.value}.\n"
            f"Supporting notice text: {e.source_text or 'Not retained'}.\n"
            f"Notice page: {e.page_number if e.page_number is not None else 'Not recorded'}.\n"
            f"Extraction method: {e.extraction_method or 'Not recorded'}.\n"
            f"Extraction confidence: {e.confidence if e.confidence is not None else 'Not recorded'}."
        )
        if question:
            match = _score_text_match(
                question,
                f"{e.field} {e.value} {e.source_text or ''}",
            )
            # Relevancy-ranked: base 0.6 + up to 0.4 based on match
            score = round(0.6 + 0.4 * match, 3)
        else:
            score = 0.85

        items.append(
            ContextItem(
                kind="evidence",
                source_id=f"evidence:{e.id}",
                title=f"{e.field.replace('_', ' ').title()}: {e.value}",
                text=text,
                score=score,
                metadata={
                    "property_id": e.property_id,
                    "document_id": e.document_id,
                    "document_chunk_id": e.document_chunk_id,
                    "field": e.field,
                    "page_number": e.page_number,
                },
            )
        )
    if question:
        items.sort(key=lambda x: x.score, reverse=True)
    return items[:limit]


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
            f"Comparable-based valuation for property {v.property_id}.\n"
            f"Estimated market value: ₹{float(v.estimated_value):,.0f}.\n"
            f"Valuation method: {v.valuation_method or 'Not recorded'}.\n"
            f"Valuation source: {v.source or 'Not recorded'}.\n"
            f"Confidence: {float(v.confidence):.0%}." if v.confidence is not None
            else (
                f"Comparable-based valuation for property {v.property_id}.\n"
                f"Estimated market value: ₹{float(v.estimated_value):,.0f}.\n"
                f"Valuation method: {v.valuation_method or 'Not recorded'}.\n"
                f"Valuation source: {v.source or 'Not recorded'}.\n"
                "Confidence was not recorded."
            )
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
            f"Deal assessment for property {pid}.\n"
            f"Deal score: {deal.deal_score} out of 100.\n"
            f"Deal rating: {deal.deal_rating or 'Not available'}.\n"
            f"Discount against estimated market value: {deal.discount_percentage}%.\n"
            f"Estimated discount amount: ₹{deal.discount_amount:,.0f}.\n"
            f"Price per square foot: ₹{deal.price_per_sqft:,.0f}.\n"
            f"Risk level: {deal.risk_level}.\n"
            f"Bank opening bid: {deal.opening_bid}.\n"
            f"Comparable-based market estimate: {deal.estimated_value}.\n"
            f"Comparables used: {deal.comparable_count}.\n"
            f"Factors: {factors or 'No additional factors recorded'}.\n"
            f"Explanation: {deal.explanation}"
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
            retrieve_evidence_context(
                db,
                property_ids=property_ids,
                question=question,
            )
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

    # Keep the best excerpt per document page before numbering prompt citations.
    deduplicated_items: list[ContextItem] = []
    seen_document_pages: set[tuple[int | None, int | None]] = set()
    for item in items:
        if item.kind == "document":
            meta = item.metadata or {}
            page_key = (
                meta.get("document_id"),
                meta.get("page_number")
                if meta.get("page_number") is not None
                else item.source_id,
            )
            if page_key in seen_document_pages:
                continue
            seen_document_pages.add(page_key)
        deduplicated_items.append(item)

    ctx.items = deduplicated_items
    ctx.property_ids = sorted(set(property_ids))
    ctx.document_ids = sorted(
        {
            i.metadata["document_id"]
            for i in items
            if i.kind == "document" and "document_id" in i.metadata
        }
    )
    return ctx
