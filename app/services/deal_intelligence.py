"""
Deal intelligence layer.

Composes the shared comparable-based valuation engine with explainable
foreclosure risk rules. It must not maintain a second valuation formula.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.domain import deal_analysis as domain
from app.models import Property
from app.services.valuation import (
    calculate_valuation_from_comparables,
    find_comparables,
)


@dataclass
class DealFactor:
    direction: str  # "+" | "-" | "·"
    label: str
    detail: str | None = None


@dataclass
class DealIntelligence:
    property_id: int
    deal_score: float | None
    deal_rating: str | None
    discount_amount: float | None
    discount_percentage: float | None
    price_per_sqft: float | None
    risk_level: int
    estimated_value: float | None
    opening_bid: float | None
    comparable_count: int
    reserve_price: float | None = None
    emd: float | None = None
    factors: list[DealFactor] = field(default_factory=list)
    explanation: str = ""


def build_deal_intelligence(
    db: Session,
    property_id: int,
) -> DealIntelligence | None:
    prop = db.query(Property).filter(Property.id == property_id).first()
    if prop is None:
        return None

    reserve_price = (
        float(prop.reserve_price)
        if prop.reserve_price is not None
        else None
    )
    opening_bid = (
        float(prop.opening_bid)
        if prop.opening_bid is not None
        else None
    )
    emd = float(prop.emd) if prop.emd is not None else None

    # Reuse the same eligibility filters and median-per-square-foot
    # calculation used by the market-valuation endpoint. Never infer a
    # value by guessing whether sale_price is a unit price or total price.
    comparables = find_comparables(db=db, property_obj=prop)
    valuation_result = None
    if prop.area_sqft and prop.area_sqft > 0 and len(comparables) >= 3:
        try:
            valuation_result = calculate_valuation_from_comparables(
                area_sqft=prop.area_sqft,
                comparables=comparables,
            )
        except ValueError:
            # Sparse or invalid evidence must result in no estimate, not
            # a fallback to an arbitrary listing-entered number.
            valuation_result = None

    estimated = (
        float(valuation_result["estimated_value"])
        if valuation_result is not None
        else None
    )
    confidence = (
        float(valuation_result["confidence"])
        if valuation_result is not None
        else None
    )
    comparable_count = len(comparables)

    discount_amount, discount_pct = domain.calculate_discount(
        estimated,
        reserve_price,
    )
    price_psf = domain.calculate_price_per_sqft(
        reserve_price,
        float(prop.area_sqft) if prop.area_sqft else None,
    )
    risk = domain.get_risk_level(prop.foreclosure_status)
    base_score = domain.calculate_deal_score(discount_pct, risk)
    score = domain.calculate_confidence_adjusted_score(base_score, confidence)
    rating = domain.calculate_deal_rating(discount_pct)

    factors: list[DealFactor] = []
    if discount_pct is not None and discount_pct >= 20:
        factors.append(
            DealFactor(
                "+",
                f"Reserve is {discount_pct:.1f}% below the comparable-based estimate",
            )
        )
    elif discount_pct is not None and discount_pct < 5:
        factors.append(
            DealFactor(
                "-",
                f"Thin discount ({discount_pct:.1f}%) vs estimated value",
            )
        )

    if valuation_result is not None:
        factors.append(
            DealFactor(
                "+",
                f"{comparable_count} eligible local comparables support the estimate",
            )
        )
    elif comparable_count:
        factors.append(
            DealFactor(
                "-",
                f"Only {comparable_count} eligible comparables; at least 3 valid matches are required",
            )
        )
    else:
        factors.append(
            DealFactor("-", "No eligible local comparables support a market estimate")
        )

    if emd is None:
        factors.append(DealFactor("-", "EMD was not found in structured auction data"))
    if reserve_price is None:
        factors.append(DealFactor("-", "Reserve price was not found in structured auction data"))

    if risk <= 1:
        factors.append(DealFactor("+", "Lower foreclosure process risk based on current status"))
    elif risk >= 3:
        factors.append(
            DealFactor(
                "-",
                f"Higher process risk (status={prop.foreclosure_status})",
            )
        )

    if prop.foreclosure_status and prop.foreclosure_status.lower() in {
        "sold",
        "cancelled",
    }:
        factors.append(
            DealFactor("-", "Auction already concluded or cancelled")
        )

    lines = [
        f"Deal score: {score:.0f}/100" if score is not None else "Deal score: n/a"
    ]
    if rating:
        lines.append(f"Rating: {rating}")
    lines.append(f"Reserve price: {reserve_price if reserve_price is not None else 'not found'}")
    lines.append(f"EMD: {emd if emd is not None else 'not found'}")
    lines.append(
        f"Comparable-based estimate: {estimated if estimated is not None else 'insufficient evidence'}"
    )
    for factor in factors:
        lines.append(f"{factor.direction} {factor.label}")

    return DealIntelligence(
        property_id=property_id,
        deal_score=score,
        deal_rating=rating,
        discount_amount=discount_amount,
        discount_percentage=discount_pct,
        price_per_sqft=price_psf,
        risk_level=risk,
        estimated_value=estimated,
        opening_bid=opening_bid,
        comparable_count=comparable_count,
        reserve_price=reserve_price,
        emd=emd,
        factors=factors,
        explanation="\n".join(lines),
    )
