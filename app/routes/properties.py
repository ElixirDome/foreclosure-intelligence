from fastapi import (APIRouter,Query,
Depends,status, HTTPException)
from sqlalchemy.orm import Session
from math import ceil

from app.services.properties import (
    create_property,get_properties,
    update_property,delete_property
)
from app.database import SessionLocal,get_db
from app.models import Property, User
from app.schemas import PropertyResponse,PropertyListResponse,PropertyCreate,PropertyUpdate #didn't import it lost 10 mins
from app.security import (get_current_user, require_role,
                          require_property_owner #
                          )

router = APIRouter(prefix="/properties",tags=["properties"])

@router.get(
    "/",
    response_model=PropertyListResponse
)
def get_properties_route(
    page: int = Query(1, ge=1),#FastAPI lets us constrain query parameters.
    limit: int = Query(20, ge=1, le=100),# now a client couldn't do GET /properties?limit=100000000
    min_price: int | None = Query(None, ge=0),
    max_price: int | None = Query(None, ge=0),
    bedrooms: int | None = Query(None, ge=0),
    sort_by: str = Query("id"),
    order: str = Query("asc"),
    db: Session = Depends(get_db)
):
    try:
        return get_properties(
            db=db,
            page=page,
            limit=limit,
            min_price=min_price,
            max_price=max_price,
            bedrooms=bedrooms,
            sort_by=sort_by,
            order=order
        )

    except ValueError as e:
        raise HTTPException(
                status_code=400,
                detail=str(e)
            )

@router.post(
    "/",
    response_model=PropertyResponse,
    status_code=status.HTTP_201_CREATED
)
def create_property_route(
    property_data: PropertyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
   
):
    property = create_property(
        db=db,
# Right side (property_data.address) — property_data is the Pydantic object (PropertyCreate), already validated by FastAPI when the request came in. .address is just normal attribute access on that validated object — safe to trust, since Pydantic already confirmed it's a string.
# Left side (Property(...)) — this is instantiating the SQLAlchemy model (from models.py), creating an in-memory Python object representing a future database row. Important: at this point, nothing has touched Postgres yet. This object exists only in Python's memory — no INSERT has run.
        address=property_data.address,
        price=property_data.price,
        bedrooms=property_data.bedrooms,
        bathrooms=property_data.bathrooms,
        area_sqft=property_data.area_sqft,
        user_id=current_user.id
    )

    return property#In Python, a function with no explicit return statement returns None by default — no error, no warning, it just silently happens. If you (or a version of this code) forgot to add return property at the end, this is exactly the symptom: the INSERT into Postgres likely succeeded (data's probably actually in the properties table), but the HTTP response has nothing to send back, and response_model=PropertyResponse then chokes trying to validate None against a schema that expects real fields.

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

