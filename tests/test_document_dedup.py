from app.models import Document, DocumentChunk, Evidence, Property
from app.ingestion.document_ingest import ingest_document
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
    # Simulate an existing pre-normalization database row.
    first.source_url = "https://BANK-A.example/notice.pdf#page=1"
    db.commit()

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



def test_unchanged_reingestion_keeps_chunks_and_changed_content_rebuilds_them(client, db):
    payload = {
        "source_name": "Bank A",
        "source_url": "https://bank-a.example/notice.txt",
        "document_type": "auction_notice",
        "title": "Auction notice 123",
        "content": "Reserve price: 40 lakh",
        "mime_type": "text/plain",
    }

    first = ingest_document(db, payload, pages=["Reserve price: 40 lakh"])
    db.commit()
    document_id = first["document"].id
    first_chunk = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .one()
    )

    property_obj = Property(
        user_id=1,
        address="123 Test Road",
        property_key="test-document-dedup-property",
    )
    db.add(property_obj)
    db.flush()
    evidence = Evidence(
        property_id=property_obj.id,
        document_id=document_id,
        document_chunk_id=first_chunk.id,
        field="reserve_price",
        value="4000000",
        page_number=1,
        source_text="Reserve price: 40 lakh",
        extraction_method="test",
        confidence=0.9,
    )
    db.add(evidence)
    db.commit()

    unchanged = ingest_document(
        db,
        payload,
        pages=["Reserve price: 40 lakh"],
    )
    db.commit()
    unchanged_chunk = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .one()
    )
    assert unchanged["document"].id == document_id
    assert unchanged_chunk.id == first_chunk.id
    assert db.query(Evidence).count() == 1

    revised_payload = {
        **payload,
        "content": "Revised reserve price: 35 lakh",
    }
    revised = ingest_document(
        db,
        revised_payload,
        pages=["Revised reserve price: 35 lakh"],
    )
    db.commit()
    revised_chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .all()
    )

    assert revised["document"].id == document_id
    assert len(revised_chunks) == 1
    assert revised_chunks[0].text == "Revised reserve price: 35 lakh"
    # Old facts must not remain linked to a revised notice.
    assert db.query(Evidence).count() == 0



def test_pipeline_persists_document_when_property_extraction_fails(client, db):
    from app.ingestion.base import SourceAdapter, SourceDocument
    from app.ingestion.pipeline import run_ingestion

    class DocumentOnlyAdapter(SourceAdapter):
        def fetch(self):
            return [{"pages": ["A sale notice with no recognized property fields"]}]

        def extract(self, item):
            return None

        def get_documents(self, item):
            return [
                SourceDocument(
                    source_name="TestBank",
                    source_url="https://testbank.example/notice.txt",
                    document_type="auction_notice",
                    title="Unparsed notice",
                    content="A sale notice with no recognized property fields",
                    mime_type="text/plain",
                )
            ]

    result = run_ingestion(
        db=db,
        adapter=DocumentOnlyAdapter(),
        user_id=1,
    )

    assert "error" not in result
    assert result["items_extracted"] == 0
    assert result["documents_ingested_without_property"] == 1
    assert db.query(Document).count() == 1
    assert db.query(DocumentChunk).count() == 1
