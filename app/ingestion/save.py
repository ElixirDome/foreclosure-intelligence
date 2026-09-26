from sqlalchemy.orm import Session
from datetime import datetime

from app.models import Document, IngestionRun, Property, PropertyDocument
from app.services.normalization import create_property_key

import hashlib

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

        existing_property = (
            db.query(Property)
            .filter(Property.property_key == property_key)
            .first()
        )

        if existing_property:
            skipped.append({
                "property_id": existing_property.id,
                "address": existing_property.address,
                "reason": "duplicate",
            })
            continue
        # 3. Create property
        property_obj = Property(
            user_id=user_id,
            address=property_data["address"],
            area_sqft=property_data.get("area_sqft"),
            opening_bid=property_data.get("opening_bid"),
            price=property_data.get("opening_bid"),
            property_type=property_data.get("property_type"),
            survey_number=property_data.get("survey_number"),
            foreclosure_status="scheduled",
            property_key=property_key,
        )

        db.add(property_obj)
        saved.append(property_obj)
         # 4. Create this property's documents
        for document_data in documents:
            content = document_data.get("content")

            if isinstance(content, str):
                content = content.encode("utf-8")

            content_hash = (
                hashlib.sha256(content).hexdigest()
                if content is not None
                else None
            )

            document = None

            if content_hash:
                document = (
                    db.query(Document)
                    .filter(Document.content_hash == content_hash)
                    .first()
                )

            if document is None:
                document = Document(# calling the constructor of the Document class to instantiate a new Document object in memory.
                    source_name=document_data["source_name"],
                    source_url=document_data["source_url"],#Keyword Arguments (key=value): You are passing named parameters (source_name=..., source_url=...) to initialize the attributes of that specific object instance.
                    document_type=document_data["document_type"],
                    title=document_data.get("title"),
                    content_hash=content_hash,
                    fetched_at=datetime.utcnow(),
                )
                

                db.add(document)
                db.flush()

            property_document = PropertyDocument(
                property_id=property_obj.id,
                document_id=document.id,
                relationship_type=document_data["document_type"],
            )

            db.add(property_document)     

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