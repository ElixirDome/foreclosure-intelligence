import json
from datetime import date
from pathlib import Path

from app.ingestion.base import SourceAdapter


class KaveriTransactionAdapter(SourceAdapter):
    """
    Adapter for authorized Kaveri transaction data.

    The input file represents transaction records obtained through
    an authorized Kaveri workflow/export.

    This adapter does not scrape or bypass Kaveri authentication.
    """

    def __init__(self, json_path: str):
        self.json_path = Path(json_path)

    def fetch(self) -> list[dict]:
        if not self.json_path.exists():
            raise FileNotFoundError(
                f"Kaveri transaction file not found: {self.json_path}"
            )

        with self.json_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError(
                "Kaveri transaction file must contain a JSON list."
            )

        return data

    def extract(self, item: dict) -> dict | None:
        property_type = (
            item.get("property_type")
            or item.get("propertyType")
            or ""
        ).strip().lower()

        residential_types = {
            "residential",
            "residential house",
            "residential flat",
            "apartment",
            "flat",
            "house",
            "villa",
        }

        if property_type not in residential_types:
            return None

        address = (
            item.get("address")
            or item.get("property_address")
            or ""
        ).strip()

        if not address:
            return None

        area_sqft = item.get("area_sqft")

        if area_sqft is None:
            return None

        try:
            area_sqft = int(float(area_sqft))
        except (TypeError, ValueError):
            return None

        if area_sqft <= 0:
            return None

        sale_price = item.get("sale_price")

        if sale_price is None:
            return None

        try:
            sale_price = float(sale_price)
        except (TypeError, ValueError):
            return None

        if sale_price <= 0:
            return None

        sale_date = item.get("sale_date")

        if sale_date:
            try:
                sale_date = date.fromisoformat(str(sale_date))
            except ValueError:
                return None
        else:
            sale_date = None

        return {
            "address": address,
            "city": self._clean(item.get("city")),
            "locality": self._clean(item.get("locality")),
            "property_type": property_type,
            "area_sqft": area_sqft,
            "sale_price": sale_price,
            "sale_date": sale_date,
            "source": "Kaveri",
            "source_url": self._clean(item.get("source_url")),
        }

    @staticmethod
    def _clean(value):
        if value is None:
            return None

        value = str(value).strip()

        return value if value else None