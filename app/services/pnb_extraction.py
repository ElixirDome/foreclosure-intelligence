import re
from datetime import datetime


def _parse_date(text: str):
    match = re.search(
        r"(\d{2}[./-]\d{2}[./-]\d{4})",
        text,
    )

    if not match:
        return None

    date_text = match.group(1).replace("/", ".").replace("-", ".")

    try:
        return datetime.strptime(date_text, "%d.%m.%Y").date()
    except ValueError:
        return None


def _parse_area_sqft(text: str):
    # Square metres
    match = re.search(
        r"([\d,.]+)\s*Sq\.?\s*M(?:tr|eter|etre)?",
        text,
        re.IGNORECASE,
    )

    if match:
        value = float(match.group(1).replace(",", ""))
        return round(value * 10.7639)

    # Square feet
    match = re.search(
        r"([\d,.]+)\s*Sq\.?\s*(?:Ft|Feet)",
        text,
        re.IGNORECASE,
    )

    if match:
        return round(float(match.group(1).replace(",", "")))

    # Square yards
    match = re.search(
        r"([\d,.]+)\s*(?:Sq\.?\s*Yards?|Square\s*Yards?)",
        text,
        re.IGNORECASE,
    )

    if match:
        value = float(match.group(1).replace(",", ""))
        return round(value * 9)

    return None


def _parse_price(text: str):
    match = re.search(
        r"(?:Reserve Price|R\.P\.?)"
        r"\s*[:\-]?\s*"
        r"(?:Rs\.?|₹)?\s*"
        r"([\d,]+(?:\.\d+)?)"
        r"\s*(?:lakh|lac)?",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    value = float(match.group(1).replace(",", ""))

    if re.search(
        r"\b(?:lakh|lac)\b",
        match.group(0),
        re.IGNORECASE,
    ):
        value *= 100000

    return value


def _parse_survey_number(text: str):
    match = re.search(
        r"(?:Survey No\.?|Sy\. No\.?|Survey Number|"
        r"Khasra No\.?|Khasra Number)"
        r"\s*[:\-]?\s*([A-Za-z0-9./-]+)",
        text,
        re.IGNORECASE,
    )

    if match:
        return match.group(1)

    return None


def _extract_address(text: str):
    # Example:
    # Residential Property situated at Plot No. 198...
    match = re.search(
    r"Residential\s+(?:Property|House)"
    r"\s+(?:situated|located|standing)"
    r"\s+(?:at|on)\s+(.+?)"
    r"(?:\bMeasuring\b|\bBounded\b|\bReserve Price\b|\bEMD\b|\n\s*\d+\s*[.)])",
    text,
    re.IGNORECASE | re.DOTALL,
)

    if match:
        address = match.group(1)
        address = re.sub(r"\s+", " ", address)
        return address.strip(" ,.-")

    # Example:
    # All part & parcel of Residential House measuring...
    match = re.search(
        r"(?:All\s+part\s*(?:&|and)\s*parcel\s+of\s+)"
        r"(Residential\s+(?:House|Property).+?)"
        r"(?=\bmeasuring\b)",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if match:
        address = re.sub(r"\s+", " ", match.group(1))
        return address.strip(" ,.-")

    # Example:
    # All that part and parcel of the Residential Property situated...
    match = re.search(
        r"All\s+that\s+part\s+and\s+parcel\s+of\s+the\s+"
        r"(Residential\s+(?:House|Property).+?)"
        r"(?=\bmeasuring\b|\bTotal Area\b)",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if match:
        address = re.sub(r"\s+", " ", match.group(1))
        return address.strip(" ,.-")

    return None


def extract_pnb_property(text: str) -> dict:
    """
    Extract one residential property from a PNB section.
    """

    return {
        "address": _extract_address(text),
        "area_sqft": _parse_area_sqft(text),
        "opening_bid": _parse_price(text),
        "auction_date": _parse_date(text),
        "property_type": "Residential Property",
        "survey_number": _parse_survey_number(text),
    }


def extract_location(address: str) -> tuple[str | None, str | None]:
    """
    Extract a best-effort city and locality from an Indian property address.

    This is intentionally conservative. If the address does not contain
    enough information, None is returned rather than inventing a location.
    """

    parts = [
        part.strip()
        for part in address.split(",")
        if part.strip()
    ]

    if not parts:
        return None, None

    # Remove PIN-code suffixes such as "- 342014".
    parts = [
        re.sub(r"\s*[-–—]?\s*\d{6}\s*$", "", part).strip()
        for part in parts
    ]

    parts = [part for part in parts if part]

    if not parts:
        return None, None

    # Common Indian state / UT names and abbreviations.
    state_patterns = [
        r"\bU\.?P\.?\b",
        r"\bUttar Pradesh\b",
        r"\bKarnataka\b",
        r"\bMaharashtra\b",
        r"\bTamil Nadu\b",
        r"\bKerala\b",
        r"\bTelangana\b",
        r"\bAndhra Pradesh\b",
        r"\bRajasthan\b",
        r"\bGujarat\b",
        r"\bHaryana\b",
        r"\bPunjab\b",
        r"\bHimachal Pradesh\b",
        r"\bUttarakhand\b",
        r"\bBihar\b",
        r"\bJharkhand\b",
        r"\bOdisha\b",
        r"\bWest Bengal\b",
        r"\bAssam\b",
        r"\bGoa\b",
        r"\bDelhi\b",
        r"\bNCT of Delhi\b",
        r"\bMadhya Pradesh\b",
        r"\bChhattisgarh\b",
        r"\bChandigarh\b",
    ]

    state_index = None

    for index, part in enumerate(parts):
        if any(
            re.search(pattern, part, re.IGNORECASE)
            for pattern in state_patterns
        ):
            state_index = index
            break

    # If a state appears at the end, the part immediately before it
    # is usually the city.
    if state_index is not None and state_index > 0:
        city = parts[state_index - 1]

        locality = (
            parts[state_index - 2]
            if state_index >= 2
            else None
        )

        return city, locality

    # Otherwise, when a PIN is present and no state is explicit,
    # use the final address component as the city.
    if len(parts) >= 2:
        city = parts[-1]
        locality = parts[-2]

        return city, locality

    return parts[0], None


def extract_pnb_properties(text: str) -> list[dict]:
    """
    Extract all residential properties from a PNB auction notice.

    A single PNB document can contain:

    - industrial properties
    - commercial properties
    - agricultural land
    - residential properties

    We only extract sections explicitly identified as
    Residential Property or Residential House.
    """

    candidates = []

    matches = list(
        re.finditer(
            r"\bResidential\s+(?:Property|House)\b",
            text,
            re.IGNORECASE,
        )
    )

    for match in matches:
        # Include some text before the residential phrase because
        # the address may begin immediately before it.
        start = max(0, match.start() - 500)

        # Look for the beginning of the next numbered lot/section.
        remaining_text = text[match.end():]

        next_match = re.search(
            r"\n\s*(?:Lot\s*)?\d+\s*[.)]"
            r"|\n\s*[A-Z]\s*\)",
            remaining_text,
            re.IGNORECASE,
        )

        if next_match:
            end = match.end() + next_match.start()
        else:
            end = min(
                len(text),
                match.end() + 2500,
            )

        section = text[start:end]

        property_data = extract_pnb_property(section)

        if not property_data["address"]:
            # Try a larger section if the first window was too small.
            section = text[
                start:min(len(text), match.end() + 4000)
            ]

            property_data = extract_pnb_property(section)

        if property_data["address"]:
            city, locality = extract_location(
                property_data["address"]
            )

            property_data["city"] = city
            property_data["locality"] = locality

            candidates.append(property_data)

    # Remove repeated OCR sections / duplicate occurrences.
    unique_properties = []
    seen = set()

    for property_data in candidates:
        key = (
            property_data.get("address"),
            property_data.get("area_sqft"),
            property_data.get("opening_bid"),
            property_data.get("survey_number"),
        )

        if key in seen:
            continue

        seen.add(key)
        unique_properties.append(property_data)

    return unique_properties