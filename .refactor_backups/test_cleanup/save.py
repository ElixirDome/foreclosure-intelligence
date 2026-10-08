import hashlib
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    Document,
    IngestionRun,
    Property,
    PropertyDocument,
)
from app.services.normalization import create_property_key


def save_ingested_properties(
    db: Session,
    properties: list[dict],
    user_id: int,
    ingestion_run_id: int,
):
    saved = []
    skipped = []

    for item in properties:
        property_data = item["property"]
        documents = item["documents"]

        property_key = create_property_key(
            address=property_data["address"],
            area_sqft=property_data.get("area_sqft"),
            property_type=property_data.get("property_type"),
            survey_number=property_data.get("survey_number"),
        )

        # 1. Find or create the property
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

            skipped.append({
                "property_id": property_obj.id,
                "address": property_obj.address,
                "reason": "duplicate",
            })
        else:
            property_obj = Property(
                user_id=user_id,
                address=property_data["address"],
                area_sqft=property_data.get("area_sqft"),
                opening_bid=property_data.get("opening_bid"),
                price=property_data.get("opening_bid"),
                property_type=property_data.get("property_type"),
                survey_number=property_data.get("survey_number"),
                auction_date=property_data.get("auction_date"),
                foreclosure_status="scheduled",
                property_key=property_key,
            )

            db.add(property_obj)
            db.flush()
            saved.append(property_obj)

        # 2. Process documents even if property already exists
        for document_data in documents:
            content = document_data.get("content")

            if isinstance(content, str):
                content = content.encode("utf-8")

            content_hash = (
                hashlib.sha256(content).hexdigest()
                if content is not None
                else None
            )

            now = datetime.utcnow()

            document = None

            # Find an existing document by its content.
            if content_hash:
                document = (
                    db.query(Document)
                    .filter(Document.content_hash == content_hash)
                    .first()
                )

            if document is None:
                # Brand-new document.
                document = Document(
                    source_name=document_data["source_name"],
                    source_url=document_data["source_url"],
                    document_type=document_data["document_type"],
                    title=document_data.get("title"),
                    content_hash=content_hash,
                    first_seen_at=now,
                    last_seen_at=now,
                )

                db.add(document)
                db.flush()

            else:
                # Same document seen again.
                # Preserve its original first_seen_at.
                document.last_seen_at = now

            # 3. Avoid duplicate property-document relationships
            existing_relationship = (
                db.query(PropertyDocument)
                .filter(
                    PropertyDocument.property_id == property_obj.id,
                    PropertyDocument.document_id == document.id,
                )
                .first()
            )

            if existing_relationship:
                continue

            property_document = PropertyDocument(
                property_id=property_obj.id,
                document_id=document.id,
                relationship_type=document_data["document_type"],
            )

            db.add(property_document)

    # 4. Update ingestion statistics
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