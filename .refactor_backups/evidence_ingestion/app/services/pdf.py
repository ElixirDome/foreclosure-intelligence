from pathlib import Path

from pypdf import PdfReader


def extract_text_from_pdf(
    pdf_path: str | Path,
) -> str:

    reader = PdfReader(pdf_path)

    pages = []

    for page in reader.pages:
        text = page.extract_text()

        if text:
            pages.append(text)

    return "\n".join(pages)