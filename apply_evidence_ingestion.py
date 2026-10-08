from pathlib import Path
from textwrap import dedent
import shutil
import subprocess
import sys

ROOT = Path.cwd()

FILES = [
    Path("app/services/pdf.py"),
    Path("app/services/extraction.py"),
    Path("app/ingestion/pdf_source.py"),
    Path("app/ingestion/pipeline.py"),
    Path("app/ingestion/save.py"),
]

BACKUP_DIR = ROOT / ".refactor_backups" / "evidence_ingestion"

def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")

def backup():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    for path in FILES:
        if not path.exists():
            raise RuntimeError(f"Required file does not exist: {path}")

        destination = BACKUP_DIR / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)

def restore():
    print("\nRestoring backups...")
    for path in FILES:
        backup_path = BACKUP_DIR / path
        if backup_path.exists():
            shutil.copy2(backup_path, path)
    print("Restore complete.")

def run(command):
    print("\n>", " ".join(command))
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}"
        )

backup()

try:
    write_file(
        Path("app/services/pdf.py"),
        r'''
        from pathlib import Path

        from pypdf import PdfReader


        def extract_pages_from_pdf(
            pdf_path: str | Path,
        ) -> list[str]:
            """
            Extract PDF text while preserving page boundaries.

            Page numbers are represented by their list position:
            index 0 = page 1, index 1 = page 2, etc.
            """
            reader = PdfReader(pdf_path)

            pages: list[str] = []

            for page in reader.pages:
                text = page.extract_text() or ""
                pages.append(text)

            return pages


        def extract_text_from_pdf(
            pdf_path: str | Path,
        ) -> str:
            """
            Backwards-compatible full-document text extraction.
            """
            pages = extract_pages_from_pdf(pdf_path)

            return "\n".join(
                page
                for page in pages
                if page
            )
        ''',
    )

    write_file(
        Path("app/services/extraction.py"),
        r'''
        import re
        from datetime import datetime
        from dataclasses import dataclass

        from app.schemas import ExtractedProperty


        @dataclass
        class ExtractedEvidence:
            field: str
            value: str
            page_number: int | None
            source_text: str | None
            extraction_method: str = "regex"
            confidence: float | None = None


        @dataclass
        class PropertyExtractionResult:
            property: ExtractedProperty
            evidence: list[ExtractedEvidence]


        def clean_property_address(
            address: str,
            area_sqft: float | None,
            survey_number: str | None,
        ) -> str:

            if survey_number:
                address = re.sub(
                    rf"\bSy\s+No\s+{re.escape(survey_number)}\s*-\s*",
                    "",
                    address,
                    flags=re.IGNORECASE,
                )

            if area_sqft is not None:
                area_number = str(area_sqft).removesuffix(".0")

                address = re.sub(
                    rf"\b{re.escape(area_number)}\s*Sq\s*Ft\s*-?\s*",
                    "",
                    address,
                    flags=re.IGNORECASE,
                )

            address = re.sub(r"\s*-\s*", " ", address)
            address = re.sub(r"\s+", " ", address)

            return address.strip()


        def _page_for_text(
            pages: list[str],
            value: str | None,
            start_page: int = 1,
        ) -> int | None:
            """
            Find the first page containing a value.

            This is deliberately conservative. If the value cannot
            be located in the page text, page_number remains None.
            """
            if not value:
                return None

            value = str(value).strip()

            if not value:
                return None

            for index, page in enumerate(
                pages[start_page - 1:],
                start=start_page,
            ):
                if value.lower() in page.lower():
                    return index

            return None


        def _source_line(
            pages: list[str],
            value: str | None,
            page_number: int | None,
        ) -> str | None:
            """
            Return the most useful source line containing the value.
            """
            if value is None or page_number is None:
                return None

            page = pages[page_number - 1]

            for line in page.splitlines():
                if value.lower() in line.lower():
                    return line.strip()

            return None


        def _make_evidence(
            field: str,
            value,
            pages: list[str],
            search_value: str | None = None,
            start_page: int = 1,
        ) -> ExtractedEvidence | None:
            if value is None:
                return None

            value_string = str(value)

            page_number = _page_for_text(
                pages=pages,
                value=search_value or value_string,
                start_page=start_page,
            )

            return ExtractedEvidence(
                field=field,
                value=value_string,
                page_number=page_number,
                source_text=_source_line(
                    pages=pages,
                    value=search_value or value_string,
                    page_number=page_number,
                ),
                extraction_method="regex",
            )


        def extract_properties_from_pages(
            pages: list[str],
        ) -> list[PropertyExtractionResult]:
            """
            Extract properties and field-level provenance from
            page-aware PDF text.

            The property extraction rules intentionally remain the
            same as the existing extractor.
            """
            text = "\n".join(pages)

            properties: list[PropertyExtractionResult] = []

            auction_number_match = re.search(
                r"Auction No:\s*(.+)",
                text,
                re.IGNORECASE,
            )

            seller_match = re.search(
                r"Seller:\s*(.+)",
                text,
                re.IGNORECASE,
            )

            auction_start_match = re.search(
                r"Scheduled Auction Start:\s*(\d{2}-\d{2}-\d{2})\s+(\d{2}:\d{2})",
                text,
                re.IGNORECASE,
            )

            auction_close_match = re.search(
                r"Scheduled Auction Close:\s*(\d{2}-\d{2}-\d{2})\s+(\d{2}:\d{2})",
                text,
                re.IGNORECASE,
            )

            auction_number = (
                auction_number_match.group(1).strip()
                if auction_number_match
                else None
            )

            seller_name = (
                seller_match.group(1).strip()
                if seller_match
                else None
            )

            auction_start = None
            if auction_start_match:
                auction_start = datetime.strptime(
                    f"{auction_start_match.group(1)} "
                    f"{auction_start_match.group(2)}",
                    "%d-%m-%y %H:%M",
                )

            auction_close = None
            if auction_close_match:
                auction_close = datetime.strptime(
                    f"{auction_close_match.group(1)} "
                    f"{auction_close_match.group(2)}",
                    "%d-%m-%y %H:%M",
                )

            lot_sections = re.split(
                r"Lot No - Doc No",
                text,
                flags=re.IGNORECASE,
            )

            for section in lot_sections[1:]:

                document_match = re.search(
                    r"\s*(\d+/\d+)",
                    section,
                )

                if not document_match:
                    continue

                document_number = document_match.group(1)

                area_match = re.search(
                    r"(\d+(?:\.\d+)?)\s*Sq\s*Ft",
                    section,
                    re.IGNORECASE,
                )

                opening_bid_match = re.search(
                    r"Start Price in INR\s*-\s*([\d.]+)",
                    section,
                    re.IGNORECASE,
                )

                pre_bid_emd_match = re.search(
                    r"PRE BID EMD:\s*([\d.]+)",
                    section,
                    re.IGNORECASE,
                )

                increment_match = re.search(
                    r"Minimum\s+Increment:\s*([\d.]+)",
                    section,
                    re.IGNORECASE,
                )

                post_emd_match = re.search(
                    r"Post Bid EMD %\s*-\s*([\d.]+)",
                    section,
                    re.IGNORECASE,
                )

                survey_match = re.search(
                    r"(?:Sy No|Survey No)\s*:?\s*([0-9/]+)",
                    section,
                    re.IGNORECASE,
                )

                property_type_match = re.search(
                    r"Product Type\s*-\s*(.*?)\n",
                    section,
                    re.IGNORECASE,
                )

                category_match = re.search(
                    r"Category\s*-\s*(.*?)\n",
                    section,
                    re.IGNORECASE,
                )

                sub_category_match = re.search(
                    r"Sub Category\s*-\s*(.*?)\n",
                    section,
                    re.IGNORECASE,
                )

                defaulter_match = re.search(
                    r"Defaulter Name:\s*(.*?)\n",
                    section,
                    re.IGNORECASE,
                )

                lot_location_match = re.search(
                    r"Lot Location\s*-\s*(.*?)(?=\nState\s*:)",
                    section,
                    re.IGNORECASE | re.DOTALL,
                )

                state_match = re.search(
                    r"Lot State\s*-\s*(.*?)(?=\n|$)",
                    section,
                    re.IGNORECASE,
                )

                address = None

                if lot_location_match:
                    address = re.sub(
                        r"\s+",
                        " ",
                        lot_location_match.group(1),
                    ).strip()

                pincode = None

                if address:
                    pincode_match = re.search(
                        r"\b(\d{6})\b",
                        address,
                    )

                    if pincode_match:
                        pincode = pincode_match.group(1)

                city = None

                if address:
                    city_match = re.search(
                        r",\s*([A-Za-z ]+)\s+\d{6}\s*$",
                        address,
                    )

                    if city_match:
                        city = city_match.group(1).strip()

                area_sqft = (
                    float(area_match.group(1))
                    if area_match
                    else None
                )

                survey_number = (
                    survey_match.group(1)
                    if survey_match
                    else None
                )

                cleaned_address = (
                    clean_property_address(
                        address=address,
                        area_sqft=area_sqft,
                        survey_number=survey_number,
                    )
                    if address
                    else None
                )

                property_type = (
                    property_type_match.group(1).strip()
                    if property_type_match
                    else None
                )

                category = (
                    category_match.group(1).strip()
                    if category_match
                    else None
                )

                sub_category = (
                    sub_category_match.group(1).strip()
                    if sub_category_match
                    else None
                )

                defaulter_name = (
                    defaulter_match.group(1).strip()
                    if defaulter_match
                    else None
                )

                opening_bid = (
                    float(opening_bid_match.group(1))
                    if opening_bid_match
                    else None
                )

                pre_bid_emd = (
                    float(pre_bid_emd_match.group(1))
                    if pre_bid_emd_match
                    else None
                )

                minimum_increment = (
                    float(increment_match.group(1))
                    if increment_match
                    else None
                )

                post_bid_emd_percent = (
                    float(post_emd_match.group(1))
                    if post_emd_match
                    else None
                )

                property_data = ExtractedProperty(
                    lot_number=document_number,
                    document_number=document_number,
                    property_type=property_type,
                    category=category,
                    sub_category=sub_category,
                    defaulter_name=defaulter_name,
                    address=cleaned_address,
                    city=city,
                    state=(
                        state_match.group(1).strip()
                        if state_match
                        else None
                    ),
                    pincode=pincode,
                    area_sqft=area_sqft,
                    survey_number=survey_number,
                    opening_bid=opening_bid,
                    pre_bid_emd=pre_bid_emd,
                    minimum_increment=minimum_increment,
                    post_bid_emd_percent=post_bid_emd_percent,
                    auction_number=auction_number,
                    auction_start=auction_start,
                    auction_close=auction_close,
                    seller_name=seller_name,
                )

                evidence: list[ExtractedEvidence] = []

                evidence_values = [
                    (
                        "lot_number",
                        document_number,
                        document_number,
                    ),
                    (
                        "document_number",
                        document_number,
                        document_number,
                    ),
                    (
                        "property_type",
                        property_type,
                        property_type_match.group(0)
                        if property_type_match
                        else None,
                    ),
                    (
                        "category",
                        category,
                        category_match.group(0)
                        if category_match
                        else None,
                    ),
                    (
                        "sub_category",
                        sub_category,
                        sub_category_match.group(0)
                        if sub_category_match
                        else None,
                    ),
                    (
                        "defaulter_name",
                        defaulter_name,
                        defaulter_match.group(0)
                        if defaulter_match
                        else None,
                    ),
                    (
                        "address",
                        cleaned_address,
                        lot_location_match.group(0)
                        if lot_location_match
                        else None,
                    ),
                    (
                        "city",
                        city,
                        city,
                    ),
                    (
                        "state",
                        (
                            state_match.group(1).strip()
                            if state_match
                            else None
                        ),
                        state_match.group(0)
                        if state_match
                        else None,
                    ),
                    (
                        "pincode",
                        pincode,
                        pincode,
                    ),
                    (
                        "area_sqft",
                        area_sqft,
                        area_match.group(0)
                        if area_match
                        else None,
                    ),
                    (
                        "survey_number",
                        survey_number,
                        survey_match.group(0)
                        if survey_match
                        else None,
                    ),
                    (
                        "opening_bid",
                        opening_bid,
                        opening_bid_match.group(0)
                        if opening_bid_match
                        else None,
                    ),
                    (
                        "pre_bid_emd",
                        pre_bid_emd,
                        pre_bid_emd_match.group(0)
                        if pre_bid_emd_match
                        else None,
                    ),
                    (
                        "minimum_increment",
                        minimum_increment,
                        increment_match.group(0)
                        if increment_match
                        else None,
                    ),
                    (
                        "post_bid_emd_percent",
                        post_bid_emd_percent,
                        post_emd_match.group(0)
                        if post_emd_match
                        else None,
                    ),
                    (
                        "auction_number",
                        auction_number,
                        auction_number_match.group(0)
                        if auction_number_match
                        else None,
                    ),
                    (
                        "seller_name",
                        seller_name,
                        seller_match.group(0)
                        if seller_match
                        else None,
                    ),
                    (
                        "auction_start",
                        auction_start.isoformat()
                        if auction_start
                        else None,
                        auction_start_match.group(0)
                        if auction_start_match
                        else None,
                    ),
                    (
                        "auction_close",
                        auction_close.isoformat()
                        if auction_close
                        else None,
                        auction_close_match.group(0)
                        if auction_close_match
                        else None,
                    ),
                ]

                for field, value, search_value in evidence_values:
                    evidence_item = _make_evidence(
                        field=field,
                        value=value,
                        pages=pages,
                        search_value=search_value,
                    )

                    if evidence_item is not None:
                        evidence.append(evidence_item)

                properties.append(
                    PropertyExtractionResult(
                        property=property_data,
                        evidence=evidence,
                    )
                )

            return properties


        def extract_properties_from_text(
            text: str,
        ) -> list[ExtractedProperty]:
            """
            Backwards-compatible extractor.

            Existing callers still receive exactly the old
            list[ExtractedProperty] result.
            """
            results = extract_properties_from_pages([text])

            return [
                result.property
                for result in results
            ]
        ''',
    )

    write_file(
        Path("app/ingestion/pdf_source.py"),
        r'''
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
        ''',
    )

    write_file(
        Path("app/ingestion/pipeline.py"),
        r'''
        from datetime import datetime, timezone
        import traceback

        from sqlalchemy.orm import Session

        from app.ingestion.base import SourceAdapter
        from app.ingestion.save import save_ingested_properties
        from app.models import IngestionRun


        def run_ingestion(
            db: Session,
            adapter: SourceAdapter,
            user_id: int,
        ):
            ingestion_run = IngestionRun(
                source_name=adapter.__class__.__name__,
                started_at=datetime.now(timezone.utc),
                status="running",
            )

            db.add(ingestion_run)
            db.commit()
            db.refresh(ingestion_run)

            try:
                raw_items = adapter.fetch()

                extracted_items = []

                for item in raw_items:
                    extracted = adapter.extract(item)

                    if extracted is None:
                        continue

                    documents = adapter.get_documents(item)

                    get_evidence = getattr(
                        adapter,
                        "get_evidence",
                        None,
                    )

                    evidence = (
                        get_evidence(item)
                        if get_evidence
                        else []
                    )

                    if isinstance(extracted, list):
                        for property_data in extracted:
                            extracted_items.append({
                                "property": property_data,
                                "documents": documents,
                                "evidence": evidence,
                            })
                    else:
                        extracted_items.append({
                            "property": extracted,
                            "documents": documents,
                            "evidence": evidence,
                        })

                save_result = save_ingested_properties(
                    db=db,
                    properties=extracted_items,
                    user_id=user_id,
                    ingestion_run_id=ingestion_run.id,
                )

                ingestion_run.finished_at = datetime.now(timezone.utc)
                ingestion_run.status = "success"
                ingestion_run.items_found = len(raw_items)

                db.commit()

                return {
                    "ingestion_run_id": ingestion_run.id,
                    "items_found": len(raw_items),
                    "items_extracted": len(extracted_items),
                    "saved": save_result["saved"],
                    "skipped": save_result["skipped"],
                }

            except Exception as exc:

                traceback.print_exc()

                ingestion_run.finished_at = datetime.now(timezone.utc)
                ingestion_run.status = "failed"
                ingestion_run.error_message = str(exc)

                db.commit()

                return {
                    "ingestion_run_id": ingestion_run.id,
                    "items_found": 0,
                    "items_extracted": 0,
                    "saved": [],
                    "skipped": [],
                    "error": str(exc),
                }
        ''',
    )

    write_file(
        Path("app/ingestion/save.py"),
        r'''
        import hashlib
        from datetime import datetime, timezone

        from sqlalchemy.orm import Session

        from app.models import (
            Document,
            Evidence,
            IngestionRun,
            Property,
            PropertyDocument,
        )
        from app.services.normalization import create_property_key


        def _evidence_value(evidence):
            if isinstance(evidence, dict):
                return evidence

            return {
                "field": evidence.field,
                "value": evidence.value,
                "page_number": evidence.page_number,
                "source_text": evidence.source_text,
                "extraction_method": evidence.extraction_method,
                "confidence": evidence.confidence,
            }


        def save_ingested_properties(
            db: Session,
            properties: list[dict],
            user_id: int,
            ingestion_run_id: int,
        ):
            saved = []
            skipped = []

            for item in properties:
                property_data = item["property"]
                documents = item["documents"]
                evidence_items = item.get("evidence", [])

                property_key = create_property_key(
                    address=property_data["address"],
                    area_sqft=property_data.get("area_sqft"),
                    property_type=property_data.get("property_type"),
                    survey_number=property_data.get("survey_number"),
                )

                property_obj = (
                    db.query(Property)
                    .filter(Property.property_key == property_key)
                    .first()
                )

                if property_obj:
                    if not property_obj.city and property_data.get("city"):
                        property_obj.city = property_data["city"]

                    if not property_obj.locality and property_data.get("locality"):
                        property_obj.locality = property_data["locality"]

                    skipped.append({
                        "property_id": property_obj.id,
                        "address": property_obj.address,
                        "reason": "duplicate",
                    })

                else:
                    property_obj = Property(
                        user_id=user_id,
                        address=property_data["address"],
                        area_sqft=property_data.get("area_sqft"),
                        opening_bid=property_data.get("opening_bid"),
                        price=property_data.get("opening_bid"),
                        property_type=property_data.get("property_type"),
                        survey_number=property_data.get("survey_number"),
                        auction_date=property_data.get("auction_date"),
                        foreclosure_status="scheduled",
                        property_key=property_key,
                    )

                    db.add(property_obj)
                    db.flush()
                    saved.append(property_obj)

                for document_data in documents:
                    content = document_data.get("content")

                    if isinstance(content, str):
                        content = content.encode("utf-8")

                    content_hash = (
                        hashlib.sha256(content).hexdigest()
                        if content is not None
                        else None
                    )

                    now = datetime.now(timezone.utc)

                    document = None

                    if content_hash:
                        document = (
                            db.query(Document)
                            .filter(
                                Document.content_hash == content_hash
                            )
                            .first()
                        )

                    if document is None:
                        document = Document(
                            source_name=document_data["source_name"],
                            source_url=document_data["source_url"],
                            document_type=document_data["document_type"],
                            title=document_data.get("title"),
                            content_hash=content_hash,
                            first_seen_at=now,
                            last_seen_at=now,
                        )

                        db.add(document)
                        db.flush()

                    else:
                        document.last_seen_at = now

                    existing_relationship = (
                        db.query(PropertyDocument)
                        .filter(
                            PropertyDocument.property_id == property_obj.id,
                            PropertyDocument.document_id == document.id,
                        )
                        .first()
                    )

                    if not existing_relationship:
                        property_document = PropertyDocument(
                            property_id=property_obj.id,
                            document_id=document.id,
                            relationship_type=document_data[
                                "document_type"
                            ],
                        )

                        db.add(property_document)

                    # Evidence belongs to the property + document.
                    # We avoid inserting the same field/value/page
                    # repeatedly when the same PDF is ingested again.
                    for raw_evidence in evidence_items:
                        evidence_data = _evidence_value(raw_evidence)

                        existing_evidence = (
                            db.query(Evidence)
                            .filter(
                                Evidence.property_id == property_obj.id,
                                Evidence.document_id == document.id,
                                Evidence.field == evidence_data["field"],
                                Evidence.value == evidence_data["value"],
                                Evidence.page_number
                                == evidence_data["page_number"],
                            )
                            .first()
                        )

                        if existing_evidence:
                            continue

                        db.add(
                            Evidence(
                                property_id=property_obj.id,
                                document_id=document.id,
                                field=evidence_data["field"],
                                value=evidence_data["value"],
                                page_number=evidence_data["page_number"],
                                source_text=evidence_data["source_text"],
                                extraction_method=evidence_data[
                                    "extraction_method"
                                ],
                                confidence=evidence_data["confidence"],
                            )
                        )

            ingestion_run = (
                db.query(IngestionRun)
                .filter(IngestionRun.id == ingestion_run_id)
                .first()
            )

            if ingestion_run:
                ingestion_run.items_created = len(saved)
                ingestion_run.items_skipped = len(skipped)

            db.commit()

            for property_obj in saved:
                db.refresh(property_obj)

            return {
                "saved": saved,
                "skipped": skipped,
            }
        ''',
    )

    # Basic syntax validation.
    run([
        sys.executable,
        "-m",
        "compileall",
        "-q",
        "app",
    ])

    # Run the existing test suite.
    run([
        sys.executable,
        "-m",
        "pytest",
    ])

    # Verify Alembic is synchronized.
    run([
        sys.executable,
        "-m",
        "alembic",
        "check",
    ])

    print("\n========================================")
    print("Evidence ingestion refactor completed.")
    print("Backups:", BACKUP_DIR)
    print("========================================")

except Exception as exc:
    print("\nREFactor failed:")
    print(exc)
    restore()
    sys.exit(1)
