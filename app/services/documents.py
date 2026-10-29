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
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Document, DocumentChunk, Evidence


def compute_content_hash(content: bytes | str) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def chunk_pages(
    pages: list[str],
    *,
    max_chars: int = 512,
    overlap: int = 77,
) -> list[dict]:
    """
    Build standard chunks from page-aware text.
    Standardized to 512 characters with 15% overlap (~77 chars).
    Keeps page_number on every chunk for citation integrity.
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

        step = max(1, max_chars - overlap)
        pos = 0
        text_len = len(text)

        while pos < text_len:
            end = min(pos + max_chars, text_len)
            if end < text_len:
                # Look for sentence or whitespace boundary near the cut
                best_cut = -1
                for delim in ("\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " "):
                    cut = text.rfind(delim, pos + step // 2, end)
                    if cut != -1:
                        best_cut = cut + len(delim)
                        break
                if best_cut != -1:
                    end = best_cut

            piece = text[pos:end].strip()
            if piece:
                chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "page_number": page_number,
                        "text": piece,
                        "metadata_json": {
                            "strategy": "sliding_window_512",
                            "offset": pos,
                            "overlap": overlap,
                        },
                    }
                )
                chunk_index += 1

            if end >= text_len:
                break

            next_pos = max(pos + 1, end - overlap)
            if next_pos <= pos:
                next_pos = pos + step
            pos = next_pos

    return chunks


def chunk_plain_text(
    text: str,
    *,
    max_chars: int = 512,
    overlap: int = 77,
) -> list[dict]:
    """Chunk a single string of text with no page information."""
    if not text or not text.strip():
        return []
    return chunk_pages([text], max_chars=max_chars, overlap=overlap)


def canonicalize_source_url(source_url: str | None) -> str:
    """Normalize URL spelling without removing meaningful query parameters."""
    value = (source_url or "").strip()
    if not value:
        return ""
    parts = urlsplit(value)
    if not parts.scheme or not parts.netloc:
        return value.split("#", 1)[0]
    return urlunsplit((
        parts.scheme.lower(),
        parts.netloc.lower(),
        parts.path or "/",
        parts.query,
        "",
    ))


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

    Prefer a stable source identity (canonical URL + source + type + title)
    so a revised notice at the same link updates its existing row. Title is
    part of the identity because some portals serve many different PDFs from
    one generic POST-back URL. If no source identity matches, identical bytes
    can still be deduplicated across sources by content hash.
    """
    canonical_url = canonicalize_source_url(source_url)
    content_hash = compute_content_hash(content) if content is not None else None
    now = datetime.now(timezone.utc)

    document = None
    if canonical_url:
        # Compare canonicalized stored URLs too, so records created before
        # URL normalization (e.g. with fragments or uppercase hosts) are reused.
        candidates = (
            db.query(Document)
            .filter(
                Document.source_name == source_name,
                Document.document_type == document_type,
            )
            .order_by(Document.id.desc())
            .all()
        )
        for candidate in candidates:
            if (
                canonicalize_source_url(candidate.source_url) == canonical_url
                and candidate.title == title
            ):
                document = candidate
                break

    # Only use the global hash when there is no matching source identity.
    if document is None and content_hash:
        document = (
            db.query(Document)
            .filter(Document.content_hash == content_hash)
            .first()
        )

    if document is not None:
        old_hash = document.content_hash
        hash_owner = None
        if content_hash and content_hash != old_hash:
            hash_owner = (
                db.query(Document)
                .filter(
                    Document.content_hash == content_hash,
                    Document.id != document.id,
                )
                .first()
            )

        content_changed = bool(
            content_hash
            and content_hash != old_hash
            and (
                hash_owner is None
                or (
                    extracted_text is not None
                    and extracted_text != document.extracted_text
                )
            )
        )

        if content_changed:
            # Facts extracted from the old bytes are no longer trustworthy.
            # Remove them before chunks are rebuilt; full property ingestion
            # will write fresh evidence from the new notice.
            db.query(Evidence).filter(
                Evidence.document_id == document.id
            ).delete(synchronize_session=False)

        if content_hash and content_hash != old_hash:
            # content_hash is globally unique. If another row already owns
            # this hash, leave this source-identified row unhashed rather than
            # violating the constraint or changing its source identity.
            document.content_hash = None if hash_owner else content_hash

        document.source_url = canonical_url or document.source_url
        document.last_seen_at = now
        if title and not document.title:
            document.title = title
        if extracted_text and not document.extracted_text:
            document.extracted_text = extracted_text
        if filename and not document.filename:
            document.filename = filename
        if storage_path and not document.storage_path:
            document.storage_path = storage_path
        if mime_type and not document.mime_type:
            document.mime_type = mime_type
        # Transient signal consumed by ingest_document; it is not a DB column.
        document._ingested_content_changed = content_changed
        db.flush()
        return document, False

    if filename is None and storage_path:
        filename = Path(storage_path).name

    document = Document(
        source_name=source_name,
        source_url=canonical_url or source_url,
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
    try:
        with db.begin_nested():
            db.add(document)
            db.flush()
    except IntegrityError:
        if content_hash:
            duplicate = (
                db.query(Document)
                .filter(Document.content_hash == content_hash)
                .first()
            )
            if duplicate is not None:
                duplicate.last_seen_at = now
                db.flush()
                return duplicate, False
        raise

    document._ingested_content_changed = False
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
    # Flush pending document updates before bulk deletes, then expire stale
    # chunk objects so SQLite primary-key reuse cannot confuse the identity map.
    db.flush()
    old_chunk_ids = [
        row[0]
        for row in db.query(DocumentChunk.id)
        .filter(DocumentChunk.document_id == document.id)
        .all()
    ]
    # Evidence rows must survive manual rechunking, but old chunk references cannot.
    if old_chunk_ids:
        db.query(Evidence).filter(
            Evidence.document_chunk_id.in_(old_chunk_ids)
        ).update(
            {Evidence.document_chunk_id: None},
            synchronize_session="fetch",
        )
    db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document.id
    ).delete(synchronize_session="fetch")
    db.flush()
    db.expire_all()

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
    if full_text and (force or not document.extracted_text):
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
