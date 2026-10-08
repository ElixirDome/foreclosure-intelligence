from datetime import date

from sqlalchemy.orm import Session

from app.models import (
    MarketComparable,
    Property,
    PropertyValuation,
)


MIN_COMPARABLES = 3
AREA_TOLERANCE = 0.30


def record_valuation(
    db: Session,
    property_id: int,
    estimated_value: float,
    valuation_method: str,
    source: str | None = None,
    confidence: float | None = None,
    valuation_date: date | None = None,
):
    property_obj = (
        db.query(Property)
        .filter(Property.id == property_id)
        .first()
    )

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

    property_obj.estimated_value = estimated_value

    db.commit()
    db.refresh(valuation)
    db.refresh(property_obj)

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



def find_comparables(
    db: Session,
    property_obj: Property,
):
    if property_obj.area_sqft is None:
        return []

    lower_area = property_obj.area_sqft * (
        1 - AREA_TOLERANCE
    )

    upper_area = property_obj.area_sqft * (
        1 + AREA_TOLERANCE
    )

    query = db.query(MarketComparable).filter(
        MarketComparable.area_sqft >= lower_area,
        MarketComparable.area_sqft <= upper_area,
    )

    # City is the primary geographic filter.
    if property_obj.city:
        query = query.filter(
            MarketComparable.city == property_obj.city
        )

    # Locality is an additional filter when available.
    if property_obj.locality:
        query = query.filter(
            MarketComparable.locality
            == property_obj.locality
        )

    if property_obj.property_type:
        query = query.filter(
            MarketComparable.property_type
            == property_obj.property_type
        )

    return query.all()

def calculate_valuation_confidence(
    price_per_sqft_values: list[float],
    comparables_count: int,
) -> float:
    if not price_per_sqft_values:
        return 0.0

    mean_price = sum(price_per_sqft_values) / len(
        price_per_sqft_values
    )

    if mean_price <= 0:
        return 0.0

    variance = sum(
        (value - mean_price) ** 2
        for value in price_per_sqft_values
    ) / len(price_per_sqft_values)

    standard_deviation = variance ** 0.5

    coefficient_of_variation = (
        standard_deviation / mean_price
    )

    # More comparable sales increase confidence.
    count_score = min(comparables_count / 6, 1.0)

    # Lower variation between comparable prices increases confidence.
    consistency_score = max(
        0.0,
        1.0 - coefficient_of_variation,
    )

    confidence = (
        0.4 * count_score
        + 0.6 * consistency_score
    )

    return round(
        min(max(confidence, 0.0), 1.0),
        2,
    )

def calculate_market_valuation(
    db: Session,
    property_obj: Property,
):
    if property_obj.area_sqft is None:
        raise ValueError(
            "Property area_sqft is required for market valuation"
        )

    if property_obj.area_sqft <= 0:
        raise ValueError(
            "Property area_sqft must be greater than 0"
        )

    if not property_obj.city:
        raise ValueError(
            "Property city is required for market valuation"
        )

    comparables = find_comparables(
        db=db,
        property_obj=property_obj,
    )

    if len(comparables) < MIN_COMPARABLES:
        raise ValueError(
            f"Insufficient comparable properties. "
            f"At least {MIN_COMPARABLES} matching "
            f"residential comparables are required."
        )

    price_per_sqft_values = [
        float(comparable.sale_price)
        / comparable.area_sqft
        for comparable in comparables
        if comparable.area_sqft > 0
        and comparable.sale_price > 0
    ]

    if len(price_per_sqft_values) < MIN_COMPARABLES:
        raise ValueError(
            f"Insufficient valid comparable properties. "
            f"At least {MIN_COMPARABLES} are required."
        )

    price_per_sqft_values.sort()

    middle = len(price_per_sqft_values) // 2

    if len(price_per_sqft_values) % 2 == 0:
        median_price_per_sqft = (
            price_per_sqft_values[middle - 1]
            + price_per_sqft_values[middle]
        ) / 2
    else:
        median_price_per_sqft = (
            price_per_sqft_values[middle]
        )

    estimated_value = (
    median_price_per_sqft
    * property_obj.area_sqft
    )

    confidence = calculate_valuation_confidence(
        price_per_sqft_values=price_per_sqft_values,
        comparables_count=len(comparables),
    )

    return {
        "estimated_value": estimated_value,
        "median_price_per_sqft": median_price_per_sqft,
        "comparables_used": len(comparables),
        "confidence": confidence,
        "valuation_method": (
            "residential_comparable_sales"
        ),
    }