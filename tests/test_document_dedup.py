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


def test_changed_notice_at_same_url_updates_existing_document(client, db):
    first, first_created = get_or_create_document(
        db,
        source_name="Bank A",
        source_url="https://bank-a.example/notice.pdf",
        document_type="auction_notice",
        title="Auction notice 123",
        content=b"reserve price: 40 lakh",
        mime_type="application/pdf",
    )
    original_hash = first.content_hash

    second, second_created = get_or_create_document(
        db,
        source_name="Bank A",
        source_url="https://bank-a.example/notice.pdf",
        document_type="auction_notice",
        title="Auction notice 123",
        content=b"revised reserve price: 35 lakh",
        mime_type="application/pdf",
    )
    db.commit()

    assert first_created is True
    assert second_created is False
    assert first.id == second.id
    assert second.content_hash != original_hash
    assert db.query(Document).count() == 1


def test_same_generic_url_keeps_different_notice_titles_separate(client, db):
    first, first_created = get_or_create_document(
        db,
        source_name="PNB",
        source_url="https://pnb.example/EAuction.aspx",
        document_type="auction_notice",
        title="Auction notice A",
        content=b"notice A",
    )
    second, second_created = get_or_create_document(
        db,
        source_name="PNB",
        source_url="https://pnb.example/EAuction.aspx",
        document_type="auction_notice",
        title="Auction notice B",
        content=b"notice B",
    )
    db.commit()

    assert first_created is True
    assert second_created is True
    assert first.id != second.id
    assert db.query(Document).count() == 2


def test_source_url_fragment_does_not_create_duplicate(client, db):
    first, first_created = get_or_create_document(
        db,
        source_name="Bank A",
        source_url="https://bank-a.example/notice.pdf#page=1",
        document_type="auction_notice",
        title="Auction notice 123",
        content=b"same notice",
    )
    second, second_created = get_or_create_document(
        db,
        source_name="Bank A",
        source_url="https://BANK-A.example/notice.pdf#page=2",
        document_type="auction_notice",
        title="Auction notice 123",
        content=b"same notice",
    )
    db.commit()

    assert first_created is True
    assert second_created is False
    assert first.id == second.id
    assert second.source_url == "https://bank-a.example/notice.pdf"
    assert db.query(Document).count() == 1
