from app.database import SessionLocal

from app.services.properties import save_extracted_properties
from app.services.pdf import extract_text_from_pdf
from app.services.extraction import extract_properties_from_text


PDF_PATH = r"C:\Users\user\OneDrive\Desktop\auction_catalogue_598373 (1).pdf"

db = SessionLocal()

try:
    text = extract_text_from_pdf(PDF_PATH)

    extracted_properties = extract_properties_from_text(text)

    print(f"Extracted: {len(extracted_properties)} properties")

    result = save_extracted_properties(
        db=db,
        properties=extracted_properties,
        user_id=1,
    )

    saved_properties = result["saved"]
    skipped_properties = result["skipped"]

    print(f"Saved: {len(saved_properties)} properties")
    print(f"Skipped: {len(skipped_properties)} duplicates")

    for property_obj in saved_properties:
        print(
            property_obj.id,
            property_obj.address,
            property_obj.price,
            property_obj.area_sqft,
        )

finally:
    db.close()