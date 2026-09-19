from app.services.normalization import create_property_key
from app.services.pdf import extract_text_from_pdf
from app.services.extraction import extract_properties_from_text


pdf_path = r"C:\Users\user\OneDrive\Desktop\auction_catalogue_598373 (1).pdf"

text = extract_text_from_pdf(pdf_path)

properties = extract_properties_from_text(text)

print(f"Found {len(properties)} properties")

for property in properties:
    print("\n--- PROPERTY ---")
    print("Address:", property.address)
    print("Survey:", property.survey_number)
    print("Area:", property.area_sqft)
    print("Type:", property.property_type)
    print("Pincode:", property.pincode)
    print("City:", property.city)
    print("State:", property.state)

    key = create_property_key(
    address=property.address,
    area_sqft=property.area_sqft,
    property_type=property.property_type,
    survey_number=property.survey_number,
)
key1 = create_property_key(
    address="No 5 somasundaram Mudali streeet Chennai 600079",
    area_sqft=1824,
    property_type="Immovable Property",
    survey_number="6657/1",
)

key2 = create_property_key(
    address="No 5 somasundaram Mudali streeet Chennai 600079",
    area_sqft=1824,
    property_type="Immovable Property",
    survey_number="6657/1",
)

print("Same property:", key1 == key2)
print("Key:", key)

for property in properties:
    print()
    print(property.model_dump())