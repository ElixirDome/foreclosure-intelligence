"""
Integration tests for FastAPI endpoints:
- Auth registration, login, token authentication, and role authorization
- Properties CRUD, filtering, pagination, sorting, and deal intelligence
- Sources listing, discovery, and status
- Documents listing and retrieval
"""

import pytest
from app.main import app
from app.models import Document, Property, PropertyDocument, User
from app.security import create_access_token, get_current_user


@pytest.mark.integration
class TestAuthAPI:
    def test_user_registration_success(self, client):
        payload = {
            "email": "newuser@example.com",
            "password": "StrongPassword123!",
        }
        res = client.post("/auth/register", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["email"] == "newuser@example.com"
        assert "id" in data
        assert "password" not in data

    def test_duplicate_registration_rejected(self, client):
        payload = {
            "email": "test@example.com",  # Already seeded by client fixture
            "password": "Password123!",
        }
        res = client.post("/auth/register", json=payload)
        assert res.status_code == 400
        assert "already registered" in res.json()["detail"].lower()

    def test_login_success(self, client):
        client.post("/auth/register", json={"email": "loginuser@example.com", "password": "Password123!"})
        res = client.post(
            "/auth/login",
            data={"username": "loginuser@example.com", "password": "Password123!"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_password(self, client):
        client.post("/auth/register", json={"email": "loginfail@example.com", "password": "Password123!"})
        res = client.post(
            "/auth/login",
            data={"username": "loginfail@example.com", "password": "WrongPassword!"},
        )
        assert res.status_code == 401
        assert "invalid" in res.json()["detail"].lower()

    def test_login_nonexistent_user(self, client):
        res = client.post(
            "/auth/login",
            data={"username": "nobody@example.com", "password": "Password123!"},
        )
        assert res.status_code == 401

    def test_get_current_user_profile(self, client):
        token = create_access_token(user_id=1, role="user")
        res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == 1
        assert data["email"] == "test@example.com"

    def test_unauthenticated_protected_route_fails(self, client):
        # Temporarily remove dependency override to test actual unauthenticated behavior
        saved_override = app.dependency_overrides.pop(get_current_user, None)
        try:
            res = client.get("/auth/me", headers={"Authorization": "Bearer invalid-token"})
            assert res.status_code == 401
        finally:
            if saved_override:
                app.dependency_overrides[get_current_user] = saved_override


@pytest.mark.integration
class TestPropertiesAPI:
    def test_list_properties_empty_and_pagination(self, client):
        res = client.get("/properties/?page=1&limit=10")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert data["page"] == 1

    def test_create_and_get_property(self, client):
        prop_payload = {
            "address": "House No 42, Green Park",
            "city": "Jalandhar",
            "locality": "Model Town",
            "property_type": "residential",
            "price": 4_500_000,
            "opening_bid": 4_000_000,
            "area_sqft": 1500,
            "bedrooms": 3,
            "bathrooms": 2,
            "foreclosure_status": "scheduled",
        }
        res = client.post("/properties/", json=prop_payload)
        assert res.status_code == 201
        created = res.json()
        assert created["address"] == "House No 42, Green Park"
        assert created["city"] == "Jalandhar"
        prop_id = created["id"]

        # Fetch by ID
        get_res = client.get(f"/properties/{prop_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == prop_id

    def test_property_not_found_returns_404(self, client):
        res = client.get("/properties/999999")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()

    def test_property_filtering_by_city_and_type(self, client):
        client.post("/properties/", json={
            "address": "Villa A, Amritsar",
            "city": "Amritsar",
            "property_type": "residential",
            "price": 3_000_000,
        })
        client.post("/properties/", json={
            "address": "Villa B, Ludhiana",
            "city": "Ludhiana",
            "property_type": "commercial",
            "price": 8_000_000,
        })

        # Filter by Amritsar
        res = client.get("/properties/?city=Amritsar")
        assert res.status_code == 200
        items = res.json()["items"]
        assert all(p["city"] == "Amritsar" for p in items)

        # Filter by residential
        res_type = client.get("/properties/?property_type=residential")
        assert res_type.status_code == 200
        assert all(p.get("property_type") == "residential" for p in res_type.json()["items"])

    def test_property_summary_route(self, client):
        res = client.get("/properties/summary")
        assert res.status_code == 200
        data = res.json()
        assert "total_properties" in data
        assert "residential" in data
        assert "upcoming_auctions" in data

    def test_property_live_status(self, client):
        res = client.get("/properties/live-status")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "online"
        assert "active_subscribers" in data
        assert "total_properties" in data


@pytest.mark.integration
class TestSourcesAndDocumentsAPI:
    @pytest.fixture(autouse=True)
    def setup_admin_user(self):
        """Sources endpoints require admin role."""
        prev = app.dependency_overrides.get(get_current_user)
        app.dependency_overrides[get_current_user] = lambda: User(
            id=1, email="admin@example.com", role="admin"
        )
        yield
        if prev:
            app.dependency_overrides[get_current_user] = prev

    def test_list_sources(self, client):
        res = client.get("/sources/")
        assert res.status_code == 200
        sources = res.json()
        assert isinstance(sources, list)

    def test_source_discovery_known_portal(self, client):
        res = client.post("/sources/discover", json={"url_or_name": "pnb"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "discovered"
        assert "pnb" in data["candidate_url"].lower()

    def test_source_discovery_ssrf_rejection(self, client):
        res = client.post("/sources/discover", json={"url_or_name": "http://127.0.0.1:8000/admin"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "failed"
        assert "security" in data["failure_reason"].lower()

    def test_list_documents(self, client):
        res = client.get("/documents/?limit=10")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_document_not_found(self, client):
        res = client.get("/documents/888888")
        assert res.status_code == 404
