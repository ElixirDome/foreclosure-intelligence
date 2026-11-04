import re
from datetime import datetime


def _parse_date(text: str):
    # 1. Prefer explicit auction date label
    match = re.search(
        r"(?:Auction\s*Date|Date\s*(?:&|and|/)?\s*Time\s*of\s*(?:E-?)?Auction|Date\s*of\s*Auction)"
        r"\s*[:\-]?\s*(\d{2}[./-]\d{2}[./-]\d{4})",
        text,
        re.IGNORECASE,
    )
    if not match:
        # 2. Date followed by auction hours (e.g. 27/10/2026 From 11AM or @11:00)
        match = re.search(
            r"(\d{2}[./-]\d{2}[./-]\d{4})\s*(?:From|@|Between|to)\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM)",
            text,
            re.IGNORECASE,
        )
    if not match:
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
        r"(\d[\d,.]*)\s*Sq\.?\s*M(?:tr|eter|etre)?",
        text,
        re.IGNORECASE,
    )

    if match:
        value = float(match.group(1).replace(",", ""))
        return round(value * 10.7639)

    # Square feet
    match = re.search(
        r"(\d[\d,.]*)\s*Sq\.?\s*(?:Ft|Feet)",
        text,
        re.IGNORECASE,
    )

    if match:
        return round(float(match.group(1).replace(",", "")))

    # Square yards
    match = re.search(
        r"(\d[\d,.]*)\s*(?:Sq\.?\s*Yards?|Square\s*Yards?)",
        text,
        re.IGNORECASE,
    )

    if match:
        value = float(match.group(1).replace(",", ""))
        return round(value * 9)

    # Kanal and Marla (North Indian / Punjab land measurement)
    match = re.search(
        r"(\d+)\s*Kanal(?:s)?(?:\s*(?:and\s*)?(\d+(?:\.\d+)?)\s*Marla(?:s)?)?",
        text,
        re.IGNORECASE,
    )
    if match:
        kanals = float(match.group(1))
        marlas = float(match.group(2)) if match.group(2) else 0.0
        return round((kanals * 20 + marlas) * 272.25)

    match = re.search(
        r"(\d+(?:\.\d+)?)\s*Marla(?:s)?",
        text,
        re.IGNORECASE,
    )
    if match:
        return round(float(match.group(1)) * 272.25)

    return None


def _clean_amount(val_str: str, has_lakh: bool = False) -> float:
    value = float(val_str.replace(",", ""))
    if has_lakh:
        value *= 100000
    return value


def _parse_price(text: str):
    # 1. Inline Reserve Price: "Reserve Price: Rs. 34,38,000" or "R.P. : Rs. 34,38,000"
    match = re.search(
        r"(?:Reserve\s*Price|R\.P\.?)[^0-9\n]{0,60}?(?:Rs\.?|₹)?\s*"
        r"(\d[\d,]*(?:\.\d+)?)"
        r"\s*(?:lakh|lac)?",
        text,
        re.IGNORECASE,
    )

    if match:
        has_lakh = bool(re.search(r"\b(?:lakh|lac)\b", match.group(0), re.IGNORECASE))
        return _clean_amount(match.group(1), has_lakh)

    # 2. Table formatted: "A)\s*Rs\s*(\d[\d,]*(?:\.\d+)?)"
    match = re.search(
        r"A\)\s*(?:Rs\.?|₹)\s*(\d[\d,]*(?:\.\d+)?)\s*(?:lakh|lac)?\s*/?-?",
        text,
        re.IGNORECASE,
    )

    if match:
        has_lakh = bool(re.search(r"\b(?:lakh|lac)\b", match.group(0), re.IGNORECASE))
        return _clean_amount(match.group(1), has_lakh)

    return None


def _parse_opening_bid(text: str):
    """Parse an opening/start bid only when the notice labels it explicitly."""
    match = re.search(
        r"(?:Opening\s+Bid|Starting\s+Bid|Start\s+Price|Initial\s+Bid)"
        r"\s*[:\-]?\s*(?:Rs\.?|₹)?\s*"
        r"([\d,]+(?:\.\d+)?)\s*(?:lakh|lac)?",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None

    value = float(match.group(1).replace(",", ""))
    if re.search(r"\b(?:lakh|lac)\b", match.group(0), re.IGNORECASE):
        value *= 100000
    return value


def _parse_emd(text: str, reserve_price: float | None = None):
    # 1. Inline explicit EMD: "EMD : Rs. 3,44,000" or "Earnest Money : Rs. ..."
    for match in re.finditer(
        r"(?:EMD|Earnest\s*Money(?:\s*Deposit)?)[^0-9\n]{0,60}?(?:Rs\.?|₹)?\s*"
        r"(\d[\d,]*(?:\.\d+)?)"
        r"\s*(?:lakh|lac)?",
        text,
        re.IGNORECASE,
    ):
        has_lakh = bool(re.search(r"\b(?:lakh|lac)\b", match.group(0), re.IGNORECASE))
        val = _clean_amount(match.group(1), has_lakh)
        if reserve_price is None or val <= reserve_price:
            return val

    # 2. Table formatted: "B)\s*Rs\s*(\d[\d,]*(?:\.\d+)?)"
    for match in re.finditer(
        r"B\)\s*(?:Rs\.?|₹)\s*(\d[\d,]*(?:\.\d+)?)\s*(?:lakh|lac)?\s*/?-?",
        text,
        re.IGNORECASE,
    ):
        prefix = text[max(0, match.start() - 60):match.start()]
        if re.search(r"(?:outstanding|dues|amount\s*as\s*on)", prefix, re.IGNORECASE):
            continue
        has_lakh = bool(re.search(r"\b(?:lakh|lac)\b", match.group(0), re.IGNORECASE))
        val = _clean_amount(match.group(1), has_lakh)
        if reserve_price is None or val <= reserve_price:
            return val

    return None


def _parse_survey_number(text: str):
    match = re.search(
        r"(?:Khasra\s*No\.?|Khasra\s*Number|"
        r"Survey\s*No\.?|Sy\.\s*No\.?|Survey\s*Number|"
        r"Khewat\s*No\.?|Khatauni\s*No\.?)"
        r"\s*[:\-]?\s*([A-Za-z0-9./\-\(\)]+)",
        text,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).rstrip(".,;")

    return None


def _clean_text(t: str) -> str:
    cleaned_lines = []
    for line in t.splitlines():
        line = line.strip()
        # Filter interleaved table column lines (Greek Alpha, A.-D., amounts, possession keywords)
        if re.match(
            r"^(?:[A-Za-z\u0391-\u03a9][.)]|Rs\.?|further|\d{2}[./-]\d{2}[./-]\d{4}|Physical|Symbolic)",
            line,
            re.IGNORECASE,
        ):
            continue
        cleaned_lines.append(line)
    res = " ".join(cleaned_lines)
    res = re.sub(r"andDistt([A-Za-z]+)", r", Distt \1", res)
    res = re.sub(r"HB No\s*(\d+)Tehsil", r"HB No \1, Tehsil", res)
    return re.sub(r"\s+", " ", res).strip(" ,.-")


def _extract_address(text: str):
    # Pattern 1: Flat / Apartment notices
    match = re.search(
        r"(?:All\s+(?:that\s+)?part\s*(?:&|and)\s*parcel\s+of\s+(?:the\s+)?)?"
        r"((?:Flat|Apartment)\s+No\.?.+?)"
        r"(?=\b(?:Total\s+Area|measuring|Bounded|Reserve\s*Price|EMD|in\s+the\s+name\s+of|\(?\s*Symbolic|\(?\s*Physical)\b|\n\s*\n)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return _clean_text(match.group(1))

    # Pattern 2: "situated at ..." after Residential House / Land / Building
    match = re.search(
        r"(?:Residential\s+(?:House|Property|Flat|Apartment|Building)|Land\s+and\s+Residential\s+House)"
        r".*?\b(?:situated|located|standing)\s+(?:at|on)\s+(.+?)"
        r"(?=\b(?:Bounded|Reserve\s*Price|EMD|Sale\s*deed|North:|South:)\b|\n\s*\d+\s*[.)])",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        addr = _clean_text(match.group(1))
        addr = re.split(
            r"(?i)Comprising|Khewat|Khatauni|Khasra|measuring",
            addr,
        )[0]
        return addr.strip(" ,.-")

    # Pattern 3: Residential Property situated at Plot No. 198...
    match = re.search(
        r"Residential\s+(?:Property|House|Flat|Plot|Land)"
        r"\s+(?:situated|located|standing)"
        r"\s+(?:at|on)\s+(.+?)"
        r"(?:\bMeasuring\b|\bBounded\b|\bReserve\s*Price\b|\bEMD\b|\n\s*\d+\s*[.)])",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return _clean_text(match.group(1))

    # Pattern 4: All part & parcel of Residential House measuring...
    match = re.search(
        r"(?:All\s+part\s*(?:&|and)\s*parcel\s+of\s+)"
        r"(Residential\s+(?:House|Property).+?)"
        r"(?=\b(?:measuring|Total\s+Area|Bounded)\b)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return _clean_text(match.group(1))

    # Pattern 5: All that part and parcel of the Residential Property situated...
    match = re.search(
        r"All\s+that\s+part\s+and\s+parcel\s+of\s+the\s+"
        r"(Residential\s+(?:House|Property).+?)"
        r"(?=\bmeasuring\b|\bTotal Area\b)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return _clean_text(match.group(1))

    return None
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

    # Remove PIN-code suffixes such as "- 342014" or "342014".
    parts = [
        re.sub(r"\s*[-–—]?\s*\d{6}\s*$", "", part).strip()
        for part in parts
    ]

    # Filter out housing categories that are not cities
    parts = [
        part for part in parts
        if part and not re.match(r"^\(?\s*(?:M\.?I\.?G\.?|H\.?I\.?G\.?|L\.?I\.?G\.?|E\.?W\.?S\.?)\s*\)?$", part, re.IGNORECASE)
    ]

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

    def _strip_prefix(name: str) -> str:
        s = re.sub(
            r"^(?:Tehsil\s+and\s+)?(?:Distt\.?|District)\s*",
            "",
            name,
            flags=re.IGNORECASE,
        ).strip()
        s = re.sub(r"^Tehsil\s+", "", s, flags=re.IGNORECASE).strip()
        s = re.sub(r"^\d+\.\s*", "", s).strip()
        return s

    # If a state appears at the end, the part immediately before it
    # is usually the city.
    if state_index is not None and state_index > 0:
        city = _strip_prefix(parts[state_index - 1])

        locality = (
            _strip_prefix(parts[state_index - 2])
            if state_index >= 2
            else None
        )

        return city, locality

    # Otherwise, when no state is explicit, use the final address components.
    if len(parts) >= 2:
        city = _strip_prefix(parts[-1])
        locality = _strip_prefix(parts[-2])

        return city, locality

    return _strip_prefix(parts[0]), None


def extract_pnb_property(text: str) -> dict:
    """
    Extract one residential property from a PNB section.
    """

    reserve_price = _parse_price(text)
    emd = _parse_emd(text, reserve_price=reserve_price)
    return {
        "address": _extract_address(text),
        "area_sqft": _parse_area_sqft(text),
        "opening_bid": _parse_opening_bid(text),
        "reserve_price": reserve_price,
        "emd": emd,
        "auction_date": _parse_date(text),
        "property_type": "Residential Property",
        "survey_number": _parse_survey_number(text),
    }


def _is_usable_address(addr: str | None) -> bool:
    if not addr or len(addr.strip()) < 15:
        return False
    if re.search(r"\b(?:not\s+known|unknown|n/?a)\b", addr, re.IGNORECASE):
        return False
    return True


def extract_pnb_properties(text: str) -> list[dict]:
    """
    Extract all residential properties from a PNB auction notice.

    A single PNB document can contain:
    - industrial properties
    - commercial properties
    - agricultural land
    - residential properties
    """

    candidates = []

    # Normalize common OCR confusions in the residential keyword.
    text = re.sub(r"res[i1l]dent[i1l]a[l1]", "Residential", text, flags=re.IGNORECASE)
    text = re.sub(r"residen\s+tial", "Residential", text, flags=re.IGNORECASE)

    matches = list(
        re.finditer(
            r"(?:\bResidential\s+(?:Property|House|Flat|Apartment|Building|Plot|Land)\b"
            r"|\b(?:Flat|Apartment)\s+No\.?\b"
            r"|\bEM\s+of\s+(?:Land\s+and\s+)?Residential\b"
            r"|\bAll\s+(?:that\s+)?part\s*(?:&|and)\s*parcel\s+of\s+(?:the\s+)?(?:Flat|Residential))",
            text,
            re.IGNORECASE,
        )
    )

    for match in matches:
        start = max(0, match.start() - 500)
        remaining_text = text[match.end():]

        # Stop at the next numbered lot or major section, NOT sub-fields like A) or B)
        next_match = re.search(
            r"\n\s*(?:Lot|Item|Sr\.?\s*No\.?)\s*\d+[.:)]"
            r"|\n\s*\d+\s*[.)]\s*(?:[A-Z][a-z]+|M/s|Smt|Shri|Sh\b)"
            r"|\n\s*(?:TERMS\s+AND\s+CONDITIONS|Appendix\b)",
            remaining_text,
            re.IGNORECASE,
        )

        if next_match:
            end = match.end() + next_match.start()
        else:
            end = min(
                len(text),
                match.end() + 3000,
            )

        section = text[start:end]
        property_data = extract_pnb_property(section)

        if not property_data["address"]:
            # Try a larger section if the first window was too small.
            section = text[
                start:min(len(text), match.end() + 4500)
            ]
            property_data = extract_pnb_property(section)

        if _is_usable_address(property_data["address"]):
            city, locality = extract_location(property_data["address"])
            property_data["city"] = city
            property_data["locality"] = locality
            candidates.append(property_data)

    # Deduplicate and merge candidate properties across pages
    unique_properties = []
    for cand in candidates:
        matched = False
        c_tokens = set(re.findall(r"[a-zA-Z0-9]+", cand["address"].lower()))
        for i, existing in enumerate(unique_properties):
            ex_tokens = set(re.findall(r"[a-zA-Z0-9]+", existing["address"].lower()))
            overlap = len(c_tokens & ex_tokens) / max(1, min(len(c_tokens), len(ex_tokens)))
            if overlap >= 0.65:
                # Target is the candidate with the longer, more complete address
                if len(cand["address"]) > len(existing["address"]):
                    target = cand.copy()
                    source = existing
                    unique_properties[i] = target
                else:
                    target = existing
                    source = cand

                for field in [
                    "opening_bid",
                    "reserve_price",
                    "emd",
                    "auction_date",
                    "area_sqft",
                    "survey_number",
                    "city",
                    "locality",
                ]:
                    if target.get(field) is None and source.get(field) is not None:
                        target[field] = source[field]
                matched = True
                break

        if not matched:
            unique_properties.append(cand.copy())

    return unique_properties
