import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path

from app.ingestion.base import SourceAdapter
from app.services.pdf import extract_text_from_pdf
from app.services.extraction import extract_properties_from_text


class PDFSourceAdapter(SourceAdapter):

    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path

    def fetch(self):
        url = "https://www.pnb.bank.in/EAuction.aspx"

        response = requests.get(
            url,
            timeout=20,
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        links = soup.find_all("a")

        auction_links = []

        for link in links:
            text = link.get_text(" ", strip=True)

            if "Auction" in text or "auction" in text:
                auction_links.append(text)

        print("AUCTION ENTRIES FOUND:", len(auction_links))

        for entry in auction_links[:10]:
            print("-", entry)

        return []

    def extract(self, item):
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

    def get_documents(self, item):
        return [
            {
                "source_name": "PDFUpload",
                "source_url": str(self.pdf_path),
                "document_type": "auction_notice",
                "title": self.pdf_path.name,
                "content": self.pdf_path.read_bytes(),#Now the saver can calculate a hash from the actual PDF bytes.
            }
        ]

# PDFSourceAdapter.fetch()
#         ↓
# [ExtractedProperty, ExtractedProperty, ...]
#         ↓
# pipeline loops over them
#         ↓
# adapter.extract(one ExtractedProperty)
#         ↓
# one property dict    