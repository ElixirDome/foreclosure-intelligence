import pytest

from app.dependencies import get_llm_provider
from app.main import app
from app.models import Property
from app.schemas import PropertyAIAnalysis
from app.services.properties import analyze_property_with_ai
from app.services.valuation import record_valuation


def _create_property(client, *, address="Test Property", **overrides):
    payload = {
        "address": address,
        "city": "Bengaluru",
        "locality": "Whitefield",
        "price": 100000,
        "bedrooms": 3,
        "bathrooms": 2,
        "area_sqft": 1500,
        "auction_date": "2026-08-22",
        "foreclosure_status": "active",
        "opening_bid": 60000,
        "property_type": "single_family",
    }
    payload.update(overrides)
    return client.post("/properties/", json=payload)


def _record_test_valuation(
    db,
    property_id: int,
    value: float = 90000,
    *,
    set_reserve_price: bool = True,
):
    """Seed a valuation through the same service used by automated valuation."""
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if set_reserve_price and property_obj.reserve_price is None:
        property_obj.reserve_price = property_obj.opening_bid
        db.commit()
    return record_valuation(
        db=db,
        property_id=property_id,
        estimated_value=value,
        valuation_method="residential_comparable_sales",
        source="market_comparables",
        confidence=None,
    )


def test_create_property(client):
    response = _create_property(
        client,
        address="123 Test Street",
        opening_bid=300000,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["address"] == "123 Test Street"
    assert data["foreclosure_status"] == "active"
    assert data["opening_bid"] == 300000
    assert data["estimated_value"] is None


def test_create_property_invalid_foreclosure_status(client):
    response = _create_property(
        client,
        address="123 Invalid Street",
        foreclosure_status="banana",
    )
    assert response.status_code == 422


def test_property_analysis(client, db):
    response = _create_property(client, address="123 Analysis Street")
    assert response.status_code == 201
    property_id = response.json()["id"]
    _record_test_valuation(db, property_id)

    analysis_response = client.get(f"/properties/{property_id}/analysis")
    assert analysis_response.status_code == 200
    analysis = analysis_response.json()
    assert analysis["discount_amount"] == 30000
    assert analysis["discount_percentage"] == pytest.approx(33.333333333333336)
    assert analysis["deal_score"] == pytest.approx(23.333333333333336)


def test_property_analysis_rejects_missing_automated_estimate(client):
    response = _create_property(client, address="123 Unvalued Street")
    assert response.status_code == 201

    analysis_response = client.get(
        f"/properties/{response.json()['id']}/analysis"
    )
    assert analysis_response.status_code == 400
    assert analysis_response.json()["detail"] == (
        "Deal analysis requires an automated comparable-based valuation"
    )


def test_property_analysis_rejects_missing_reserve_price(client, db):
    response = _create_property(
        client,
        address="123 Missing Reserve Street",
        opening_bid=60000,
    )
    assert response.status_code == 201
    property_id = response.json()["id"]
    _record_test_valuation(db, property_id, set_reserve_price=False)

    analysis_response = client.get(f"/properties/{property_id}/analysis")
    assert analysis_response.status_code == 400
    assert analysis_response.json()["detail"] == (
        "Deal analysis requires reserve_price"
    )


def test_list_properties(client, db):
    response = _create_property(client, address="123 List Street")
    assert response.status_code == 201
    _record_test_valuation(db, response.json()["id"])

    response = client.get("/properties/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["limit"] == 20
    assert data["pages"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["address"] == "123 List Street"
    assert data["items"][0]["discount_percentage"] == pytest.approx(33.333333333333336)
    assert data["items"][0]["deal_score"] == pytest.approx(23.333333333333336)


def test_list_properties_filters_by_foreclosure_status(client):
    _create_property(client, address="Active Property", foreclosure_status="active")
    _create_property(client, address="Scheduled Property", foreclosure_status="scheduled")

    response = client.get("/properties/", params={"foreclosure_status": "active"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["address"] == "Active Property"


def test_list_properties_filters_by_discount(client, db):
    good = _create_property(client, address="Good Deal", opening_bid=50000)
    small = _create_property(client, address="Small Deal", opening_bid=90000)
    assert good.status_code == 201
    assert small.status_code == 201

    for response in (good, small):
        _record_test_valuation(db, response.json()["id"], 100000)

    response = client.get("/properties/", params={"min_discount": 30})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["address"] == "Good Deal"


def test_analyze_property_with_ai(client, fake_llm_provider, db):
    response = _create_property(client, address="123 Main Street")
    assert response.status_code == 201
    property_id = response.json()["id"]
    _record_test_valuation(db, property_id)
    property_obj = db.query(Property).filter(Property.id == property_id).first()

    result = analyze_property_with_ai(
        property=property_obj,
        provider=fake_llm_provider,
    )
    assert isinstance(result, PropertyAIAnalysis)
    assert result.summary == "Test property analysis."


def test_property_ai_analysis(client, fake_llm_provider):
    response = _create_property(client, address="123 Main Street")
    assert response.status_code == 201

    app.dependency_overrides[get_llm_provider] = lambda: fake_llm_provider
    try:
        response = client.get(
            f"/properties/{response.json()['id']}/analysis/ai"
        )
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)

    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Test property analysis."
    assert data["strengths"] == ["Good discount"]
    assert data["risks"] == ["Foreclosure risk"]
    assert data["due_diligence"] == ["Review foreclosure documents"]
    assert data["recommendation"] == "Investigate further."


def test_residential_filter_excludes_commercial_properties(client, db):
    # Create residential property
    res_resp = _create_property(
        client,
        address="101 Rose Avenue, Gurdaspur",
        property_type="Residential Flat",
        city="Gurdaspur",
    )
    assert res_resp.status_code == 201

    # Create commercial property
    comm_resp = _create_property(
        client,
        address="Commercial Complex Sector 4, Gurdaspur",
        property_type="Commercial Shop",
        city="Gurdaspur",
    )
    assert comm_resp.status_code == 201

    # Query with property_type=residential
    res_query = client.get("/properties/?property_type=residential&city=Gurdaspur")
    assert res_query.status_code == 200
    res_items = res_query.json()["items"]
    res_types = [item["property_type"] for item in res_items]

    # Verify no commercial property leaked into residential results
    assert all("commercial" not in (t or "").lower() for t in res_types)
    assert any("Rose Avenue" in item["address"] for item in res_items)
    assert not any("Commercial Complex" in item["address"] for item in res_items)


def test_location_and_property_type_combined_filtering(client, db):
    _create_property(
        client,
        address="55 Palm Grove, Ghaziabad",
        property_type="Residential House",
        city="Ghaziabad",
    )
    _create_property(
        client,
        address="22 Mill Road, Amritsar",
        property_type="Residential House",
        city="Amritsar",
    )

    # Filter by city + residential
    resp = client.get("/properties/?city=Ghaziabad&property_type=residential")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert all(item["city"] == "Ghaziabad" for item in items if item.get("city"))
    assert not any(item.get("city") == "Amritsar" for item in items)


def test_get_properties_deal_score_reflects_valuation_confidence(client, db):
    """SQL list deal score must adjust by valuation confidence, matching detail analysis."""
    from app.models import Property, PropertyValuation
    from datetime import date

    prop = Property(
        user_id=1,
        address="99 Concourse Way, Gurdaspur",
        city="Gurdaspur",
        reserve_price=2000000.0,
        foreclosure_status="scheduled",  # risk_level = 1 -> penalty = 5
        property_key="99_concourse_way",
    )
    db.add(prop)
    db.commit()

    # Discount = (4M - 2M) / 4M * 100 = 50%
    # Raw deal score = 50 - (1 * 5) = 45
    # With confidence 0.8: adjusted = 45 * 0.8 = 36.0
    val = PropertyValuation(
        property_id=prop.id,
        estimated_value=4000000.0,
        valuation_method="residential_comparable_sales",
        source="market_comparables",
        confidence=0.8,
        valuation_date=date.today(),
    )
    db.add(val)
    db.commit()

    resp = client.get(f"/properties/?search=Concourse")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["deal_score"] == pytest.approx(36.0)


