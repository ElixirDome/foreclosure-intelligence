"""
Document + chunk helpers for Phase 1 architecture.

The document is the source of truth. Chunks are the unit of retrieval.
Property extraction and evidence linking come later; this module only
persists documents and builds chunks from text.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk


def compute_content_hash(content: bytes | str) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def chunk_pages(
    pages: list[str],
    *,
    max_chars: int = 1800,
) -> list[dict]:
    """
    Build chunks from page-aware text.

    Strategy (Phase 1 — no vectors yet):
    - Prefer one chunk per page when the page is short enough.
    - Split long pages on blank lines / paragraph boundaries.
    - Keep page_number on every chunk for citation.
    """
    chunks: list[dict] = []
    chunk_index = 0

    for page_number, page_text in enumerate(pages, start=1):
        text = (page_text or "").strip()
        if not text:
            continue

        if len(text) <= max_chars:
            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "page_number": page_number,
                    "text": text,
                    "metadata_json": {"strategy": "whole_page"},
                }
            )
            chunk_index += 1
            continue

        # Split long pages into paragraph-sized pieces.
        paragraphs = re.split(r"\n\s*\n", text)
        buffer = ""

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph

            if len(candidate) <= max_chars:
                buffer = candidate
                continue

            if buffer:
                chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "page_number": page_number,
                        "text": buffer,
                        "metadata_json": {"strategy": "paragraph_split"},
                    }
                )
                chunk_index += 1

            # Paragraph itself may still exceed max_chars.
            if len(paragraph) <= max_chars:
                buffer = paragraph
            else:
                for start in range(0, len(paragraph), max_chars):
                    piece = paragraph[start : start + max_chars].strip()
                    if not piece:
                        continue
                    chunks.append(
                        {
                            "chunk_index": chunk_index,
                            "page_number": page_number,
                            "text": piece,
                            "metadata_json": {
                                "strategy": "hard_split",
                                "offset": start,
                            },
                        }
                    )
                    chunk_index += 1
                buffer = ""

        if buffer:
            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "page_number": page_number,
                    "text": buffer,
                    "metadata_json": {"strategy": "paragraph_split"},
                }
            )
            chunk_index += 1

    return chunks


def chunk_plain_text(
    text: str,
    *,
    max_chars: int = 1800,
) -> list[dict]:
    """Chunk a single string of text with no page information."""
    if not text or not text.strip():
        return []
    return chunk_pages([text], max_chars=max_chars)


def get_or_create_document(
    db: Session,
    *,
    source_name: str,
    source_url: str,
    document_type: str,
    content: bytes | str | None = None,
    title: str | None = None,
    filename: str | None = None,
    mime_type: str | None = None,
    storage_path: str | None = None,
    extracted_text: str | None = None,
) -> tuple[Document, bool]:
    """
    Return (document, created).

    Deduplicates on content_hash when content is provided.
    """
    content_hash = None
    if content is not None:
        content_hash = compute_content_hash(content)

    now = datetime.now(timezone.utc)

    document = None
    if content_hash:
        document = (
            db.query(Document)
            .filter(Document.content_hash == content_hash)
            .first()
        )

    if document is not None:
        document.last_seen_at = now
        if extracted_text and not document.extracted_text:
            document.extracted_text = extracted_text
        if filename and not document.filename:
            document.filename = filename
        if storage_path and not document.storage_path:
            document.storage_path = storage_path
        if mime_type and not document.mime_type:
            document.mime_type = mime_type
        db.flush()
        return document, False

    if filename is None and storage_path:
        filename = Path(storage_path).name

    document = Document(
        source_name=source_name,
        source_url=source_url,
        document_type=document_type,
        title=title,
        filename=filename,
        mime_type=mime_type,
        storage_path=storage_path,
        extracted_text=extracted_text,
        content_hash=content_hash,
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(document)
    db.flush()
    return document, True


def replace_document_chunks(
    db: Session,
    document: Document,
    chunks: list[dict],
) -> list[DocumentChunk]:
    """
    Replace all chunks for a document.

    Safe for re-ingestion of the same PDF: old chunks are removed and
    new ones written in chunk_index order.
    """
    db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document.id
    ).delete(synchronize_session=False)

    from app.services.embeddings import embed_text

    created: list[DocumentChunk] = []
    for item in chunks:
        meta = dict(item.get("metadata_json") or {})
        meta["embedding"] = embed_text(item["text"])
        chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=item["chunk_index"],
            page_number=item.get("page_number"),
            text=item["text"],
            metadata_json=meta,
        )
        db.add(chunk)
        created.append(chunk)

    db.flush()
    return created


def ensure_document_chunks_from_pages(
    db: Session,
    document: Document,
    pages: list[str],
    *,
    force: bool = False,
) -> list[DocumentChunk]:
    """
    Persist extracted_text + chunks from page list.

    Skips if chunks already exist unless force=True.
    """
    full_text = "\n\n".join(p.strip() for p in pages if p and p.strip())
    if full_text and not document.extracted_text:
        document.extracted_text = full_text

    existing = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .count()
    )
    if existing and not force:
        return (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.chunk_index)
            .all()
        )

    chunks = chunk_pages(pages)
    return replace_document_chunks(db, document, chunks)
