from sqlalchemy.orm import Session

from app.models import MarketComparable

def create_comparable_key(
address: str,
area_sqft: int,
sale_price: float,
sale_date,
source: str,
) -> str:
    normalized_address = " ".join(address.lower().split())
    normalized_source = source.lower().strip()

    sale_date_value = (
    sale_date.isoformat()
    if sale_date is not None
    else ""
    )

    normalized_price = format(float(sale_price), ".2f")

    return (
        f"{normalized_source}|"
        f"{normalized_address}|"
        f"{area_sqft}|"
        f"{normalized_price}|"
        f"{sale_date_value}"
    )

def save_market_comparables(
    db: Session,
    comparables: list[dict],
):
    saved = []
    skipped = []

    try:
        for comparable_data in comparables:
            comparable_key = create_comparable_key(
                address=comparable_data["address"],
                area_sqft=comparable_data["area_sqft"],
                sale_price=comparable_data["sale_price"],
                sale_date=comparable_data.get("sale_date"),
                source=comparable_data["source"],
            )

            existing = (
                db.query(MarketComparable)
                .filter(
                    MarketComparable.comparable_key == comparable_key
                )
                .first()
            )

            if existing:
                skipped.append({
                    "comparable_id": existing.id,
                    "address": existing.address,
                    "reason": "duplicate",
                })
                continue

            comparable = MarketComparable(
                address=comparable_data["address"],
                city=comparable_data.get("city"),
                locality=comparable_data.get("locality"),
                property_type=comparable_data.get("property_type"),
                area_sqft=comparable_data["area_sqft"],
                sale_price=comparable_data["sale_price"],
                sale_date=comparable_data.get("sale_date"),
                source=comparable_data["source"],
                source_url=comparable_data.get("source_url"),
                comparable_key=comparable_key,
            )

            db.add(comparable)
            db.flush()
            saved.append(comparable)

        db.commit()

        for comparable in saved:
            db.refresh(comparable)

        return {
            "saved": saved,
            "skipped": skipped,
        }

    except Exception:
        db.rollback()
        raise