import pytest
from datetime import date, datetime, timezone
from app.services.analyst import process_analyst_turn
from app.models import (
    Property,
    Document,
    DocumentChunk,
    PropertyDocument,
    Evidence,
    User,
    MarketComparable,
)


@pytest.fixture(autouse=True)
def seed_test_data(db):
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(id=1, email="analyst@example.com", password_hash="hash", role="user")
        db.add(user)
        db.commit()

    prop = db.query(Property).filter(Property.id == 1).first()
    if not prop:
        prop = Property(
            id=1,
            user_id=1,
            address="Village Tugalwal HB No 533, Gurdaspur",
            city="Gurdaspur",
            locality="Tehsil",
            property_type="Residential Property",
            area_sqft=1200,
            reserve_price=2500000.0,
            opening_bid=2500000.0,
            emd=250000.0,
            auction_date=date(2026, 11, 15),
            foreclosure_status="scheduled",
        )
        db.add(prop)

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
                comparable_key=f"comp_key_{i}",
            ))

        doc = Document(
            id=1,
            title="ARMB Pathankot Sale Notice",
            source_name="PNB",
            source_url="https://www.pnb.bank.in/EAuction.aspx",
            document_type="auction_notice",
            extracted_text=(
                "SALE NOTICE FOR SALE OF IMMOVABLE PROPERTIES\n"
                "Authorised OfficeroftheBank/SecuredCreditor\n"
                "ARMB -PATHANKOT\n"
                "(Near Kamal Sweets Saili Road Pathankot, Punjab-145001)\n"
                "[Phone No. 9115554320] e mail: cs829500@pnb.bank.in\n"
                "DATE:05.10.2026 PLACE: PATHANKOT"
            ),
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(doc)
        db.add(DocumentChunk(
            document_id=1,
            chunk_index=0,
            page_number=1,
            text=(
                "SALE NOTICE FOR SALE OF IMMOVABLE PROPERTIES\n"
                "ARMB -PATHANKOT [Phone No. 9115554320] e mail: cs829500@pnb.bank.in\n"
                "Authorised OfficeroftheBank/SecuredCreditor"
            ),
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
        db.commit()


def test_analyst_source_onboarding_guidance(db):
    res = process_analyst_turn(db, "How do I connect a foreclosure source to Foreclosure Intelligence?")
    assert res.intent == "onboarding_guide"
    assert "Punjab National Bank" in res.answer or "PNB" in res.answer
    assert any("/import" in link["url"] for link in res.action_links)


def test_analyst_valuation_explanation(db):
    res = process_analyst_turn(db, "How was the property value calculated?", property_id=1)
    assert res.intent == "valuation_explanation"
    assert "Lot #1" in res.answer
    assert "Estimated Market Value" in res.answer
    assert len(res.citations) >= 1


def test_analyst_status_and_evidence_inquiry(db):
    res = process_analyst_turn(db, "What are its EMD and reserve price and current status?", property_id=1)
    assert res.intent == "status_inquiry"
    assert "Reserve Price" in res.answer
    assert "Earnest Money Deposit" in res.answer or "EMD" in res.answer
    assert "Secured Creditor" in res.answer or "PNB" in res.answer
    assert len(res.citations) >= 1


def test_analyst_original_notice_document(db):
    res = process_analyst_turn(db, "Show me the original auction notice for this property", property_id=1)
    assert res.intent == "document_retrieval"
    assert any("/documents/" in link["url"] for link in res.action_links)


def test_analyst_discovery_location_search(db):
    res = process_analyst_turn(db, "Show the latest residential auctions in Gurdaspur")
    assert res.intent == "inventory_discovery"
    assert "Residential Auctions" in res.answer
    assert "Tugalwal" in res.answer


def test_analyst_representative_inquiry_with_contact_details(db):
    res = process_analyst_turn(db, "Who is the representative for this property?", property_id=1)
    assert res.intent == "representative_inquiry"
    assert "Authorised Officer" in res.answer
    assert "9115554320" in res.answer
    assert "cs829500@pnb.bank.in" in res.answer
    assert "ARMB -PATHANKOT" in res.answer or "ARMB" in res.answer
    assert len(res.citations) >= 1
    assert res.citations[0].document_id == 1
    assert any("/documents/1/file" in link["url"] for link in res.action_links)


def test_analyst_representative_inquiry_by_lot_in_query(db):
    res = process_analyst_turn(db, "What are the representative's contact details for Lot #1?")
    assert res.intent == "representative_inquiry"
    assert res.property_id == 1
    assert "9115554320" in res.answer
    assert "cs829500@pnb.bank.in" in res.answer


def test_analyst_representative_inquiry_missing_notice_details(db):
    prop99 = Property(
        id=999,
        user_id=1,
        address="Empty Notice Villa, Gurdaspur",
        property_type="Residential Property",
    )
    doc99 = Document(
        id=999,
        title="Notice Without Rep Info",
        source_name="Bank",
        source_url="https://bank.example.com/notice999",
        document_type="auction_notice",
        extracted_text="General auction terms only. No phone or email given.",
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(prop99)
    db.add(doc99)
    db.add(PropertyDocument(property_id=999, document_id=999, relationship_type="notice"))
    db.commit()

    res = process_analyst_turn(db, "Who is the representative for this property?", property_id=999)
    assert res.intent == "representative_inquiry"
    assert "Representative Contact Details Not Found" in res.answer
    assert "9115554320" not in res.answer  # does not hallucinate
    assert len(res.citations) >= 1


def test_analyst_representative_inquiry_unspecified_lot(db):
    res = process_analyst_turn(db, "Who is the representative?")
    assert res.intent == "representative_inquiry"
    assert "specify the property lot" in res.answer.lower() or "lot" in res.answer.lower()
