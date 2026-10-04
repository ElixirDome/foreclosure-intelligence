from pathlib import Path

from app.ingestion.pnb_source import PNBSourceAdapter
from app.services.pnb_extraction import extract_pnb_properties


pdf_path = Path("pnb_test_notice.pdf")

adapter = PNBSourceAdapter()

print("Running OCR...")
text = adapter._extract_ocr_text(pdf_path)

print("\n========== OCR TEXT ==========")
print(text)
print("========== END OCR TEXT ==========")


print("\nExtracting properties...")
properties = extract_pnb_properties(text)

print("\nPROPERTIES EXTRACTED")
print("--------------------")
print("Count:", len(properties))

for index, property_data in enumerate(properties, start=1):
    print(f"\nProperty {index}")
    print("Address:", property_data["address"])
    print("Area:", property_data["area_sqft"])
    print("Opening bid:", property_data["opening_bid"])
    print("Auction date:", property_data["auction_date"])
    print("Property type:", property_data["property_type"])
    print("Survey number:", property_data["survey_number"])
