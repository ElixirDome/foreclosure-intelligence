"""
Auction Date Intelligence & Verification Service.

Authoritative date logic for foreclosure auctions:
1. Always compares against Indian Standard Time (Asia/Kolkata).
2. Distinguishes auction dates from demand notice dates, publication dates,
   sale deed dates, inspection windows, and EMD submission deadlines.
3. Handles multiple auction dates (postponements, rescheduling, corrigenda)
   by selecting the latest verified auction date.
"""

from __future__ import annotations

from datetime import date, datetime
import re
from zoneinfo import ZoneInfo

IST_TIMEZONE = ZoneInfo("Asia/Kolkata")


def get_current_ist_datetime() -> datetime:
    """Returns the current timezone-aware datetime in Indian Standard Time (Asia/Kolkata)."""
    return datetime.now(IST_TIMEZONE)


def get_current_ist_date() -> date:
    """Returns the current local date in Indian Standard Time (Asia/Kolkata)."""
    return get_current_ist_datetime().date()


def is_auction_current(
    auction_date: date | None,
    auction_end: datetime | None = None,
    as_of_date: date | None = None,
) -> bool:
    """
    Determines whether an auction is current and actionable (today or in the future in Asia/Kolkata).
    Past auction dates are expired.
    """
    if as_of_date is None:
        as_of_date = get_current_ist_date()

    if auction_date is not None:
        return auction_date >= as_of_date

    if auction_end is not None:
        end_date = (
            auction_end.astimezone(IST_TIMEZONE).date()
            if auction_end.tzinfo
            else auction_end.date()
        )
        return end_date >= as_of_date

    # If no auction date is stated, it has not expired by date
    return True


# Month name to number mapping
MONTHS_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def parse_indian_date_string(date_str: str) -> date | None:
    """
    Robust parsing of common Indian date formats (DD/MM/YYYY, DD.MM.YYYY, DD-MM-YYYY, DD Month YYYY).
    """
    if not date_str:
        return None
    cleaned = date_str.strip().strip(",.").replace("/", ".").replace("-", ".")

    # Format 1: DD.MM.YYYY or DD.MM.YY
    parts = cleaned.split(".")
    if len(parts) == 3:
        try:
            d = int(parts[0])
            m = int(parts[1])
            y = int(parts[2])
            if y < 100:
                y += 2000
            if 1 <= d <= 31 and 1 <= m <= 12 and 1990 <= y <= 2100:
                return date(y, m, d)
        except (ValueError, TypeError):
            pass

    # Format 2: DD Month YYYY (e.g. 26 November 2026 or 26 Nov 2026)
    match_alpha = re.search(
        r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})",
        date_str,
    )
    if match_alpha:
        try:
            d = int(match_alpha.group(1))
            m_str = match_alpha.group(2).lower()
            y = int(match_alpha.group(3))
            m = MONTHS_MAP.get(m_str)
            if m and 1 <= d <= 31 and 1990 <= y <= 2100:
                return date(y, m, d)
        except (ValueError, TypeError):
            pass

    return None


def extract_verified_auction_dates(text: str) -> list[date]:
    """
    Extracts all verified auction dates from auction notice text,
    strictly distinguishing auction dates from demand notice dates, publication
    dates, sale deed dates, inspection dates, and EMD deadlines.
    """
    if not text:
        return []

    auction_dates: set[date] = set()

    # Pattern 1: Rescheduled / Postponed / Corrigendum auction dates (Highest Priority)
    rescheduled_matches = re.finditer(
        r"(?:Rescheduled|Postponed|Extended|Corrigendum|Revised)\s*(?:Date\s*of\s*(?:E-?)?Auction|Auction\s*Date|Date\s*(?:&|and|/)?\s*Time\s*of\s*(?:E-?)?Auction)"
        r"\s*[:\-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        text,
        re.IGNORECASE,
    )
    for m in rescheduled_matches:
        d = parse_indian_date_string(m.group(1))
        if d:
            auction_dates.add(d)

    # Pattern 2: Explicit Auction Date / Date and Time of E-Auction
    # Exclude matches preceded by "Demand Notice", "Sale Deed", "Inspection", "EMD"
    explicit_matches = re.finditer(
        r"(?<!Demand\sNotice\s)(?<!Notice\s)(?<!Deed\s)(?<!Inspection\s)(?<!EMD\s)"
        r"(?:Date\s*(?:&|and|/)?\s*Time\s*of\s*(?:E-?)?Auction|Date\s*of\s*(?:E-?)?Auction|Date\s*of\s*Sale|E-?Auction\s*Date|Auction\s*Date)"
        r"\s*[:\-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        text,
        re.IGNORECASE,
    )
    for m in explicit_matches:
        # Check preceding context within 40 characters for disqualifying labels
        start_idx = max(0, m.start() - 40)
        prefix = text[start_idx:m.start()].lower()
        if any(bad in prefix for bad in ("demand notice", "13(2)", "sale deed", "inspection")):
            continue
        d = parse_indian_date_string(m.group(1))
        if d:
            auction_dates.add(d)

    # Pattern 3: Date immediately followed by auction hours (e.g. "26.11.2026 11:00 AM to 4:00 PM")
    time_window_matches = re.finditer(
        r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\s*\n?\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM|A\.M\.|P\.M\.)\s*\n?\s*(?:to|Between|-)\s*\n?\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM|A\.M\.|P\.M\.)",
        text,
        re.IGNORECASE,
    )
    for m in time_window_matches:
        start_idx = max(0, m.start() - 50)
        prefix = text[start_idx:m.start()].lower()
        # Verify it's not inspection hours
        if "inspection" in prefix:
            continue
        d = parse_indian_date_string(m.group(1))
        if d:
            auction_dates.add(d)

    # Pattern 4: Date followed by "From 11:00 AM" or "@ 11:00 AM"
    single_time_matches = re.finditer(
        r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\s*(?:From|@)\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM|A\.M\.|P\.M\.)",
        text,
        re.IGNORECASE,
    )
    for m in single_time_matches:
        start_idx = max(0, m.start() - 50)
        prefix = text[start_idx:m.start()].lower()
        if "inspection" in prefix:
            continue
        d = parse_indian_date_string(m.group(1))
        if d:
            auction_dates.add(d)

    return sorted(list(auction_dates))


def extract_latest_auction_date(text: str) -> date | None:
    """
    Extracts the latest verified auction date from auction notice text.
    If multiple auction dates exist (e.g. initial auction date and rescheduled auction date),
    the latest verified auction date is returned.
    """
    dates = extract_verified_auction_dates(text)
    if not dates:
        return None
    return max(dates)
