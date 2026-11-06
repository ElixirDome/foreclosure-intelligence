"""
Pure business rules and deterministic calculations for auction intelligence.

This module contains domain business logic only.
It does not depend on FastAPI, SQLAlchemy, HTTP, database sessions, or LLMs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


MARKET_VALUATION_UNAVAILABLE_MESSAGE = (
    "Market valuation unavailable — verified comparable transaction data is not available."
)

LABEL_FURTHER_INVESTIGATION = "Further investigation required"
LABEL_IMPORTANT_RISKS = "Important risks identified"
LABEL_INSUFFICIENT_INFO = "Insufficient information"
LABEL_NO_MAJOR_CONCERNS = "No major concerns identified in the available documents"

VALID_ASSESSMENT_LABELS = {
    LABEL_FURTHER_INVESTIGATION,
    LABEL_IMPORTANT_RISKS,
    LABEL_INSUFFICIENT_INFO,
    LABEL_NO_MAJOR_CONCERNS,
}


def calculate_emd_percentage(
    emd: float | int | None,
    reserve_price: float | int | None,
) -> float | None:
    """
    Calculate EMD as a percentage of reserve price.
    Formula: (EMD / Reserve Price) * 100.
    Returns None if either value is missing or invalid.
    Never assumes missing values are zero.
    """
    if emd is None or reserve_price is None:
        return None

    try:
        emd_val = float(emd)
        reserve_val = float(reserve_price)
    except (TypeError, ValueError):
        return None

    if reserve_val <= 0 or emd_val < 0:
        return None

    return round((emd_val / reserve_val) * 100, 2)


def calculate_reserve_price_per_sqft(
    reserve_price: float | int | None,
    area_sqft: float | int | None,
) -> float | None:
    """
    Calculate reserve price per square foot.
    Formula: Reserve Price / Property Area.
    Returns None if either value is missing or invalid.
    """
    if reserve_price is None or area_sqft is None:
        return None

    try:
        reserve_val = float(reserve_price)
        area_val = float(area_sqft)
    except (TypeError, ValueError):
        return None

    if area_val <= 0 or reserve_val < 0:
        return None

    return round(reserve_val / area_val, 2)


@dataclass
class FinancialIntelligence:
    reserve_price: float | None = None
    emd: float | None = None
    emd_percentage: float | None = None
    property_area: float | None = None
    reserve_price_per_sqft: float | None = None
    disclosed_outstanding_dues: str | float | None = None
    other_financial_obligations: list[str] = field(default_factory=list)
    market_valuation_status: str = MARKET_VALUATION_UNAVAILABLE_MESSAGE


@dataclass
class AuctionIntelligenceDetails:
    auction_date: date | None = None
    auction_start: datetime | None = None
    auction_end: datetime | None = None
    emd_deadline: datetime | None = None
    inspection_start: datetime | None = None
    inspection_end: datetime | None = None
    inspection_window: str | None = None
    auction_status: str | None = None  # Procedural state only, NOT property risk
    bank_name: str | None = None
    branch_name: str | None = None
    contact_details: str | None = None
    auction_platform: str | None = None


@dataclass
class PropertyLegalIntelligence:
    possession_type: str = "not specified"  # "physical" | "symbolic" | "not specified"
    disclosed_encumbrances: list[str] = field(default_factory=list)
    pending_litigation: list[str] = field(default_factory=list)
    title_concerns: list[str] = field(default_factory=list)
    property_discrepancies: list[str] = field(default_factory=list)
    missing_documentation: list[str] = field(default_factory=list)
    bank_conditions: list[str] = field(default_factory=list)


@dataclass
class AuctionAssessment:
    assessment_label: str
    important_concerns: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    financial_considerations: list[str] = field(default_factory=list)
    possession_concerns: list[str] = field(default_factory=list)
    procedural_considerations: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class AuctionIntelligenceResult:
    property_id: int
    financial: FinancialIntelligence
    auction: AuctionIntelligenceDetails
    legal: PropertyLegalIntelligence
    assessment: AuctionAssessment


def evaluate_auction_assessment(
    financial: FinancialIntelligence,
    auction: AuctionIntelligenceDetails,
    legal: PropertyLegalIntelligence,
) -> AuctionAssessment:
    """
    Transparently evaluate an auction listing into descriptive assessment categories and a label.
    Does not use arbitrary numerical scores or equate auction status with property risk.
    """
    important_concerns: list[str] = []
    missing_information: list[str] = []
    financial_considerations: list[str] = []
    possession_concerns: list[str] = []
    procedural_considerations: list[str] = []

    # 1. Missing information audit
    if financial.reserve_price is None:
        missing_information.append("Reserve price was not found or is undisclosed")
    if financial.emd is None:
        missing_information.append("EMD amount was not found in auction data")
    if financial.property_area is None:
        missing_information.append("Property area in square feet is not specified")
    if legal.possession_type == "not specified":
        missing_information.append("Possession type (physical vs symbolic) is not specified in notice")
    if not auction.auction_date and not auction.auction_start:
        missing_information.append("Auction date/time is not specified")
    if not auction.emd_deadline:
        missing_information.append("EMD submission deadline is not specified")
    if not auction.inspection_start and not auction.inspection_end and not auction.inspection_window:
        missing_information.append("Inspection window is not specified")

    # 2. Financial considerations
    if financial.reserve_price is not None:
        financial_considerations.append(f"Published reserve price: ₹{financial.reserve_price:,.0f}")
    if financial.emd is not None and financial.emd_percentage is not None:
        financial_considerations.append(
            f"Required EMD: ₹{financial.emd:,.0f} ({financial.emd_percentage:.1f}% of reserve price)"
        )
    if financial.reserve_price_per_sqft is not None:
        financial_considerations.append(
            f"Reserve price rate: ₹{financial.reserve_price_per_sqft:,.2f} per sq ft"
        )
    if financial.disclosed_outstanding_dues:
        financial_considerations.append(
            f"Disclosed outstanding borrower/statutory dues: {financial.disclosed_outstanding_dues}"
        )
    for obligation in financial.other_financial_obligations:
        financial_considerations.append(f"Disclosed financial obligation: {obligation}")
    financial_considerations.append(financial.market_valuation_status)

    # 3. Possession concerns
    possession_lower = legal.possession_type.lower()
    if "symbolic" in possession_lower:
        possession_concerns.append(
            "Bank holds symbolic possession under Section 13(4) SARFAESI. "
            "Physical possession is not with the bank and may require an order under Section 14 from the DM/CMM."
        )
        important_concerns.append(
            "Symbolic possession: borrower or third-party occupants may still occupy the premises."
        )
    elif "physical" in possession_lower:
        possession_concerns.append(
            "Bank has actual physical possession of the secured asset."
        )
    else:
        possession_concerns.append(
            "Possession status is unstated in available documents. Physical status must be confirmed with the bank."
        )

    # 4. Property and legal concerns
    for enc in legal.disclosed_encumbrances:
        important_concerns.append(f"Disclosed encumbrance/lien: {enc}")
    for lit in legal.pending_litigation:
        important_concerns.append(f"Pending litigation mentioned in document: {lit}")
    for title in legal.title_concerns:
        important_concerns.append(f"Title consideration: {title}")
    for disc in legal.property_discrepancies:
        important_concerns.append(f"Property description discrepancy: {disc}")
    for doc in legal.missing_documentation:
        missing_information.append(f"Missing documentation: {doc}")

    # 5. Procedural considerations (note: auction status is purely procedural, NOT risk level)
    if auction.auction_status:
        procedural_considerations.append(
            f"Current procedural auction status: {auction.auction_status}"
        )
    if auction.auction_start or auction.auction_date:
        dt_str = (
            auction.auction_start.strftime("%Y-%m-%d %H:%M")
            if auction.auction_start
            else str(auction.auction_date)
        )
        procedural_considerations.append(f"Auction scheduled for: {dt_str}")
    if auction.emd_deadline:
        procedural_considerations.append(
            f"EMD submission deadline: {auction.emd_deadline.strftime('%Y-%m-%d %H:%M')}"
        )
    if auction.inspection_window:
        procedural_considerations.append(f"Inspection window: {auction.inspection_window}")
    if auction.bank_name:
        procedural_considerations.append(
            f"Foreclosing institution: {auction.bank_name}"
            + (f" ({auction.branch_name})" if auction.branch_name else "")
        )
    if auction.auction_platform:
        procedural_considerations.append(f"Auction platform / portal: {auction.auction_platform}")
    for cond in legal.bank_conditions:
        procedural_considerations.append(f"Bank auction condition: {cond}")

    # 6. Deterministic label selection
    # Priority 1: If basic identifying financial or procedural information is missing
    if financial.reserve_price is None or financial.emd is None or len(missing_information) >= 4:
        assessment_label = LABEL_INSUFFICIENT_INFO
    # Priority 2: If active litigation, encumbrances, or adverse legal defects are disclosed
    elif (
        len(legal.pending_litigation) > 0
        or len(legal.disclosed_encumbrances) > 0
        or any("litigation" in c.lower() or "stay" in c.lower() or "drt" in c.lower() for c in important_concerns)
    ):
        assessment_label = LABEL_IMPORTANT_RISKS
    # Priority 3: If symbolic possession, unstated possession, or title/document discrepancies require buyer diligence
    elif (
        "symbolic" in possession_lower
        or "not specified" in possession_lower
        or len(legal.title_concerns) > 0
        or len(legal.property_discrepancies) > 0
        or len(legal.missing_documentation) > 0
        or len(important_concerns) > 0
    ):
        assessment_label = LABEL_FURTHER_INVESTIGATION
    # Priority 4: Verified clean documentation with physical possession and no major concerns
    else:
        assessment_label = LABEL_NO_MAJOR_CONCERNS

    summary_lines = [
        f"Assessment: {assessment_label}",
        f"Reserve Price: {f'₹{financial.reserve_price:,.0f}' if financial.reserve_price is not None else 'Undisclosed'}",
        f"EMD: {f'₹{financial.emd:,.0f} ({financial.emd_percentage:.1f}%)' if financial.emd is not None and financial.emd_percentage is not None else 'Undisclosed'}",
        f"Possession: {legal.possession_type.capitalize()}",
    ]
    if important_concerns:
        summary_lines.append(f"Key Concerns: {'; '.join(important_concerns[:2])}")

    return AuctionAssessment(
        assessment_label=assessment_label,
        important_concerns=important_concerns,
        missing_information=missing_information,
        financial_considerations=financial_considerations,
        possession_concerns=possession_concerns,
        procedural_considerations=procedural_considerations,
        summary="\n".join(summary_lines),
    )
