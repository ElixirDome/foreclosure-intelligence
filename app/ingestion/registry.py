"""Pluggable listing-source registry.

Built-in adapters (PNB, BankNet) and admin-connected sources share the same
registry. A connected source configured for a built-in adapter key replaces
that built-in entry, avoiding a duplicate run of the same adapter.
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
    """Return built-ins plus enabled connected sources without duplicate keys."""
    rows = (
        db.query(ConnectedSource)
        .filter(ConnectedSource.enabled.is_(True))
        .order_by(ConnectedSource.id)
        .all()
    )
    connected_builtin_keys = {
        (row.adapter_key or "").lower()
        for row in rows
        if (row.adapter_key or "").lower() in BUILTIN_KEYS
    }

    adapters: list[tuple[str, SourceAdapter]] = []
    for adapter in builtin_adapters():
        key = (
            "pnb"
            if isinstance(adapter, PNBSourceAdapter)
            else "banknet"
            if isinstance(adapter, BankNetSourceAdapter)
            else None
        )
        if key not in connected_builtin_keys:
            adapters.append((adapter.__class__.__name__, adapter))

    adapters.extend(
        (
            f"connected:{row.id}:{row.name}",
            adapter_for_connected(row),
        )
        for row in rows
    )
    return adapters
