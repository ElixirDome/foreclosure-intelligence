from datetime import datetime
import traceback
from sqlalchemy.orm import Session

from app.ingestion.base import SourceAdapter
from app.ingestion.save import save_ingested_properties
from app.models import IngestionRun


def run_ingestion(
    db: Session,
    adapter: SourceAdapter,
    user_id: int,
):
    ingestion_run = IngestionRun(
        source_name=adapter.__class__.__name__,
        started_at=datetime.utcnow(),
        status="running",
    )

    db.add(ingestion_run)
    db.commit()
    db.refresh(ingestion_run)

    try:
        raw_items = adapter.fetch()

        extracted_items = []

        for item in raw_items:
            extracted = adapter.extract(item)

            if extracted is None:
                continue

            documents = adapter.get_documents(item)

            if isinstance(extracted, list):
                for property_data in extracted:
                    extracted_items.append({
                        "property": property_data,
                        "documents": documents,
                    })
            else:
                # Keep compatibility with adapters that return
                # a single property dictionary.
                extracted_items.append({
                    "property": extracted,
                    "documents": documents,
                })

        save_result = save_ingested_properties(
            db=db,
            properties=extracted_items,
            user_id=user_id,
            ingestion_run_id=ingestion_run.id,
        )

        ingestion_run.finished_at = datetime.utcnow()
        ingestion_run.status = "success"
        ingestion_run.items_found = len(raw_items)

        db.commit()

        return {
            "ingestion_run_id": ingestion_run.id,
            "items_found": len(raw_items),
            "items_extracted": len(extracted_items),
            "saved": save_result["saved"],
            "skipped": save_result["skipped"],
        }

    except Exception as exc:

        traceback.print_exc()

        ingestion_run.finished_at = datetime.utcnow()
        ingestion_run.status = "failed"
        ingestion_run.error_message = str(exc)

        db.commit()

        return {
            "ingestion_run_id": ingestion_run.id,
            "items_found": 0,
            "items_extracted": 0,
            "saved": [],
            "skipped": [],
            "error": str(exc),
        }