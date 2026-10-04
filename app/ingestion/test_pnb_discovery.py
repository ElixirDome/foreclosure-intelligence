import pytesseract
from pdf2image import convert_from_path

from app.ingestion.pnb_source import PNBSourceAdapter


adapter = PNBSourceAdapter()

items = adapter.fetch()

print("\nFIRST PAGE INSPECTION")
print("---------------------")

for index, item in enumerate(items, start=1):

    print(f"\nDOCUMENT {index}")
    print("TITLE:", item["title"])
    print("SIZE:", item["pdf_path"].stat().st_size)

    pages = convert_from_path(
        item["pdf_path"],
        dpi=150,
        first_page=1,
        last_page=1,
        poppler_path=r"C:\Dev\poppler-26.09.0\Library\bin",
    )

    text = pytesseract.image_to_string(
        pages[0]
    )

    print("\nOCR PREVIEW:")
    print("FULL OCR:") 
    print(text)