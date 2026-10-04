from datetime import date

from app.database import SessionLocal

from app.ingestion.market_comparable_source import (
    MarketComparableCSVAdapter,
)

from app.services.valuation import (
    add_market_comparable,
)


CSV_PATH = "data/market_comparables.csv"


def main():
    db = SessionLocal()

    try:
        adapter = MarketComparableCSVAdapter(CSV_PATH)

        raw_items = adapter.fetch()

        saved = 0

        for item in raw_items:
            comparable = adapter.extract(item)

            sale_date = None

            if comparable["sale_date"]:
                sale_date = date.fromisoformat(
                    comparable["sale_date"]
                )

            add_market_comparable(
                db=db,
                address=comparable["address"],
                city=comparable["city"],
                locality=comparable["locality"],
                property_type=comparable[
                    "property_type"
                ],
                area_sqft=comparable["area_sqft"],
                sale_price=comparable["sale_price"],
                sale_date=sale_date,
                source=comparable["source"],
                source_url=comparable["source_url"],
            )

            saved += 1

        print(
            "MARKET COMPARABLE IMPORT COMPLETE"
        )
        print("---------------------------------")
        print("Found:", len(raw_items))
        print("Saved:", saved)

    finally:
        db.close()


if __name__ == "__main__":
    main()