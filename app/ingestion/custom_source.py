"""User-connected HTML listing source.

Extraction rules are regexes supplied when the source is connected, e.g.

    {"reserve": "Reserve Price[:\\s]*₹?([\\d,]+)", "emd": "EMD[:\\s]*₹?([\\d,]+)"}
"""

from __future__ import annotations

import re
from typing import Any

import requests
from bs4 import BeautifulSoup

from app.ingestion.base import SourceAdapter, SourceDocument


def _money(text: str, pattern: str | None) -> float | None:
    if not pattern or not text:
        return None
    match = re.search(pattern, text, flags=re.I)
    if not match:
        return None
    raw = match.group(1).replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


class CustomHtmlSourceAdapter(SourceAdapter):
    def __init__(self, name: str, listing_url: str, rules: dict | None = None):
        self.name = name
        self.listing_url = listing_url
        self.rules = rules or {}

    def fetch(self) -> list[Any]:
        response = requests.get(
            self.listing_url,
            timeout=30,
            headers={"User-Agent": "ForeclosureIntelligence/1.0"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select(self.rules.get("item_selector") or "article, .property, tr")
        if not cards:
            return [{"html": response.text, "url": self.listing_url}]
        items = []
        for card in cards[: int(self.rules.get("limit") or 40)]:
            link = card.find("a", href=True)
            items.append(
                {
                    "html": str(card),
                    "text": card.get_text(" ", strip=True),
                    "url": link["href"] if link else self.listing_url,
                    "title": card.get_text(" ", strip=True)[:180],
                }
            )
        return items

    def extract(self, item: Any) -> dict:
        text = item.get("text") or BeautifulSoup(item.get("html") or "", "html.parser").get_text(
            " ", strip=True
        )
        reserve = _money(text, self.rules.get("reserve"))
        emd = _money(text, self.rules.get("emd"))
        return {
            "address": (item.get("title") or text[:240] or "Unknown listing").strip(),
            "reserve_price": reserve,
            "opening_bid": reserve,
            "emd": emd,
            "price": reserve,
            "source_url": item.get("url") or self.listing_url,
            "source_name": self.name,
        }

    def get_documents(self, item: Any) -> list[SourceDocument]:
        html = item.get("html") or ""
        return [
            SourceDocument(
                source_name=self.name,
                source_url=item.get("url") or self.listing_url,
                document_type="listing_page",
                content=html,
                title=item.get("title"),
                mime_type="text/html",
            )
        ]
