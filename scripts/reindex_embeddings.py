"""Rebuild stored chunk vectors after the deterministic embedding change.

Run from the repository root:
    python -m scripts.reindex_embeddings
"""

from app.database import SessionLocal
from app.models import DocumentChunk
from app.services.embeddings import EMBEDDING_VERSION, embed_text


def main(batch_size: int = 500) -> int:
    db = SessionLocal()
    updated = 0
    last_id = 0
    try:
        while True:
            chunks = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.id > last_id)
                .order_by(DocumentChunk.id.asc())
                .limit(batch_size)
                .all()
            )
            if not chunks:
                break
            for chunk in chunks:
                metadata = dict(chunk.metadata_json or {})
                metadata["embedding"] = embed_text(chunk.text)
                metadata["embedding_version"] = EMBEDDING_VERSION
                chunk.metadata_json = metadata
                updated += 1
                last_id = chunk.id
            db.commit()
            print(f"Reindexed {updated} document chunks...")
        return updated
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    total = main()
    print(f"Completed. Reindexed {total} chunks to embedding version {EMBEDDING_VERSION}.")
