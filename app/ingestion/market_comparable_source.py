import csv
from pathlib import Path

from app.ingestion.base import SourceAdapter


class MarketComparableCSVAdapter(SourceAdapter):
    def __init__(self, csv_path: str):
        self.csv_path = Path(csv_path)

    def fetch(self) -> list[dict]:
        if not self.csv_path.exists():
            raise FileNotFoundError(
                f"Comparable data file not found: {self.csv_path}"
            )

        with self.csv_path.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as file:
            return list(csv.DictReader(file))

    def extract(self, item: dict) -> dict:
        area_sqft = int(float(item["area_sqft"]))
        sale_price = float(item["sale_price"])

        if area_sqft <= 0:
            raise ValueError(
                "area_sqft must be greater than 0"
            )

        if sale_price <= 0:
            raise ValueError(
                "sale_price must be greater than 0"
            )

        return {
            "address": item["address"].strip(),

            "city": (
                item["city"].strip()
                if item.get("city")
                else None
            ),

            "locality": (
                item["locality"].strip()
                if item.get("locality")
                else None
            ),

            "property_type": (
                item["property_type"].strip()
                if item.get("property_type")
                else None
            ),

            "area_sqft": area_sqft,
            "sale_price": sale_price,

            "sale_date": (
                item["sale_date"].strip()
                if item.get("sale_date")
                else None
            ),

            "source": item["source"].strip(),

            "source_url": (
                item["source_url"].strip()
                if item.get("source_url")
                else None
            ),
        }