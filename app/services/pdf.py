"""
PDF Text Extraction Service.

Provides robust, fault-tolerant PDF page extraction combining pypdf native parsing
with automatic OCR fallback (pdf2image + pytesseract) when native streams fail,
exceed recursion limits (LimitReachedError), or contain unmapped/broken fonts.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import LimitReachedError, PdfReadError, PyPdfError

logger = logging.getLogger(__name__)


def get_poppler_path() -> str | None:
    """Resolve poppler binary directory from environment or standard locations."""
    configured = os.getenv("POPPLER_PATH")
    if configured and os.path.isdir(configured):
        return configured

    # Standard Windows fallback if installed in development path
    default_poppler = Path(r"C:\Dev\poppler-26.09.0\Library\bin")
    if default_poppler.is_dir():
        return str(default_poppler)

    return None


def is_text_usable(text: str) -> bool:
    """
    Validate that extracted text represents readable domain content rather than
    empty scans, raw binary noise, or unmapped CID font replacement artifacts.
    """
    if not text or not text.strip():
        return False

    stripped = text.strip()
    if len(stripped) < 100:
        return False

    visible = [char for char in stripped if not char.isspace()]
    if not visible:
        return False

    # Check alphanumeric ratio
    alnum_count = sum(char.isalnum() for char in visible)
    if alnum_count / len(visible) < 0.35:
        return False

    # Check Unicode replacement character count
    if text.count("\ufffd") >= 5:
        return False

    # Check unmapped CID font artifacts like (cid:135)
    cid_count = len(re.findall(r"\(cid:\d+\)", text, re.IGNORECASE))
    if cid_count >= 8:
        return False

    return True


def extract_pages_with_ocr(
    pdf_path: str | Path,
    first_page: int | None = None,
    last_page: int | None = None,
) -> list[str]:
    """
    Render PDF pages to images and extract text using pytesseract OCR.
    Safely degrades if poppler or pytesseract is unavailable.
    """
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError as exc:
        logger.warning("OCR libraries (pdf2image or pytesseract) not available: %s", exc)
        return []

    poppler_dir = get_poppler_path()
    kwargs: dict = {"dpi": 200}
    if poppler_dir:
        kwargs["poppler_path"] = poppler_dir
    if first_page is not None:
        kwargs["first_page"] = first_page
    if last_page is not None:
        kwargs["last_page"] = last_page

    try:
        images = convert_from_path(str(pdf_path), **kwargs)
        pages: list[str] = []
        for img in images:
            text = pytesseract.image_to_string(img) or ""
            pages.append(text)
        return pages
    except Exception as exc:
        logger.warning(
            "OCR page rendering failed for %s (pages %s-%s): %s",
            pdf_path, first_page, last_page, exc,
        )
        return []


def ocr_single_page(pdf_path: str | Path, page_number: int) -> str:
    """Run OCR on a single 1-based page number."""
    pages = extract_pages_with_ocr(
        pdf_path,
        first_page=page_number,
        last_page=page_number,
    )
    return pages[0] if pages else ""


def extract_pages_from_pdf(
    pdf_path: str | Path,
    enable_ocr_fallback: bool = True,
) -> list[str]:
    """
    Extract PDF text while preserving page boundaries.
    Page numbers are represented by list index: index 0 = page 1, index 1 = page 2, etc.

    Fault-tolerant features:
    - Handles pypdf LimitReachedError on oversized or cyclic content streams.
    - Isolates page-level failures so one broken page does not fail the document.
    - Automatically falls back to OCR if native text is absent, unmapped, or corrupted.
    """
    pages: list[str] = []
    reader = None

    try:
        reader = PdfReader(str(pdf_path))
    except (LimitReachedError, PdfReadError, PyPdfError, Exception) as exc:
        logger.warning(
            "pypdf reader initialization failed for %s (%s: %s); attempting OCR fallback",
            pdf_path, type(exc).__name__, exc,
        )
        if enable_ocr_fallback:
            ocr_pages = extract_pages_with_ocr(pdf_path)
            if ocr_pages:
                return ocr_pages
        raise

    for page_idx, page in enumerate(reader.pages, start=1):
        page_text = ""
        try:
            page_text = page.extract_text() or ""
        except LimitReachedError as exc:
            logger.warning(
                "pypdf LimitReachedError on page %d of %s: %s; falling back to page OCR",
                page_idx, pdf_path, exc,
            )
            if enable_ocr_fallback:
                page_text = ocr_single_page(pdf_path, page_idx)
        except (PdfReadError, PyPdfError, Exception) as exc:
            logger.warning(
                "pypdf extraction error on page %d of %s (%s: %s); falling back to page OCR",
                page_idx, pdf_path, type(exc).__name__, exc,
            )
            if enable_ocr_fallback:
                page_text = ocr_single_page(pdf_path, page_idx)

        pages.append(page_text)

    # Check overall document usability
    combined_text = "\n".join(pages)
    if enable_ocr_fallback and not is_text_usable(combined_text):
        logger.info(
            "Native text extraction for %s produced unusable content (length=%d); attempting document OCR",
            pdf_path, len(combined_text.strip()),
        )
        ocr_pages = extract_pages_with_ocr(pdf_path)
        if ocr_pages and (
            is_text_usable("\n".join(ocr_pages))
            or sum(len(p.strip()) for p in ocr_pages) > sum(len(p.strip()) for p in pages)
        ):
            logger.info("OCR successfully recovered %d pages for %s", len(ocr_pages), pdf_path)
            return ocr_pages

    return pages


def extract_text_from_pdf(
    pdf_path: str | Path,
    enable_ocr_fallback: bool = True,
) -> str:
    """
    Backwards-compatible full-document text extraction.
    """
    pages = extract_pages_from_pdf(pdf_path, enable_ocr_fallback=enable_ocr_fallback)

    return "\n".join(
        page
        for page in pages
        if page
    )
