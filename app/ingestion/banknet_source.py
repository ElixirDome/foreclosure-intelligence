"""
BankNet (baanknet.com) discovery adapter.

BankNet is the common e-auction portal used by many Indian banks.
This adapter discovers listing / notice URLs so documents can enter
the universal ingest pipeline.

Full PDF download + OCR remains document_ingest's job once a
SourceDocument is produced.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.ingestion.base import SourceAdapter, SourceDocument

BANKNET_HOME = "https://baanknet.com"
# Public pages that often surface auction notices / sale listings
BANKNET_SEED_PATHS = [
    "/",
    "/Home",
    "/Home/Index",
]


class BankNetSourceAdapter(SourceAdapter):
    """
    Discover auction-related links from BankNet.

    fetch() returns lightweight items with document metadata.
    Property extraction is optional; document retention is primary.
    """

    def __init__(self, base_url: str = BANKNET_HOME, timeout: int = 25):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "ForeclosureIntelligenceBot/1.0 "
                    "(+https://github.com/ElixirDome/foreclosure-intelligence)"
                ),
                "Accept": "text/html,application/xhtml+xml",
            }
        )

    def fetch(self):
        discovered: list[dict] = []
        seen: set[str] = set()

        for path in BANKNET_SEED_PATHS:
            url = urljoin(self.base_url + "/", path.lstrip("/"))
            try:
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
            except Exception as exc:
                print(f"BankNet seed failed {url}: {exc}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                text = a.get_text(" ", strip=True)
                full = urljoin(url, href)

                if full in seen:
                    continue
                if not self._looks_relevant(full, text):
                    continue

                seen.add(full)
                discovered.append(
                    {
                        "title": text or full,
                        "url": full,
                        "source_name": "BankNet",
                    }
                )

        print(f"BankNet discovered {len(discovered)} candidate links")
        return discovered

    @staticmethod
    def _looks_relevant(url: str, text: str) -> bool:
        blob = f"{url} {text}".lower()
        keys = (
            "auction",
            "sale notice",
            "e-auction",
            "eauction",
            "sarfaesi",
            "property",
            "tender",
            "notice",
            "pdf",
        )
        if not any(k in blob for k in keys):
            return False
        # Skip pure login / static assets
        if any(x in blob for x in ("login", "javascript:", ".css", ".js")):
            return False
        return True

    def extract(self, item):
        # Discovery-only for now — structured lots come after PDF/OCR ingest.
        return None

    def get_documents(self, item):
        url = item.get("url") if isinstance(item, dict) else None
        title = item.get("title") if isinstance(item, dict) else str(item)
        if not url:
            return []

        content = b""
        mime = "text/html"
        filename = None
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            content = resp.content
            ctype = (resp.headers.get("content-type") or "").lower()
            if "pdf" in ctype or url.lower().endswith(".pdf"):
                mime = "application/pdf"
                filename = url.rstrip("/").split("/")[-1] or "banknet.pdf"
            else:
                mime = "text/html"
                filename = "banknet_page.html"
        except Exception as exc:
            print(f"BankNet fetch document failed {url}: {exc}")

        return [
            SourceDocument(
                source_name="BankNet",
                source_url=url,
                document_type="auction_notice",
                title=title,
                filename=filename,
                mime_type=mime,
                content=content,
            )
        ]
