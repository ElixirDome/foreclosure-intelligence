from sqlalchemy.orm import Session

from app.models import Evidence
from app.schemas import EvidenceCreate


def create_evidence(
    db: Session,
    evidence_data: EvidenceCreate,
) -> Evidence:
    """Create a provenance record for an extracted fact."""

    evidence = Evidence(
        property_id=evidence_data.property_id,
        document_id=evidence_data.document_id,
        field=evidence_data.field,
        value=evidence_data.value,
        page_number=evidence_data.page_number,
        source_text=evidence_data.source_text,
        extraction_method=evidence_data.extraction_method,
        confidence=evidence_data.confidence,
    )

    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    return evidence


def get_property_evidence(
    db: Session,
    property_id: int,
) -> list[Evidence]:
    """Return all evidence associated with a property."""

    return (
        db.query(Evidence)
        .filter(Evidence.property_id == property_id)
        .order_by(Evidence.id)
        .all()
    )


def get_document_evidence(
    db: Session,
    document_id: int,
) -> list[Evidence]:
    """Return all evidence extracted from a document."""

    return (
        db.query(Evidence)
        .filter(Evidence.document_id == document_id)
        .order_by(Evidence.id)
        .all()
    )