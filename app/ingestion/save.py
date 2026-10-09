from sqlalchemy.orm import Session

from app.ingestion.document_ingest import ingest_document
from app.models import (
    Evidence,
    IngestionRun,
    Property,
    PropertyDocument,
)
from app.services.normalization import create_property_key


def _evidence_value(evidence):
    if isinstance(evidence, dict):
        return evidence

    return {
        "field": evidence.field,
        "value": evidence.value,
        "page_number": evidence.page_number,
        "source_text": evidence.source_text,
        "extraction_method": evidence.extraction_method,
        "confidence": evidence.confidence,
        "document_chunk_id": getattr(
            evidence,
            "document_chunk_id",
            None,
        ),
    }


def _normalize_document_payload(document_data):
    """Accept SourceDocument, dict, or dict-like from adapters."""
    if hasattr(document_data, "__dataclass_fields__"):
        return {
            "source_name": document_data.source_name,
            "source_url": document_data.source_url,
            "document_type": document_data.document_type,
            "content": document_data.content,
            "title": document_data.title,
            "filename": document_data.filename,
            "mime_type": document_data.mime_type,
            "storage_path": document_data.storage_path,
        }
    return document_data


def save_ingested_properties(
    db: Session,
    properties: list[dict],
    user_id: int,
    ingestion_run_id: int,
):
    """
    Persist properties, linking each to universally ingested documents.

    Document path (Phase 2):
        SourceDocument → Document + extracted_text + DocumentChunk[]
    Property path (unchanged for now):
        structured fields → Property + Evidence
    """
    saved = []
    skipped = []

    for item in properties:
        property_data = item["property"]
        documents = item.get("documents") or []
        evidence_items = item.get("evidence", [])

        property_key = create_property_key(
            address=property_data["address"],
            area_sqft=property_data.get("area_sqft"),
            property_type=property_data.get("property_type"),
            survey_number=property_data.get("survey_number"),
        )

        property_obj = (
            db.query(Property)
            .filter(Property.property_key == property_key)
            .first()
        )

        if property_obj:
            if not property_obj.city and property_data.get("city"):
                property_obj.city = property_data["city"]

            if not property_obj.locality and property_data.get("locality"):
                property_obj.locality = property_data["locality"]

            # Refresh status from portal when provided (sold / live / etc.)
            new_status = property_data.get("foreclosure_status")
            if new_status and new_status != property_obj.foreclosure_status:
                property_obj.foreclosure_status = new_status

            if property_data.get("opening_bid") and not property_obj.opening_bid:
                property_obj.opening_bid = property_data.get("opening_bid")
                property_obj.price = property_data.get("opening_bid")

            skipped.append({
                "property_id": property_obj.id,
                "address": property_obj.address,
                "reason": "duplicate",
            })

        else:
            property_obj = Property(
                user_id=user_id,
                address=property_data["address"],
                city=property_data.get("city"),
                locality=property_data.get("locality"),
                area_sqft=property_data.get("area_sqft"),
                opening_bid=property_data.get("opening_bid"),
                price=property_data.get("opening_bid"),
                property_type=property_data.get("property_type"),
                survey_number=property_data.get("survey_number"),
                auction_date=property_data.get("auction_date"),
                foreclosure_status=(
                    property_data.get("foreclosure_status") or "scheduled"
                ),
                property_key=property_key,
            )

            db.add(property_obj)
            db.flush()
            saved.append(property_obj)

        for document_data in documents:
            payload = _normalize_document_payload(document_data)
            pages = item.get("pages")

            ingest_result = ingest_document(
                db,
                payload,
                pages=pages,
            )
            document = ingest_result["document"]

            existing_relationship = (
                db.query(PropertyDocument)
                .filter(
                    PropertyDocument.property_id == property_obj.id,
                    PropertyDocument.document_id == document.id,
                )
                .first()
            )

            if not existing_relationship:
                property_document = PropertyDocument(
                    property_id=property_obj.id,
                    document_id=document.id,
                    relationship_type=payload.get(
                        "document_type",
                        document.document_type,
                    ),
                )
                db.add(property_document)

            # Evidence belongs to the property + document.
            for raw_evidence in evidence_items:
                evidence_data = _evidence_value(raw_evidence)

                existing_evidence = (
                    db.query(Evidence)
                    .filter(
                        Evidence.property_id == property_obj.id,
                        Evidence.document_id == document.id,
                        Evidence.field == evidence_data["field"],
                        Evidence.value == str(evidence_data["value"]),
                        Evidence.page_number
                        == evidence_data.get("page_number"),
                    )
                    .first()
                )

                if existing_evidence:
                    continue

                db.add(
                    Evidence(
                        property_id=property_obj.id,
                        document_id=document.id,
                        document_chunk_id=evidence_data.get(
                            "document_chunk_id"
                        ),
                        field=evidence_data["field"],
                        value=str(evidence_data["value"]),
                        page_number=evidence_data.get("page_number"),
                        source_text=evidence_data.get("source_text"),
                        extraction_method=evidence_data.get(
                            "extraction_method"
                        ),
                        confidence=evidence_data.get("confidence"),
                    )
                )

    ingestion_run = (
        db.query(IngestionRun)
        .filter(IngestionRun.id == ingestion_run_id)
        .first()
    )

    if ingestion_run:
        ingestion_run.items_created = len(saved)
        ingestion_run.items_skipped = len(skipped)

    db.commit()

    for property_obj in saved:
        db.refresh(property_obj)

    return {
        "saved": saved,
        "skipped": skipped,
    }

