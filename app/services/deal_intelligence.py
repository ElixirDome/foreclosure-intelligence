"""
Auction intelligence adapter.

Wraps build_auction_intelligence to provide transparent factor explanations,
deterministic financial calculations, and descriptive assessments.
Arbitrary numerical deal scores and unverified comparable valuations are removed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.domain.auction_intelligence import (
    MARKET_VALUATION_UNAVAILABLE_MESSAGE,
    AuctionAssessment,
    AuctionIntelligenceDetails,
    AuctionIntelligenceResult,
    FinancialIntelligence,
    PropertyLegalIntelligence,
)
from app.services.auction_intelligence import build_auction_intelligence


@dataclass
class DealFactor:
    direction: str  # "+" | "-" | "·"
    label: str
    detail: str | None = None


@dataclass
class DealIntelligence:
    property_id: int
    assessment_label: str
    reserve_price: float | None
    emd: float | None
    emd_percentage: float | None
    property_area: float | None
    reserve_price_per_sqft: float | None
    disclosed_outstanding_dues: str | float | None
    possession_type: str
    auction_status: str | None
    factors: list[DealFactor] = field(default_factory=list)
    explanation: str = ""
    financial: FinancialIntelligence | None = None
    auction: AuctionIntelligenceDetails | None = None
    legal: PropertyLegalIntelligence | None = None
    assessment: AuctionAssessment | None = None

    # Obsolete AVM fields removed / defaulted to None or unavailable indicator
    deal_score: float | None = None
    deal_rating: str | None = None
    discount_amount: float | None = None
    discount_percentage: float | None = None
    price_per_sqft: float | None = None
    risk_level: int = 1
    estimated_value: float | None = None
    opening_bid: float | None = None
    comparable_count: int = 0
    market_valuation_status: str = MARKET_VALUATION_UNAVAILABLE_MESSAGE


def build_deal_intelligence(
    db: Session,
    property_id: int,
) -> DealIntelligence | None:
    """Build transparent auction intelligence for a property."""
    result = build_auction_intelligence(db, property_id)
    if result is None:
        return None

    factors: list[DealFactor] = []

    # Financial factors
    if result.financial.reserve_price is not None:
        factors.append(
            DealFactor(
                "·",
                f"Reserve price: ₹{result.financial.reserve_price:,.0f}",
            )
        )
    else:
        factors.append(DealFactor("-", "Reserve price was not disclosed in auction notice"))

    if result.financial.emd is not None and result.financial.emd_percentage is not None:
        factors.append(
            DealFactor(
                "·",
                f"EMD: ₹{result.financial.emd:,.0f} ({result.financial.emd_percentage:.1f}% of reserve)",
            )
        )

    if result.financial.reserve_price_per_sqft is not None:
        factors.append(
            DealFactor(
                "·",
                f"Reserve rate: ₹{result.financial.reserve_price_per_sqft:,.2f} per sq ft",
            )
        )

    # Possession factors
    pos_type = result.legal.possession_type.lower()
    if "physical" in pos_type:
        factors.append(DealFactor("+", "Bank has physical custody of the property"))
    elif "symbolic" in pos_type:
        factors.append(
            DealFactor(
                "-",
                "Symbolic possession under Sec 13(4) SARFAESI — physical possession requires Sec 14 DM order",
            )
        )
    else:
        factors.append(DealFactor("-", "Possession status not specified in notice — verify with bank"))

    # Legal / Encumbrances factors
    for enc in result.legal.disclosed_encumbrances:
        factors.append(DealFactor("-", f"Disclosed encumbrance: {enc}"))
    for lit in result.legal.pending_litigation:
        factors.append(DealFactor("-", f"Pending litigation: {lit}"))

    # Assessment concerns
    for concern in result.assessment.important_concerns:
        if not any(f.label == concern for f in factors):
            factors.append(DealFactor("-", concern))

    # Market valuation note
    factors.append(DealFactor("·", MARKET_VALUATION_UNAVAILABLE_MESSAGE))

    explanation_lines = [
        f"Auction Assessment: {result.assessment.assessment_label}",
        f"Reserve Price: {f'₹{result.financial.reserve_price:,.0f}' if result.financial.reserve_price is not None else 'Undisclosed'}",
        f"EMD: {f'₹{result.financial.emd:,.0f}' if result.financial.emd is not None else 'Undisclosed'}",
        f"Possession: {result.legal.possession_type.capitalize()}",
        f"Status: {result.auction.auction_status or 'Scheduled'}",
    ]
    for factor in factors:
        explanation_lines.append(f"{factor.direction} {factor.label}")

    return DealIntelligence(
        property_id=property_id,
        assessment_label=result.assessment.assessment_label,
        reserve_price=result.financial.reserve_price,
        emd=result.financial.emd,
        emd_percentage=result.financial.emd_percentage,
        property_area=result.financial.property_area,
        reserve_price_per_sqft=result.financial.reserve_price_per_sqft,
        disclosed_outstanding_dues=result.financial.disclosed_outstanding_dues,
        possession_type=result.legal.possession_type,
        auction_status=result.auction.auction_status,
        factors=factors,
        explanation="\n".join(explanation_lines),
        financial=result.financial,
        auction=result.auction,
        legal=result.legal,
        assessment=result.assessment,
        price_per_sqft=result.financial.reserve_price_per_sqft,
        market_valuation_status=MARKET_VALUATION_UNAVAILABLE_MESSAGE,
    )
