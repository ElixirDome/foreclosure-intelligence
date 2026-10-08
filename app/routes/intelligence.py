"""Deal intelligence and property-level evidence routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Evidence, Property
from app.schemas import (
    DealFactorResponse,
    DealIntelligenceResponse,
    EvidenceResponse,
)
from app.services.deal_intelligence import build_deal_intelligence

router = APIRouter(tags=["intelligence"])


@router.get(
    "/properties/{property_id}/deal",
    response_model=DealIntelligenceResponse,
)
def property_deal_intelligence(
    property_id: int,
    db: Session = Depends(get_db),
):
    prop = db.query(Property).filter(Property.id == property_id).first()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")

    result = build_deal_intelligence(db, property_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Property not found")

    return DealIntelligenceResponse(
        property_id=result.property_id,
        deal_score=result.deal_score,
        deal_rating=result.deal_rating,
        discount_amount=result.discount_amount,
        discount_percentage=result.discount_percentage,
        price_per_sqft=result.price_per_sqft,
        risk_level=result.risk_level,
        estimated_value=result.estimated_value,
        opening_bid=result.opening_bid,
        comparable_count=result.comparable_count,
        factors=[
            DealFactorResponse(
                direction=f.direction,
                label=f.label,
                detail=f.detail,
            )
            for f in result.factors
        ],
        explanation=result.explanation,
    )


@router.get(
    "/properties/{property_id}/evidence",
    response_model=list[EvidenceResponse],
)
def property_evidence(
    property_id: int,
    db: Session = Depends(get_db),
):
    prop = db.query(Property).filter(Property.id == property_id).first()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")

    return (
        db.query(Evidence)
        .filter(Evidence.property_id == property_id)
        .order_by(Evidence.id)
        .all()
    )
