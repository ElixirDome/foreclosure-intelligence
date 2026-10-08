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
