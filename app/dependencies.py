"""
Centralized FastAPI Dependency Injection Hub.

Exports and manages lifecycle for:
- Database Sessions (SessionLocal with guaranteed cleanup)
- Authentication & JWT Token Verification (OAuth2 Bearer)
- Role-based Authorization (Admin & Property Ownership)
- External Service Providers (Ollama LocalLLMProvider)
"""

from __future__ import annotations

from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db as _base_get_db
from app.models import Property, User
from app.security import (
    decode_access_token,
    oauth2_scheme,
    get_current_user as _base_get_current_user,
    require_property_owner as _base_require_property_owner,
)
from app.services.llm import LLMProvider, LocalLLMProvider


def get_db() -> Generator[Session, None, None]:
    """
    Provide transactional database session per request with guaranteed cleanup.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Authenticate request via JWT Bearer token and retrieve the user.
    """
    return _base_get_current_user(token=token, db=db)


def get_optional_user(
    db: Session = Depends(get_db),
    token: str | None = Depends(OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)),
) -> User | None:
    """
    Extract user when Bearer token is provided, otherwise return None without raising 401.
    """
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub", 0))
        return db.query(User).filter(User.id == user_id).first()
    except Exception:
        return None


def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Assert that the authenticated user possesses admin privileges.
    """
    if getattr(current_user, "role", "user") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def require_property_owner(
    property_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Property:
    """
    Assert that the property exists and the current user owns it (or is admin).
    """
    return _base_require_property_owner(
        property_id=property_id,
        current_user=current_user,
        db=db,
    )


def get_llm_provider() -> LocalLLMProvider:
    """
    Provide configured local LLM provider instance.
    """
    return LocalLLMProvider()
