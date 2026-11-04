"""
Automated security audit tests:
- SSRF prevention (cloud metadata, loopback, private RFC 1918 IPs, forbidden URI schemes)
- Broken object-level authorization (BOLA / IDOR) cross-user modification guards
- Authentication bypass and forged JWT rejection
- SQL injection safety with parameterized queries
- Rate limiting protection on sensitive routes
"""

import pytest
from app.ingestion.source_security import UnsafeSourceURL, validate_source_url
from app.models import Property, User
from app.security import create_access_token


@pytest.mark.security
class TestSSRFProtections:
    def test_reject_cloud_metadata_endpoints(self):
        cloud_targets = [
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://169.254.169.254/metadata/v1.json",
        ]
        for url in cloud_targets:
            with pytest.raises(UnsafeSourceURL):
                validate_source_url(url)

    def test_reject_loopback_and_local_addresses(self):
        loopback_targets = [
            "http://127.0.0.1:8000/admin",
            "http://localhost:5432",
            "http://0.0.0.0:80",
            "http://[::1]:8080",
        ]
        for url in loopback_targets:
            with pytest.raises(UnsafeSourceURL):
                validate_source_url(url)

    def test_reject_private_rfc1918_networks(self):
        private_ips = [
            "http://10.0.0.1/internal",
            "http://172.16.0.5/api",
            "http://192.168.1.1/router",
        ]
        for url in private_ips:
            with pytest.raises(UnsafeSourceURL):
                validate_source_url(url)

    def test_reject_invalid_uri_schemes(self):
        unsafe_schemes = [
            "file:///etc/passwd",
            "gopher://127.0.0.1:70",
            "ftp://anonymous@evil.com/payload",
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
        ]
        for url in unsafe_schemes:
            with pytest.raises(UnsafeSourceURL):
                validate_source_url(url)

    def test_allow_public_legitimate_bank_urls(self):
        valid_urls = [
            "https://www.pnb.bank.in/EAuction.aspx",
            "https://ibapi.in",
            "https://bankauctions.in/sbi",
        ]
        for url in valid_urls:
            assert validate_source_url(url).startswith("https://")


@pytest.mark.security
class TestAccessControlAndBOLA:
    def test_user_cannot_modify_another_users_property(self, client, db):
        # User 1 owns Property 1
        user1 = User(id=1, email="owner1@example.com", password_hash="hash", role="user")
        db.add(user1)
        db.commit()

        prop = Property(address="Secret Villa", user_id=user1.id, city="Delhi")
        db.add(prop)
        db.commit()

        # User 2 tries to modify Property 1
        user2 = User(id=999, email="attacker@example.com", password_hash="hash", role="user")
        db.add(user2)
        db.commit()

        from app.security import require_property_owner
        with pytest.raises(Exception) as exc:
            require_property_owner(property_id=prop.id, current_user=user2, db=db)
        assert exc.value.status_code == 403

    def test_forged_or_manipulated_jwt_rejected(self, client):
        from app.main import app
        from app.security import get_current_user
        saved_override = app.dependency_overrides.pop(get_current_user, None)
        try:
            res = client.get("/auth/me", headers={"Authorization": "Bearer forged.jwt.token"})
            assert res.status_code == 401
        finally:
            if saved_override:
                app.dependency_overrides[get_current_user] = saved_override

    def test_sql_injection_attempt_in_search_parameter_safe(self, client):
        # Attempt standard SQL injection
        res = client.get("/properties/?search=' OR '1'='1' --")
        # Should execute safely as a literal search string, not crash or return unescaped SQL
        assert res.status_code == 200
        assert isinstance(res.json()["items"], list)

    def test_excessive_limit_parameter_constrained(self, client):
        # Client tries limit=10000000
        res = client.get("/properties/?limit=10000000")
        # FastAPI Query validation le=100 will return 422 Unprocessable Entity
        assert res.status_code == 422
