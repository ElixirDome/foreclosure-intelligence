"""
Auction and financial domain rules.

Re-exports pure deterministic financial calculations and assessment labels
from app.domain.auction_intelligence.
Arbitrary numerical deal scoring, AVM discounts, and discount ratings are removed.
"""

from __future__ import annotations

from app.domain.auction_intelligence import (
    LABEL_FURTHER_INVESTIGATION,
    LABEL_IMPORTANT_RISKS,
    LABEL_INSUFFICIENT_INFO,
    LABEL_NO_MAJOR_CONCERNS,
    MARKET_VALUATION_UNAVAILABLE_MESSAGE,
    AuctionAssessment,
    AuctionIntelligenceDetails,
    AuctionIntelligenceResult,
    FinancialIntelligence,
    PropertyLegalIntelligence,
    calculate_emd_percentage,
    calculate_reserve_price_per_sqft,
    evaluate_auction_assessment,
)


def calculate_price_per_sqft(
    reserve_price: float | int | None,
    area_sqft: float | int | None,
) -> float | None:
    """Calculate reserve price per square foot (alias)."""
    return calculate_reserve_price_per_sqft(reserve_price, area_sqft)


__all__ = [
    "calculate_emd_percentage",
    "calculate_reserve_price_per_sqft",
    "calculate_price_per_sqft",
    "evaluate_auction_assessment",
    "FinancialIntelligence",
    "AuctionIntelligenceDetails",
    "PropertyLegalIntelligence",
    "AuctionAssessment",
    "AuctionIntelligenceResult",
    "MARKET_VALUATION_UNAVAILABLE_MESSAGE",
    "LABEL_FURTHER_INVESTIGATION",
    "LABEL_IMPORTANT_RISKS",
    "LABEL_INSUFFICIENT_INFO",
    "LABEL_NO_MAJOR_CONCERNS",
]
