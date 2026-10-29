from unittest import result
import asyncio
import json
import time

from fastapi import (APIRouter, Query, HTTPException, Request,
Depends, status,
File, UploadFile)
from fastapi.responses import StreamingResponse

from pathlib import Path
import uuid
from sqlalchemy.orm import Session
from math import ceil
from datetime import date

from app.services.properties import (
    create_property,get_properties,
    update_property,delete_property,
    get_property_by_id,
    analyze_property,
    get_property_or_404,
   
)
from app.database import SessionLocal,get_db
from app.models import Property, User, PropertyValuation, Document, PropertyDocument, IngestionRun
from app.schemas import PropertyResponse,PropertyListResponse,PropertyCreate,PropertyUpdate,PropertyAnalysis,PropertyAIAnalysis, PropertyValuationResponse, DocumentResponse
from app.security import (get_current_user, require_role,
                          require_property_owner, decode_access_token #
                          )
from app.dependencies import get_llm_provider
from app.services.llm import LLMProvider
from app.services.properties import analyze_property_with_ai
from app.services.live_events import broker, format_sse

from app.services.valuation import (
    record_valuation,
    add_market_comparable,
    calculate_market_valuation,
    get_latest_comparable_valuation,
)

from app.schemas import (
    PropertyValuationResponse,
    MarketComparableCreate,
    MarketComparableResponse,
)
from app.services.properties import get_property_summary;

router = APIRouter(prefix="/properties",tags=["properties"])

@router.get(
    "/",
    response_model=PropertyListResponse#response_model constraint
)
def get_properties_route(
    page: int = Query(1, ge=1),#FastAPI lets us constrain query parameters.
    limit: int = Query(20, ge=1, le=100),# now a client couldn't do GET /properties?limit=100000000
    search: str | None = Query(None),
    min_price: int | None = Query(None, ge=0),
    max_price: int | None = Query(None, ge=0),
    bedrooms: int | None = Query(None, ge=0),
    sort_by: str = Query("id"),
    order: str = Query("asc"),
    db: Session = Depends(get_db),
    
    min_area: int | None = Query(None, ge=0),
    max_area: int | None = Query(None, ge=0),
    min_discount: float | None = Query(None, ge=0, le=100),
    max_discount: float | None = Query(
    None,
    ge=0,
    le=100
    ),
    foreclosure_status: str | None = Query(None),
    auction_date_from: date | None = Query(None),
    auction_date_to: date | None = Query(None),
    property_type: str | None = Query(None, description="residential | commercial | all"),
    city: str | None = Query(None),
    district: str | None = Query(None),
    locality: str | None = Query(None),
):
    
    if foreclosure_status:
        foreclosure_status = foreclosure_status.lower()

    else:
        foreclosure_status = None

    cache_key = f"property:list:{page}:{limit}:{sort_by}:{order}:{search}:{min_price}:{max_price}:{bedrooms}:{property_type}:{city}:{district}:{locality}:{min_area}:{max_area}:{min_discount}:{max_discount}:{foreclosure_status}:{auction_date_from}:{auction_date_to}"
    from app.services.cache import cache
    cached_list = cache.get(cache_key)
    if cached_list is not None:
        return cached_list

    try:
        result = get_properties(
            db=db,#for the parameter named db in get_properties's signature, use the value currently held by my local variable also named db.
            page=page,
            limit=limit,
            search=search,
            min_price=min_price,
            max_price=max_price,
            bedrooms=bedrooms,
            sort_by=sort_by,
            order=order,
            min_area=min_area,
            max_area=max_area,
            min_discount=min_discount,
            max_discount=max_discount,
            foreclosure_status=foreclosure_status,
            auction_date_from=auction_date_from,
            auction_date_to=auction_date_to,
            property_type=property_type,
            city=city,
            district=district,
            locality=locality,
        )
        cache.set(cache_key, result, ttl=30.0)
        return result

    except ValueError as e:
        raise HTTPException(
                status_code=400,
                detail=str(e)
            )

@router.get("/summary")
def property_summary_route(
    db: Session = Depends(get_db),
):
    from app.services.cache import cache
    cached_summary = cache.get("property:summary")
    if cached_summary is not None:
        return cached_summary

    summary = get_property_summary(db)
    cache.set("property:summary", summary, ttl=30.0)
    return summary

@router.get(
    "/{property_id}/analysis",
    response_model=PropertyAnalysis
)
def analyze_property_route(
    property_id: int,
    db: Session = Depends(get_db)
):
    from app.services.cache import cache
    cache_key = f"property:analysis:{property_id}"
    cached_analysis = cache.get(cache_key)
    if cached_analysis is not None:
        return cached_analysis

    property = get_property_by_id(
        property_id=property_id,
        db=db
    )

    analysis = analyze_property(property)
    if analysis["estimated_value"] is None or analysis["estimated_value"] <= 0:
        raise HTTPException(
            status_code=400,
            detail="Deal analysis requires an automated comparable-based valuation",
        )

    if analysis["reserve_price"] is None:
        raise HTTPException(
            status_code=400,
            detail="Deal analysis requires reserve_price",
        )

    cache.set(cache_key, analysis, ttl=60.0)
    return analysis

@router.get(
    "/{property_id}/analysis/ai",
    response_model=PropertyAIAnalysis,
)
def analyze_property_ai_route(
    property_id: int,
    db: Session = Depends(get_db),
    provider: LLMProvider = Depends(get_llm_provider),
):
    property = get_property_by_id(
        property_id=property_id,
        db=db,
    )

    return analyze_property_with_ai(
        property=property,
        provider=provider,
    )


@router.get(
    "/{property_id}/documents",
    response_model=list[DocumentResponse],
)
def list_property_documents(
    property_id: int,
    db: Session = Depends(get_db),
):
    """Sale notices and other documents linked to this property."""
    property_obj = get_property_by_id(property_id=property_id, db=db)
    return (
        db.query(Document)
        .join(PropertyDocument, PropertyDocument.document_id == Document.id)
        .filter(PropertyDocument.property_id == property_obj.id)
        .order_by(Document.last_seen_at.desc())
        .all()
    )


@router.get("/stream")
async def property_event_stream(
    request: Request,
    token: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    Server-Sent Events (SSE) stream for near-real-time property updates.
    Enforces authentication via query parameter ?token= or Authorization header.
    Emits heartbeats every 15s and cleans up when the client disconnects.
    """
    raw_token = token
    if not raw_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header.split(" ", 1)[1]

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for live stream",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(raw_token)
        user_id = int(payload.get("sub", 0))
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired stream token")

    if not broker.can_subscribe():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SSE connection limit reached for this worker. Please retry shortly.",
        )

    queue = broker.subscribe()

    async def sse_generator():
        try:
            yield format_sse("connected", {
                "status": "connected",
                "user_id": user_id,
                "timestamp": time.time(),
                "subscriber_count": broker.subscriber_count,
            }, event_id="init")

            # Check if client provided Last-Event-ID for missed event replay
            last_event_id = request.headers.get("Last-Event-ID")
            if last_event_id:
                for past_evt in broker.get_events_after(last_event_id):
                    yield format_sse(past_evt["event"], past_evt["data"], event_id=past_evt.get("id"))
            else:
                for past_evt in broker.get_recent_events(limit=5):
                    yield format_sse(past_evt["event"], past_evt["data"], event_id=past_evt.get("id"))

            while True:
                if await request.is_disconnected():
                    break

                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield format_sse(payload["event"], payload["data"], event_id=payload.get("id"))
                except asyncio.TimeoutError:
                    yield format_sse("ping", {"timestamp": time.time()})
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            pass
        finally:
            broker.unsubscribe(queue)

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/live-status")
def get_live_ingestion_status(db: Session = Depends(get_db)):
    """
    Returns truthful status information regarding live ingestion,
    source polling, last property save, and connection health.
    """
    latest_run = (
        db.query(IngestionRun)
        .order_by(IngestionRun.id.desc())
        .first()
    )

    last_saved_prop = (
        db.query(Property)
        .order_by(Property.id.desc())
        .first()
    )

    total_properties = db.query(Property).count()

    latest_run_dict = None
    if latest_run:
        latest_run_dict = {
            "id": latest_run.id,
            "source_name": latest_run.source_name,
            "status": latest_run.status,
            "started_at": latest_run.started_at.isoformat() if latest_run.started_at else None,
            "finished_at": latest_run.finished_at.isoformat() if latest_run.finished_at else None,
            "items_found": latest_run.items_found,
            "items_created": latest_run.items_created,
            "items_skipped": latest_run.items_skipped,
            "error_message": latest_run.error_message,
        }

    return {
        "status": "online",
        "active_subscribers": broker.subscriber_count,
        "last_event_time": broker.last_event_time,
        "total_properties": total_properties,
        "last_property_saved_id": last_saved_prop.id if last_saved_prop else None,
        "latest_run": latest_run_dict,
    }


@router.get(
    "/{property_id}",
    response_model=PropertyResponse
)
def get_property(
    property_id: int,
    db: Session = Depends(get_db)
):
    property_obj = get_property_by_id(
        property_id=property_id,
        db=db,
    )
    response = PropertyResponse.model_validate(property_obj)
    valuation = get_latest_comparable_valuation(db, property_id)
    response.estimated_value = (
        float(valuation.estimated_value)
        if valuation is not None
        else None
    )
    return response

@router.post(
    "/",
    response_model=PropertyResponse,
    status_code=status.HTTP_201_CREATED
)
def create_property_route(
    property_data: PropertyCreate,#If your create_property_route currently receives a PropertyCreate object: then no need to manually add auction_date, opening_bid,etc . to the route. They're already inside: property_data, once you've added them to Propertycreate
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
   
):
    prop = create_property(
        db=db,
        property_data=property_data,
        user_id=current_user.id
     ) #In Python, a function with no explicit return statement returns None by default — no error, no warning, it just silently happens. If you (or a version of this code) forgot to add return property at the end, this is exactly the symptom: the INSERT into Postgres likely succeeded (data's probably actually in the properties table), but the HTTP response has nothing to send back, and response_model=PropertyResponse then chokes trying to validate None against a schema that expects real fields.
    from app.services.cache import cache
    cache.invalidate_prefix("property:")
    broker.publish(
        "property_created",
        {
            "property_id": prop.id,
            "action": "created",
            "address": prop.address,
            "city": prop.city,
            "locality": prop.locality,
            "property_type": prop.property_type,
            "reserve_price": float(prop.reserve_price) if prop.reserve_price is not None else None,
            "emd": float(prop.emd) if prop.emd is not None else None,
            "opening_bid": float(prop.opening_bid) if prop.opening_bid is not None else None,
            "auction_date": prop.auction_date.isoformat() if prop.auction_date else None,
            "foreclosure_status": prop.foreclosure_status or "scheduled",
            "survey_number": prop.survey_number,
            "area_sqft": prop.area_sqft,
            "timestamp": time.time(),
        },
    )
    return prop

@router.delete(
    "/{property_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_property_route(
    property: Property = Depends(require_property_owner),
    db: Session = Depends(get_db)
):  
    print("ROUTE DB:", id(db))

    delete_property(
        db=db,
        property=property
    )
    from app.services.cache import cache
    cache.invalidate_prefix("property:")
    return

@router.patch(
    "/{property_id}",
    response_model=PropertyResponse
)
def update_property_route(
    property_data: PropertyUpdate,
    property: Property = Depends(require_property_owner),
    db: Session = Depends(get_db)
):
    update_data = property_data.model_dump(
        exclude_unset=True
    )

    updated = update_property(
        db=db,
        property=property,
        update_data=update_data
    )
    from app.services.cache import cache
    cache.invalidate_prefix("property:")
    broker.publish(
        "property_updated",
        {
            "property_id": updated.id,
            "action": "updated",
            "address": updated.address,
            "city": updated.city,
            "locality": updated.locality,
            "property_type": updated.property_type,
            "reserve_price": float(updated.reserve_price) if updated.reserve_price is not None else None,
            "emd": float(updated.emd) if updated.emd is not None else None,
            "opening_bid": float(updated.opening_bid) if updated.opening_bid is not None else None,
            "auction_date": updated.auction_date.isoformat() if updated.auction_date else None,
            "foreclosure_status": updated.foreclosure_status or "scheduled",
            "survey_number": updated.survey_number,
            "area_sqft": updated.area_sqft,
            "timestamp": time.time(),
        },
    )
    return updated

@router.post("/import")
def import_properties_from_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported",
        )

    upload_dir = Path("data/uploads").resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = upload_dir / (uuid.uuid4().hex + ".pdf")
    stored_path.write_bytes(file.file.read())

    try:
        from app.ingestion.pdf_source import PDFSourceAdapter
        from app.ingestion.pipeline import run_ingestion

        result = run_ingestion(
            db=db,
            adapter=PDFSourceAdapter(stored_path),
            user_id=current_user.id,
        )

        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=f"PDF ingestion failed: {result['error']}",
            )

        return {
            "message": "PDF ingestion completed",
            "saved_count": len(result.get("saved") or []),
            "skipped_count": len(result.get("skipped") or []),
            "properties": result.get("saved") or [],
            "skipped": result.get("skipped") or [],
            "ingestion_run_id": result.get("ingestion_run_id"),
        }
    finally:
        file.file.close()

@router.get(
    "/{property_id}/valuations",
    response_model=list[PropertyValuationResponse],
)
def get_property_valuations(
    property_id: int,
    db: Session = Depends(get_db),
):
    property_obj = get_property_by_id(
        property_id=property_id,
        db=db,
    )

    return (
        db.query(PropertyValuation)
        .filter(
            PropertyValuation.property_id == property_obj.id,
            PropertyValuation.source == "market_comparables",
            PropertyValuation.valuation_method == "residential_comparable_sales",
        )
        .order_by(PropertyValuation.id.desc())
        .all()
    )    

@router.get(
    "/market-comparables",
    response_model=list[MarketComparableResponse],
)
def get_market_comparables(
    db: Session = Depends(get_db),
):
    from app.models import MarketComparable

    return (
        db.query(MarketComparable)
        .order_by(MarketComparable.sale_date.desc())
        .all()
    )

@router.post(
    "/market-comparables",
    response_model=MarketComparableResponse,
)
def create_market_comparable(
    comparable: MarketComparableCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role("admin")),
):
    return add_market_comparable(
        db=db,
        address=comparable.address,
        city=comparable.city,
        locality=comparable.locality,
        property_type=comparable.property_type,
        area_sqft=comparable.area_sqft,
        sale_price=comparable.sale_price,
        sale_date=comparable.sale_date,
        source=comparable.source,
        source_url=comparable.source_url,
    )


@router.post(
    "/{property_id}/market-valuation",
)
def calculate_property_market_valuation(
    property_id: int,
    property_obj: Property = Depends(require_property_owner),
    db: Session = Depends(get_db),
):

    try:
        valuation_result = calculate_market_valuation(
            db=db,
            property_obj=property_obj,
        )

        valuation = record_valuation(
            db=db,
            property_id=property_obj.id,
            estimated_value=valuation_result["estimated_value"],
            valuation_method=valuation_result["valuation_method"],
            source="market_comparables",
            confidence=valuation_result["confidence"],
        )

        return {
            **valuation_result,
            "valuation_id": valuation.id,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
