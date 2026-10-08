"""
Universal document ingestion (Phase 2).

Flow:
    Any source payload
        → Document (deduped by content_hash)
        → text extraction (PDF pages / plain text / pre-supplied text)
        → DocumentChunk[]

Source adapters decide *where* the document comes from.
This module decides *how* it is stored and chunked.
Property parsing is intentionally out of scope here.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.ingestion.base import SourceDocument
from app.models import Document
from app.services.documents import (
    ensure_document_chunks_from_pages,
    get_or_create_document,
)
from app.services.pdf import extract_pages_from_pdf


def _as_source_document(raw: SourceDocument | dict[str, Any]) -> SourceDocument:
    if isinstance(raw, SourceDocument):
        return raw

    return SourceDocument(
        source_name=raw["source_name"],
        source_url=raw["source_url"],
        document_type=raw["document_type"],
        content=raw.get("content", b""),
        title=raw.get("title"),
        filename=raw.get("filename"),
        mime_type=raw.get("mime_type"),
        storage_path=raw.get("storage_path"),
    )


def _infer_mime_type(doc: SourceDocument) -> str | None:
    if doc.mime_type:
        return doc.mime_type

    name = (doc.filename or doc.storage_path or doc.source_url or "").lower()
    if name.endswith(".pdf"):
        return "application/pdf"
    if name.endswith((".html", ".htm")):
        return "text/html"
    if name.endswith(".txt"):
        return "text/plain"
    if isinstance(doc.content, str):
        return "text/plain"
    return None


def extract_pages_from_source(
    doc: SourceDocument,
) -> list[str]:
    """
    Normalize any document payload into a list of page texts.

    Supports:
    - local PDF path (storage_path or source_url file path)
    - PDF bytes in content
    - plain string content (single "page")
    """
    # Explicit text content
    if isinstance(doc.content, str) and doc.content.strip():
        return [doc.content]

    mime = _infer_mime_type(doc) or ""

    # Local file path
    path_candidates: list[Path] = []
    if doc.storage_path:
        path_candidates.append(Path(doc.storage_path))
    if doc.source_url and not doc.source_url.startswith("http"):
        path_candidates.append(Path(doc.source_url))

    for path in path_candidates:
        if path.exists() and path.is_file():
            if path.suffix.lower() == ".pdf" or "pdf" in mime:
                return extract_pages_from_pdf(path)
            try:
                return [path.read_text(encoding="utf-8", errors="ignore")]
            except Exception:
                pass

    # PDF bytes in memory
    if isinstance(doc.content, (bytes, bytearray)) and doc.content:
        if "pdf" in mime or doc.content[:4] == b"%PDF":
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
                tmp.write(doc.content)
                tmp.flush()
                return extract_pages_from_pdf(tmp.name)
        # Treat other binary as opaque — no text pages yet (OCR later)
        return []

    return []


def ingest_document(
    db: Session,
    raw: SourceDocument | dict[str, Any],
    *,
    pages: list[str] | None = None,
    force_rechunk: bool = False,
) -> dict[str, Any]:
    """
    Persist a document and its chunks.

    Returns:
        {
            "document": Document,
            "created": bool,
            "pages": list[str],
            "chunk_count": int,
        }
    """
    source = _as_source_document(raw)

    if pages is None:
        pages = extract_pages_from_source(source)

    extracted_text = "\n\n".join(
        p.strip() for p in pages if p and p.strip()
    ) or None

    document, created = get_or_create_document(
        db,
        source_name=source.source_name,
        source_url=source.source_url,
        document_type=source.document_type,
        content=source.content if source.content not in (None, b"", "") else None,
        title=source.title,
        filename=source.filename,
        mime_type=_infer_mime_type(source),
        storage_path=source.storage_path,
        extracted_text=extracted_text,
    )

    chunks = []
    if pages:
        chunks = ensure_document_chunks_from_pages(
            db,
            document,
            pages,
            force=force_rechunk,
        )

    return {
        "document": document,
        "created": created,
        "pages": pages,
        "chunk_count": len(chunks),
    }


def ingest_documents(
    db: Session,
    raw_docs: list[SourceDocument | dict[str, Any]],
    *,
    force_rechunk: bool = False,
) -> list[dict[str, Any]]:
    """Ingest many documents; returns one result dict per input."""
    results = []
    for raw in raw_docs:
        results.append(
            ingest_document(
                db,
                raw,
                force_rechunk=force_rechunk,
            )
        )
    return results
