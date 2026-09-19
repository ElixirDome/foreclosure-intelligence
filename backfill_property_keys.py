from app.database import SessionLocal
from app.models import Property
from app.services.normalization import create_property_key


db = SessionLocal()

try:
    properties = db.query(Property).all()

    for property in properties:
        if property.property_key is None:
            property.property_key = create_property_key(
                address=property.address,
                area_sqft=property.area_sqft,
                property_type=property.property_type,
                survey_number=None,
            )

            print(
                f"Property {property.id}: "
                f"{property.property_key}"
            )

    db.commit()

    print(f"Backfilled {len(properties)} properties.")

finally:
    db.close()