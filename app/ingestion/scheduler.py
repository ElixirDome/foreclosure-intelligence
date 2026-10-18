from concurrent.futures import ThreadPoolExecutor

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.ingestion.pipeline import run_ingestion
from app.ingestion.registry import adapters_to_run


scheduler = BackgroundScheduler()
_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ingest")


def _run_adapter(name: str):
    db = SessionLocal()
    try:
        pairs = adapters_to_run(db)
        match = next((adapter for label, adapter in pairs if label == name), None)
        if match is None:
            return
        result = run_ingestion(db=db, adapter=match, user_id=1)
        print(f"INGEST {name}: saved={len(result.get('saved') or [])} skipped={len(result.get('skipped') or [])}")
    except Exception as exc:
        print(f"INGEST {name} FAILED:", exc)
    finally:
        db.close()


def run_incremental_ingestion():
    """Queue every enabled source. Each source uses its own DB session."""
    db = SessionLocal()
    try:
        names = [label for label, _ in adapters_to_run(db)]
    finally:
        db.close()
    for name in names:
        _pool.submit(_run_adapter, name)


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