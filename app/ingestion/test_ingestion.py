from app.database import SessionLocal
from app.ingestion.mock_source import MockAuctionSource
from app.ingestion.pipeline import run_ingestion


db = SessionLocal()

try:
    adapter = MockAuctionSource()

    result = run_ingestion(
        db=db,
        adapter=adapter,
        user_id=1,
    )

    

    print("\nINGESTION COMPLETE")
    print("Found:", result["items_found"])
    print("Extracted:", result["items_extracted"])
    print("Saved:", len(result["saved"]))
    print("Skipped:", len(result["skipped"]))
    if "error" in result:
       print("ERROR:", result["error"])

    for property_obj in result["saved"]:
        print(
            "Saved property:",
            property_obj.id,
            property_obj.address,
        )

    for property_obj in result["skipped"]:
        print(
            "Skipped duplicate:",
            property_obj["property_id"],
            property_obj["address"],
        )

finally:
    db.close()