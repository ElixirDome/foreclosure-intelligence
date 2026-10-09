from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.ingestion.pnb_source import PNBSourceAdapter
from app.ingestion.banknet_source import BankNetSourceAdapter
from app.ingestion.pipeline import run_ingestion, run_document_ingestion


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


def run_banknet_ingestion():
    db = SessionLocal()
    try:
        adapter = BankNetSourceAdapter(
            # Nationwide by default; pass city_id=2458 for Chennai-only
            limit=50,
            max_pages=3,
            download_documents=True,
        )
        result = run_ingestion(db=db, adapter=adapter, user_id=1)
        print("\nAUTOMATIC BANKNET INGESTION COMPLETE")
        print("Found:", result.get("items_found"))
        print("Extracted:", result.get("items_extracted"))
        print("Saved:", len(result.get("saved") or []))
        print("Skipped:", len(result.get("skipped") or []))
        if result.get("error"):
            print("ERROR:", result["error"])
    except Exception as exc:
        print("\nAUTOMATIC BANKNET INGESTION FAILED")
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
    scheduler.add_job(
        run_banknet_ingestion,
        "interval",
        hours=6,
        id="banknet_ingestion",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()

    print("Schedulers started: PNB + BankNet every 6 hours")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()