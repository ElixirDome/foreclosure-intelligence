"""
Schema-oriented property extraction with evidence (Phases 6–7).

Two modes:
  1. Deterministic regex over retrieved / full page text
  2. Optional LLM structured fill when a provider is available

Every extracted field can carry source chunk / page / quote.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk
from app.schemas import ExtractedProperty
from app.services.retrieval import RetrievedChunk, retrieve
from app.services.validation import (
    parse_money_token,
    validate_extraction,
)


@dataclass
class FieldEvidence:
    field: str
    value: str
    page_number: int | None = None
    source_text: str | None = None
    document_id: int | None = None
    document_chunk_id: int | None = None
    extraction_method: str = "regex"
    confidence: float | None = None


@dataclass
class StructuredExtractionResult:
    property: ExtractedProperty
    evidence: list[FieldEvidence] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    valid: bool = True
    method: str = "regex"


_RESERVE_PATTERNS = [
    re.compile(
        r"reserve\s*price[^0-9]{0,40}([\d,.]+)\s*(lakh|lac|lacs|lakhs)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"start\s*price(?:\s*in\s*inr)?[^0-9]{0,20}([\d,.]+)\s*(lakh|lac|lacs|lakhs)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"opening\s*bid[^0-9]{0,20}([\d,.]+)\s*(lakh|lac|lacs|lakhs)?",
        re.IGNORECASE,
    ),
]

_AREA_PATTERNS = [
    re.compile(
        r"measuring\s+([\d,.]+)\s*(sq\.?\s*mtr|sq\.?\s*mt|sqm|sq\.?\s*ft|sqft)",
        re.IGNORECASE,
    ),
    re.compile(
        r"([\d,.]+)\s*(sq\.?\s*ft|sqft|sq\.?\s*mtr|sqm)",
        re.IGNORECASE,
    ),
]

_LOT_PATTERNS = [
    re.compile(r"\b(?:lot|item)\s*(?:no\.?|number)?\s*[:\-]?\s*(\d+)\b", re.I),
]

_SURVEY_PATTERNS = [
    re.compile(r"(?:sy|survey)\s*no\.?\s*([0-9/\-]+)", re.I),
]

_PLOT_PATTERNS = [
    re.compile(
        r"(plot\s*no\.?\s*[A-Za-z0-9\-]+[^\n]{0,120})",
        re.I,
    ),
]


def _sqm_to_sqft(value: float) -> float:
    return value * 10.7639


def _match_money(text: str) -> tuple[float | None, str | None]:
    for pattern in _RESERVE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        raw = m.group(1)
        unit = m.group(2) if m.lastindex and m.lastindex >= 2 else None
        token = f"{raw} {unit or ''}".strip()
        amount = parse_money_token(token)
        return amount, m.group(0)
    return None, None


def _match_area(text: str) -> tuple[float | None, str | None]:
    for pattern in _AREA_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        number = float(m.group(1).replace(",", ""))
        unit = m.group(2).lower().replace(" ", "").replace(".", "")
        if "mtr" in unit or "mt" in unit or unit == "sqm":
            number = _sqm_to_sqft(number)
        return number, m.group(0)
    return None, None


def extract_from_text(
    text: str,
    *,
    document_id: int | None = None,
    document_chunk_id: int | None = None,
    page_number: int | None = None,
    method: str = "regex",
) -> StructuredExtractionResult:
    evidence: list[FieldEvidence] = []
    data: dict[str, Any] = {}

    money, money_src = _match_money(text)
    if money is not None:
        data["opening_bid"] = money
        evidence.append(
            FieldEvidence(
                field="opening_bid",
                value=str(money),
                page_number=page_number,
                source_text=money_src,
                document_id=document_id,
                document_chunk_id=document_chunk_id,
                extraction_method=method,
                confidence=0.8,
            )
        )

    area, area_src = _match_area(text)
    if area is not None:
        data["area_sqft"] = round(area, 2)
        evidence.append(
            FieldEvidence(
                field="area_sqft",
                value=str(data["area_sqft"]),
                page_number=page_number,
                source_text=area_src,
                document_id=document_id,
                document_chunk_id=document_chunk_id,
                extraction_method=method,
                confidence=0.75,
            )
        )

    for pattern in _LOT_PATTERNS:
        m = pattern.search(text)
        if m:
            data["lot_number"] = m.group(1)
            evidence.append(
                FieldEvidence(
                    field="lot_number",
                    value=m.group(1),
                    page_number=page_number,
                    source_text=m.group(0),
                    document_id=document_id,
                    document_chunk_id=document_chunk_id,
                    extraction_method=method,
                    confidence=0.85,
                )
            )
            break

    for pattern in _SURVEY_PATTERNS:
        m = pattern.search(text)
        if m:
            data["survey_number"] = m.group(1)
            evidence.append(
                FieldEvidence(
                    field="survey_number",
                    value=m.group(1),
                    page_number=page_number,
                    source_text=m.group(0),
                    document_id=document_id,
                    document_chunk_id=document_chunk_id,
                    extraction_method=method,
                    confidence=0.8,
                )
            )
            break

    for pattern in _PLOT_PATTERNS:
        m = pattern.search(text)
        if m:
            address = m.group(1).strip()
            data["address"] = address
            evidence.append(
                FieldEvidence(
                    field="address",
                    value=address,
                    page_number=page_number,
                    source_text=m.group(0),
                    document_id=document_id,
                    document_chunk_id=document_chunk_id,
                    extraction_method=method,
                    confidence=0.7,
                )
            )
            break

    if "address" not in data:
        # Fallback: first non-trivial line
        for line in text.splitlines():
            line = line.strip()
            if len(line) > 20 and not line.lower().startswith("sale notice"):
                data["address"] = line[:240]
                evidence.append(
                    FieldEvidence(
                        field="address",
                        value=data["address"],
                        page_number=page_number,
                        source_text=line[:240],
                        document_id=document_id,
                        document_chunk_id=document_chunk_id,
                        extraction_method=method,
                        confidence=0.4,
                    )
                )
                break

    evidence_map = {e.field: e.source_text for e in evidence}
    validation = validate_extraction(data, evidence_by_field=evidence_map)

    prop = ExtractedProperty(
        lot_number=data.get("lot_number"),
        address=data.get("address"),
        area_sqft=data.get("area_sqft"),
        survey_number=data.get("survey_number"),
        opening_bid=data.get("opening_bid"),
        property_type=data.get("property_type"),
        city=data.get("city"),
        state=data.get("state"),
        pincode=data.get("pincode"),
    )

    return StructuredExtractionResult(
        property=prop,
        evidence=evidence,
        validation_errors=validation.errors,
        valid=validation.valid,
        method=method,
    )


def extract_from_chunks(
    chunks: list[RetrievedChunk] | list[DocumentChunk],
) -> list[StructuredExtractionResult]:
    """Run deterministic extraction on each chunk separately (lot-level)."""
    results = []
    for chunk in chunks:
        if isinstance(chunk, RetrievedChunk):
            text = chunk.text
            document_id = chunk.document_id
            chunk_id = chunk.chunk_id
            page = chunk.page_number
        else:
            text = chunk.text
            document_id = chunk.document_id
            chunk_id = chunk.id
            page = chunk.page_number

        result = extract_from_text(
            text,
            document_id=document_id,
            document_chunk_id=chunk_id,
            page_number=page,
        )
        if result.property.address or result.property.opening_bid:
            results.append(result)
    return results


def extract_from_document(
    db: Session,
    document_id: int,
) -> list[StructuredExtractionResult]:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        return []

    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )
    if chunks:
        return extract_from_chunks(chunks)

    if doc.extracted_text:
        return [
            extract_from_text(
                doc.extracted_text,
                document_id=document_id,
            )
        ]
    return []


def extract_with_retrieval(
    db: Session,
    query: str,
    *,
    document_id: int | None = None,
    limit: int = 6,
) -> list[StructuredExtractionResult]:
    """Retrieve relevant chunks then extract structured fields (Phase 6+3)."""
    chunks = retrieve(
        db,
        query,
        mode="hybrid",
        document_id=document_id,
        limit=limit,
    )
    return extract_from_chunks(chunks)


def llm_extract_from_text(
    text: str,
    *,
    document_id: int | None = None,
    document_chunk_id: int | None = None,
    page_number: int | None = None,
    provider: Any | None = None,
) -> StructuredExtractionResult:
    """
    LLM-assisted extraction (Phase 7).

    Falls back to regex if no provider is supplied or the call fails.
    """
    fallback = extract_from_text(
        text,
        document_id=document_id,
        document_chunk_id=document_chunk_id,
        page_number=page_number,
        method="regex",
    )

    if provider is None:
        return fallback

    prompt = f"""Extract foreclosure/auction property fields as pure JSON.
Keys: lot_number, address, city, state, pincode, area_sqft, survey_number,
opening_bid (INR number, convert lakhs), property_type, seller_name.
Use null for unknown. Do not invent values not supported by the text.

TEXT:
{text[:6000]}
"""
    try:
        raw = provider.generate_raw(prompt) if hasattr(provider, "generate_raw") else None
        if raw is None and hasattr(provider, "generate"):
            # Existing providers return typed analysis; skip if incompatible
            return fallback
        data = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(data, dict):
            return fallback

        evidence = []
        for key, value in data.items():
            if value is None:
                continue
            evidence.append(
                FieldEvidence(
                    field=key,
                    value=str(value),
                    page_number=page_number,
                    source_text=None,
                    document_id=document_id,
                    document_chunk_id=document_chunk_id,
                    extraction_method="llm",
                    confidence=0.6,
                )
            )

        prop = ExtractedProperty(
            lot_number=data.get("lot_number"),
            address=data.get("address"),
            city=data.get("city"),
            state=data.get("state"),
            pincode=data.get("pincode"),
            area_sqft=data.get("area_sqft"),
            survey_number=data.get("survey_number"),
            opening_bid=data.get("opening_bid"),
            property_type=data.get("property_type"),
            seller_name=data.get("seller_name"),
        )
        evidence_map = {e.field: e.source_text for e in evidence}
        validation = validate_extraction(
            prop.model_dump(),
            evidence_by_field=evidence_map,
            require_evidence=False,
        )
        return StructuredExtractionResult(
            property=prop,
            evidence=evidence,
            validation_errors=validation.errors,
            valid=validation.valid,
            method="llm",
        )
    except Exception:
        return fallback
