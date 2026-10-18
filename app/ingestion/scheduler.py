import logging
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.ingestion.pipeline import run_ingestion
from app.ingestion.registry import adapter_for_connected, adapters_to_run
from app.models import ConnectedSource, User

logger = logging.getLogger(__name__)


scheduler = BackgroundScheduler()
_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ingest")


def _run_adapter(name: str):
    db = SessionLocal()
    try:
        pairs = adapters_to_run(db)
        match = next((adapter for label, adapter in pairs if label == name), None)
        if match is None:
            return

        owner = (
            db.query(User)
            .filter(User.role == "admin")
            .order_by(User.id)
            .first()
        )
        if owner is None:
            owner = db.query(User).order_by(User.id).first()
        if owner is None:
            logger.warning("Skipping source %s: no user exists to own ingested properties", name)
            return

        result = run_ingestion(db=db, adapter=match, user_id=owner.id)
        logger.info(
            "INGEST %s: saved=%s skipped=%s",
            name,
            len(result.get("saved") or []),
            len(result.get("skipped") or []),
        )
    except Exception:
        logger.exception("Scheduled ingestion failed (source=%s)", name)
    finally:
        db.close()


def _run_connected_source(source_id: int, user_id: int | None = None) -> None:
    """Run one admin-connected source using the shared bounded worker pool."""
    db = SessionLocal()
    try:
        source = (
            db.query(ConnectedSource)
            .filter(ConnectedSource.id == source_id)
            .first()
        )
        if source is None or not source.enabled:
            return

        if user_id is None:
            owner = (
                db.query(User)
                .filter(User.role == "admin")
                .order_by(User.id)
                .first()
            )
            if owner is None:
                owner = db.query(User).order_by(User.id).first()
            if owner is None:
                logger.warning(
                    "Skipping connected source %s: no user exists to own ingested properties",
                    source_id,
                )
                return
            user_id = owner.id

        result = run_ingestion(
            db=db,
            adapter=adapter_for_connected(source),
            user_id=user_id,
        )
        source.last_run_at = datetime.now(timezone.utc)
        source.last_status = "error" if result.get("error") else "ok"
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Connected source sync failed (source_id=%s)", source_id)
        source = (
            db.query(ConnectedSource)
            .filter(ConnectedSource.id == source_id)
            .first()
        )
        if source is not None:
            source.last_run_at = datetime.now(timezone.utc)
            source.last_status = "error"
            db.commit()
    finally:
        db.close()


def enqueue_connected_source(source_id: int, user_id: int) -> Future:
    """Queue a connected source without creating a second execution path."""
    return _pool.submit(_run_connected_source, source_id, user_id)


def run_incremental_ingestion():
    """Queue built-in and connected sources on the shared bounded worker pool."""
    db = SessionLocal()
    try:
        source_jobs = adapters_to_run(db)
    finally:
        db.close()

    for label, _adapter in source_jobs:
        if label.startswith("connected:"):
            try:
                source_id = int(label.split(":", 2)[1])
            except (IndexError, ValueError):
                logger.error("Skipping malformed connected-source label: %s", label)
                continue
            _pool.submit(_run_connected_source, source_id, None)
        else:
            _pool.submit(_run_adapter, label)


def start_scheduler():
    scheduler.add_job(
        run_incremental_ingestion,
        "interval",
        minutes=20,
        id="incremental_ingestion",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    print("Scheduler started: incremental multi-source ingestion every 20 minutes")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)