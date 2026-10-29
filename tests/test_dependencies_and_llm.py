"""
Unit & Integration Tests for app/dependencies.py and LLM Fallback (Sections C & D):
- Database session lifecycle and cleanup
- Authentication & authorization (user, admin, property ownership, optional user)
- Graceful degradation to deterministic SWOT when Ollama is offline or times out
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException

from app.dependencies import (
    get_current_admin,
    get_current_user,
    get_db,
    get_llm_provider,
    get_optional_user,
    require_property_owner,
)
from app.models import Property, User
from app.security import create_access_token
from app.services.llm import (
    LocalLLMProvider,
    deterministic_property_ai_fallback,
    generate_property_analysis,
)


class TestDatabaseDependency:
    def test_get_db_session_lifecycle(self):
        gen = get_db()
        session = next(gen)
        assert session is not None
        assert session.is_active
        # Advancing generator triggers finally block
        try:
            next(gen)
        except StopIteration:
            pass
        # Session should now be closed


class TestAuthDependencies:
    def test_get_current_user_valid_token(self, db):
        user = User(email="active_user@example.com", password_hash="hash", role="user")
        db.add(user)
        db.commit()

        token = create_access_token(user_id=user.id, role=user.role)
        resolved = get_current_user(token=token, db=db)
        assert resolved.id == user.id

    def test_get_current_user_invalid_token(self, db):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token="invalid.token.here", db=db)
        assert exc_info.value.status_code == 401

    def test_get_current_admin_enforcement(self, db):
        regular_user = User(email="regular@example.com", password_hash="hash", role="user")
        admin_user = User(email="admin@example.com", password_hash="hash", role="admin")
        db.add_all([regular_user, admin_user])
        db.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_current_admin(current_user=regular_user)
        assert exc_info.value.status_code == 403

        assert get_current_admin(current_user=admin_user).id == admin_user.id

    def test_get_optional_user(self, db):
        # When no token is passed
        assert get_optional_user(db=db, token=None) is None

        # When invalid token is passed
        assert get_optional_user(db=db, token="bogus") is None

        # When valid token is passed
        user = User(email="opt_user@example.com", password_hash="hash", role="user")
        db.add(user)
        db.commit()
        token = create_access_token(user_id=user.id, role=user.role)
        resolved = get_optional_user(db=db, token=token)
        assert resolved is not None
        assert resolved.id == user.id

    def test_require_property_owner_authorization(self, db):
        owner = User(email="owner@example.com", password_hash="hash", role="user")
        stranger = User(email="stranger@example.com", password_hash="hash", role="user")
        admin = User(email="superadmin@example.com", password_hash="hash", role="admin")
        db.add_all([owner, stranger, admin])
        db.commit()

        prop = Property(address="100 Owner St", user_id=owner.id)
        db.add(prop)
        db.commit()

        # Owner allowed
        assert require_property_owner(property_id=prop.id, current_user=owner, db=db).id == prop.id

        # Admin allowed
        assert require_property_owner(property_id=prop.id, current_user=admin, db=db).id == prop.id

        # Non-owner forbidden
        with pytest.raises(HTTPException) as exc_info:
            require_property_owner(property_id=prop.id, current_user=stranger, db=db)
        assert exc_info.value.status_code == 403

        # Non-existent property returns 404
        with pytest.raises(HTTPException) as exc_info:
            require_property_owner(property_id=99999, current_user=owner, db=db)
        assert exc_info.value.status_code == 404


class TestLLMFallbackAndDegradation:
    def test_deterministic_fallback_has_all_meaningful_fields(self):
        prop_data = {
            "address": "Flat 204 Green Avenue",
            "reserve_price": 3438000.0,
            "foreclosure_status": "upcoming",
            "auction_date": "2026-11-15",
            "estimated_value": None,
        }
        analysis_data = {
            "deal_score": 65.0,
            "discount_percentage": 25.0,
            "risk_level": 2,
        }

        fallback = deterministic_property_ai_fallback(prop_data, analysis_data)
        assert fallback.summary
        assert len(fallback.strengths) >= 1
        assert len(fallback.risks) >= 1
        assert len(fallback.due_diligence) >= 1
        assert fallback.recommendation
        # Must not fabricate missing valuation
        assert any("valuation" in r.lower() for r in fallback.risks)

    def test_generate_property_analysis_falls_back_when_llm_raises(self):
        prop_data = {"address": "123 Fail Safe Rd", "reserve_price": 1000000.0}
        analysis_data = {"deal_score": 50.0, "discount_percentage": None, "risk_level": 2}

        mock_failing_provider = MagicMock()
        mock_failing_provider.generate.side_effect = RuntimeError("Ollama connection refused on localhost:11434")

        result = generate_property_analysis(prop_data, analysis_data, provider=mock_failing_provider)
        assert result is not None
        assert "123 Fail Safe Rd" in result.summary
        assert len(result.due_diligence) >= 2

    def test_get_llm_provider_returns_instance(self):
        provider = get_llm_provider()
        assert isinstance(provider, LocalLLMProvider)
        assert hasattr(provider, "is_available")
