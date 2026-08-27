import pytest
from app.services.properties import analyze_property_with_ai
from app.services.llm import LLMProvider
from app.schemas import PropertyAIAnalysis
from app.dependencies import get_llm_provider
from app.main import app
from app.models import Property

# Pytest handles that connection automatically.

# So the pattern is:

# conftest.py
#     ↓
# @pytest.fixture
# def client():
#     ...
#     ↓
# test_properties.py
#     ↓
# def test_create_property(client):

# That's one of the nice things about pytest fixtures.


def test_create_property(client):
    response = client.post(
        "/properties/",
        json={
            "address": "123 Test Street",
            "price": 500000,
            "bedrooms": 3,
            "bathrooms": 2,
            "area_sqft": 1800,
            "auction_date": "2026-08-22",
            "foreclosure_status": "active",
            "opening_bid": 300000,
            "estimated_value": 500000,
            "property_type": "single_family",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["address"] == "123 Test Street"
    assert data["foreclosure_status"] == "active"
    assert data["opening_bid"] == 300000
    assert data["estimated_value"] == 500000

def test_create_property_invalid_foreclosure_status(client):
    response = client.post(
        "/properties/",
        json={
            "address": "123 Invalid Street",
            "price": 500000,
            "bedrooms": 3,
            "bathrooms": 2,
            "area_sqft": 1800,
            "auction_date": "2026-08-22",
            "foreclosure_status": "banana",
            "opening_bid": 300000,
            "estimated_value": 500000,
            "property_type": "single_family",
        },
    )

    assert response.status_code == 422

def test_property_analysis(client):
    response = client.post(
        "/properties/",
        json={
            "address": "123 Analysis Street",
            "price": 100000,
            "bedrooms": 3,
            "bathrooms": 2,
            "area_sqft": 1500,
            "auction_date": "2026-08-22",
            "foreclosure_status": "active",
            "opening_bid": 60000,
            "estimated_value": 90000,
            "property_type": "single_family",
        },
    )

    assert response.status_code == 201

    property_id = response.json()["id"]

    analysis_response = client.get(
        f"/properties/{property_id}/analysis"
    )

    assert analysis_response.status_code == 200

    analysis = analysis_response.json()

    assert analysis["discount_amount"] == 30000
    assert analysis["discount_percentage"] == pytest.approx(33.333333333333336)
    assert analysis["deal_score"] == pytest.approx(23.333333333333336)

def test_property_analysis_rejects_zero_estimated_value(client):
    response = client.post(
        "/properties/",
        json={
            "address": "123 Zero Value Street",
            "price": 100000,
            "bedrooms": 3,
            "bathrooms": 2,
            "area_sqft": 1500,
            "auction_date": "2026-08-22",
            "foreclosure_status": "active",
            "opening_bid": 60000,
            "estimated_value": 0,
            "property_type": "single_family",
        },
    )

    assert response.status_code == 201

    property_id = response.json()["id"]

    analysis_response = client.get(
        f"/properties/{property_id}/analysis"
    )

    assert analysis_response.status_code == 400

    assert analysis_response.json()["detail"] == (
        "Deal analysis requires estimated_value greater than 0"
    )    

def test_property_analysis_rejects_missing_opening_bid(client): 
    response = client.post(
        "/properties/",
        json={
            "address": "123 Missing Bid Street",
            "price": 100000,
            "bedrooms": 3,
            "bathrooms": 2,
            "area_sqft": 1500,
            "auction_date": "2026-08-22",
            "foreclosure_status": "active",
            "opening_bid": None,
            "estimated_value": 90000,
            "property_type": "single_family",
        },
    )

    assert response.status_code == 201

    property_id = response.json()["id"]

    analysis_response = client.get(
        f"/properties/{property_id}/analysis"
    )

    assert analysis_response.status_code == 400

    assert analysis_response.json()["detail"] == (
        "Deal analysis requires opening_bid"
    )

def test_list_properties(client):
    client.post(
        "/properties/",
        json={
            "address": "123 List Street",
            "price": 100000,
            "bedrooms": 3,
            "bathrooms": 2,
            "area_sqft": 1500,
            "auction_date": "2026-08-22",
            "foreclosure_status": "active",
            "opening_bid": 60000,
            "estimated_value": 90000,
            "property_type": "single_family",
        },
    )

    response = client.get("/properties/")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["page"] == 1
    assert data["limit"] == 20
    assert data["pages"] == 1
    assert len(data["items"]) == 1

    item = data["items"][0]

    assert item["address"] == "123 List Street"
    assert item["discount_percentage"] == pytest.approx(33.333333333333336)
    assert item["deal_score"] == pytest.approx(23.333333333333336)

def test_list_properties_filters_by_foreclosure_status(client):
    client.post(
        "/properties/",
        json={
            "address": "Active Property",
            "price": 100000,
            "bedrooms": 3,
            "bathrooms": 2,
            "area_sqft": 1500,
            "auction_date": "2026-08-22",
            "foreclosure_status": "active",
            "opening_bid": 60000,
            "estimated_value": 90000,
            "property_type": "single_family",
        },
    )

    client.post(
        "/properties/",
        json={
            "address": "Open Property",
            "price": 200000,
            "bedrooms": 4,
            "bathrooms": 3,
            "area_sqft": 2000,
            "auction_date": "2026-08-23",
            "foreclosure_status": "open",
            "opening_bid": 120000,
            "estimated_value": 180000,
            "property_type": "single_family",
        },
    )

    response = client.get(
        "/properties/",
        params={"foreclosure_status": "active"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["items"][0]["address"] == "Active Property"

def test_list_properties_filters_by_discount(client):
    client.post(
        "/properties/",
        json={
            "address": "Good Deal",
            "price": 100000,
            "bedrooms": 3,
            "bathrooms": 2,
            "area_sqft": 1500,
            "auction_date": "2026-08-22",
            "foreclosure_status": "active",
            "opening_bid": 50000,
            "estimated_value": 100000,
            "property_type": "single_family",
        },
    )

    client.post(
        "/properties/",
        json={
            "address": "Small Deal",
            "price": 100000,
            "bedrooms": 3,
            "bathrooms": 2,
            "area_sqft": 1500,
            "auction_date": "2026-08-23",
            "foreclosure_status": "active",
            "opening_bid": 90000,
            "estimated_value": 100000,
            "property_type": "single_family",
        },
    )

    response = client.get(
        "/properties/",
        params={"min_discount": 30},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["items"][0]["address"] == "Good Deal"    

def test_analyze_property_with_ai(fake_llm_provider,db):
    property = Property(
        user_id=1,
        address="123 Main Street",
        price=60000,
        bedrooms=3,
        bathrooms=2,
        area_sqft=1500,
        foreclosure_status="active",
        opening_bid=60000,
        estimated_value=90000,
    )

    db.add(property)
    db.commit()
    db.refresh(property)

    result = analyze_property_with_ai(
        property=property,
        provider=fake_llm_provider,
    )

    assert isinstance(result, PropertyAIAnalysis)
    assert result.summary == "Test property analysis."    

def test_property_ai_analysis(client, fake_llm_provider,db):
    app.dependency_overrides[get_llm_provider] = (
        lambda: fake_llm_provider
    )

#     The route is registered. The 404 is therefore almost certainly coming from this:

# property = get_property_by_id(
#     property_id=property_id,
#     db=db,
# )

# Your client fixture creates a test user, but it doesn't create a property with id=1.

# So the request reaches:

# GET /properties/1/analysis/ai
#         ↓
# AI route ✅
#         ↓
# get_property_by_id(1)
#         ↓
# property doesn't exist ❌
#         ↓
# 404

# That's actually a great debugging lesson: a 404 doesn't necessarily mean the route wasn't found. The endpoint itself can return a 404 because the resource doesn't exist.

# Fix the test

# Inside test_property_ai_analysis, create the property before making the request.
    test_property = Property( 
        id=1,         # struck the not null constraind then added userid but 'userid' is an invalid keyword argument for Property canged it to user_id the actual column name
        user_id=1,
        address="123 Main Street",
        price=60000,
        bedrooms=3,
        bathrooms=2,
        area_sqft=1500,
        foreclosure_status="active",
        opening_bid=60000,
        estimated_value=90000,
    )

    db.add(test_property)
    db.commit()


    response = client.get("/properties/1/analysis/ai")

    assert response.status_code == 200

    data = response.json()

    assert data["summary"] == "Test property analysis."
    assert data["strengths"] == ["Good discount"]
    assert data["risks"] == ["Foreclosure risk"]
    assert data["due_diligence"] == ["Review foreclosure documents"]
    assert data["recommendation"] == "Investigate further."

    app.dependency_overrides.clear()    