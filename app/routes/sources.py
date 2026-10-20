"""Admin-managed listing-source configuration and sync controls."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.ingestion.source_security import UnsafeSourceURL, validate_source_url
from app.ingestion.scheduler import enqueue_connected_source
from app.models import ConnectedSource, User
from app.security import require_role

router = APIRouter(prefix="/sources", tags=["sources"])

_ALLOWED_RULES = {"item_selector", "reserve", "emd", "limit"}
_REGEX_RULES = {"reserve", "emd"}


class ConnectSourceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=8, max_length=2048)
    adapter_key: Literal["custom_html", "pnb", "banknet"] = "custom_html"
    rules: dict = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Source name cannot be blank.")
        return value

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        try:
            return validate_source_url(value)
        except UnsafeSourceURL as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("rules")
    @classmethod
    def validate_rules(cls, value: dict) -> dict:
        unknown = set(value) - _ALLOWED_RULES
        if unknown:
            raise ValueError(
                "Unsupported extraction rule(s): " + ", ".join(sorted(unknown))
            )

        selector = value.get("item_selector")
        if selector is not None:
            if not isinstance(selector, str) or not selector.strip() or len(selector) > 200:
                raise ValueError("item_selector must be a non-empty CSS selector of at most 200 characters.")

        for key in _REGEX_RULES:
            pattern = value.get(key)
            if pattern is None:
                continue
            if not isinstance(pattern, str) or not pattern.strip() or len(pattern) > 200:
                raise ValueError(f"{key} must be a non-empty regex of at most 200 characters.")
            try:
                compiled = re.compile(pattern, flags=re.I)
            except re.error as exc:
                raise ValueError(f"{key} contains an invalid regex.") from exc
            if compiled.groups < 1:
                raise ValueError(f"{key} must contain a capture group for the amount.")

        limit = value.get("limit")
        if limit is not None:
            if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
                raise ValueError("limit must be an integer between 1 and 100.")

        return value


class SourceResponse(BaseModel):
    id: int
    name: str
    base_url: str
    adapter_key: str
    enabled: bool
    last_run_at: datetime | None
    last_status: str | None

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[SourceResponse])
def list_sources(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin")),
):
    return db.query(ConnectedSource).order_by(ConnectedSource.id).all()


@router.post("/", response_model=SourceResponse, status_code=201)
def connect_source(
    body: ConnectSourceRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin")),
):
    existing = (
        db.query(ConnectedSource)
        .filter(ConnectedSource.base_url == body.base_url)
        .first()
    )
    config = {"rules": body.rules}
    if existing:
        existing.name = body.name
        existing.adapter_key = body.adapter_key
        existing.config_json = config
        existing.enabled = True
        db.commit()
        db.refresh(existing)
        return existing

    row = ConnectedSource(
        name=body.name,
        base_url=body.base_url,
        adapter_key=body.adapter_key,
        config_json=config,
        enabled=True,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        # A concurrent request may have registered this base URL after the
        # initial lookup. Treat that race as an upsert rather than a 500.
        existing = (
            db.query(ConnectedSource)
            .filter(ConnectedSource.base_url == body.base_url)
            .first()
        )
        if existing is None:
            raise
        existing.name = body.name
        existing.adapter_key = body.adapter_key
        existing.config_json = config
        existing.enabled = True
        row = existing

    db.commit()
    db.refresh(row)
    return row


@router.post("/{source_id}/run")
def run_source(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    source = (
        db.query(ConnectedSource)
        .filter(ConnectedSource.id == source_id)
        .first()
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.enabled:
        raise HTTPException(status_code=409, detail="Source is disabled")

    source.last_status = "queued"
    db.commit()
    enqueue_connected_source(source_id, current_user.id)
    return {"status": "queued", "source_id": source_id}
