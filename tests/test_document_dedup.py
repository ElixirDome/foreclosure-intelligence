from app.models import Document
from app.services.documents import get_or_create_document


def test_identical_document_content_is_deduplicated_across_sources(client, db):
    first, first_created = get_or_create_document(
        db,
        source_name="Bank A",
        source_url="https://bank-a.example/notice.pdf",
        document_type="auction_notice",
        content=b"identical auction notice",
        mime_type="application/pdf",
    )
    second, second_created = get_or_create_document(
        db,
        source_name="Bank B",
        source_url="https://bank-b.example/notice.pdf",
        document_type="auction_notice",
        content=b"identical auction notice",
        mime_type="application/pdf",
    )
    db.commit()

    assert first_created is True
    assert second_created is False
    assert first.id == second.id
    assert db.query(Document).count() == 1


def test_changed_notice_at_same_url_creates_new_document_version(client, db):
    first, first_created = get_or_create_document(
        db,
        source_name="Bank A",
        source_url="https://bank-a.example/notice.pdf",
        document_type="auction_notice",
        content=b"reserve price: 40 lakh",
        mime_type="application/pdf",
    )
    second, second_created = get_or_create_document(
        db,
        source_name="Bank A",
        source_url="https://bank-a.example/notice.pdf",
        document_type="auction_notice",
        content=b"revised reserve price: 35 lakh",
        mime_type="application/pdf",
    )
    db.commit()

    assert first_created is True
    assert second_created is True
    assert first.id != second.id
    assert db.query(Document).count() == 2
