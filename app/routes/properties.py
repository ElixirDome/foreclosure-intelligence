from fastapi import (APIRouter,Query,
Depends,status, HTTPException)
from sqlalchemy.orm import Session
from math import ceil

from app.database import SessionLocal
from app.models import Property, User
from app.schemas import PropertyResponse,PropertyListResponse,PropertyCreate,PropertyUpdate #didn't import it lost 10 mins
from app.security import (get_current_user, require_role,
                          require_property_owner #
                          )

router = APIRouter(prefix="/properties",tags=["properties"])

def get_db():
    db = SessionLocal()# runs a session is created and yielded to the endpoint function, which can then use it to query the database. After the request is complete, the session is closed in the finally block.

    try:
        yield db
    finally:#using finally ensures that the session is closed even if an exception occurs during the request handling. This is important for resource management and preventing connection leaks.
        db.close()

@router.get(
    "/",
    response_model=PropertyListResponse
)
def get_properties(
    page: int = Query(1, ge=1),#FastAPI lets us constrain query parameters.
    limit: int = Query(20, ge=1, le=100),# now a client couldn't do GET /properties?limit=100000000
    db: Session = Depends(get_db)
):
    offset = (page - 1) * limit

    total = db.query(Property).count()#COUNT(*) How many properties exist?

    properties = (
        db.query(Property)
        .order_by(Property.id)#The database isn't required to return rows in a stable order unless you ask for one.
        .offset(offset)
        .limit(limit)
        .all()
    )
    pages = ceil(total / limit)

    return {
        "items": properties,
        "page": page,
        "limit": limit,
        "total": total,
        "pages": pages
    }

@router.post(
    "/",
    response_model=PropertyResponse,
    status_code=status.HTTP_201_CREATED
)
def create_property(
    property_data: PropertyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
   
):
    property = Property(
# Right side (property_data.address) — property_data is the Pydantic object (PropertyCreate), already validated by FastAPI when the request came in. .address is just normal attribute access on that validated object — safe to trust, since Pydantic already confirmed it's a string.
# Left side (Property(...)) — this is instantiating the SQLAlchemy model (from models.py), creating an in-memory Python object representing a future database row. Important: at this point, nothing has touched Postgres yet. This object exists only in Python's memory — no INSERT has run.
        address=property_data.address,
        price=property_data.price,
        bedrooms=property_data.bedrooms,
        bathrooms=property_data.bathrooms,
        area_sqft=property_data.area_sqft,
        user_id=current_user.id
    )

    db.add(property)
    db.commit()
    db.refresh(property)
    return property#In Python, a function with no explicit return statement returns None by default — no error, no warning, it just silently happens. If you (or a version of this code) forgot to add return property at the end, this is exactly the symptom: the INSERT into Postgres likely succeeded (data's probably actually in the properties table), but the HTTP response has nothing to send back, and response_model=PropertyResponse then chokes trying to validate None against a schema that expects real fields.

@router.delete(
    "/{property_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_property(
    property_id: int,
    current_user: User=Depends(require_property_owner),
    db: Session = Depends(get_db)
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

    db.delete(property)
    db.commit()
    return

@router.patch(
    "/{property_id}",
    response_model=PropertyResponse
)
def update_property(
    property_id: int,
    property_data: PropertyUpdate,
    property: Property = Depends(require_property_owner),
    db: Session = Depends(get_db)
):
    update_data = property_data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():#loops over the fields the client actually supplied.
        setattr(property, field, value)  #is equivalent to dynamically doing: property.price = 250000

    db.commit()
    db.refresh(property)

    return property