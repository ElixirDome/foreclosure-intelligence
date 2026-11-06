"""
Unit tests for app.security helper logic:
Argon2 password hashing, JWT creation & decoding, expiration, role guards, and owner checks.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import jwt
import pytest
from app.models import Property, User
from app.security import (
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    create_access_token,
    decode_access_token,
    require_property_owner,
    require_role,
    verify_password,
)
from fastapi import HTTPException


@pytest.mark.unit
class TestPasswordHashing:
    def test_verify_password_correct(self):
        from pwdlib import PasswordHash
        hasher = PasswordHash.recommended()
        plain = "SecureP@ssw0rd!123"
        hashed = hasher.hash(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_password_wrong(self):
        from pwdlib import PasswordHash
        hasher = PasswordHash.recommended()
        hashed = hasher.hash("CorrectPassword")
        assert verify_password("WrongPassword", hashed) is False

    def test_verify_password_empty(self):
        from pwdlib import PasswordHash
        hasher = PasswordHash.recommended()
        hashed = hasher.hash("Something")
        assert verify_password("", hashed) is False


@pytest.mark.unit
class TestJWTManagement:
    def test_create_and_decode_valid_token(self):
        token = create_access_token(user_id=42, role="admin")
        assert isinstance(token, str)
        payload = decode_access_token(token)
        assert payload["sub"] == "42"
        assert payload["role"] == "admin"
        assert "exp" in payload

    def test_expired_token_raises_expired_signature_error(self):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        expired_payload = {"sub": "1", "role": "user", "exp": past}
        expired_token = jwt.encode(expired_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(expired_token)

    def test_tampered_token_raises_invalid_signature_error(self):
        token = create_access_token(user_id=1, role="user")
        tampered = token[:-4] + "abcd"
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(tampered)

    def test_wrong_secret_token_rejected(self):
        fake_token = jwt.encode({"sub": "1", "role": "user"}, "wrong-secret-key", algorithm=JWT_ALGORITHM)
        with pytest.raises(jwt.InvalidSignatureError):
            decode_access_token(fake_token)


@pytest.mark.unit
class TestRoleGuard:
    def test_role_allowed(self):
        admin_user = User(id=1, email="admin@example.com", role="admin")
        checker = require_role("admin")
        assert checker(current_user=admin_user) == admin_user

    def test_role_forbidden_raises_403(self):
        standard_user = User(id=2, email="user@example.com", role="user")
        checker = require_role("admin")
        with pytest.raises(HTTPException) as exc_info:
            checker(current_user=standard_user)
        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail


@pytest.mark.unit
class TestPropertyOwnerGuard:
    def test_owner_can_modify(self):
        user = User(id=10, role="user")
        prop = Property(id=100, user_id=10)
        db_mock = MagicMock()
        db_mock.query().filter().first.return_value = prop

        result = require_property_owner(property_id=100, current_user=user, db=db_mock)
        assert result == prop

    def test_admin_can_modify_any_property(self):
        admin = User(id=99, role="admin")
        prop = Property(id=100, user_id=10)  # different owner
        db_mock = MagicMock()
        db_mock.query().filter().first.return_value = prop

        result = require_property_owner(property_id=100, current_user=admin, db=db_mock)
        assert result == prop

    def test_non_owner_forbidden_raises_403(self):
        other_user = User(id=5, role="user")
        prop = Property(id=100, user_id=10)  # owned by 10
        db_mock = MagicMock()
        db_mock.query().filter().first.return_value = prop

        with pytest.raises(HTTPException) as exc_info:
            require_property_owner(property_id=100, current_user=other_user, db=db_mock)
        assert exc_info.value.status_code == 403
        assert "do not have permission" in exc_info.value.detail

    def test_property_not_found_raises_404(self):
        user = User(id=1, role="user")
        db_mock = MagicMock()
        db_mock.query().filter().first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            require_property_owner(property_id=9999, current_user=user, db=db_mock)
        assert exc_info.value.status_code == 404
