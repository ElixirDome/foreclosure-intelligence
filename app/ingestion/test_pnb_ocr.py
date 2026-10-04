from pathlib import Path

import pytesseract
from pdf2image import convert_from_path


pdf_path = Path("pnb_test_notice.pdf")
output_path = Path("pnb_test_ocr.txt")

print("Rendering PDF...")

pages = convert_from_path(
    pdf_path,
    dpi=200,
    poppler_path=r"C:\Dev\poppler-26.09.0\Library\bin",
)

print("Pages:", len(pages))

all_text = []

for index, page in enumerate(pages):
    print(f"OCR PAGE {index + 1}/{len(pages)}...")

    text = pytesseract.image_to_string(page)

    all_text.append(
        f"\n\n===== PAGE {index + 1} =====\n\n{text}"
    )

full_text = "".join(all_text)

output_path.write_text(
    full_text,
    encoding="utf-8",
)

print("\nOCR COMPLETE")
print("TEXT LENGTH:", len(full_text))
print("SAVED:", output_path)