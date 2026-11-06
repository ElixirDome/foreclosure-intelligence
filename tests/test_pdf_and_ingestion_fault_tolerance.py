import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from pypdf.errors import LimitReachedError, PdfReadError

from app.ingestion.base import SourceAdapter
from app.ingestion.document_ingest import ingest_document, ingest_documents
from app.ingestion.pipeline import run_ingestion
from app.ingestion.pnb_source import PNBSourceAdapter
from app.ingestion.save import save_ingested_properties
from app.models import Document, DocumentChunk, IngestionRun, Property, PropertyDocument, User
from app.services.live_events import broker
from app.services.pdf import (
    extract_pages_from_pdf,
    extract_pages_with_ocr,
    is_text_usable,
)


@pytest.fixture(autouse=True)
def setup_user(db):
    broker._recent_events.clear()
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(id=1, email="fault_test@example.com", password_hash="hash", role="user")
        db.add(user)
        db.commit()
    yield
    broker._recent_events.clear()


# =====================================================================
# 1. PDF Parsing Failure & LimitReachedError Isolation
# =====================================================================

def test_limit_reached_error_isolated_to_page():
    """LimitReachedError on page 1 should not crash extraction of subsequent pages."""
    mock_page1 = MagicMock()
    mock_page1.extract_text.side_effect = LimitReachedError("Recursion limit in content stream exceeded")

    mock_page2 = MagicMock()
    mock_page2.extract_text.return_value = "Page 2 text with valid reserve price Rs 25,00,000 and EMD Rs 2,50,000."

    mock_reader = MagicMock()
    mock_reader.pages = [mock_page1, mock_page2]

    with patch("app.services.pdf.PdfReader", return_value=mock_reader), \
         patch("app.services.pdf.ocr_single_page", return_value="OCR recovered page 1 content."):
        pages = extract_pages_from_pdf("dummy.pdf", enable_ocr_fallback=True)

    assert len(pages) == 2
    assert "OCR recovered page 1" in pages[0]
    assert "Page 2 text" in pages[1]


def test_pdf_reader_init_failure_triggers_ocr():
    """If PdfReader fails entirely (e.g. corrupted PDF header), fallback to OCR."""
    with patch("app.services.pdf.PdfReader", side_effect=PdfReadError("Corrupted EOF marker")), \
         patch("app.services.pdf.extract_pages_with_ocr", return_value=["OCR extracted full page 1"]):
        pages = extract_pages_from_pdf("corrupt.pdf", enable_ocr_fallback=True)

    assert len(pages) == 1
    assert "OCR extracted full page 1" in pages[0]


# =====================================================================
# 2. OCR Fallback Triggering & Unusable Text Detection
# =====================================================================

def test_unusable_text_detection():
    """is_text_usable correctly identifies empty, CID-corrupted, or garbled text."""
    # Empty or very short
    assert is_text_usable("") is False
    assert is_text_usable("short text") is False

    # Broken CID fonts
    cid_garbage = "Notice " + " (cid:120) (cid:121) (cid:122)" * 5
    assert is_text_usable(cid_garbage) is False

    # Excessive unicode replacement chars
    replacement_garbage = "Auction " + "\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd"
    assert is_text_usable(replacement_garbage) is False

    # Valid text
    valid_notice = (
        "SALE NOTICE FOR SALE OF IMMOVABLE PROPERTIES. "
        "E-Auction Sale Notice for Sale of Immovable Assets under SARFAESI Act, 2002. "
        "Reserve Price: Rs. 45,00,000/-. Earnest Money Deposit: Rs. 4,50,000/-. "
        "Property situated at Flat No 204, Royal Palms, Model Town, Pathankot."
    )
    assert is_text_usable(valid_notice) is True


def test_ocr_fallback_when_native_text_is_unusable():
    """When native pages contain only unusable text, extract_pages_from_pdf calls OCR."""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "scan "  # unusable short text

    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    ocr_recovered = [
        "SALE NOTICE FOR SALE OF IMMOVABLE PROPERTIES. "
        "Reserve Price: Rs. 35,00,000/-. EMD: Rs. 3,50,000/-. "
        "Auction date: 20/12/2026. Property at Civil Lines, Gurdaspur."
    ]

    with patch("app.services.pdf.PdfReader", return_value=mock_reader), \
         patch("app.services.pdf.extract_pages_with_ocr", return_value=ocr_recovered):
        pages = extract_pages_from_pdf("scanned.pdf", enable_ocr_fallback=True)

    assert pages == ocr_recovered
    assert "Reserve Price: Rs. 35,00,000" in pages[0]


def test_pnb_adapter_caches_ocr_and_avoids_duplicate_extraction():
    """PNBSourceAdapter must cache extracted text and not run extraction/OCR again in get_evidence."""
    from tests.test_pnb_extraction import _get_armb_sample_path
    sample_text = _get_armb_sample_path().read_text(encoding="utf-8")
    adapter = PNBSourceAdapter()
    sample_pages = [sample_text]

    item = {
        "title": "PNB Auction Notice",
        "source_url": "https://pnb.example.com/notice.pdf",
        "pdf_path": Path("fake_notice.pdf"),
    }

    with patch("app.ingestion.pnb_source.extract_pages_from_pdf", return_value=sample_pages) as mock_extract:
        # First call: extract
        props = adapter.extract(item)
        assert props is not None
        assert len(props) >= 1
        assert mock_extract.call_count == 1

        # Second call: get_evidence (must reuse cached _extracted_text without calling extract_pages_from_pdf)
        evidence = adapter.get_evidence(item)
        assert len(evidence) >= 1
        assert mock_extract.call_count == 1  # Still 1, NOT called again!

        # Third call: get_documents (must include pages and extracted_text)
        docs = adapter.get_documents(item)
        assert len(docs) == 1
        assert docs[0]["pages"] == sample_pages
        assert "Tugalwal" in docs[0]["extracted_text"]


# =====================================================================
# 3. Correct Document-to-Text Association
# =====================================================================

def test_documents_receive_their_own_distinct_pages(db):
    """Multiple documents attached to a property must each receive their own pages."""
    item = {
        "property": {
            "address": "Distinct Notice House, Gurdaspur",
            "city": "Gurdaspur",
            "reserve_price": 4000000.0,
            "property_type": "Residential Property",
        },
        "pages": ["Item fallback pages that should not be forced on multi-docs"],
        "documents": [
            {
                "source_name": "BankNoticeA",
                "source_url": "https://bank.example.com/docA.pdf",
                "document_type": "auction_notice",
                "title": "Document A Notice",
                "pages": ["Text for Document A Page 1", "Text for Document A Page 2"],
            },
            {
                "source_name": "BankNoticeB",
                "source_url": "https://bank.example.com/docB.pdf",
                "document_type": "title_deed",
                "title": "Document B Annexure",
                "pages": ["Text for Document B Page 1 - Boundary Details"],
            },
        ],
    }

    result = save_ingested_properties(
        db=db,
        properties=[item],
        user_id=1,
        ingestion_run_id=1,
    )

    assert len(result["saved"]) == 1
    prop_id = result["saved"][0].id

    # Retrieve both documents
    pdocs = db.query(PropertyDocument).filter(PropertyDocument.property_id == prop_id).all()
    assert len(pdocs) == 2

    docA = db.query(Document).filter(Document.id == pdocs[0].document_id).first()
    docB = db.query(Document).filter(Document.id == pdocs[1].document_id).first()

    # Ensure document A has Document A's chunks and NOT Document B's
    chunksA = db.query(DocumentChunk).filter(DocumentChunk.document_id == docA.id).all()
    textA = " ".join(c.text for c in chunksA)
    assert "Document A Page 1" in textA or "Document A Page 2" in textA
    assert "Document B Page 1" not in textA

    # Ensure document B has Document B's chunks and NOT Document A's
    chunksB = db.query(DocumentChunk).filter(DocumentChunk.document_id == docB.id).all()
    textB = " ".join(c.text for c in chunksB)
    assert "Document B Page 1" in textB
    assert "Document A Page" not in textB


# =====================================================================
# 4. Fault-Tolerant Ingestion: Failure Isolation & Status
# =====================================================================

def test_failed_document_does_not_abort_batch(db):
    """If one document fails during ingestion, remaining documents and the property are saved."""
    item = {
        "property": {
            "address": "Partially Valid Doc Villa, Gurdaspur",
            "city": "Gurdaspur",
            "reserve_price": 3000000.0,
            "property_type": "Residential Property",
        },
        "documents": [
            {
                "source_name": "ValidDoc",
                "source_url": "https://bank.example.com/valid.pdf",
                "document_type": "auction_notice",
                "title": "Valid Notice",
                "pages": ["Valid Notice Content on Page 1"],
            },
            {
                # Intentionally corrupted document payload with invalid content type causing failure
                "source_name": None,  # NOT NULL constraint will fail
                "source_url": None,
                "document_type": "invalid",
            },
        ],
    }

    result = save_ingested_properties(
        db=db,
        properties=[item],
        user_id=1,
        ingestion_run_id=1,
    )

    # Property was still saved successfully
    assert len(result["saved"]) == 1
    # Document failure was recorded
    assert len(result.get("failed_documents", [])) == 1

    # Valid document was persisted
    valid_doc = db.query(Document).filter(Document.title == "Valid Notice").first()
    assert valid_doc is not None


class FlakyBatchAdapter(SourceAdapter):
    """Adapter with 1 successful item and 1 item that fails property extraction."""
    def fetch(self):
        return [
            {"id": "item1", "title": "Good Notice"},
            {"id": "item2", "title": "Failing Notice"},
        ]

    def extract(self, item):
        if item["id"] == "item2":
            raise ValueError("Corrupt PDF stream encountered in item 2")
        return [{
            "address": "House 10, Good Colony, Gurdaspur",
            "city": "Gurdaspur",
            "reserve_price": 2000000.0,
            "property_type": "Residential Property",
        }]

    def get_documents(self, item):
        return [{
            "source_name": "Bank",
            "source_url": f"https://bank.example.com/{item['id']}",
            "document_type": "auction_notice",
            "title": item["title"],
            "pages": [f"Text for {item['title']}"],
        }]


def test_pipeline_records_partial_success_on_extraction_error(db):
    """Extraction error on item 2 should result in partial_success, not failed or unrecorded."""
    adapter = FlakyBatchAdapter()
    run_ingestion(db, adapter, user_id=1)

    ingestion_run = db.query(IngestionRun).order_by(IngestionRun.id.desc()).first()
    assert ingestion_run is not None
    # Must be partial_success, not full success or total crash
    assert ingestion_run.status == "partial_success"
    assert "Corrupt PDF stream encountered" in ingestion_run.error_message
    assert ingestion_run.items_created == 1
