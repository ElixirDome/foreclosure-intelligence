import os
import re
import tempfile
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from app.services.property_classifier import is_residential_property
from app.ingestion.base import SourceAdapter
from app.services.pnb_extraction import extract_pnb_property
from app.services.pnb_extraction import extract_pnb_properties
from app.services.live_events import broker

NON_PROPERTY_KEYWORDS = (
    "vehicle", "vehicles", "car", "cars", "bus", "buses", "truck", "trucks",
    "tractor", "tractors", "scrap", "furniture", "stationery", "computer", "printer",
    "dead stock", "air conditioner", "generator", "two wheeler", "four wheeler",
    "almirah", "old tyre", "unserviceable",
)


class PNBSourceAdapter(SourceAdapter):

    def fetch(self):
        url = "https://www.pnb.bank.in/EAuction.aspx"

        session = requests.Session()

        # ---------------------------------------------------------
        # 1. Load auction page
        # ---------------------------------------------------------

        response = session.get(
            url,
            timeout=20,
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        # ---------------------------------------------------------
        # 2. Collect hidden ASP.NET fields
        # ---------------------------------------------------------

        form_data = {}

        for field in soup.select(
            "input[type=hidden]"
        ):
            name = field.get("name")

            if name:
                form_data[name] = field.get(
                    "value",
                    "",
                )

        # ---------------------------------------------------------
        # 3. Discover auction rows
        # ---------------------------------------------------------

        auction_items = []
        seen_targets: set[tuple[str, str]] = set()

        for row in soup.find_all("tr"):
            postback_link = row.find(
                "a",
                href=re.compile(r"__doPostBack"),
            )

            if postback_link is None:
                continue

            title = postback_link.get_text(" ", strip=True) or "Untitled PNB auction document"
            clean_title = title.strip()

            if not clean_title:
                continue

            # Skip pagination numbers and navigation controls (e.g., "1", "2", "...", "Next")
            if (
                clean_title.isdigit()
                or len(clean_title) <= 2
                or clean_title.lower() in {"next", "prev", "previous", "first", "last", "...", "more", "select"}
            ):
                continue

            href = postback_link.get(
                "href",
                "",
            )

            match = re.search(
                r"__doPostBack\('([^']*)','([^']*)'\)",
                href,
            )

            if match is None:
                continue

            target_pair = (match.group(1), match.group(2))
            if target_pair in seen_targets:
                continue
            seen_targets.add(target_pair)

            auction_items.append(
                {
                    "title": clean_title,
                    "event_target": match.group(1),
                    "event_argument": match.group(2),
                }
            )

        print("\nAUCTIONS DISCOVERED")
        print("-------------------")
        print("Count:", len(auction_items))

        # ---------------------------------------------------------
        # 4. Download sale notices
        # ---------------------------------------------------------

        downloaded_items = []

        for index, auction in enumerate(
            auction_items,
            start=1,
        ):
            title = auction["title"]

            print(
                f"\n[{index}/{len(auction_items)}] "
                f"{title}"
            )

            # We currently only want real estate / property-sale notices.
            title_lower = (title or "").lower()

            if (
                "sale" not in title_lower
                and "auction" not in title_lower
                and "notice" not in title_lower
            ):
                print("  Skipping: not a sale/auction notice")
                continue

            # Exclude movable assets / non-real-estate notices (vehicles, scrap, etc.)
            if any(kw in title_lower for kw in NON_PROPERTY_KEYWORDS):
                print("  Skipping: movable asset / non-property notice")
                continue

            # Emit granular SSE progress for live UI update
            broker.publish(
                "ingestion_status",
                {
                    "source": "PNBSourceAdapter",
                    "stage": "downloading_pdf",
                    "current": index,
                    "total": len(auction_items),
                    "item_title": title,
                    "timestamp": time.time(),
                },
            )

            post_data = form_data.copy()

            post_data["__EVENTTARGET"] = auction[
                "event_target"
            ]

            post_data["__EVENTARGUMENT"] = auction[
                "event_argument"
            ]

            post_response = session.post(
                url,
                data=post_data,
                timeout=20,
            )

            post_response.raise_for_status()

            content_type = post_response.headers.get(
                "Content-Type",
                "",
            )

            if "application/pdf" not in content_type.lower():
                print(
                    "  Skipping: response was not PDF"
                )
                continue

            pdf_bytes = post_response.content

            if not pdf_bytes.startswith(b"%PDF"):
                print(
                    "  Skipping: invalid PDF"
                )
                continue

            temp_file = tempfile.NamedTemporaryFile(
                suffix=".pdf",
                delete=False,
            )

            temp_file.write(pdf_bytes)
            temp_file.close()

            pdf_path = Path(
                temp_file.name
            )

            print(f"  Downloaded: {len(pdf_bytes)} bytes")
            print(f"  PDF path: {pdf_path}")

            downloaded_items.append(
                {
                    "pdf_path": pdf_path,
                    "source_url": post_response.url,
                    "title": title,
                }
            )

        print(
            "\nPDFs DOWNLOADED:",
            len(downloaded_items),
        )

        return downloaded_items

    def _extract_native_text(self, pdf_path):
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(pdf_path))
            pages = []
            for page in reader.pages:
                pages.append(page.extract_text() or "")
            return "\n".join(pages).strip()
        except Exception:
            return ""

    def _get_text(self, pdf_path):
        native = self._extract_native_text(pdf_path)
        if len(native) >= 200:
            return native
        return self._extract_ocr_text(pdf_path)

    def extract(self, item):
        title = item.get("title", "")
        broker.publish(
            "ingestion_status",
            {
                "source": "PNBSourceAdapter",
                "stage": "extracting_text",
                "item_title": title,
                "timestamp": time.time(),
            },
        )
        text = self._get_text(item["pdf_path"])
        print("\n--- OCR TEXT SAMPLE ---")
        print(repr(text[:2500]))
        print("--- END OCR SAMPLE ---\n")
    
        properties = extract_pnb_properties(text)

        if not properties:
            print("  Skipping document: no residential property found")
            return None

        valid_properties = []

        for property_data in properties:
            if not property_data.get("address"):
                continue
            print(
            "  Location:",
            property_data.get("city"),
            "|",
            property_data.get("locality"),
            )
            valid_properties.append(property_data)

        if not valid_properties:
            print("  Skipping residential document: address not found")
            return None

        print(
            f"  Extracted {len(valid_properties)} residential "
            f"property/properties"
        )

        return valid_properties

    def get_documents(self, item):
        return [
            {
                "source_name": "PNB",
                "source_url": item["source_url"],
                "document_type": "auction_notice",
                "title": item["title"],
                "content": item["pdf_path"].read_bytes(),
            }
        ]

    def get_evidence(self, item):
        text = self._get_text(item["pdf_path"])
        properties = extract_pnb_properties(text) or []
        evidence = []
        for prop in properties:
            if prop.get("address"):
                evidence.append({
                    "field": "address",
                    "value": prop["address"],
                    "source_text": prop["address"][:200],
                    "extraction_method": "regex_structured",
                    "confidence": 0.95,
                })
            if prop.get("reserve_price") is not None:
                evidence.append({
                    "field": "reserve_price",
                    "value": str(prop["reserve_price"]),
                    "source_text": f"Reserve Price: {prop['reserve_price']}",
                    "extraction_method": "regex_structured",
                    "confidence": 0.95,
                })
            if prop.get("emd") is not None:
                evidence.append({
                    "field": "emd",
                    "value": str(prop["emd"]),
                    "source_text": f"EMD: {prop['emd']}",
                    "extraction_method": "regex_structured",
                    "confidence": 0.95,
                })
            if prop.get("auction_date"):
                evidence.append({
                    "field": "auction_date",
                    "value": str(prop["auction_date"]),
                    "source_text": f"Auction Date: {prop['auction_date']}",
                    "extraction_method": "regex_structured",
                    "confidence": 0.95,
                })
        return evidence

    def _extract_ocr_text(self, pdf_path):
        import time

        from pdf2image import convert_from_path
        import pytesseract

        start = time.perf_counter()

        print("  [1/3] Rendering PDF...")

        configured_poppler = os.getenv("POPPLER_PATH")
        if not configured_poppler:
            # Preserve the developer's existing Windows setup when present,
            # but do not require that machine-specific path elsewhere.
            default_poppler = Path(
                r"C:\Dev\poppler-26.09.0\Library\bin"
            )
            configured_poppler = (
                str(default_poppler) if default_poppler.is_dir() else None
            )

        pages = convert_from_path(
            pdf_path,
            dpi=200,
            poppler_path=configured_poppler,
        )

        print(
            f"  Rendered {len(pages)} pages in "
            f"{time.perf_counter() - start:.2f}s"
        )

        all_text = []

        print("  [2/3] Running OCR...")

        ocr_start = time.perf_counter()

        for index, page in enumerate(
            pages,
            start=1,
        ):
            print(
                f"    OCR page {index}/{len(pages)}..."
            )

            text = pytesseract.image_to_string(page)
            all_text.append(text)

        print(
            f"  OCR completed in "
            f"{time.perf_counter() - ocr_start:.2f}s"
        )

        print("  [3/3] Combining OCR text...")

        return "\n".join(all_text)