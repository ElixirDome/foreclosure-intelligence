from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from math import ceil
from datetime import date, datetime
from app.models import Property, PropertyDocument, Document, PropertyValuation, Evidence

from sqlalchemy import and_, case, func, or_, select

from fastapi import HTTPException
from app.schemas import PropertyCreate, ExtractedProperty
from app.services.llm import LLMProvider,generate_property_analysis
from app.services.normalization import create_property_key

from app.services.valuation import record_valuation
from app.services.auction_date import get_current_ist_date

from app.domain.auction_intelligence import (
    calculate_emd_percentage,
    calculate_reserve_price_per_sqft,
    evaluate_auction_assessment,
    MARKET_VALUATION_UNAVAILABLE_MESSAGE,
    FinancialIntelligence,
    AuctionIntelligenceDetails,
    PropertyLegalIntelligence,
)
def get_property_by_id(
    property_id: int,
    db: Session
):
    return get_property_or_404(property_id,db)

def create_property(
    db: Session,
    property_data: PropertyCreate,
    user_id: int
):
    property_key = create_property_key(
        address=property_data.address,
        area_sqft=property_data.area_sqft,
        property_type=property_data.property_type,
        survey_number=property_data.survey_number,
    )

    property = Property(
        **property_data.model_dump(),
        user_id=user_id,
        property_key=property_key,
    )

    db.add(property)
    db.commit()
    db.refresh(property)

    return property

def save_extracted_properties(
    db: Session,
    properties: list[ExtractedProperty],
    user_id: int,
):
    saved_properties = []
    skipped_properties = []
    today_ist = get_current_ist_date()

    for extracted in properties:

        property_key = create_property_key(
            address=extracted.address or "Unknown",
            area_sqft=extracted.area_sqft,
            property_type=extracted.property_type,
            survey_number=extracted.survey_number,
        )

        existing_property = (
            db.query(Property)
            .filter(Property.property_key == property_key)
            .first()
        )

        auction_date = (
            extracted.auction_start.date()
            if extracted.auction_start is not None
            else None
        )

        if existing_property:
            # Re-auction / Rescheduled: if the property has a new future auction date, reactivate it
            if auction_date is not None and auction_date >= today_ist:
                existing_property.auction_date = auction_date
                existing_property.auction_start = extracted.auction_start
                existing_property.auction_end = extracted.auction_end
                existing_property.foreclosure_status = "scheduled"
                if extracted.opening_bid is not None:
                    existing_property.opening_bid = extracted.opening_bid
                    existing_property.reserve_price = extracted.opening_bid
                db.commit()

            skipped_properties.append({
                "property_id": existing_property.id,
                "address": existing_property.address,
                "reason": "duplicate",
            })
            continue

        # Prevent creation of new active property listings from outdated/historical auction notices
        if auction_date is not None and auction_date < today_ist:
            skipped_properties.append({
                "address": extracted.address or "Unknown",
                "auction_date": str(auction_date),
                "reason": "historical_expired_auction_archived",
            })
            continue

        property_obj = Property(
            user_id=user_id,
            address=extracted.address or "Unknown",
            price=extracted.opening_bid,
            area_sqft=(
                int(extracted.area_sqft)
                if extracted.area_sqft is not None
                else None
            ),
            opening_bid=extracted.opening_bid,
            property_type=extracted.property_type,
            survey_number=extracted.survey_number,
            auction_date=auction_date,
            foreclosure_status="scheduled",
            property_key=property_key,
        )

        db.add(property_obj)
        saved_properties.append(property_obj)

    db.commit()

    for property_obj in saved_properties:
        db.refresh(property_obj)

    return {
        "saved": saved_properties,
        "skipped": skipped_properties,
    }

def get_properties(
    db: Session,
    page: int = 1,
    limit: int = 20,
    search: str | None = None,
    min_price: int | float | None = None,
    max_price: int | float | None = None,
    bedrooms: int | None = None,
    sort_by: str = "id",
    order: str = "asc",
    min_area: int | float | None = None,
    max_area: int | float | None = None,
    min_discount: float | None = None,
    max_discount: float | None = None,
    foreclosure_status: str | None = None,
    auction_date_from: date | None = None,
    auction_date_to: date | None = None,
    property_type: str | None = None,
    city: str | None = None,
    district: str | None = None,
    locality: str | None = None,
    include_expired: bool = False,
    **kwargs,
):
    """
    Query properties with calculated deal metrics.

    Database-specific SQL expressions live here, while the
    underlying business rules are defined in
    app.domain.deal_analysis.
    """

    query = db.query(Property)

    # Search across address, city, and locality
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Property.address.ilike(search_term),
                Property.city.ilike(search_term),
                Property.locality.ilike(search_term),
            )
        )

    # Price filters
    if min_price is not None:
        query = query.filter(Property.reserve_price >= min_price)

    if max_price is not None:
        query = query.filter(Property.reserve_price <= max_price)

    # Property filters
    if bedrooms is not None:
        query = query.filter(Property.bedrooms == bedrooms)

    if min_area is not None:
        query = query.filter(Property.area_sqft >= min_area)

    if max_area is not None:
        query = query.filter(Property.area_sqft <= max_area)

    # Foreclosure status visibility rules:
    # If caller specifies a status, filter to that exact status.
    # Otherwise, hide sold and cancelled properties from active listings.
    if foreclosure_status is not None:
        query = query.filter(
            func.lower(Property.foreclosure_status)
            == foreclosure_status.lower()
        )
    else:
        query = query.filter(
            or_(
                Property.foreclosure_status.is_(None),
                func.lower(Property.foreclosure_status).notin_(["sold", "cancelled"]),
            )
        )

    # Auction date visibility rules:
    # If explicit date bounds are passed, honour them.
    # Otherwise, if include_expired is False, restrict to current/future actionable auctions.
    today_ist = get_current_ist_date()
    if auction_date_from is not None:
        query = query.filter(
            Property.auction_date >= auction_date_from
        )
    elif not include_expired:
        today_start = datetime.combine(today_ist, datetime.min.time())
        query = query.filter(
            or_(
                Property.auction_date >= today_ist,
                and_(
                    Property.auction_date.is_(None),
                    Property.auction_end.is_not(None),
                    Property.auction_end >= today_start,
                ),
                and_(
                    Property.auction_date.is_(None),
                    Property.auction_end.is_(None),
                ),
            )
        )

    if auction_date_to is not None:
        query = query.filter(
            Property.auction_date <= auction_date_to
        )

    if property_type is not None:
        pt = property_type.strip().lower()
        if pt == "residential":
            query = query.filter(
                or_(
                    func.lower(Property.property_type).ilike("%residential%"),
                    func.lower(Property.property_type).ilike("%flat%"),
                    func.lower(Property.property_type).ilike("%apartment%"),
                    func.lower(Property.property_type).ilike("%house%"),
                    func.lower(Property.property_type).ilike("%villa%"),
                    func.lower(Property.property_type).ilike("%duplex%"),
                ),
                ~func.lower(Property.property_type).ilike("%commercial%"),
                ~func.lower(Property.property_type).ilike("%industrial%"),
                ~func.lower(Property.property_type).ilike("%shop%"),
                ~func.lower(Property.property_type).ilike("%office%"),
                ~func.lower(Property.property_type).ilike("%factory%"),
                ~func.lower(Property.property_type).ilike("%warehouse%"),
            )
        elif pt == "commercial":
            query = query.filter(
                or_(
                    func.lower(Property.property_type).ilike("%commercial%"),
                    func.lower(Property.property_type).ilike("%industrial%"),
                    func.lower(Property.property_type).ilike("%shop%"),
                    func.lower(Property.property_type).ilike("%office%"),
                    func.lower(Property.property_type).ilike("%factory%"),
                    func.lower(Property.property_type).ilike("%warehouse%"),
                )
            )
        elif pt != "all":
            query = query.filter(
                func.lower(Property.property_type) == pt
            )

    # Location filters
    if city:
        query = query.filter(func.lower(Property.city).ilike(f"%{city.strip().lower()}%"))
    if locality:
        query = query.filter(func.lower(Property.locality).ilike(f"%{locality.strip().lower()}%"))
    if district:
        query = query.filter(
            or_(
                func.lower(Property.city).ilike(f"%{district.strip().lower()}%"),
                func.lower(Property.address).ilike(f"%{district.strip().lower()}%"),
            )
        )

    # Pagination count
    total = query.count()

    # Sorting whitelist
    sort_fields = {
        "id": Property.id,
        "price": Property.reserve_price,
        "bedrooms": Property.bedrooms,
        "bathrooms": Property.bathrooms,
        "area_sqft": Property.area_sqft,
    }

    if sort_by not in sort_fields:
        raise ValueError("Invalid sort field")

    if order not in {"asc", "desc"}:
        raise ValueError("Order must be 'asc' or 'desc'")

    sort_column = sort_fields[sort_by]

    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Pagination
    offset = (page - 1) * limit

    results = (
        query
        .offset(offset)
        .limit(limit)
        .all()
    )

    properties = []

    for property in results:
        res_price = float(property.reserve_price) if property.reserve_price is not None else None
        emd_val = float(property.emd) if getattr(property, "emd", None) is not None else None
        area_val = float(property.area_sqft) if property.area_sqft is not None else None
        emd_pct = calculate_emd_percentage(emd_val, res_price)
        res_psf = calculate_reserve_price_per_sqft(res_price, area_val)

        property_data = {
            "id": property.id,
            "address": property.address,
            "city": property.city,
            "locality": property.locality,
            "price": property.price,
            "bedrooms": property.bedrooms,
            "bathrooms": property.bathrooms,
            "area_sqft": property.area_sqft,
            "auction_date": property.auction_date,
            "foreclosure_status": property.foreclosure_status,
            "opening_bid": property.opening_bid,
            "reserve_price": res_price,
            "emd": emd_val,
            "emd_percentage": emd_pct,
            "reserve_price_per_sqft": res_psf,
            "estimated_value": None,
            "property_type": property.property_type,
            "property_sub_type": property.property_sub_type,
            "survey_number": property.survey_number,
            "district": property.district,
            "state": property.state,
            "pincode": property.pincode,
            "bank_name": property.bank_name,
            "branch_name": property.branch_name,
            "possession_type": property.possession_type,
            "auction_start": property.auction_start,
            "auction_end": property.auction_end,
            "emd_deadline": property.emd_deadline,
            "inspection_start": property.inspection_start,
            "inspection_end": property.inspection_end,
            "property_unique_id": property.property_unique_id,
            "auction_id": property.auction_id,
            "property_images": property.property_images or [],
            "listing_url": property.listing_url,
            "extra_data": property.extra_data or {},
            "raw_status": property.raw_status,
            "market_valuation_status": MARKET_VALUATION_UNAVAILABLE_MESSAGE,
            "discount_percentage": None,
            "deal_score": None,
        }

        properties.append(property_data)

    pages = ceil(total / limit)

    if properties:
        prop_ids = [item["id"] for item in properties]
        rows = (
            db.query(
                PropertyDocument.property_id,
                Document.source_name,
                Document.source_url,
                Document.document_type,
                Document.title,
                Document.filename,
            )
            .join(Document, Document.id == PropertyDocument.document_id)
            .filter(PropertyDocument.property_id.in_(prop_ids))
            .all()
        )
        by_prop: dict[int, list] = {}
        for prop_id, s_name, s_url, d_type, d_title, d_fname in rows:
            by_prop.setdefault(prop_id, []).append({
                "source_name": s_name,
                "source_url": s_url,
                "document_type": d_type,
                "title": d_title,
                "filename": d_fname,
            })
        for item in properties:
            item["sources"] = by_prop.get(item["id"], [])
            ptype = item.get("property_type")
            if ptype:
                low = str(ptype).lower()
                if "commercial" in low:
                    item["property_type"] = "commercial"
                elif any(
                    k in low
                    for k in (
                        "residential",
                        "flat",
                        "apartment",
                        "house",
                        "villa",
                        "duplex",
                    )
                ):
                    item["property_type"] = "residential"

    return {
        "items": properties,
        "page": page,
        "limit": limit,
        "total": total,
        "pages": pages,
    }


def update_property(
    db: Session,
    property: Property,
    update_data: dict
):
    allowed_fields = {
        "address",
        "price",
        "bedrooms",
        "bathrooms",
        "area_sqft",
        "auction_date",
        "foreclosure_status",
        "opening_bid",
        "property_type",
        "survey_number",
    }

    for field, value in update_data.items():
        if field in allowed_fields:
            setattr(property, field, value)

    property.property_key = create_property_key(
        address=property.address,
        area_sqft=property.area_sqft,
        property_type=property.property_type,
        survey_number=property.survey_number,
    )

    try:
        db.commit()
        db.refresh(property)

    except SQLAlchemyError:
        db.rollback()
        raise

    return property

def delete_property(
    db: Session,
    property: Property
):
    db.delete(property)
    db.commit()

def get_property_or_404(# helper function
    property_id: int,
    db: Session
):
    property = (
        db.query(Property)
        .filter(Property.id == property_id)
        .first()
    )

    if property is None:
        raise HTTPException(
            status_code=404,
            detail="Property not found"
        )
    
    return property    
    
# Layer 1 — deterministic
# analyze_property()
# It should always produce the same answer for the same property.

def analyze_property(property: Property):
    """
    Deterministic auction intelligence analysis.
    Eliminates unverified AVM estimates, arbitrary deal scores, and discount ratings.
    Evaluates financial intelligence, operational particulars, legal intelligence, and transparent assessments.
    """
    extra = property.extra_data or {}

    # Financial Intelligence
    reserve_price = float(property.reserve_price) if property.reserve_price is not None else None
    emd = float(property.emd) if getattr(property, "emd", None) is not None else None
    area_sqft = float(property.area_sqft) if property.area_sqft is not None else None
    opening_bid = float(property.opening_bid) if property.opening_bid is not None else None

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

    # Operational Auction Intelligence
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

    inspection_window = None
    if property.inspection_start or property.inspection_end:
        s_str = property.inspection_start.strftime("%d-%b-%Y %I:%M %p") if property.inspection_start else ""
        e_str = property.inspection_end.strftime("%d-%b-%Y %I:%M %p") if property.inspection_end else ""
        inspection_window = f"{s_str} to {e_str}".strip(" to ")

    platform = extra.get("auctionPlatform")
    if not platform and property.listing_url:
        platform = property.listing_url.split("/")[2] if "://" in property.listing_url else None

    auction = AuctionIntelligenceDetails(
        auction_date=property.auction_date,
        auction_start=property.auction_start,
        auction_end=property.auction_end,
        emd_deadline=property.emd_deadline,
        inspection_start=property.inspection_start,
        inspection_end=property.inspection_end,
        inspection_window=inspection_window,
        auction_status=property.foreclosure_status or "scheduled",
        bank_name=property.bank_name,
        branch_name=property.branch_name,
        contact_details=contact_details,
        auction_platform=platform,
    )

    # Property and Legal Intelligence
    possession_raw = property.possession_type or extra.get("possessionType") or extra.get("possession")
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
    bank_conditions = [
        "Sold on 'As is where is, as is what is, and whatever there is' basis",
        "Successful bidder must deposit 25% of purchase price (inclusive of EMD) on same/next day",
        "Balance 75% within 15 days of confirmation of sale",
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

    assessment = evaluate_auction_assessment(
        financial=financial,
        auction=auction,
        legal=legal,
    )

    return {
        # Financial Intelligence
        "reserve_price": reserve_price,
        "emd": emd,
        "emd_percentage": emd_percentage,
        "area_sqft": area_sqft,
        "reserve_price_per_sqft": reserve_psf,
        "disclosed_outstanding_dues": disclosed_dues,
        "other_financial_obligations": financial_obligations,
        "market_valuation_status": MARKET_VALUATION_UNAVAILABLE_MESSAGE,
        # Auction Intelligence
        "auction_date": property.auction_date,
        "auction_start": property.auction_start,
        "auction_end": property.auction_end,
        "emd_deadline": property.emd_deadline,
        "inspection_start": property.inspection_start,
        "inspection_end": property.inspection_end,
        "inspection_window": inspection_window,
        "auction_status": property.foreclosure_status or "scheduled",
        "bank_name": property.bank_name,
        "branch_name": property.branch_name,
        "contact_details": contact_details,
        "auction_platform": platform,
        # Property and Legal Intelligence
        "possession_type": possession_type,
        "disclosed_encumbrances": disclosed_encumbrances,
        "pending_litigation": pending_litigation,
        "title_concerns": title_concerns,
        "property_discrepancies": property_discrepancies,
        "missing_documentation": missing_documentation,
        "bank_conditions": bank_conditions,
        # Transparent Assessment
        "assessment_label": assessment.assessment_label,
        "important_concerns": assessment.important_concerns,
        "missing_information": assessment.missing_information,
        "financial_considerations": assessment.financial_considerations,
        "possession_concerns": assessment.possession_concerns,
        "procedural_considerations": assessment.procedural_considerations,
        "summary": assessment.summary,
        # Legacy fields
        "opening_bid": opening_bid,
        "estimated_value": None,
        "discount_amount": None,
        "discount_percentage": None,
        "price_per_sqft": reserve_psf,
        "potential_upside": None,
        "risk_level": 1,
        "deal_rating": None,
        "deal_score": None,
        "valuation_confidence": None,
    }

#It takes those facts and asks the LLM to interpret them.
def analyze_property_with_ai(
    property: Property,
    provider: LLMProvider,
):
    deterministic_analysis = analyze_property(property)

    property_data = {
        "address": property.address,
        "property_type": property.property_type,
            "survey_number": property.survey_number,
        "price": property.price,
        "bedrooms": property.bedrooms,
        "bathrooms": property.bathrooms,
        "area_sqft": property.area_sqft,
        "auction_date": property.auction_date,
        "foreclosure_status": property.foreclosure_status,
        "opening_bid": property.opening_bid,
        "reserve_price": property.reserve_price,
        "emd": property.emd,
        "estimated_value": deterministic_analysis["estimated_value"],
    }

    return generate_property_analysis(
        property_data=property_data,
        analysis_data=deterministic_analysis,
        provider=provider,
    )

def get_property_summary(db: Session):
    today_ist = get_current_ist_date()
    today_start = datetime.combine(today_ist, datetime.min.time())

    active_condition = and_(
        or_(
            Property.foreclosure_status.is_(None),
            func.lower(Property.foreclosure_status).notin_(["sold", "cancelled"]),
        ),
        or_(
            Property.auction_date >= today_ist,
            and_(
                Property.auction_date.is_(None),
                Property.auction_end.is_not(None),
                Property.auction_end >= today_start,
            ),
            and_(
                Property.auction_date.is_(None),
                Property.auction_end.is_(None),
            ),
        ),
    )

    total_properties = (
        db.query(func.count(Property.id)).scalar() or 0
    )

    upcoming_auctions = (
        db.query(func.count(Property.id))
        .filter(active_condition)
        .scalar()
        or 0
    )

    residential = (
        db.query(func.count(Property.id))
        .filter(
            active_condition,
            or_(
                func.lower(Property.property_type).ilike("%residential%"),
                func.lower(Property.property_type).ilike("%flat%"),
                func.lower(Property.property_type).ilike("%house%"),
                func.lower(Property.property_type).ilike("%apartment%"),
                func.lower(Property.property_type).ilike("%villa%"),
                func.lower(Property.property_type).ilike("%duplex%"),
            ),
            ~func.lower(Property.property_type).ilike("%commercial%"),
            ~func.lower(Property.property_type).ilike("%industrial%"),
            ~func.lower(Property.property_type).ilike("%shop%"),
            ~func.lower(Property.property_type).ilike("%office%"),
            ~func.lower(Property.property_type).ilike("%factory%"),
            ~func.lower(Property.property_type).ilike("%warehouse%"),
        )
        .scalar()
        or 0
    )

    commercial = (
        db.query(func.count(Property.id))
        .filter(
            active_condition,
            or_(
                func.lower(Property.property_type).ilike("%commercial%"),
                func.lower(Property.property_type).ilike("%industrial%"),
                func.lower(Property.property_type).ilike("%shop%"),
                func.lower(Property.property_type).ilike("%office%"),
                func.lower(Property.property_type).ilike("%factory%"),
                func.lower(Property.property_type).ilike("%warehouse%"),
            ),
        )
        .scalar()
        or 0
    )

    sold = (
        db.query(func.count(Property.id))
        .filter(func.lower(Property.foreclosure_status) == "sold")
        .scalar()
        or 0
    )

    return {
        "total_properties": total_properties,
        "upcoming_auctions": upcoming_auctions,
        "properties_with_estimates": 0,
        "residential": residential,
        "commercial": commercial,
        "sold": sold,
    }


def delete_expired_properties(
    db: Session,
    as_of_date: date | None = None,
) -> int:
    """
    Delete all properties whose auction date has expired (strictly before as_of_date, defaults to today).
    Cascades deletion to dependent child records (PropertyDocument, PropertyValuation, Evidence)
    to maintain relational integrity without leaving orphaned records.
    Returns the count of deleted properties.
    """
    if as_of_date is None:
        as_of_date = date.today()

    expired_props = (
        db.query(Property)
        .filter(
            or_(
                and_(Property.auction_date.is_not(None), Property.auction_date < as_of_date),
                and_(
                    Property.auction_date.is_(None),
                    Property.auction_end.is_not(None),
                    Property.auction_end < datetime.combine(as_of_date, datetime.min.time()),
                ),
            )
        )
        .all()
    )

    if not expired_props:
        return 0

    expired_ids = [p.id for p in expired_props]

    # Delete foreign key references in child tables
    db.query(Evidence).filter(Evidence.property_id.in_(expired_ids)).delete(synchronize_session=False)
    db.query(PropertyValuation).filter(PropertyValuation.property_id.in_(expired_ids)).delete(synchronize_session=False)
    db.query(PropertyDocument).filter(PropertyDocument.property_id.in_(expired_ids)).delete(synchronize_session=False)

    deleted_count = (
        db.query(Property)
        .filter(Property.id.in_(expired_ids))
        .delete(synchronize_session=False)
    )

    db.commit()
    return deleted_count
