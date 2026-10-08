"""
Deal intelligence layer (Phase 10).

Composes valuation + domain rules into an explainable deal summary.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.domain import deal_analysis as domain
from app.models import MarketComparable, Property, PropertyValuation


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
    factors: list[DealFactor] = field(default_factory=list)
    explanation: str = ""


def _comparables_for_property(
    db: Session,
    prop: Property,
) -> list[MarketComparable]:
    q = db.query(MarketComparable)
    if prop.city:
        q = q.filter(MarketComparable.city == prop.city)
    if prop.property_type:
        q = q.filter(MarketComparable.property_type == prop.property_type)
    return q.limit(50).all()


def build_deal_intelligence(
    db: Session,
    property_id: int,
) -> DealIntelligence | None:
    prop = db.query(Property).filter(Property.id == property_id).first()
    if prop is None:
        return None

    opening_bid = (
        float(prop.opening_bid)
        if prop.opening_bid is not None
        else None
    )
    estimated = (
        float(prop.estimated_value)
        if prop.estimated_value is not None
        else None
    )

    # Latest valuation confidence if present
    valuation = (
        db.query(PropertyValuation)
        .filter(PropertyValuation.property_id == property_id)
        .order_by(PropertyValuation.id.desc())
        .first()
    )
    confidence = (
        float(valuation.confidence)
        if valuation and valuation.confidence is not None
        else None
    )

    comps = _comparables_for_property(db, prop)
    discount_amount, discount_pct = domain.calculate_discount(
        estimated, opening_bid
    )
    price_psf = domain.calculate_price_per_sqft(
        opening_bid,
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
                f"Opening bid is {discount_pct:.1f}% below estimated value",
            )
        )
    elif discount_pct is not None and discount_pct < 5:
        factors.append(
            DealFactor(
                "-",
                f"Thin discount ({discount_pct:.1f}%) vs estimated value",
            )
        )

    if len(comps) >= 3:
        factors.append(
            DealFactor(
                "+",
                f"{len(comps)} market comparables support valuation context",
            )
        )
    elif estimated is not None:
        factors.append(
            DealFactor(
                "·",
                "Estimated value present but few local comparables",
            )
        )
    else:
        factors.append(
            DealFactor("-", "No estimated market value on file")
        )

    if risk <= 1:
        factors.append(DealFactor("+", "Lower foreclosure process risk"))
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

    lines = [f"Deal score: {score:.0f}/100" if score is not None else "Deal score: n/a"]
    if rating:
        lines.append(f"Rating: {rating}")
    for f in factors:
        lines.append(f"{f.direction} {f.label}")

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
        comparable_count=len(comps),
        factors=factors,
        explanation="\n".join(lines),
    )
