from pathlib import Path

import requests
from bs4 import BeautifulSoup

from app.ingestion.base import SourceAdapter
from app.services.extraction import extract_properties_from_pages
from app.services.pdf import extract_pages_from_pdf


class PDFSourceAdapter(SourceAdapter):

    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path
        self._evidence_by_item_id = {}

    def fetch(self):
        """
        Parse the supplied PDF into extraction results.

        The network lookup is retained as an informational
        discovery step, but local PDF ingestion is what
        produces the actual items.
        """
        pages = extract_pages_from_pdf(self.pdf_path)

        results = extract_properties_from_pages(pages)

        items = []

        for index, result in enumerate(results):
            item = {
                "property": result.property,
                "evidence": result.evidence,
            }

            self._evidence_by_item_id[id(item)] = result.evidence
            items.append(item)

        return items

    def extract(self, item):
        if isinstance(item, dict) and "property" in item:
            property_data = item["property"]

            if hasattr(property_data, "model_dump"):
                return property_data.model_dump()

            return property_data

        if hasattr(item, "model_dump"):
            return item.model_dump()

        return {
            "address": item.address,
            "area_sqft": item.area_sqft,
            "opening_bid": item.opening_bid,
            "property_type": item.property_type,
            "survey_number": item.survey_number,
            "auction_date": (
                item.auction_start.date()
                if item.auction_start
                else None
            ),
        }

    def get_evidence(self, item):
        if isinstance(item, dict):
            return item.get("evidence", [])

        return []

    def get_documents(self, item):
        return [
            {
                "source_name": "PDFUpload",
                "source_url": str(self.pdf_path),
                "document_type": "auction_notice",
                "title": self.pdf_path.name,
                "content": self.pdf_path.read_bytes(),
            }
        ]
