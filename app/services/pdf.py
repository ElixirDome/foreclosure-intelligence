from pathlib import Path

from pypdf import PdfReader


def extract_pages_from_pdf(
    pdf_path: str | Path,
) -> list[str]:
    """
    Extract PDF text while preserving page boundaries.

    Page numbers are represented by their list position:
    index 0 = page 1, index 1 = page 2, etc.
    """
    reader = PdfReader(pdf_path)

    pages: list[str] = []

    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)

    return pages


def extract_text_from_pdf(
    pdf_path: str | Path,
) -> str:
    """
    Backwards-compatible full-document text extraction.
    """
    pages = extract_pages_from_pdf(pdf_path)

    return "\n".join(
        page
        for page in pages
        if page
    )
