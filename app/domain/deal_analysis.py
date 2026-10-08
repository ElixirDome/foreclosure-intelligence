"""
Pure business rules for evaluating foreclosure deals.

This module contains business logic only.
It does not know about FastAPI, SQLAlchemy, HTTP,
database sessions, or LLMs.
"""

DEAL_SCORE_RISK_MULTIPLIER = 5

FORECLOSURE_RISK_LEVELS = {
    "scheduled": 1,
    "upcoming": 1,
    "active": 2,
    "sold": 3,
    "cancelled": 3,
}


def calculate_discount(
    estimated_value: float | None,
    opening_bid: float | None,
) -> tuple[float | None, float | None]:
    """Return discount amount and discount percentage."""
    if estimated_value is None or estimated_value <= 0:
        return None, None

    if opening_bid is None:
        return None, None

    discount_amount = estimated_value - opening_bid
    discount_percentage = (
        discount_amount / estimated_value
    ) * 100

    return discount_amount, discount_percentage


def calculate_price_per_sqft(
    opening_bid: float | None,
    area_sqft: float | None,
) -> float | None:
    """Calculate opening-bid price per square foot."""
    if opening_bid is None:
        return None

    if area_sqft is None or area_sqft <= 0:
        return None

    return opening_bid / area_sqft


def calculate_deal_score(
    discount_percentage: float | None,
    risk_level: int,
) -> float | None:
    """Calculate the base deal score."""
    if discount_percentage is None:
        return None

    score = discount_percentage - (
        risk_level * DEAL_SCORE_RISK_MULTIPLIER
    )

    return max(0, min(score, 100))


def calculate_confidence_adjusted_score(
    base_score: float | None,
    valuation_confidence: float | None,
) -> float | None:
    """Reduce the score when valuation confidence is low."""
    if base_score is None:
        return None

    if valuation_confidence is None:
        return base_score

    return base_score * valuation_confidence


def calculate_deal_rating(
    discount_percentage: float | None,
) -> str | None:
    """Convert discount percentage into a human-readable rating."""
    if discount_percentage is None:
        return None

    if discount_percentage >= 30:
        return "excellent"

    if discount_percentage >= 20:
        return "good"

    if discount_percentage >= 10:
        return "moderate"

    return "low"


def get_risk_level(
    foreclosure_status: str | None,
) -> int:
    """Map foreclosure status to its risk level."""
    if foreclosure_status is None:
        return 2

    return FORECLOSURE_RISK_LEVELS.get(
        foreclosure_status.lower(),
        2,
    )
