from sqlalchemy.orm import Session

from app.ingestion.base import SourceAdapter
from app.ingestion.comparable_save import save_market_comparables


def run_comparable_ingestion(
    db: Session,
    adapter: SourceAdapter,
):
    raw_items = adapter.fetch()

    extracted_items = []

    for item in raw_items:
        extracted = adapter.extract(item)

        if extracted is None:
            continue

        if isinstance(extracted, list):
            extracted_items.extend(extracted)
        else:
            extracted_items.append(extracted)

    save_result = save_market_comparables(
        db=db,
        comparables=extracted_items,
    )

    return {
        "items_found": len(raw_items),
        "items_extracted": len(extracted_items),
        "saved": save_result["saved"],
        "skipped": save_result["skipped"],
    }