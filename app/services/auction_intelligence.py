"""
Auction intelligence service layer.

Provides deterministic financial calculations, operational auction particulars,
legal intelligence extraction, and transparent assessments.
AVM discount percentages, arbitrary numerical scoring, and discount ratings are eliminated.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.domain.auction_intelligence import (
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
from app.models import Document, Property, PropertyDocument


def _format_inspection_window(start: Any, end: Any) -> str | None:
    if not start and not end:
        return None
    start_str = start.strftime("%d-%b-%Y %I:%M %p") if hasattr(start, "strftime") else str(start) if start else ""
    end_str = end.strftime("%d-%b-%Y %I:%M %p") if hasattr(end, "strftime") else str(end) if end else ""
    if start_str and end_str:
        return f"{start_str} to {end_str}"
    return start_str or end_str


def _extract_platform_from_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if "bankeauctions.com" in netloc:
            return "bankeauctions.com (C1 India)"
        if "eauctions.gov.in" in netloc:
            return "eauctions.gov.in"
        if "ibapi.in" in netloc:
            return "IBAPI (e-Bkray)"
        if "foreclosureindia.com" in netloc:
            return "ForeclosureIndia"
        if "banknet" in netloc:
            return "Banknet"
        return netloc or None
    except Exception:
        return None


def build_auction_intelligence(
    db: Session,
    property_id: int,
) -> AuctionIntelligenceResult | None:
    """Build transparent auction intelligence without numerical deal scoring or unverified AVMs."""
    prop = db.query(Property).filter(Property.id == property_id).first()
    if prop is None:
        return None

    extra = prop.extra_data or {}

    # 1. Financial Intelligence
    reserve_price = float(prop.reserve_price) if prop.reserve_price is not None else None
    emd = float(prop.emd) if prop.emd is not None else None
    area_sqft = float(prop.area_sqft) if prop.area_sqft is not None else None

    emd_percentage = calculate_emd_percentage(emd, reserve_price)
    reserve_psf = calculate_reserve_price_per_sqft(reserve_price, area_sqft)

    disclosed_dues = (
        extra.get("borrowerDues")
        or extra.get("outstandingDues")
        or extra.get("statutoryDues")
        or extra.get("dues")
    )
    if disclosed_dues:
        disclosed_dues = str(disclosed_dues).strip()

    financial_obligations: list[str] = []
    if extra.get("otherObligations"):
        raw_obs = extra.get("otherObligations")
        if isinstance(raw_obs, list):
            financial_obligations.extend(str(o) for o in raw_obs if o)
        elif isinstance(raw_obs, str):
            financial_obligations.append(raw_obs)
    if extra.get("pendingElectricityDues"):
        financial_obligations.append(f"Electricity dues: {extra.get('pendingElectricityDues')}")
    if extra.get("societyMaintenanceDues"):
        financial_obligations.append(f"Society maintenance: {extra.get('societyMaintenanceDues')}")

    financial = FinancialIntelligence(
        reserve_price=reserve_price,
        emd=emd,
        emd_percentage=emd_percentage,
        property_area=area_sqft,
        reserve_price_per_sqft=reserve_psf,
        disclosed_outstanding_dues=disclosed_dues,
        other_financial_obligations=financial_obligations,
        market_valuation_status=MARKET_VALUATION_UNAVAILABLE_MESSAGE,
    )

    # 2. Auction Operational Intelligence
    contact_parts: list[str] = []
    if extra.get("contactPerson"):
        contact_parts.append(f"Officer: {extra.get('contactPerson')}")
    if extra.get("contactPhone") or extra.get("phone"):
        contact_parts.append(f"Phone: {extra.get('contactPhone') or extra.get('phone')}")
    if extra.get("contactEmail") or extra.get("email"):
        contact_parts.append(f"Email: {extra.get('contactEmail') or extra.get('email')}")
    if extra.get("branchAddress"):
        contact_parts.append(f"Branch: {extra.get('branchAddress')}")
    contact_details = " | ".join(contact_parts) if contact_parts else None

    platform = (
        extra.get("auctionPlatform")
        or _extract_platform_from_url(prop.listing_url)
    )

    auction = AuctionIntelligenceDetails(
        auction_date=prop.auction_date,
        auction_start=prop.auction_start,
        auction_end=prop.auction_end,
        emd_deadline=prop.emd_deadline,
        inspection_start=prop.inspection_start,
        inspection_end=prop.inspection_end,
        inspection_window=_format_inspection_window(prop.inspection_start, prop.inspection_end),
        auction_status=prop.foreclosure_status or "scheduled",
        bank_name=prop.bank_name,
        branch_name=prop.branch_name,
        contact_details=contact_details,
        auction_platform=platform,
    )

    # 3. Property and Legal Intelligence
    possession_raw = prop.possession_type or extra.get("possessionType") or extra.get("possession")
    if possession_raw:
        pos_lower = str(possession_raw).strip().lower()
        if "physical" in pos_lower:
            possession_type = "physical"
        elif "symbolic" in pos_lower:
            possession_type = "symbolic"
        else:
            possession_type = pos_lower
    else:
        possession_type = "not specified"

    disclosed_encumbrances: list[str] = []
    if extra.get("encumbrances"):
        raw_enc = extra.get("encumbrances")
        if isinstance(raw_enc, list):
            disclosed_encumbrances.extend(str(e) for e in raw_enc if e)
        else:
            disclosed_encumbrances.append(str(raw_enc))

    pending_litigation: list[str] = []
    if extra.get("litigation") or extra.get("pendingLitigation"):
        raw_lit = extra.get("litigation") or extra.get("pendingLitigation")
        if isinstance(raw_lit, list):
            pending_litigation.extend(str(l) for l in raw_lit if l)
        else:
            pending_litigation.append(str(raw_lit))

    title_concerns: list[str] = []
    if extra.get("titleConcerns"):
        raw_tc = extra.get("titleConcerns")
        if isinstance(raw_tc, list):
            title_concerns.extend(str(t) for t in raw_tc if t)
        else:
            title_concerns.append(str(raw_tc))

    property_discrepancies: list[str] = []
    if extra.get("discrepancies"):
        raw_disc = extra.get("discrepancies")
        if isinstance(raw_disc, list):
            property_discrepancies.extend(str(d) for d in raw_disc if d)
        else:
            property_discrepancies.append(str(raw_disc))

    missing_documentation: list[str] = []
    # Check attached documents
    linked_docs_count = (
        db.query(PropertyDocument)
        .filter(PropertyDocument.property_id == property_id)
        .count()
    )
    if linked_docs_count == 0:
        missing_documentation.append("No official auction notice PDF attached to property record")

    bank_conditions: list[str] = [
        "Sold on 'As is where is, as is what is, and whatever there is' basis",
        "Successful bidder must deposit 25% of sale price (including EMD) on the day of auction or next working day",
        "Balance 75% payable within 15 days of confirmation of sale",
        "All statutory dues, stamp duty, transfer charges, and registration fees to be borne by purchaser",
    ]
    if extra.get("customConditions"):
        raw_cc = extra.get("customConditions")
        if isinstance(raw_cc, list):
            bank_conditions.extend(str(c) for c in raw_cc if c)

    legal = PropertyLegalIntelligence(
        possession_type=possession_type,
        disclosed_encumbrances=disclosed_encumbrances,
        pending_litigation=pending_litigation,
        title_concerns=title_concerns,
        property_discrepancies=property_discrepancies,
        missing_documentation=missing_documentation,
        bank_conditions=bank_conditions,
    )

    # 4. Transparent Assessment
    assessment = evaluate_auction_assessment(
        financial=financial,
        auction=auction,
        legal=legal,
    )

    return AuctionIntelligenceResult(
        property_id=property_id,
        financial=financial,
        auction=auction,
        legal=legal,
        assessment=assessment,
    )
