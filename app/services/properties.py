from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from math import ceil
from datetime import date
from app.models import Property, PropertyDocument, Document, PropertyValuation

from sqlalchemy import and_, case, func, select

from fastapi import HTTPException
from app.schemas import PropertyCreate, ExtractedProperty
from app.services.llm import LLMProvider,generate_property_analysis
from app.services.normalization import create_property_key

from app.services.valuation import record_valuation

from app.domain.deal_analysis import (
    DEAL_SCORE_RISK_MULTIPLIER,
    FORECLOSURE_RISK_LEVELS,
    calculate_deal_score,
    calculate_deal_rating,
    calculate_discount,
    calculate_price_per_sqft,
    calculate_confidence_adjusted_score,
)
def get_property_by_id(
    property_id: int,
    db: Session
):
    return get_property_or_404(property_id,db)

def create_property(
    db: Session,
    property_data: PropertyCreate,
    user_id: int
):
    property_key = create_property_key(
        address=property_data.address,
        area_sqft=property_data.area_sqft,
        property_type=property_data.property_type,
        survey_number=property_data.survey_number,
    )

    property = Property(
        **property_data.model_dump(),
        user_id=user_id,
        property_key=property_key,
    )

    db.add(property)
    db.commit()
    db.refresh(property)

    return property

def save_extracted_properties(
    db: Session,
    properties: list[ExtractedProperty],
    user_id: int,
):
    saved_properties = []
    skipped_properties = []

    for extracted in properties:

        property_key = create_property_key(
            address=extracted.address or "Unknown",
            area_sqft=extracted.area_sqft,
            property_type=extracted.property_type,
            survey_number=extracted.survey_number,
        )

        existing_property = (
            db.query(Property)
            .filter(Property.property_key == property_key)
            .first()
        )

        if existing_property:
           
            skipped_properties.append({
                "property_id": existing_property.id,
                "address": existing_property.address,
                "reason": "duplicate",
            })
            continue

        property_obj = Property(
            user_id=user_id,
            address=extracted.address or "Unknown",
            price=extracted.opening_bid,
            area_sqft=(
                int(extracted.area_sqft)
                if extracted.area_sqft is not None
                else None
            ),
            opening_bid=extracted.opening_bid,
            property_type=extracted.property_type,
            survey_number=extracted.survey_number,
            auction_date=(
                extracted.auction_start.date()
                if extracted.auction_start is not None
                else None
            ),
            foreclosure_status="scheduled",
            property_key=property_key,
        )

        db.add(property_obj)
        saved_properties.append(property_obj)

    db.commit()

    for property_obj in saved_properties:
        db.refresh(property_obj)

    return {
        "saved": saved_properties,
        "skipped": skipped_properties,
    }

def get_properties(
    db: Session,
    page: int,
    limit: int,
    search: str | None,
    min_price: int | None,
    max_price: int | None,
    bedrooms: int | None,
    sort_by: str,
    order: str,
    min_area: int | None,
    max_area: int | None,
    min_discount: float | None,
    max_discount: float | None,
    foreclosure_status: str | None,
    auction_date_from: date | None,
    auction_date_to: date | None,
    property_type: str | None = None,
):
    """
    Query properties with calculated deal metrics.

    Database-specific SQL expressions live here, while the
    underlying business rules are defined in
    app.domain.deal_analysis.
    """

    trusted_estimate = (
        select(PropertyValuation.estimated_value)
        .where(
            PropertyValuation.property_id == Property.id,
            PropertyValuation.source == "market_comparables",
            PropertyValuation.valuation_method == "residential_comparable_sales",
        )
        .order_by(PropertyValuation.id.desc())
        .limit(1)
        .scalar_subquery()
    )

    discount_percentage = case(
        (
            and_(
                trusted_estimate.is_not(None),
                Property.reserve_price.is_not(None),
                trusted_estimate > 0,
            ),
            (
                (
                    trusted_estimate
                    - Property.reserve_price
                )
                / trusted_estimate
                * 100
            ),
        ),
        else_=None,
    ).label("discount_percentage")

    risk_level = case(
        *[
            (
                func.lower(Property.foreclosure_status) == status,
                risk,
            )
            for status, risk in FORECLOSURE_RISK_LEVELS.items()
        ],
        else_=2,
    )

    raw_deal_score = (
        discount_percentage
        - (risk_level * DEAL_SCORE_RISK_MULTIPLIER)
    )

    deal_score = case(
        (
            discount_percentage.is_(None),
            None,
        ),
        (
            raw_deal_score < 0,
            0,
        ),
        (
            raw_deal_score > 100,
            100,
        ),
        else_=raw_deal_score,
    ).label("deal_score")

    query = db.query(
        Property,
        discount_percentage,
        deal_score,
        trusted_estimate.label("trusted_estimated_value"),
    )

    # Search
    if search:
        query = query.filter(
            Property.address.ilike(f"%{search.strip()}%")
        )

    # Price filters
    if min_price is not None:
        query = query.filter(Property.reserve_price >= min_price)

    if max_price is not None:
        query = query.filter(Property.reserve_price <= max_price)

    # Property filters
    if bedrooms is not None:
        query = query.filter(Property.bedrooms == bedrooms)

    if min_area is not None:
        query = query.filter(Property.area_sqft >= min_area)

    if max_area is not None:
        query = query.filter(Property.area_sqft <= max_area)

    # Discount filters
    if min_discount is not None:
        query = query.filter(
            trusted_estimate.is_not(None),
            Property.reserve_price.is_not(None),
            trusted_estimate > 0,
            (
                (
                    trusted_estimate
                    - Property.reserve_price
                )
                / trusted_estimate
                * 100
            ) >= min_discount,
        )

    if max_discount is not None:
        query = query.filter(
            trusted_estimate.is_not(None),
            Property.reserve_price.is_not(None),
            trusted_estimate > 0,
            (
                (
                    trusted_estimate
                    - Property.reserve_price
                )
                / trusted_estimate
                * 100
            ) <= max_discount,
        )

    # Foreclosure status
    if foreclosure_status is not None:
        query = query.filter(
            func.lower(Property.foreclosure_status)
            == foreclosure_status.lower()
        )

    # Auction date filters
    if auction_date_from is not None:
        query = query.filter(
            Property.auction_date >= auction_date_from
        )

    if auction_date_to is not None:
        query = query.filter(
            Property.auction_date <= auction_date_to
        )

    if property_type is not None:
        pt = property_type.strip().lower()
        if pt in {"residential", "commercial"}:
            query = query.filter(
                func.lower(Property.property_type).ilike(f"%{pt}%")
            )
        else:
            query = query.filter(
                func.lower(Property.property_type) == pt
            )

    # Pagination count
    total = query.count()

    # Sorting whitelist
    sort_fields = {
        "id": Property.id,
        "price": Property.reserve_price,
        "bedrooms": Property.bedrooms,
        "bathrooms": Property.bathrooms,
        "area_sqft": Property.area_sqft,
    }

    if sort_by not in sort_fields:
        raise ValueError("Invalid sort field")

    if order not in {"asc", "desc"}:
        raise ValueError("Order must be 'asc' or 'desc'")

    sort_column = sort_fields[sort_by]

    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Pagination
    offset = (page - 1) * limit

    results = (
        query
        .offset(offset)
        .limit(limit)
        .all()
    )

    properties = []

    for property, discount, score, trusted_estimated_value in results:
        property_data = {
            "id": property.id,
            "address": property.address,
            "city": property.city,
            "locality": property.locality,
            "price": property.price,
            "bedrooms": property.bedrooms,
            "bathrooms": property.bathrooms,
            "area_sqft": property.area_sqft,
            "auction_date": property.auction_date,
            "foreclosure_status": property.foreclosure_status,
            "opening_bid": property.opening_bid,
            "reserve_price": (
                float(property.reserve_price)
                if property.reserve_price is not None
                else None
            ),
            "emd": (
                float(property.emd)
                if getattr(property, "emd", None) is not None
                else None
            ),
            "estimated_value": (
                float(trusted_estimated_value)
                if trusted_estimated_value is not None
                else None
            ),
            "property_type": property.property_type,
            "survey_number": property.survey_number,
            "discount_percentage": (
                float(discount)
                if discount is not None
                else None
            ),
            "deal_score": (
                float(score)
                if score is not None
                else None
            ),
        }

        properties.append(property_data)

    pages = ceil(total / limit)

    if properties:
        prop_ids = [item["id"] for item in properties]
        rows = (
            db.query(PropertyDocument, Document)
            .join(Document, Document.id == PropertyDocument.document_id)
            .filter(PropertyDocument.property_id.in_(prop_ids))
            .all()
        )
        by_prop: dict[int, list] = {}
        for link, doc in rows:
            by_prop.setdefault(link.property_id, []).append({
                "source_name": doc.source_name,
                "source_url": doc.source_url,
                "document_type": doc.document_type,
                "title": doc.title,
                "filename": doc.filename,
            })
        for item in properties:
            item["sources"] = by_prop.get(item["id"], [])
            ptype = item.get("property_type")
            if ptype:
                low = str(ptype).lower()
                if "commercial" in low:
                    item["property_type"] = "commercial"
                elif any(
                    k in low
                    for k in (
                        "residential",
                        "flat",
                        "apartment",
                        "house",
                        "villa",
                        "duplex",
                    )
                ):
                    item["property_type"] = "residential"

    return {
        "items": properties,
        "page": page,
        "limit": limit,
        "total": total,
        "pages": pages,
    }


def update_property(
    db: Session,
    property: Property,
    update_data: dict
):
    allowed_fields = {
        "address",
        "price",
        "bedrooms",
        "bathrooms",
        "area_sqft",
        "auction_date",
        "foreclosure_status",
        "opening_bid",
        "property_type",
        "survey_number",
    }

    for field, value in update_data.items():
        if field in allowed_fields:
            setattr(property, field, value)

    property.property_key = create_property_key(
        address=property.address,
        area_sqft=property.area_sqft,
        property_type=property.property_type,
        survey_number=property.survey_number,
    )

    try:
        db.commit()
        db.refresh(property)

    except SQLAlchemyError:
        db.rollback()
        raise

    return property

def delete_property(
    db: Session,
    property: Property
):
    db.delete(property)
    db.commit()

def get_property_or_404(# helper function
    property_id: int,
    db: Session
):
    property = (
        db.query(Property)
        .filter(Property.id == property_id)
        .first()
    )

    if property is None:
        raise HTTPException(
            status_code=404,
            detail="Property not found"
        )
    
    return property    
    
# Layer 1 — deterministic
# analyze_property()
# It should always produce the same answer for the same property.

def analyze_property(property: Property):
    valuation_confidence = None
    automated_valuations = [
        valuation
        for valuation in property.valuations
        if valuation.source == "market_comparables"
        and valuation.valuation_method == "residential_comparable_sales"
    ]
    latest_valuation = (
        max(automated_valuations, key=lambda valuation: valuation.id)
        if automated_valuations
        else None
    )
    if latest_valuation is not None:
        if latest_valuation.confidence is not None:
            valuation_confidence = float(latest_valuation.confidence)
        estimated_value = float(latest_valuation.estimated_value)
    else:
        # Do not trust legacy estimates that were typed into property fields.
        estimated_value = None
    opening_bid = (
        float(property.opening_bid)
        if property.opening_bid is not None
        else None
    )
    reserve_price = (
        float(property.reserve_price)
        if property.reserve_price is not None
        else None
    )
    emd = float(property.emd) if property.emd is not None else None

    result = {
        "estimated_value": estimated_value,
        "opening_bid": opening_bid,
        "reserve_price": reserve_price,
        "emd": emd,
        "discount_amount": None,
        "discount_percentage": None,
        "price_per_sqft": None,
        "potential_upside": None,
        "risk_level": None,
        "deal_rating": None,
        "deal_score": None,
        "valuation_confidence": valuation_confidence,
    }

    # A lister's opening bid is not a substitute for a published reserve.
    if estimated_value is None or estimated_value <= 0 or reserve_price is None:
        return result

    discount_amount, discount_percentage = calculate_discount(
        estimated_value,
        reserve_price,
    )
    price_per_sqft = calculate_price_per_sqft(
        reserve_price,
        property.area_sqft,
    )

    status = (
        property.foreclosure_status.lower()
        if property.foreclosure_status
        else None
    )
    risk_level = FORECLOSURE_RISK_LEVELS.get(status, 2)
    base_score = calculate_deal_score(discount_percentage, risk_level)
    confidence_adjusted_score = calculate_confidence_adjusted_score(
        base_score,
        valuation_confidence,
    )
    deal_rating = calculate_deal_rating(discount_percentage)

    result.update(
        {
            "discount_amount": discount_amount,
            "discount_percentage": discount_percentage,
            "price_per_sqft": price_per_sqft,
            "potential_upside": discount_amount,
            "risk_level": risk_level,
            "deal_rating": deal_rating,
            "deal_score": confidence_adjusted_score,
        }
    )
    return result

#It takes those facts and asks the LLM to interpret them.
def analyze_property_with_ai(
    property: Property,
    provider: LLMProvider,
):
    deterministic_analysis = analyze_property(property)

    property_data = {
        "address": property.address,
        "property_type": property.property_type,
            "survey_number": property.survey_number,
        "price": property.price,
        "bedrooms": property.bedrooms,
        "bathrooms": property.bathrooms,
        "area_sqft": property.area_sqft,
        "auction_date": property.auction_date,
        "foreclosure_status": property.foreclosure_status,
        "opening_bid": property.opening_bid,
        "reserve_price": property.reserve_price,
        "emd": property.emd,
        "estimated_value": deterministic_analysis["estimated_value"],
    }

    return generate_property_analysis(
        property_data=property_data,
        analysis_data=deterministic_analysis,
        provider=provider,
    )

def get_property_summary(db: Session):
    total_properties = (
        db.query(func.count(Property.id)).scalar() or 0
    )

    upcoming_auctions = (
        db.query(func.count(Property.id))
        .filter(
            Property.auction_date >= date.today(),
            Property.foreclosure_status.in_(
                ["scheduled", "upcoming", "active"]
            ),
        )
        .scalar()
        or 0
    )

    latest_valuation_ids = (
        db.query(
            PropertyValuation.property_id,
            func.max(PropertyValuation.id).label("latest_id"),
        )
        .filter(
            PropertyValuation.source == "market_comparables",
            PropertyValuation.valuation_method == "residential_comparable_sales",
        )
        .group_by(PropertyValuation.property_id)
        .subquery()
    )
    properties_with_estimates = (
        db.query(func.count(Property.id))
        .join(
            latest_valuation_ids,
            latest_valuation_ids.c.property_id == Property.id,
        )
        .join(
            PropertyValuation,
            PropertyValuation.id == latest_valuation_ids.c.latest_id,
        )
        .filter(
            Property.reserve_price.is_not(None),
            PropertyValuation.estimated_value > 0,
            Property.reserve_price < PropertyValuation.estimated_value,
        )
        .scalar()
        or 0
    )

    residential = (
        db.query(func.count(Property.id))
        .filter(func.lower(Property.property_type) == "residential")
        .scalar()
        or 0
    )
    commercial = (
        db.query(func.count(Property.id))
        .filter(func.lower(Property.property_type) == "commercial")
        .scalar()
        or 0
    )
    sold = (
        db.query(func.count(Property.id))
        .filter(func.lower(Property.foreclosure_status) == "sold")
        .scalar()
        or 0
    )

    return {
        "total_properties": total_properties,
        "upcoming_auctions": upcoming_auctions,
        "properties_with_estimates": properties_with_estimates,
        "residential": residential,
        "commercial": commercial,
        "sold": sold,
    }
