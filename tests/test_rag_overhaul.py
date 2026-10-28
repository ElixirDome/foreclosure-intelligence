"""
Comprehensive test suite for RAG and Conversational Intelligence Overhaul:
1. Single-character ("h"), incomplete, and gibberish queries return guided clarification without retrieval.
2. Conversational greetings return polite introductions without querying the corpus.
3. Domain terminology queries (SARFAESI, EMD, Possession, Reserve Price) return authoritative legal definitions.
4. Follow-up queries without property context prompt the user for lot disambiguation.
5. Follow-up queries with property context resolve correctly.
6. Confidential OTS/settlement queries adhere to negative constraints.
7. Citation deduplication eliminates repeated documents and pages.
8. User-facing answers are devoid of internal pipeline labels or raw unformatted OCR dumps.
9. HTTP API /documents/rag endpoint integration.
"""

from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    Document,
    DocumentChunk,
    Evidence,
    MarketComparable,
    Property,
    PropertyDocument,
    User,
)
from app.services.analyst import process_analyst_turn
from app.services.query_understanding import (
    CLARIFICATION_PROMPT,
    GREETING_MESSAGE,
    QueryIntent,
    classify_query,
    is_gibberish,
)
from app.services.rag import answer_question


@pytest.fixture(autouse=True)
def seed_rag_test_data(db):
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(id=1, email="rag_overhaul@example.com", password_hash="hash", role="user")
        db.add(user)
        db.commit()

    prop = db.query(Property).filter(Property.id == 1).first()
    if not prop:
        prop = Property(
            id=1,
            user_id=1,
            address="Plot 42, Civil Lines, Pathankot",
            city="Pathankot",
            locality="Civil Lines",
            property_type="Residential Property",
            area_sqft=1500,
            reserve_price=3000000.0,
            opening_bid=3000000.0,
            emd=300000.0,
            auction_date=date(2026, 12, 10),
            foreclosure_status="scheduled",
        )
        db.add(prop)
    else:
        if not prop.emd:
            prop.emd = 300000.0
        if not prop.reserve_price:
            prop.reserve_price = 3000000.0
    db.commit()

    if db.query(MarketComparable).filter(MarketComparable.city == "Pathankot").count() < 3:
        for i, price in enumerate([2900000.0, 3100000.0, 3050000.0], start=1):
            db.add(MarketComparable(
                address=f"Comparable #{i}, Pathankot",
                city="Pathankot",
                locality="Civil Lines",
                property_type="Residential Property",
                area_sqft=1500,
                sale_price=price,
                sale_date=date(2026, 10, 1),
                source="Registrar",
                comparable_key=f"comp_rag_key_{i}",
            ))

    now = datetime.now(timezone.utc)
    doc = db.query(Document).filter(Document.id == 1).first()
    if not doc:
        doc = Document(
            id=1,
            title="ARMB Pathankot Auction Notice",
            source_name="PNB",
            source_url="https://www.pnb.bank.in/EAuction.aspx",
            document_type="auction_notice",
            extracted_text=(
                "SALE NOTICE FOR SALE OF IMMOVABLE PROPERTIES\n"
                "Authorised Officer of Punjab National Bank\n"
                "ARMB - PATHANKOT (Civil Lines, Pathankot)\n"
                "Reserve Price: Rs. 30,00,000/- EMD: Rs. 3,00,000/-\n"
                "Physical possession of property taken under Section 14 SARFAESI Act."
            ),
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(doc)
        db.add(DocumentChunk(
            document_id=1,
            chunk_index=0,
            page_number=1,
            text=(
                "SALE NOTICE FOR SALE OF IMMOVABLE PROPERTIES\n"
                "Reserve Price: Rs. 30,00,000/- EMD: Rs. 3,00,000/-\n"
                "Physical possession of property taken under Section 14 SARFAESI Act."
            ),
        ))
        db.add(PropertyDocument(property_id=1, document_id=1, relationship_type="primary_notice"))
    db.commit()


class TestQueryUnderstandingAndIntent:
    def test_single_character_query_h_returns_clarification(self, db):
        """User input 'h' must never dump raw OCR text; must return guided clarification."""
        res = process_analyst_turn(db, "h")
        assert res.intent == "ambiguous_clarification"
        assert CLARIFICATION_PROMPT in res.answer
        assert "Could you clarify what you'd like to know?" in res.answer
        assert len(res.citations) == 0
        assert res.structured is None
        assert any("/dashboard" in link["url"] for link in res.action_links)

    @pytest.mark.parametrize("query", ["a", "?", ".", "!", " ", "", "   "])
    def test_short_and_punctuation_queries(self, db, query):
        res = process_analyst_turn(db, query)
        assert res.intent == "ambiguous_clarification"
        assert CLARIFICATION_PROMPT in res.answer
        assert len(res.citations) == 0

    @pytest.mark.parametrize("gibberish", ["asdf", "qwerty", "zxcvb", "test", "!@#$%", "zzzzz"])
    def test_gibberish_queries_trigger_clarification(self, db, gibberish):
        res = process_analyst_turn(db, gibberish)
        assert res.intent == "ambiguous_clarification"
        assert CLARIFICATION_PROMPT in res.answer

    @pytest.mark.parametrize("greeting", [
        "hi", "hello", "hey", "good morning", "Hello!", "Hey there",
        "How are you?", "how are you doing", "how's it going?", "Hello, how are you?",
        "who are you", "what can you do?", "can you help me?",
    ])
    def test_greetings_return_polite_introduction(self, db, greeting):
        """Conversational greetings and check-ins bypass retrieval and return friendly guidance."""
        res = process_analyst_turn(db, greeting)
        assert res.intent == "greeting"
        assert "Foreclosure Research Analyst" in res.answer
        assert len(res.citations) == 0
        assert res.structured is None
        assert any("/dashboard" in link["url"] for link in res.action_links)

    def test_how_are_you_specifically_bypasses_retrieval(self, db):
        """Regression test: 'How are you?' must return conversational answer, not raw auction OCR."""
        res = process_analyst_turn(db, "How are you?")
        assert res.intent == "greeting"
        assert "I'm doing well, thank you!" in res.answer
        assert len(res.citations) == 0
        assert "Document Evidence Summary" not in res.answer
        assert "SALE NOTICE" not in res.answer


class TestDomainTerminology:
    def test_sarfaesi_terminology_explanation(self, db):
        res = process_analyst_turn(db, "What is SARFAESI?")
        assert res.intent == "terminology"
        assert "Securitisation and Reconstruction" in res.answer
        assert "Section 13" in res.answer
        assert len(res.citations) >= 1
        assert res.citations[0].kind == "statute"
        assert "SARFAESI Act" in res.citations[0].title

    def test_emd_terminology_explanation(self, db):
        res = process_analyst_turn(db, "What is EMD?")
        assert res.intent == "terminology"
        assert "Earnest Money Deposit" in res.answer
        assert "10%" in res.answer
        assert len(res.citations) >= 1

    def test_possession_terminology_distinction(self, db):
        res = process_analyst_turn(db, "What is symbolic possession vs physical possession?")
        assert res.intent == "terminology"
        assert "Symbolic" in res.answer
        assert "Physical" in res.answer
        assert "Section 13(4)" in res.answer
        assert "Section 14" in res.answer
        assert len(res.citations) >= 1

    def test_reserve_price_terminology_explanation(self, db):
        res = process_analyst_turn(db, "What is reserve price?")
        assert res.intent == "terminology"
        assert "minimum threshold" in res.answer.lower() or "reserve price" in res.answer.lower()
        assert len(res.citations) >= 1


class TestFollowUpStateResolution:
    def test_follow_up_missing_property_id_prompts_for_lot(self, db):
        """Questions like 'What about the EMD?' without context prompt the user."""
        res = process_analyst_turn(db, "What about the EMD?")
        assert res.intent == "follow_up"
        assert "specify which property lot" in res.answer.lower() or "lot" in res.answer.lower()
        assert any("/dashboard" in link["url"] for link in res.action_links)

    def test_follow_up_with_property_id_resolves_status(self, db):
        """Questions like 'What about the EMD?' with property_id=1 resolve Lot 1's details."""
        res = process_analyst_turn(db, "What about the EMD?", property_id=1)
        assert res.intent == "status_inquiry"
        assert "Earnest Money Deposit" in res.answer or "EMD" in res.answer
        assert any(term in res.answer for term in ["300,000", "250,000", "3,00,000", "2,50,000"])
        assert len(res.citations) >= 1


class TestConfidentialityGuardrail:
    def test_confidential_ots_request_refused(self, db):
        res = process_analyst_turn(db, "Can I get a private OTS compromise settlement on Lot #1?")
        assert res.intent == "confidential_refusal"
        assert "Confidential Banking Records Notice" in res.answer
        assert "Private Settlement & OTS Records Are Not Public" in res.answer
        assert len(res.citations) == 1
        assert res.citations[0].kind == "system"


class TestCitationDeduplicationAndPresentation:
    def test_duplicate_citations_are_eliminated(self, db):
        """Ensure identical (document_id, page_number) citations are deduplicated."""
        now = datetime.now(timezone.utc)
        doc2 = Document(
            id=2,
            title="Duplicate Notice Test",
            source_name="PNB",
            source_url="https://pnb.bank.in/dup.pdf",
            document_type="auction_notice",
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(doc2)
        # Add two chunks on page 1 of document 2
        db.add(DocumentChunk(document_id=2, chunk_index=0, page_number=1, text="Chunk A for Lot 1"))
        db.add(DocumentChunk(document_id=2, chunk_index=1, page_number=1, text="Chunk B for Lot 1"))
        db.commit()

        ans = answer_question(db, "Is property 1 a good investment?", property_id=1)
        # Verify no duplicate citations for doc2 page 1
        doc2_p1_citations = [c for c in ans.citations if c.document_id == 2 and c.page_number == 1]
        assert len(doc2_p1_citations) <= 1

    def test_synthesized_document_answer_does_not_leak_internal_labels(self, db):
        """Legacy or extractive answer must NOT contain internal labels like (score=0.35) or [Source: chunk=...]."""
        ans = answer_question(db, "What is the notice text?", mode="hybrid", multi_source=False)
        assert "(score=" not in ans.answer
        assert "chunk=" not in ans.answer
        assert "rrf_fused" not in ans.answer


class TestHTTPDocumentsRAGRoute:
    def test_http_rag_single_character_clarification(self):
        client = TestClient(app)
        resp = client.post("/documents/rag", json={"question": "h"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["question"] == "h"
        assert "Could you clarify what you'd like to know?" in data["answer"]
        assert data["method"] == "ambiguous_clarification"

    def test_http_rag_terminology_endpoint(self):
        client = TestClient(app)
        resp = client.post("/documents/rag", json={"question": "What is SARFAESI?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "SARFAESI" in data["answer"]
        assert data["method"] == "terminology"
        assert len(data["citations"]) >= 1

    def test_http_rag_how_are_you_greeting(self):
        client = TestClient(app)
        resp = client.post("/documents/rag", json={"question": "How are you?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "I'm doing well, thank you!" in data["answer"]
        assert data["method"] == "greeting"
        assert len(data["citations"]) == 2  # Action pills only (Explore, Connect)
        assert all(c["kind"] == "action" for c in data["citations"])
        assert data["chunks_used"] == 2
