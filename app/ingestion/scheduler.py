from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.ingestion.pnb_source import PNBSourceAdapter
from app.ingestion.pipeline import run_ingestion


scheduler = BackgroundScheduler()


def run_pnb_ingestion():
    db = SessionLocal()

    try:
        adapter = PNBSourceAdapter()

        result = run_ingestion(
            db=db,
            adapter=adapter,
            user_id=1,
        )

        print("\nAUTOMATIC PNB INGESTION COMPLETE")
        print("---------------------------------")
        print("Found:", result["items_found"])
        print("Extracted:", result["items_extracted"])
        print("Saved:", len(result["saved"]))
        print("Skipped:", len(result["skipped"]))

        if "error" in result:
            print("ERROR:", result["error"])

    except Exception as exc:
        print("\nAUTOMATIC PNB INGESTION FAILED")
        print("ERROR:", exc)

    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(
        run_pnb_ingestion,
        "interval",
        hours=6,
        id="pnb_ingestion",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()

    print("PNB scheduler started: runs every 6 hours")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()