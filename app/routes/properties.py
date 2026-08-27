from fastapi import (APIRouter,Query,
Depends,status, HTTPException)
from sqlalchemy.orm import Session
from math import ceil
from datetime import date

from app.services.properties import (
    create_property,get_properties,
    update_property,delete_property,
    get_property_by_id,
    analyze_property,
    get_property_or_404,
)
from app.database import SessionLocal,get_db
from app.models import Property, User
from app.schemas import PropertyResponse,PropertyListResponse,PropertyCreate,PropertyUpdate,PropertyAnalysis,PropertyAIAnalysis #didn't import it lost 10 mins
from app.security import (get_current_user, require_role,
                          require_property_owner #
                          )
from app.dependencies import get_llm_provider
from app.services.llm import LLMProvider
from app.services.properties import analyze_property_with_ai

router = APIRouter(prefix="/properties",tags=["properties"])

@router.get(
    "/",
    response_model=PropertyListResponse#response_model constraint
)
def get_properties_route(
    page: int = Query(1, ge=1),#FastAPI lets us constrain query parameters.
    limit: int = Query(20, ge=1, le=100),# now a client couldn't do GET /properties?limit=100000000
    min_price: int | None = Query(None, ge=0),
    max_price: int | None = Query(None, ge=0),
    bedrooms: int | None = Query(None, ge=0),
    sort_by: str = Query("id"),
    order: str = Query("asc"),
    db: Session = Depends(get_db),
    min_area: int | None = Query(None, ge=0),
    max_area: int | None = Query(None, ge=0),
    min_discount: float | None = Query(None, ge=0, le=100),
    max_discount: float | None = Query(
    None,
    ge=0,
    le=100
    ),
    foreclosure_status: str | None = Query(None),
    auction_date_from: date | None = Query(None),
    auction_date_to: date | None = Query(None),
):
    
    if foreclosure_status:
        foreclosure_status = foreclosure_status.lower()

    else:
        foreclosure_status = None

    try:
        return get_properties(
            db=db,#for the parameter named db in get_properties's signature, use the value currently held by my local variable also named db.
            page=page,
            limit=limit,
            min_price=min_price,
            max_price=max_price,
            bedrooms=bedrooms,
            sort_by=sort_by,
            order=order,
            min_area=min_area,
            max_area=max_area,
            min_discount=min_discount,
            max_discount=max_discount,
            foreclosure_status=foreclosure_status,
            auction_date_from=auction_date_from,
            auction_date_to=auction_date_to,
        )

    except ValueError as e:
        raise HTTPException(
                status_code=400,
                detail=str(e)
            )

@router.get(
    "/{property_id}/analysis",
    response_model=PropertyAnalysis
)
def analyze_property_route(
    property_id: int,
    db: Session = Depends(get_db)
):
    property = get_property_by_id(
        property_id=property_id,
        db=db
    )

    return analyze_property(property)

@router.get(
    "/{property_id}/analysis/ai",
    response_model=PropertyAIAnalysis,
)
def analyze_property_ai_route(
    property_id: int,
    db: Session = Depends(get_db),
    provider: LLMProvider = Depends(get_llm_provider),
):
    property = get_property_by_id(
        property_id=property_id,
        db=db,
    )

    return analyze_property_with_ai(
        property=property,
        provider=provider,
    )

@router.get(
    "/{property_id}",
    response_model=PropertyResponse
)
def get_property(
    property_id: int,
    db: Session = Depends(get_db)
):
    return get_property_by_id(
        property_id=property_id,
        db=db
    )

@router.post(
    "/",
    response_model=PropertyResponse,
    status_code=status.HTTP_201_CREATED
)
def create_property_route(
    property_data: PropertyCreate,#If your create_property_route currently receives a PropertyCreate object: then no need to manually add auction_date, opening_bid,etc . to the route. They're already inside: property_data, once you've added them to Propertycreate
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
   
):
    return create_property(
        db=db,
        property_data=property_data,
        user_id=current_user.id
     ) #In Python, a function with no explicit return statement returns None by default — no error, no warning, it just silently happens. If you (or a version of this code) forgot to add return property at the end, this is exactly the symptom: the INSERT into Postgres likely succeeded (data's probably actually in the properties table), but the HTTP response has nothing to send back, and response_model=PropertyResponse then chokes trying to validate None against a schema that expects real fields.

@router.delete(
    "/{property_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_property_route(
    property: Property = Depends(require_property_owner),
    db: Session = Depends(get_db)
):  
    print("ROUTE DB:", id(db))

    delete_property(
        db=db,
        property=property
    )
    return

@router.patch(
    "/{property_id}",
    response_model=PropertyResponse
)
def update_property_route(
    property_data: PropertyUpdate,
    property: Property = Depends(require_property_owner),
    db: Session = Depends(get_db)
):
    update_data = property_data.model_dump(
        exclude_unset=True
    )

    return update_property(
        db=db,
        property=property,
        update_data=update_data
    )