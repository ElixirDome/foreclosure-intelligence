import os
from datetime import date, datetime, timezone
from unittest.mock import patch
import pytest

from app.models import (
    Document,
    DocumentChunk,
    Evidence,
    MarketComparable,
    Property,
    PropertyDocument,
    User,
)
from app.schemas import PropertyAIAnalysis
from app.services import embeddings
from app.services.analyst import process_analyst_turn
from app.services.llm import GeminiProvider, LocalLLMProvider


@pytest.fixture(autouse=True)
def setup_discovery_and_validity_data(db):
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(id=1, email="test_analyst@example.com", password_hash="hash", role="user")
        db.add(user)
        db.commit()

    # Property 1: In Gurdaspur (Punjab) with 95% OCR evidence, 10% EMD, symbolic possession
    prop1 = db.query(Property).filter(Property.id == 1).first()
    if not prop1:
        prop1 = Property(
            id=1,
            user_id=1,
            address="Village Tugalwal HB No 533, Gurdaspur",
            city="Gurdaspur",
            state="Punjab",
            property_type="Residential Property",
            area_sqft=1200,
            reserve_price=2500000.0,
            opening_bid=2500000.0,
            emd=250000.0,
            auction_date=date(2026, 12, 1),
            foreclosure_status="scheduled",
            possession_type="symbolic",
        )
        db.add(prop1)

        # Add 3 comparables in Gurdaspur to satisfy min_comparables for valuation
        for i, price in enumerate([2400000.0, 2600000.0, 2550000.0], start=1):
            db.add(MarketComparable(
                address=f"Comparable #{i}, Gurdaspur",
                city="Gurdaspur",
                locality="Tehsil",
                property_type="Residential Property",
                area_sqft=1200,
                sale_price=price,
                sale_date=date(2026, 9, 1),
                source="Registrar",
                comparable_key=f"comp_key_val_{i}",
            ))

        doc = Document(
            id=1,
            title="ARMB Pathankot Official Sale Notice",
            source_name="PNB",
            source_url="https://www.pnb.bank.in/EAuction.aspx",
            document_type="auction_notice",
            extracted_text="SALE NOTICE FOR SALE OF IMMOVABLE PROPERTIES. Reserve Price: Rs. 25,00,000/-, EMD: Rs. 2,50,000/-. Symbolic Possession.",
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(doc)
        db.add(DocumentChunk(
            document_id=1,
            chunk_index=0,
            page_number=1,
            text="Reserve Price: Rs. 25,00,000/-, EMD: Rs. 2,50,000/-. Symbolic Possession under Section 13(4).",
        ))
        db.add(PropertyDocument(property_id=1, document_id=1, relationship_type="primary_notice"))
        db.add(Evidence(
            property_id=1,
            field="reserve_price",
            value="25,00,000",
            source_text="Reserve Price: Rs. 25,00,000/-",
            document_id=1,
            page_number=1,
            extraction_method="regex",
            confidence=0.95,
        ))
        db.add(Evidence(
            property_id=1,
            field="emd",
            value="2,50,000",
            source_text="EMD: Rs. 2,50,000/-",
            document_id=1,
            page_number=1,
            extraction_method="regex",
            confidence=0.92,
        ))
        db.commit()


def test_discovery_best_property_in_state(db):
    """'what's the best property in Punjab?' routes to discovery and surfaces top curated deal."""
    res = process_analyst_turn(db, "what's the best property in Punjab?")
    assert res.intent == "inventory_discovery"
    assert "Top Curated Auction Deals" in res.answer
    assert "Punjab" in res.answer or "Gurdaspur" in res.answer
    assert "Lot #1" in res.answer
    assert "Reserve:" in res.answer
    assert "₹2,500,000" in res.answer
    assert any("/properties/1" in link["url"] for link in res.action_links)


def test_discovery_best_property_in_city(db):
    """'what is the best property in Gurdaspur?' filters by city and returns deal scoring."""
    res = process_analyst_turn(db, "what is the best property in Gurdaspur?")
    assert res.intent == "inventory_discovery"
    assert "Gurdaspur" in res.answer
    assert "Lot #1" in res.answer
    assert any(c.property_id == 1 for c in res.citations)


def test_discovery_cheapest_property_in_area(db):
    """'cheapest property in Punjab' ranks lots by reserve price."""
    res = process_analyst_turn(db, "cheapest property in Punjab")
    assert res.intent == "inventory_discovery"
    assert "Lot #1" in res.answer


def test_validity_verification_with_property_context(db):
    """'are the details valid?' with property context runs OCR confidence and SARFAESI checks."""
    res = process_analyst_turn(db, "are the details valid?", property_id=1)
    assert res.intent == "validity_verification"
    assert "Detail Validity & Verification Audit for Lot #1" in res.answer
    # 95% OCR confidence
    assert "95%" in res.answer or "Verified" in res.answer
    # 10% statutory EMD
    assert "Statutory Compliant" in res.answer or "10%" in res.answer
    # SARFAESI Symbolic possession risk
    assert "Symbolic Possession" in res.answer or "Section 13(4)" in res.answer
    # Document citation
    assert "ARMB Pathankot" in res.answer or "PNB" in res.answer
    assert len(res.citations) >= 2
    assert any("/documents/1/file" in link["url"] for link in res.action_links)


def test_validity_verification_safe_to_bid(db):
    """'is this property safe to bid on?' identifies possession and due-diligence risks."""
    res = process_analyst_turn(db, "is this property safe to bid on?", property_id=1)
    assert res.intent == "validity_verification"
    assert "Symbolic Possession" in res.answer or "Legal Possession Status" in res.answer
    assert "Lot #1" in res.answer


def test_validity_verification_without_property_context(db):
    """'are the details valid?' without property_id prompts user to specify the lot."""
    res = process_analyst_turn(db, "are the details valid?")
    assert res.intent == "follow_up"
    assert "specify the property lot" in res.answer.lower()
    assert any("/dashboard" in link["url"] for link in res.action_links)


def test_nomic_embed_task_prefixing(monkeypatch):
    """Nomic embedding model applies search_document: and search_query: prefixes."""
    recorded_inputs = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embeddings": [[1.0, 0.0]]}

    def fake_post(url, json=None, **kwargs):
        recorded_inputs.append(json.get("input"))
        return FakeResponse()

    monkeypatch.setattr(embeddings, "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
    monkeypatch.setattr(embeddings, "_OLLAMA_UNAVAILABLE", False)
    monkeypatch.setattr(embeddings.requests, "post", fake_post)

    # Document embedding (default)
    embeddings.embed_text("sale notice content", task="document")
    assert recorded_inputs[-1] == "search_document: sale notice content"

    # Query embedding
    embeddings.embed_text("what is reserve price", task="query")
    assert recorded_inputs[-1] == "search_query: what is reserve price"

    # Already prefixed
    embeddings.embed_text("search_query: custom query", task="query")
    assert recorded_inputs[-1] == "search_query: custom query"


def test_gemini_provider_availability(monkeypatch):
    """GeminiProvider availability depends on GEMINI_API_KEY."""
    monkeypatch.setenv("GEMINI_API_KEY", "")
    provider = GeminiProvider()
    assert not provider.is_available()

    monkeypatch.setenv("GEMINI_API_KEY", "fake_key_12345")
    provider2 = GeminiProvider()
    assert provider2.is_available()


def test_gemini_provider_generate(monkeypatch):
    """GeminiProvider calls generateContent and parses PropertyAIAnalysis."""
    class FakeGeminiResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [{
                    "content": {
                        "parts": [{
                            "text": (
                                '{"summary": "Solid deal", "strengths": ["Good location"], '
                                '"risks": ["Symbolic possession"], "due_diligence": ["Inspect site"], '
                                '"recommendation": "Bid cautiously"}'
                            )
                        }]
                    }
                }]
            }

    monkeypatch.setattr(
        "app.services.llm.requests.post",
        lambda *args, **kwargs: FakeGeminiResponse(),
    )

    provider = GeminiProvider(api_key="valid_key")
    result = provider.generate("Test prompt")
    assert isinstance(result, PropertyAIAnalysis)
    assert result.summary == "Solid deal"
    assert "Good location" in result.strengths
    assert "Symbolic possession" in result.risks


def test_analyst_deal_inquiry(db):
    """User asking 'is this a good deal' or 'how is it a good deal' receives concise deal assessment."""
    res = process_analyst_turn(db, "is this a good deal", property_id=1)
    assert res.intent == "property_deal_inquiry"
    assert "Deal Assessment" in res.answer
    assert "Assessment" in res.answer
    assert "What to Look For" in res.answer
    assert any("Details" in a["title"] for a in res.action_links)


def test_analyst_possession_inquiry(db):
    """User asking about people possessing the property gets clear physical vs symbolic answer."""
    res = process_analyst_turn(db, "are there people currently possessing the property", property_id=1)
    assert res.intent == "property_possession_inquiry"
    assert "Possession Status" in res.answer
    assert "Symbolic Possession" in res.answer or "Physical Possession" in res.answer
    assert "Section 14" in res.answer


def test_analyst_liens_inquiry(db):
    """User asking about liens and encumbrances receives notice audit and EC advice."""
    res = process_analyst_turn(db, "are there any liens on this property", property_id=1)
    assert res.intent == "property_liens_inquiry"
    assert "Liens and Encumbrances" in res.answer
    assert "As is where is" in res.answer
    assert "Encumbrance Certificate" in res.answer


def test_analyst_address_inquiry(db):
    """User asking for the proper address and boundaries receives verified location details."""
    res = process_analyst_turn(db, "what is the proper address and boundaries", property_id=1)
    assert res.intent == "property_address_inquiry"
    assert "Legal Property Location" in res.answer
    assert "Tugalwal" in res.answer
    assert "Official Address" in res.answer
