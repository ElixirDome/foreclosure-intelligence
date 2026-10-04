from app.database import SessionLocal
from app.ingestion.kaveri_transaction_source import KaveriTransactionAdapter
from app.ingestion.comparable_pipeline import run_comparable_ingestion


JSON_PATH = "data/kaveri_transactions.json"


def main():
    db = SessionLocal()

    try:
        adapter = KaveriTransactionAdapter(JSON_PATH)

        result = run_comparable_ingestion(
            db=db,
            adapter=adapter,
        )

        print("\nKAVERI COMPARABLE INGESTION COMPLETE")
        print("------------------------------------")
        print("Found:", result["items_found"])
        print("Extracted:", result["items_extracted"])
        print("Saved:", len(result["saved"]))
        print("Skipped:", len(result["skipped"]))

        for comparable in result["saved"]:
            print(
                "Saved comparable:",
                comparable.id,
                comparable.address,
            )

        for comparable in result["skipped"]:
            print(
                "Skipped duplicate:",
                comparable["comparable_id"],
                comparable["address"],
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()