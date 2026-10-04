from app.ingestion.pnb_source import PNBSourceAdapter
from app.services.pnb_extraction import extract_pnb_properties


adapter = PNBSourceAdapter()

print("Discovering PNB documents...")
items = adapter.fetch()

print("\nDocuments discovered:", len(items))

for index, item in enumerate(items, start=1):
    print(f"{index}. {item['title']}")

if len(items) < 2:
    raise RuntimeError("Expected at least 2 downloadable PNB documents")

item = items[1]

print("\n========== TESTING DOCUMENT 2 ==========")
print("Title:", item["title"])
print("URL:", item["source_url"])

print("\nRunning OCR...")
text = adapter._extract_ocr_text(item["pdf_path"])

print("\n========== DOCUMENT 2 OCR ==========")
print(text)
print("========== END DOCUMENT 2 OCR ==========")

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