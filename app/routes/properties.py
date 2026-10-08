from unittest import result

from fastapi import (APIRouter, Query, HTTPException,#<--from ... import (...) syntax requires the imported names to be separated by commas.
Depends, status, HTTPException,
File, UploadFile)

from pathlib import Path
import tempfile
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
from app.models import Property, User, PropertyValuation
from app.schemas import PropertyResponse,PropertyListResponse,PropertyCreate,PropertyUpdate,PropertyAnalysis,PropertyAIAnalysis, PropertyValuationCreate, PropertyValuationResponse #didn't import it lost 10 mins
from app.security import (get_current_user, require_role,
                          require_property_owner #
                          )
from app.dependencies import get_llm_provider
from app.services.llm import LLMProvider
from app.services.properties import analyze_property_with_ai

from app.services.valuation import (
    record_valuation,
    add_market_comparable,
    calculate_market_valuation,
)

from app.schemas import (
    PropertyValuationCreate,
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
    property_type: str | None = Query(None, description="residential | commercial"),
):
    
    if foreclosure_status:
        foreclosure_status = foreclosure_status.lower()

    else:
        foreclosure_status = None

    try:
        return get_properties(
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
            
        )

    except ValueError as e:
        raise HTTPException(
                status_code=400,
                detail=str(e)
            )

@router.get("/summary")
def property_summary_route(
    db: Session = Depends(get_db),
):
    return get_property_summary(db)

@router.get(
    "/{property_id}/analysis",
    response_model=PropertyAnalysis
)
def analyze_property_route(
    property_id: int,
    db: Session = Depends(get_db)
):
    property = get_property_by_id(
        property_id=property_id,
        db=db
    )

    if property.estimated_value is None or property.estimated_value <= 0:
        raise HTTPException(
            status_code=400,
            detail="Deal analysis requires estimated_value greater than 0",
        )

    if property.opening_bid is None:
        raise HTTPException(
            status_code=400,
            detail="Deal analysis requires opening_bid",
        )

    return analyze_property(property)

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
    "/{property_id}",
    response_model=PropertyResponse
)
def get_property(
    property_id: int,
    db: Session = Depends(get_db)
):
    return get_property_by_id(
        property_id=property_id,
        db=db
    )

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
    return create_property(
        db=db,
        property_data=property_data,
        user_id=current_user.id
     ) #In Python, a function with no explicit return statement returns None by default — no error, no warning, it just silently happens. If you (or a version of this code) forgot to add return property at the end, this is exactly the symptom: the INSERT into Postgres likely succeeded (data's probably actually in the properties table), but the HTTP response has nothing to send back, and response_model=PropertyResponse then chokes trying to validate None against a schema that expects real fields.

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

    return update_property(
        db=db,
        property=property,
        update_data=update_data
    )

@router.post("/import")
def import_properties_from_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported",
        )

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf",
    ) as temp_file:

        temp_file.write(file.file.read())
        temp_path = Path(temp_file.name)

    try:
        from app.ingestion.pdf_source import PDFSourceAdapter
        from app.ingestion.pipeline import run_ingestion
        from app.ingestion.save import save_ingested_properties

        adapter = PDFSourceAdapter(temp_path)

        result = run_ingestion(
            db=db,
            adapter=adapter,
        )

        save_result = save_ingested_properties(
            db=db,
            properties=result["items"],
            user_id=current_user.id,
            ingestion_run_id=result["ingestion_run_id"],
        )

        return {
            "message": "Properties imported successfully",
            "saved_count": len(save_result["saved"]),
            "skipped_count": len(save_result["skipped"]),
            "properties": save_result["saved"],
            "skipped": save_result["skipped"],
            "ingestion_run_id": result["ingestion_run_id"],
        }

    finally:
        temp_path.unlink(missing_ok=True)

@router.post(
    "/{property_id}/valuations",
    response_model=PropertyValuationResponse,
)
def create_property_valuation(
    property_id: int,
    valuation: PropertyValuationCreate,
    db: Session = Depends(get_db),
):
    try:
        return record_valuation(
            db=db,
            property_id=property_id,
            estimated_value=valuation.estimated_value,
            valuation_method=valuation.valuation_method,
            source=valuation.source,
            confidence=valuation.confidence,
            valuation_date=valuation.valuation_date,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )        

# frontend will also need to read valuations.
# Add this route to app/routes/properties.py:
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
        .filter(PropertyValuation.property_id == property_obj.id)
        .order_by(PropertyValuation.valuation_date.desc())
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
    db: Session = Depends(get_db),
):
    property_obj = get_property_by_id(
        property_id=property_id,
        db=db,
    )

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
