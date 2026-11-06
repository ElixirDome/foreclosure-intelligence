import pytest
from datetime import date, datetime, timedelta
from app.models import (
    Property,
    PropertyDocument,
    PropertyValuation,
    Evidence,
    Document,
    User,
)
from app.services.properties import delete_expired_properties
from app.services.analyst import process_analyst_turn


def test_delete_expired_properties_removes_past_auctions(db):
    user = db.query(User).first()
    if not user:
        user = User(email="cleanuptest@example.com", password_hash="pw")
        db.add(user)
        db.flush()

    today = date.today()
    past_date = today - timedelta(days=5)
    future_date = today + timedelta(days=10)

    # 1. Expired property
    expired_prop = Property(
        user_id=user.id,
        address="100 Expired Road, Gurdaspur",
        city="Gurdaspur",
        auction_date=past_date,
        foreclosure_status="scheduled",
        reserve_price=3000000.0,
    )
    # 2. Future active property
    active_prop = Property(
        user_id=user.id,
        address="200 Active Boulevard, Gurdaspur",
        city="Gurdaspur",
        auction_date=future_date,
        foreclosure_status="scheduled",
        reserve_price=4500000.0,
    )
    # 3. Property without auction date
    undated_prop = Property(
        user_id=user.id,
        address="300 Undated Lane, Gurdaspur",
        city="Gurdaspur",
        auction_date=None,
        foreclosure_status="scheduled",
        reserve_price=5000000.0,
    )
    db.add_all([expired_prop, active_prop, undated_prop])
    db.flush()

    # Create document and child links for expired property
    doc = Document(
        source_name="PNB",
        source_url="https://pnb.example/expired.pdf",
        document_type="auction_notice",
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
    db.add(doc)
    db.flush()

    pdoc = PropertyDocument(property_id=expired_prop.id, document_id=doc.id, relationship_type="auction_notice")
    val = PropertyValuation(
        property_id=expired_prop.id,
        estimated_value=3200000.0,
        valuation_method="residential_comparable_sales",
        source="market_comparables",
        valuation_date=today,
    )
    ev = Evidence(
        property_id=expired_prop.id,
        document_id=doc.id,
        field="reserve_price",
        value="3000000",
    )
    db.add_all([pdoc, val, ev])
    db.commit()

    expired_id = expired_prop.id
    active_id = active_prop.id
    undated_id = undated_prop.id

    # Verify initial state
    assert db.query(Property).filter(Property.id == expired_id).count() == 1
    assert db.query(PropertyDocument).filter(PropertyDocument.property_id == expired_id).count() == 1
    assert db.query(PropertyValuation).filter(PropertyValuation.property_id == expired_id).count() == 1
    assert db.query(Evidence).filter(Evidence.property_id == expired_id).count() == 1

    # Run cleanup as of today
    deleted_count = delete_expired_properties(db, as_of_date=today)
    assert deleted_count >= 1

    # Verify expired property and child records are deleted
    assert db.query(Property).filter(Property.id == expired_id).count() == 0
    assert db.query(PropertyDocument).filter(PropertyDocument.property_id == expired_id).count() == 0
    assert db.query(PropertyValuation).filter(PropertyValuation.property_id == expired_id).count() == 0
    assert db.query(Evidence).filter(Evidence.property_id == expired_id).count() == 0

    # Verify active and undated properties remain untouched
    assert db.query(Property).filter(Property.id == active_id).count() == 1
    assert db.query(Property).filter(Property.id == undated_id).count() == 1

    # Teardown
    db.query(Property).filter(Property.id.in_([active_id, undated_id])).delete(synchronize_session=False)
    db.query(Document).filter(Document.id == doc.id).delete(synchronize_session=False)
    db.commit()


def test_cleanup_expired_endpoint(client, db):
    user = db.query(User).first()
    if not user:
        user = User(email="cleanuptest2@example.com", password_hash="pw")
        db.add(user)
        db.flush()

    past_date = date.today() - timedelta(days=2)
    prop = Property(
        user_id=user.id,
        address="999 Expired Ave, Gurdaspur",
        city="Gurdaspur",
        auction_date=past_date,
        reserve_price=2000000.0,
    )
    db.add(prop)
    db.commit()
    prop_id = prop.id

    res = client.post("/properties/cleanup-expired")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["deleted_count"] >= 1

    # Ensure property was deleted
    assert db.query(Property).filter(Property.id == prop_id).count() == 0


def test_analyst_answer_formatting_has_no_double_asterisks_or_hyphens_in_status_fields(db):
    user = db.query(User).first()
    if not user:
        user = User(email="analystformat@example.com", password_hash="pw")
        db.add(user)
        db.flush()

    future_date = date.today() + timedelta(days=15)
    prop = Property(
        user_id=user.id,
        address="12 Clean Formatting Way, Gurdaspur",
        city="Gurdaspur",
        auction_date=future_date,
        foreclosure_status="scheduled",
        reserve_price=5500000.0,
        emd=550000.0,
        survey_number="123/45",
    )
    db.add(prop)
    db.flush()

    doc = Document(
        source_name="Punjab National Bank (PNB)",
        source_url="https://pnb.example/clean.pdf",
        title="PNB ARMB Notice Clean",
        document_type="auction_notice",
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
    db.add(doc)
    db.flush()

    pdoc = PropertyDocument(property_id=prop.id, document_id=doc.id, relationship_type="notice")
    ev = Evidence(
        property_id=prop.id,
        document_id=doc.id,
        field="reserve_price",
        value="5500000",
        extraction_method="banknet_api",
        page_number=1,
    )
    db.add_all([pdoc, ev])
    db.commit()

    turn = process_analyst_turn(db, "What are its EMD and reserve price and current status?", property_id=prop.id)

    # 1. Verification of clean header (renamed from 'Auction & Underwriting Status')
    assert "Auction & Underwriting Status" not in turn.answer
    assert f"### Auction Details: Lot #{prop.id}" in turn.answer

    # 2. Verification that evidence source lines like (Verified via `banknet_api` extraction...) are stripped away
    assert "Verified via" not in turn.answer
    assert "Doc #78, Page 1" not in turn.answer
    assert "Field Evidence:" not in turn.answer

    # 3. Verification of clean key-value formatting without bullet hyphens and bold keys
    assert "- **Secured Creditor" not in turn.answer
    assert "- **Reserve Price" not in turn.answer
    assert "- **Earnest Money Deposit" not in turn.answer
    assert "Reserve Price: ₹5,500,000.00" in turn.answer
    assert "Earnest Money Deposit (EMD): ₹550,000.00" in turn.answer
    assert "Secured Creditor: Punjab National Bank" in turn.answer

    # 4. Citations only contain property and notice document, no evidence citations
    assert any(c.kind == "property" for c in turn.citations)
    assert any(c.kind == "document" for c in turn.citations)
    assert not any(c.kind == "evidence" for c in turn.citations)

    # Teardown
    db.query(Evidence).filter(Evidence.property_id == prop.id).delete(synchronize_session=False)
    db.query(PropertyDocument).filter(PropertyDocument.property_id == prop.id).delete(synchronize_session=False)
    db.query(Property).filter(Property.id == prop.id).delete(synchronize_session=False)
    db.query(Document).filter(Document.id == doc.id).delete(synchronize_session=False)
    db.commit()
