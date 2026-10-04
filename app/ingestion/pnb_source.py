import re
import tempfile
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from app.services.property_classifier import is_residential_property
from app.ingestion.base import SourceAdapter
from app.services.pnb_extraction import extract_pnb_property
from app.services.pnb_extraction import extract_pnb_properties


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

        for row in soup.find_all("tr"):
            postback_link = row.find(
                "a",
                href=re.compile(r"__doPostBack"),
            )

            if postback_link is None:
                continue

            title = postback_link.get_text(" ", strip=True) or "Untitled PNB auction document"

            if not title:
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

            auction_items.append(
                {
                    "title": title,
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

            # We currently only want property-sale notices.
            title_lower = (title or "").lower()

            if (
                "sale" not in title_lower
                and "auction" not in title_lower
                and "notice" not in title_lower
            ):
                print("  Skipping: not a sale/auction notice")
                continue

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

            print(
                f"  Downloaded: {len(pdf_bytes)} bytes"
            )

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

    def extract(self, item):
        text = self._extract_ocr_text(item["pdf_path"])

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

    def _extract_ocr_text(self, pdf_path):
        import time

        from pdf2image import convert_from_path
        import pytesseract

        start = time.perf_counter()

        print("  [1/3] Rendering PDF...")

        pages = convert_from_path(
            pdf_path,
            dpi=200,
            poppler_path=r"C:\Dev\poppler-26.09.0\Library\bin",
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