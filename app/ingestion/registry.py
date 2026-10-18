"""Pluggable listing-source registry.

Built-in adapters (PNB, BankNet) plus admin-connected sources stored in
`connected_sources`. A connected source is either a known adapter key or
`custom_html` with regex extraction rules.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ingestion.banknet_source import BankNetSourceAdapter
from app.ingestion.base import SourceAdapter
from app.ingestion.custom_source import CustomHtmlSourceAdapter
from app.ingestion.pnb_source import PNBSourceAdapter
from app.models import ConnectedSource


BUILTIN_KEYS = ("pnb", "banknet")


def builtin_adapters() -> list[SourceAdapter]:
    return [
        PNBSourceAdapter(),
        BankNetSourceAdapter(limit=50, max_pages=3, download_documents=True),
    ]


def adapter_for_connected(source: ConnectedSource) -> SourceAdapter:
    key = (source.adapter_key or "custom_html").lower()
    cfg = source.config_json or {}
    if key == "pnb":
        return PNBSourceAdapter()
    if key == "banknet":
        return BankNetSourceAdapter(
            limit=int(cfg.get("limit") or 50),
            max_pages=int(cfg.get("max_pages") or 3),
            download_documents=True,
            city_id=cfg.get("city_id"),
        )
    return CustomHtmlSourceAdapter(
        name=source.name,
        listing_url=source.base_url,
        rules=cfg.get("rules") or {},
    )


def adapters_to_run(db: Session) -> list[tuple[str, SourceAdapter]]:
    """Enabled connected sources, or the built-in pair when none are stored."""
    rows = (
        db.query(ConnectedSource)
        .filter(ConnectedSource.enabled.is_(True))
        .order_by(ConnectedSource.id)
        .all()
    )
    if not rows:
        return [(a.__class__.__name__, a) for a in builtin_adapters()]
    return [(row.name, adapter_for_connected(row)) for row in rows]
