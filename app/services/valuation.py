"""
Market valuation services.

Unverified automated valuation models (median price per sqft, estimated value,
valuation confidence, and comparable-derived discounts) have been removed.
When verified market valuation data does not exist, the system explicitly indicates:
"Market valuation unavailable — verified comparable transaction data is not available."
"""

from __future__ import annotations

from datetime import date
from sqlalchemy.orm import Session

from app.domain.auction_intelligence import MARKET_VALUATION_UNAVAILABLE_MESSAGE
from app.models import MarketComparable, Property, PropertyValuation


def get_latest_comparable_valuation(
    db: Session,
    property_id: int,
) -> PropertyValuation | None:
    """Return verified valuation if one exists."""
    return (
        db.query(PropertyValuation)
        .filter(
            PropertyValuation.property_id == property_id,
        )
        .order_by(PropertyValuation.id.desc())
        .first()
    )


def record_valuation(
    db: Session,
    property_id: int,
    estimated_value: float | None = None,
    valuation_method: str = "unavailable",
    source: str | None = None,
    confidence: float | None = None,
    valuation_date: date | None = None,
):
    """Record an official or verified valuation."""
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if property_obj is None:
        raise ValueError("Property not found")

    valuation = PropertyValuation(
        property_id=property_id,
        estimated_value=estimated_value,
        valuation_method=valuation_method,
        source=source,
        confidence=confidence,
        valuation_date=valuation_date or date.today(),
    )
    db.add(valuation)
    db.commit()
    db.refresh(valuation)
    return valuation


def add_market_comparable(
    db: Session,
    address: str,
    city: str | None,
    locality: str | None,
    property_type: str | None,
    area_sqft: int,
    sale_price: float,
    sale_date: date | None,
    source: str,
    source_url: str | None,
):
    """Store an ingested market sale record for registry record keeping."""
    from app.ingestion.comparable_save import create_comparable_key

    comparable_key = create_comparable_key(
        address=address,
        area_sqft=area_sqft,
        sale_price=sale_price,
        sale_date=sale_date,
        source=source,
    )

    existing = (
        db.query(MarketComparable)
        .filter(MarketComparable.comparable_key == comparable_key)
        .first()
    )

    if existing:
        raise ValueError("This comparable sale already exists.")

    comparable = MarketComparable(
        address=address,
        city=city,
        locality=locality,
        property_type=property_type,
        area_sqft=area_sqft,
        sale_price=sale_price,
        sale_date=sale_date,
        source=source,
        source_url=source_url,
        comparable_key=comparable_key,
    )

    try:
        db.add(comparable)
        db.commit()
        db.refresh(comparable)
        return comparable
    except Exception:
        db.rollback()
        raise


def calculate_market_valuation(
    db: Session,
    property_obj: Property,
) -> dict:
    """
    Indicate that unverified comparable automated valuation is unavailable.
    Does not manufacture estimates or substitute arbitrary guesses.
    """
    return {
        "status": "unavailable",
        "message": MARKET_VALUATION_UNAVAILABLE_MESSAGE,
        "estimated_value": None,
        "confidence": None,
        "valuation_method": "none",
    }
