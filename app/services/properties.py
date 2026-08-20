from sqlalchemy.orm import Session
from math import ceil
from app.models import Property
from app.database import get_db

def create_property(
    db: Session,
    address: str,
    price: int | None,
    bedrooms: int | None,
    bathrooms: float | None,
    area_sqft: int | None,
    user_id: int
):
    property = Property(
        address=address,
        price=price,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        area_sqft=area_sqft,
        user_id=user_id
    )

    db.add(property)
    db.commit()
    db.refresh(property)

    return property

def get_properties(
    db: Session,
    page: int,
    limit: int,
    min_price: int | None,
    max_price: int | None,
    bedrooms: int | None,
    sort_by: str,
    order: str
):
    query = db.query(Property)#Yep — I see the bug immediately. Your filtering logic is correct. The problem is that you build the filtered query, but then you throw it away when fetching the properties.

    if min_price is not None:
        query = query.filter(Property.price >= min_price)

    if max_price is not None:
        query = query.filter(Property.price <= max_price)

    if bedrooms is not None:
        query = query.filter(Property.bedrooms == bedrooms)
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

    properties = (
        query
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

def update_property(
    db: Session,
    property: Property,#Notice that the service receives the already-authorized property.Authentication/authorization stays outside the service.
    update_data: dict
):
    for field, value in update_data.items():
        setattr(property, field, value)

    db.commit()
    db.refresh(property)

    return property

def delete_property(
    db: Session,
    property: Property
):
    db.delete(property)
    db.commit()