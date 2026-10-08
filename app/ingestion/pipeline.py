"""
Ingestion pipeline.

Phase 2 direction:
  Source adapter  →  documents (universal)
                  →  optional property extraction
                  →  save (Document + chunks first, Property second)

Adapters still may extract properties today; the document path is
always run through the universal ingest layer so chunks exist even
when property parsing is incomplete or fails later.
"""

from datetime import datetime, timezone
import traceback

from sqlalchemy.orm import Session

from app.ingestion.base import SourceAdapter
from app.ingestion.document_ingest import ingest_documents
from app.ingestion.save import save_ingested_properties
from app.models import IngestionRun


def run_document_ingestion(
    db: Session,
    adapter: SourceAdapter,
):
    """
    Document-only ingestion path.

    Fetches raw items, collects documents from the adapter, and
    persists Document + DocumentChunk records without requiring
    successful property extraction.
    """
    ingestion_run = IngestionRun(
        source_name=adapter.__class__.__name__,
        started_at=datetime.now(timezone.utc),
        status="running",
    )
    db.add(ingestion_run)
    db.commit()
    db.refresh(ingestion_run)

    try:
        raw_items = adapter.fetch()
        all_docs = []

        for item in raw_items:
            docs = adapter.get_documents(item) or []
            all_docs.extend(docs)

        results = ingest_documents(db, all_docs)
        db.commit()

        created = sum(1 for r in results if r["created"])
        chunks = sum(r["chunk_count"] for r in results)

        ingestion_run.finished_at = datetime.now(timezone.utc)
        ingestion_run.status = "success"
        ingestion_run.items_found = len(all_docs)
        ingestion_run.items_created = created
        ingestion_run.items_skipped = len(results) - created
        db.commit()

        return {
            "ingestion_run_id": ingestion_run.id,
            "documents_found": len(all_docs),
            "documents_created": created,
            "documents_seen": len(results),
            "chunks_written": chunks,
            "document_ids": [r["document"].id for r in results],
        }

    except Exception as exc:
        traceback.print_exc()
        ingestion_run.finished_at = datetime.now(timezone.utc)
        ingestion_run.status = "failed"
        ingestion_run.error_message = str(exc)
        db.commit()
        return {
            "ingestion_run_id": ingestion_run.id,
            "documents_found": 0,
            "documents_created": 0,
            "error": str(exc),
        }


def run_ingestion(
    db: Session,
    adapter: SourceAdapter,
    user_id: int,
):
    """
    Full property + document ingestion (backward compatible).

    Still extracts properties via the adapter, but every attached
    document is stored through the universal document ingest path
    (text + chunks) inside save_ingested_properties.
    """
    ingestion_run = IngestionRun(
        source_name=adapter.__class__.__name__,
        started_at=datetime.now(timezone.utc),
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
                # Still allow document-only items to be ingested
                # via run_document_ingestion; skip property path.
                continue

            documents = adapter.get_documents(item)

            get_evidence = getattr(
                adapter,
                "get_evidence",
                None,
            )

            evidence = (
                get_evidence(item)
                if get_evidence
                else []
            )

            pages = None
            if isinstance(item, dict):
                pages = item.get("pages")
            pages = pages or getattr(item, "pages", None)

            if isinstance(extracted, list):
                for property_data in extracted:
                    extracted_items.append({
                        "property": property_data,
                        "documents": documents,
                        "evidence": evidence,
                        "pages": pages,
                    })
            else:
                extracted_items.append({
                    "property": extracted,
                    "documents": documents,
                    "evidence": evidence,
                    "pages": pages,
                })

        save_result = save_ingested_properties(
            db=db,
            properties=extracted_items,
            user_id=user_id,
            ingestion_run_id=ingestion_run.id,
        )

        ingestion_run.finished_at = datetime.now(timezone.utc)
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

        ingestion_run.finished_at = datetime.now(timezone.utc)
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
