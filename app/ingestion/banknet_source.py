"""
BankNet (baanknet.com) property ingestion via official listing API.

Endpoint (discovered via browser Network):
  POST https://baanknet.com/api/v1/auction/detail/auction-listing

Response hits use Elasticsearch shape:
  data.data[]._index == "psba_auction_property"
  data.data[]._source == property + auction fields + documents
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

from app.ingestion.base import SourceAdapter, SourceDocument

LISTING_URL = "https://baanknet.com/api/v1/auction/detail/auction-listing"
CDN_BASE = "https://cdn.baanknet.com"

PROPERTY_TYPE_RESIDENTIAL = 1
PROPERTY_TYPE_COMMERCIAL = 2

STATUS_FILTERS = (
    "upcoming",
    "live",
    "completed",
)

AUCTION_STATUS_TO_FORECLOSURE = {
    "upcoming": "upcoming",
    "live": "active",
    "completed": "sold",
    "sold": "sold",
    "cancelled": "cancelled",
    "canceled": "cancelled",
}


class BankNetSourceAdapter(SourceAdapter):
    """
    Fetch auction properties from BankNet listing API and map to
    Property + Document payloads for run_ingestion.
    """

    def __init__(
        self,
        *,
        city_id: int | None = None,
        property_type_ids: list[int] | None = None,
        auction_statuses: list[str] | None = None,
        limit: int = 50,
        max_pages: int = 5,
        upcoming_within_days: int = 30,
        timeout: int = 30,
        download_documents: bool = True,
    ):
        self.city_id = city_id
        self.property_type_ids = property_type_ids or [
            PROPERTY_TYPE_RESIDENTIAL,
            PROPERTY_TYPE_COMMERCIAL,
        ]
        self.auction_statuses = auction_statuses or list(STATUS_FILTERS)
        self.limit = limit
        self.max_pages = max_pages
        self.upcoming_within_days = upcoming_within_days
        self.timeout = timeout
        self.download_documents = download_documents

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": "https://baanknet.com",
                "Referer": "https://baanknet.com/property-listing",
            }
        )

    def fetch(self) -> list[dict[str, Any]]:
        horizon = (
            datetime.now(timezone.utc)
            + timedelta(days=self.upcoming_within_days)
        ).isoformat().replace("+00:00", "Z")

        seen: set[str] = set()
        items: list[dict[str, Any]] = []

        for status in self.auction_statuses:
            for type_id in self.property_type_ids:
                page = 1
                total_pages = None
                while page <= self.max_pages:
                    if total_pages is not None and page > total_pages:
                        break

                    body: dict[str, Any] = {
                        "auctionStatus": status,
                        "limit": self.limit,
                        "sort": {"type": "closest"},
                        # BankNet pagination: currentPage in response
                        "page": page,
                        "currentPage": page,
                        "search": {
                            "propertyTypeId": type_id,
                            "upcomingWithinDays": horizon,
                        },
                    }
                    if self.city_id is not None:
                        body["search"]["cityId"] = self.city_id

                    try:
                        resp = self.session.post(
                            LISTING_URL,
                            json=body,
                            timeout=self.timeout,
                        )
                        resp.raise_for_status()
                        payload = resp.json()
                    except Exception as exc:
                        print(
                            f"BankNet listing failed "
                            f"status={status} type={type_id} page={page}: {exc}"
                        )
                        break

                    hits = self._extract_hits(payload)
                    meta = self._extract_page_meta(payload)
                    if meta.get("total_pages") is not None:
                        total_pages = int(meta["total_pages"])

                    if not hits:
                        break

                    new_on_page = 0
                    for hit in hits:
                        source = hit.get("_source") or hit
                        key = self._item_key(source)
                        if key in seen:
                            continue
                        seen.add(key)
                        hit["_banknet_filter_status"] = status
                        items.append(hit)
                        new_on_page += 1

                    print(
                        f"BankNet status={status} typeId={type_id} "
                        f"page={page}/{total_pages or '?'}: "
                        f"{len(hits)} hits, {new_on_page} new "
                        f"(total≈{meta.get('total', '?')})"
                    )

                    # Stop at last page from API metadata
                    if total_pages is not None and page >= total_pages:
                        break
                    if len(hits) < self.limit:
                        break
                    page += 1

        print(f"BankNet fetch total unique items: {len(items)}")
        return items

    @staticmethod
    def _extract_hits(payload: Any) -> list[dict]:
        if not isinstance(payload, dict):
            return []
        data = payload.get("data")
        if isinstance(data, dict):
            inner = data.get("data")
            if isinstance(inner, list):
                return [h for h in inner if isinstance(h, dict)]
        if isinstance(data, list):
            return [h for h in data if isinstance(h, dict)]
        return []

    @staticmethod
    def _item_key(source: dict) -> str:
        return str(
            source.get("propertyUniqueId")
            or source.get("auctionId")
            or source.get("propertyDetailId")
            or id(source)
        )

    def extract(self, item: dict) -> dict | None:
        source = item.get("_source") if isinstance(item, dict) else None
        if not isinstance(source, dict):
            source = item if isinstance(item, dict) else None
        if not source:
            return None

        address = (source.get("address") or "").strip()
        if not address:
            heading = (source.get("propertyHeading") or "").strip()
            locality = (source.get("locality") or "").strip()
            city = (source.get("cityName") or "").strip()
            address = heading or ", ".join(p for p in (locality, city) if p)
        if not address:
            return None

        area = self._parse_area(source.get("carpetAreaSqft"))
        if area is None:
            area = self._parse_area(source.get("builtupAreaSqft"))

        reserve = source.get("reservePrice")
        try:
            opening_bid = float(reserve) if reserve is not None else None
        except (TypeError, ValueError):
            opening_bid = None

        auction_date = self._parse_date(
            source.get("auctionFrom") or source.get("auctionTo")
        )

        filter_status = item.get("_banknet_filter_status")
        foreclosure = self._map_status(
            source.get("auctionStatus"),
            filter_status,
        )

        prop_type = source.get("propertyType")
        if isinstance(prop_type, str):
            prop_type = prop_type.strip().lower() or None
        else:
            prop_type = None

        unique = source.get("propertyUniqueId")

        return {
            "address": address[:2000],
            "city": (source.get("cityName") or None),
            "locality": (source.get("locality") or "").strip() or None,
            "area_sqft": int(area) if area is not None else None,
            "opening_bid": opening_bid,
            "property_type": prop_type,
            "survey_number": str(unique) if unique else None,
            "auction_date": auction_date,
            "foreclosure_status": foreclosure,
            "bank_name": source.get("propertyBankName"),
            "property_unique_id": unique,
            "auction_id": source.get("auctionId"),
            "possession": source.get("propertyPossessionType"),
        }

    def get_documents(self, item: dict) -> list[SourceDocument]:
        source = item.get("_source") if isinstance(item, dict) else None
        if not isinstance(source, dict):
            return []

        bank = source.get("propertyBankName") or "BankNet"
        unique = source.get("propertyUniqueId") or source.get("auctionId")
        detail_id = source.get("propertyDetailId")
        title = source.get("propertyHeading") or f"BankNet {unique}"

        docs: list[SourceDocument] = []
        auction_docs = source.get("auctionDocuments") or []

        for doc in auction_docs:
            if not isinstance(doc, dict):
                continue
            filepath = doc.get("filepath") or ""
            filename = doc.get("filename") or "auction.pdf"
            if not filepath:
                continue
            url = filepath
            if not filepath.startswith("http"):
                url = f"{CDN_BASE}/{filepath.lstrip('/')}"

            content: bytes | str = b""
            if self.download_documents:
                try:
                    r = self.session.get(url, timeout=self.timeout)
                    r.raise_for_status()
                    content = r.content
                except Exception as exc:
                    print(f"BankNet document download failed {url}: {exc}")
                    content = b""

            docs.append(
                SourceDocument(
                    source_name=str(bank).strip() or "BankNet",
                    source_url=url,
                    document_type="auction_notice",
                    title=doc.get("description") or title,
                    filename=filename,
                    mime_type="application/pdf",
                    content=content,
                )
            )

        if detail_id:
            listing_url = f"https://baanknet.com/view-property/{detail_id}"
        else:
            listing_url = "https://baanknet.com/property-listing"

        if not docs:
            docs.append(
                SourceDocument(
                    source_name=str(bank).strip() or "BankNet",
                    source_url=listing_url,
                    document_type="auction_listing",
                    title=title,
                    filename=None,
                    mime_type="text/html",
                    content=title or listing_url,
                )
            )

        return docs

    def get_evidence(self, item: dict) -> list[dict]:
        source = item.get("_source") if isinstance(item, dict) else None
        if not isinstance(source, dict):
            return []

        evidence: list[dict] = []
        pairs = [
            ("opening_bid", source.get("reservePrice"), "reservePrice"),
            ("address", source.get("address"), "address"),
            ("property_type", source.get("propertyType"), "propertyType"),
            ("auction_date", source.get("auctionFrom"), "auctionFrom"),
            (
                "possession",
                source.get("propertyPossessionType"),
                "propertyPossessionType",
            ),
        ]
        for field, value, key in pairs:
            if value is None or value == "":
                continue
            evidence.append(
                {
                    "field": field,
                    "value": str(value),
                    "source_text": f"{key}: {value}",
                    "extraction_method": "banknet_api",
                    "confidence": 0.95,
                    "page_number": None,
                }
            )
        return evidence

    @staticmethod
    def _parse_area(raw: Any) -> float | None:
        if raw is None:
            return None
        try:
            return float(str(raw).replace(",", "").strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_date(raw: Any) -> date | None:
        if not raw:
            return None
        text = str(raw).strip()
        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            return datetime.fromisoformat(text).date()
        except ValueError:
            try:
                return datetime.strptime(text[:10], "%Y-%m-%d").date()
            except ValueError:
                return None

    @staticmethod
    def _map_status(api_status: Any, filter_status: str | None) -> str:
        if filter_status:
            mapped = AUCTION_STATUS_TO_FORECLOSURE.get(
                str(filter_status).lower().strip()
            )
            if mapped:
                return mapped
        if api_status is not None:
            key = str(api_status).lower().strip()
            if key in AUCTION_STATUS_TO_FORECLOSURE:
                return AUCTION_STATUS_TO_FORECLOSURE[key]
        return "scheduled"
