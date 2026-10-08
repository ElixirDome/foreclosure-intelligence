from pathlib import Path

from app.services.pnb_extraction import extract_pnb_property


text = Path("pnb_test_ocr.txt").read_text(
    encoding="utf-8"
)

property_data = extract_pnb_property(text)

print("\nPNB PROPERTY")
print("------------")

for key, value in property_data.items():
    print(f"{key}: {value}")