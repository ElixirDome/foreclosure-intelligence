"""
Local PDF source adapter.

Phase 2: the adapter's job is to *locate* the document and optionally
surface structured property candidates. Document storage + chunking
happen in the universal ingest layer.
"""

from pathlib import Path

from app.ingestion.base import SourceAdapter, SourceDocument
from app.services.extraction import extract_properties_from_pages
from app.services.pdf import extract_pages_from_pdf


class PDFSourceAdapter(SourceAdapter):

    def __init__(self, pdf_path: Path):
        self.pdf_path = Path(pdf_path)
        self._evidence_by_item_id: dict = {}
        self._pages: list[str] | None = None

    def _load_pages(self) -> list[str]:
        if self._pages is None:
            self._pages = extract_pages_from_pdf(self.pdf_path)
        return self._pages

    def fetch(self):
        """
        Produce one logical item per extracted property candidate.

        Pages are attached so downstream save can chunk without
        re-reading the PDF.
        """
        pages = self._load_pages()
        results = extract_properties_from_pages(pages)

        items = []
        for result in results:
            item = {
                "property": result.property,
                "evidence": result.evidence,
                "pages": pages,
            }
            self._evidence_by_item_id[id(item)] = result.evidence
            items.append(item)

        # If the PDF has text but no properties matched, still return
        # a document-only item so the file is retained and chunked.
        if not items and any(p.strip() for p in pages):
            items.append({
                "property": None,
                "evidence": [],
                "pages": pages,
                "document_only": True,
            })

        return items

    def extract(self, item):
        if isinstance(item, dict) and item.get("document_only"):
            return None

        if isinstance(item, dict) and "property" in item:
            property_data = item["property"]

            if property_data is None:
                return None

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
            SourceDocument(
                source_name="PDFUpload",
                source_url=str(self.pdf_path.resolve()),
                document_type="auction_notice",
                title=self.pdf_path.name,
                filename=self.pdf_path.name,
                mime_type="application/pdf",
                storage_path=str(self.pdf_path.resolve()),
                content=self.pdf_path.read_bytes(),
            )
        ]
