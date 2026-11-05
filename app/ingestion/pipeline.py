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
import logging
import time
import traceback

from sqlalchemy.orm import Session

from app.ingestion.base import SourceAdapter
from app.ingestion.document_ingest import ingest_document, ingest_documents
from app.ingestion.save import save_ingested_properties
from app.models import IngestionRun
from app.services.live_events import broker

logger = logging.getLogger(__name__)


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
    *,
    purge_expired: bool = False,
):
    """
    Full property + document ingestion (backward compatible).

    Still extracts properties via the adapter, but every attached
    document is stored through the universal document ingest path
    (text + chunks) inside save_ingested_properties.
    """
    t_start = time.time()
    latency_metrics = {}

    ingestion_run = IngestionRun(
        source_name=adapter.__class__.__name__,
        started_at=datetime.now(timezone.utc),
        status="running",
    )

    db.add(ingestion_run)
    db.commit()
    db.refresh(ingestion_run)

    broker.publish(
        "ingestion_status",
        {
            "run_id": ingestion_run.id,
            "source": adapter.__class__.__name__,
            "stage": "discovery_started",
            "status": "running",
            "timestamp": time.time(),
        },
    )

    try:
        t0 = time.time()
        raw_items = adapter.fetch()
        latency_metrics["discovery_and_fetch_ms"] = round((time.time() - t0) * 1000)

        broker.publish(
            "ingestion_status",
            {
                "run_id": ingestion_run.id,
                "source": adapter.__class__.__name__,
                "stage": "documents_discovered",
                "status": "running",
                "items_found": len(raw_items),
                "discovery_time_ms": latency_metrics["discovery_and_fetch_ms"],
                "timestamp": time.time(),
            },
        )

        extracted_items = []
        document_only_items = []
        extraction_errors = []

        t1 = time.time()
        for item in raw_items:
            try:
                extracted = adapter.extract(item)
            except Exception as exc:
                # OCR/property parsing must not discard the source artifact.
                # Retain the raw document for later extraction/reprocessing.
                logger.exception(
                    "Property extraction failed for %s; preserving source document",
                    adapter.__class__.__name__,
                )
                extraction_errors.append(str(exc))
                extracted = None

            try:
                documents = adapter.get_documents(item) or []
            except Exception as exc:
                logger.exception("Failed getting documents from item: %s", exc)
                extraction_errors.append(f"get_documents failed: {exc}")
                documents = []

            pages = None
            if isinstance(item, dict):
                pages = item.get("pages")
            pages = pages or getattr(item, "pages", None)

            if not extracted:
                # Keep source documents even when property extraction fails or returns no properties.
                for document in documents:
                    doc_pages = None
                    if isinstance(document, dict):
                        doc_pages = document.get("pages")
                    elif hasattr(document, "pages"):
                        doc_pages = getattr(document, "pages", None)
                    if not doc_pages and len(documents) == 1:
                        doc_pages = pages
                    document_only_items.append((document, doc_pages))
                continue

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

        latency_metrics["extraction_ms"] = round((time.time() - t1) * 1000)

        broker.publish(
            "ingestion_status",
            {
                "run_id": ingestion_run.id,
                "source": adapter.__class__.__name__,
                "stage": "extraction_completed",
                "status": "running",
                "items_extracted": len(extracted_items),
                "extraction_errors": len(extraction_errors),
                "extraction_time_ms": latency_metrics["extraction_ms"],
                "timestamp": time.time(),
            },
        )

        t2 = time.time()
        save_result = save_ingested_properties(
            db=db,
            properties=extracted_items,
            user_id=user_id,
            ingestion_run_id=ingestion_run.id,
        )

        document_only_count = 0
        for raw_document, doc_pages in document_only_items:
            try:
                with db.begin_nested():
                    ingest_document(db, raw_document, pages=doc_pages)
                    document_only_count += 1
            except Exception as exc:
                logger.error("Failed to ingest document-only item: %s", exc, exc_info=True)
                extraction_errors.append(f"Document ingestion failed: {exc}")
        if document_only_count:
            db.commit()

        latency_metrics["commit_time_ms"] = round((time.time() - t2) * 1000)
        latency_metrics["total_time_ms"] = round((time.time() - t_start) * 1000)

        failed_docs = save_result.get("failed_documents", [])

        # Distinguish zero property extraction vs real success
        if len(raw_items) > 0 and len(extracted_items) == 0:
            final_status = "zero_properties_extracted"
        elif len(raw_items) == 0:
            final_status = "no_items_found"
        elif len(extraction_errors) > 0 or len(failed_docs) > 0:
            final_status = "partial_success"
        else:
            final_status = "success"

        ingestion_run.finished_at = datetime.now(timezone.utc)
        ingestion_run.status = final_status
        ingestion_run.items_found = len(raw_items)
        ingestion_run.items_created = len(save_result["saved"])
        ingestion_run.items_skipped = len(save_result["skipped"])
        if extraction_errors or failed_docs:
            err_msg = "; ".join(extraction_errors[:3])
            if failed_docs:
                err_msg += f" (and {len(failed_docs)} document failures)"
            ingestion_run.error_message = err_msg.strip()
        db.commit()

        if purge_expired:
            from app.services.properties import delete_expired_properties
            purged = delete_expired_properties(db)
            if purged > 0:
                logger.info("Purged %d expired properties after ingestion run %d", purged, ingestion_run.id)

        broker.publish(
            "ingestion_status",
            {
                "run_id": ingestion_run.id,
                "source": adapter.__class__.__name__,
                "stage": "completed",
                "status": final_status,
                "items_found": len(raw_items),
                "items_extracted": len(extracted_items),
                "items_saved": len(save_result["saved"]),
                "items_skipped": len(save_result["skipped"]),
                "documents_without_property": document_only_count,
                "extraction_errors": extraction_errors,
                "latency": latency_metrics,
                "timestamp": time.time(),
            },
        )

        return {
            "ingestion_run_id": ingestion_run.id,
            "status": final_status,
            "items_found": len(raw_items),
            "items_extracted": len(extracted_items),
            "saved": save_result["saved"],
            "skipped": save_result["skipped"],
            "documents_ingested_without_property": document_only_count,
            "extraction_errors": extraction_errors,
            "latency": latency_metrics,
        }

    except Exception as exc:
        traceback.print_exc()

        latency_metrics["total_time_ms"] = round((time.time() - t_start) * 1000)
        ingestion_run.finished_at = datetime.now(timezone.utc)
        ingestion_run.status = "failed"
        ingestion_run.error_message = str(exc)

        db.commit()

        broker.publish(
            "ingestion_status",
            {
                "run_id": ingestion_run.id,
                "source": adapter.__class__.__name__,
                "stage": "failed",
                "status": "failed",
                "error": str(exc),
                "latency": latency_metrics,
                "timestamp": time.time(),
            },
        )

        return {
            "ingestion_run_id": ingestion_run.id,
            "status": "failed",
            "items_found": 0,
            "items_extracted": 0,
            "saved": [],
            "skipped": [],
            "error": str(exc),
            "latency": latency_metrics,
        }
