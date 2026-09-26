from datetime import datetime

from app.database import SessionLocal
from app.models import Document


db = SessionLocal()

try:
    content = b"This is the exact same document content"

    import hashlib

    content_hash = hashlib.sha256(content).hexdigest()

    documents = []

    for i in range(2):
        document = (
            db.query(Document)
            .filter(Document.content_hash == content_hash)
            .first()
        )

        if document is None:
            document = Document(
                source_name="DedupTest",
                source_url="https://example.com/shared-auction-notice",
                document_type="auction_notice",
                title="Shared Auction Notice",
                content_hash=content_hash,
                fetched_at=datetime.utcnow(),
            )

            db.add(document)
            db.flush()

        documents.append(document)

    db.commit()

    print("DOCUMENT 1:", documents[0].id)
    print("DOCUMENT 2:", documents[1].id)
    print("SAME DOCUMENT:", documents[0].id == documents[1].id)

finally:
    db.close()