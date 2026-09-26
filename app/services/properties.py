from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, case
from math import ceil
from datetime import date
from app.models import Property

from fastapi import HTTPException
from app.schemas import PropertyCreate, ExtractedProperty
from app.services.llm import (
    LLMProvider,
    generate_property_analysis,
)
from app.services.normalization import create_property_key

DEAL_SCORE_RISK_MULTIPLIER = 5#Don't put it inside calculate_deal_score() if both calculate_deal_score() and get_properties() need it. Put it at module level.
FORECLOSURE_RISK_LEVELS = {
    "scheduled": 1,
    "upcoming": 1,
    "active": 2,
    "sold": 3,
    "cancelled": 3,
}
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

def get_properties(#service signature
    db: Session,
  
    page: int,
    limit: int,
    min_price: int | None,
    max_price: int | None,
    bedrooms: int | None,
    sort_by: str,
    order: str,
    min_area: int | None ,
    max_area: int | None,# Query() belongs in the route. Plain int | None belongs in the service.
    min_discount: float | None,
    max_discount: float | None,
    foreclosure_status: str | None,
    auction_date_from: date | None,
    auction_date_to: date | None,
):
# 1. Build base query
# 2. Create discount_percentage SQL expression
# 3. Apply filters
# 4. Apply sorting
# 5. Pagination
# 6. Execute query
    discount_percentage = case(
        (
            and_(
                Property.estimated_value.is_not(None),
                Property.opening_bid.is_not(None),
                Property.estimated_value > 0,
            ),
            (
                (
                    Property.estimated_value
                    - Property.opening_bid
                )
                / Property.estimated_value
                * 100
            ),
        ),
        else_=None,
    ).label("discount_percentage")
    
    risk_level = case(
    *[
        (Property.foreclosure_status == status, risk)
        for status, risk in FORECLOSURE_RISK_LEVELS.items()
    ],
    else_=2,
)
    deal_score = case(
    (
        discount_percentage.is_not(None),
       discount_percentage - (
       risk_level * DEAL_SCORE_RISK_MULTIPLIER),
    ),
    else_=None,
).label("deal_score")
     
    query = db.query(Property,discount_percentage,
                     deal_score)#Yep — I see the bug immediately. Your filtering logic is correct. The problem is that you build the filtered query, but then you throw it away when fetching the properties.
#UnboundLocalError: cannot access local variable 'discount_percentage' where it is not associated with a value
  
####3##########3 SQL filters
    if min_price is not None:
        query = query.filter(Property.price >= min_price)

    if max_price is not None:
        query = query.filter(Property.price <= max_price)

    if bedrooms is not None:
        query = query.filter(Property.bedrooms == bedrooms)

    if min_area is not None:
        query = query.filter(Property.area_sqft >= min_area)

    if max_area is not None:
        query = query.filter(Property.area_sqft <= max_area)

    if min_discount is not None:
     query = query.filter(
        Property.estimated_value.is_not(None),
        Property.opening_bid.is_not(None),
        Property.estimated_value > 0,
        (
            (
                Property.estimated_value
                - Property.opening_bid
            )
            / Property.estimated_value
            * 100
        ) >= min_discount
    )    
    if max_discount is not None:
     query = query.filter(
        Property.estimated_value.is_not(None),
        Property.opening_bid.is_not(None),
        Property.estimated_value > 0,
        (
            (
                Property.estimated_value
                - Property.opening_bid
            )
            / Property.estimated_value
            * 100
        ) <= max_discount
    )
     
    if foreclosure_status is not None:
      query = query.filter(
        Property.foreclosure_status == foreclosure_status
    )
    if auction_date_from is not None:
       query = query.filter(
        Property.auction_date >= auction_date_from
    )

    if auction_date_to is not None:
      query = query.filter(
        Property.auction_date <= auction_date_to
    )
      
   
    
###############################PAGINATION
    total = query.count()


    sort_fields = {#whitelist #client input  :  SQLAlchemy column
        "id": Property.id,
        "price": Property.price,
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

    offset = (page - 1) * limit

    results = (
        query#not db.query(property) that will be throwing away all the filters
        .offset(offset)
        .limit(limit)
        .all()
    )

    properties = []
# Tuple Unpacking in Loop: for property, discount, score in results: expects each item in results to be a 3-element tuple or list. In each iteration, it unpacks those three elements into the local variables property, discount, and score.
# Dictionary Construction: property_data = { ... } constructs a dictionary for the current item, combining fields from property alongside calculated metrics like discount and score.
# Outer Appending (The Current Code): Because properties.append(property_data) is outside the loop (no indentation), it runs only once after the loop finishes. Consequently, properties will only receive the very last property_data generated by the final iteration.
    for property, discount, score in results:#The too many values to unpack error means your query is returning three values, but somewhere you're still unpacking only two.
     property_data = {
        "id": property.id,
        "address": property.address,
        "price": property.price,
        "bedrooms": property.bedrooms,
        "bathrooms": property.bathrooms,#Pydantic will take those dictionaries and validate them against PropertyResponse.
        "area_sqft": property.area_sqft,
        "auction_date": property.auction_date,
        "foreclosure_status": property.foreclosure_status,
        "opening_bid": property.opening_bid,
        "estimated_value": property.estimated_value,
        "property_type": property.property_type,
        "discount_percentage": discount,
        "deal_score": score,
    }
     properties.append(property_data)#properties.append(property) So you're returning the raw Property object instead of the property_data dictionary containing the calculated values.
#    ^
#    |
#Notice the indentation: properties.append(property_data) must be inside the for loop.
    pages = ceil(total / limit)

    return {
        "items": properties,
        "page": page,
        "limit": limit,
        "total": total,
        "pages": pages
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
        "estimated_value",
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
    
def calculate_deal_score(
    discount_percentage: float | None,
    risk_level: int
) -> float:

    score = discount_percentage - (
        risk_level * DEAL_SCORE_RISK_MULTIPLIER
    )

    return max(0, min(score, 100))
    
# Layer 1 — deterministic
# analyze_property()
# It should always produce the same answer for the same property.
def analyze_property(
    property: Property
):
    if property.estimated_value is None or property.estimated_value <= 0:
        raise HTTPException(
            status_code=400,
            detail="Deal analysis requires estimated_value greater than 0"
        )

    if property.opening_bid is None:
        raise HTTPException(
            status_code=400,
            detail="Deal analysis requires opening_bid"
        )

    discount_amount = (
        property.estimated_value
        - property.opening_bid
    )

    discount_percentage = (
        discount_amount
        / property.estimated_value
        * 100
    )
    
    status = (
    property.foreclosure_status.lower()
    if property.foreclosure_status
    else None
)
    risk_level = FORECLOSURE_RISK_LEVELS.get(
    status,
    2
)
    risk_level = FORECLOSURE_RISK_LEVELS.get(status, 2)
    score = calculate_deal_score(
    discount_percentage,
    risk_level
)
  
    if discount_percentage >= 30:
        deal_rating = "excellent"
    elif discount_percentage >= 20:
        deal_rating = "good"
    elif discount_percentage >= 10:
        deal_rating = "moderate"
    else:
        deal_rating = "low"

    return {
        "estimated_value": property.estimated_value,
        "opening_bid": property.opening_bid,
        "discount_amount": discount_amount,
        "discount_percentage": discount_percentage,
        "deal_rating": deal_rating,
        "deal_score": score,
    }

#It takes those facts and asks the LLM to interpret them.
def analyze_property_with_ai(
    property: Property,
    provider: LLMProvider,
):
    deterministic_analysis = analyze_property(property)

    property_data = {
        "address": property.address,
        "property_type": property.property_type,
        "price": property.price,
        "bedrooms": property.bedrooms,
        "bathrooms": property.bathrooms,
        "area_sqft": property.area_sqft,
        "auction_date": property.auction_date,
        "foreclosure_status": property.foreclosure_status,
        "opening_bid": property.opening_bid,
        "estimated_value": property.estimated_value,
    }

    return generate_property_analysis(
        property_data=property_data,
        analysis_data=deterministic_analysis,
        provider=provider,
    )