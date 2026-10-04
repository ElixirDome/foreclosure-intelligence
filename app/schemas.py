from pydantic import BaseModel,ConfigDict
from datetime import datetime, date
from typing import Literal
#Pydantic is a library for validating and shaping data — specifically, checking that Python objects (usually built from JSON) match a schema you define, and converting/rejecting them accordingly



#This class defines the shape of incoming/outgoing JSON, separate from your database table
class PropertyCreate(BaseModel):#inheriting from BaseModel means that Pydantic will automatically generate validation logic for this class based on the type hints you provide.
    address: str
    city: str | None = None
    locality: str | None = None
    price: float | None = None# field: type | None,without = None means the field is required but nullable — the client must include it in the request body, but can send null as its value. That's a common trip-up: people expect | None alone to make it optional to omit, but it doesn't.
#To make a field genuinely optional (can be omitted entirely), you need a default:
    bedrooms: int | None = None
    bathrooms: float | None = None#default value is none
    area_sqft: int | None = None
    auction_date: date | None = None#The field is optional, and if omitted, its value is None.
    foreclosure_status: Literal[#Purpose: Literal["value"] allows type checkers (like mypy) to verify that a variable only holds specific allowed values (e.g., Literal["yes", "no"]).
        "scheduled",
        "upcoming",
        "active",
        "sold",
        "cancelled",
    ] | None = None  
    opening_bid: float | None = None
    estimated_value: float | None = None
    property_type: str | None = None
    survey_number: str | None = None

class PropertyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    address: str
    city: str | None
    locality: str | None
    price: float | None
    bedrooms: int | None
    bathrooms: float | None
    area_sqft: int | None
    auction_date: date | None #It can be date or None, but the field itself is required.
    foreclosure_status: str | None
    opening_bid: float | None
    estimated_value: float | None
    property_type: str | None
    survey_number: str | None = None
    discount_percentage: float | None = None
    deal_score: float | None = None

class PropertyUpdate(BaseModel):
    address: str | None = None
    price: float | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None
    area_sqft: int | None = None
    auction_date: date | None=None
    foreclosure_status: Literal[#Purpose: Literal["value"] allows type checkers (like mypy) to verify that a variable only holds specific allowed values (e.g., Literal["yes", "no"]).
        "scheduled",
        "upcoming",
        "active",
        "sold",
        "cancelled",
    ] | None = None
    opening_bid: float | None=None
    estimated_value: float | None=None
    property_type: str | None=None
    survey_number: str | None = None
class UserCreate(BaseModel):
    email: str
    password: str
#####################33 don't CREATE SPACE BETWEEN THESE CLASSES
class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    #The hash should never be returned as part of the normal user response either.

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class PropertyListResponse(BaseModel):
    items: list[PropertyResponse]
    page: int
    limit: int
    total: int
    pages: int

class PropertyAnalysis(BaseModel):
    estimated_value: float | None
    opening_bid: float | None
    discount_amount: float | None
    discount_percentage: float | None
    price_per_sqft: float | None
    potential_upside: float | None
    risk_level: int | None
    deal_rating: str | None
    deal_score: float | None
    valuation_confidence: float | None

class PropertyAIAnalysis(BaseModel):
    summary: str
    strengths: list[str]
    risks: list[str]
    due_diligence: list[str]
    recommendation: str

class ExtractedProperty(BaseModel):
    lot_number: str | None = None
    document_number: str | None = None

    property_type: str | None = None
    category: str | None = None
    sub_category: str | None = None

    defaulter_name: str | None = None

    address: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None

    area_sqft: float | None = None
    survey_number: str | None = None

    opening_bid: float | None = None
    pre_bid_emd: float | None = None
    minimum_increment: float | None = None
    post_bid_emd_percent: float | None = None

    auction_number: str | None = None
    auction_start: datetime | None = None
    auction_close: datetime | None = None

    seller_name: str | None = None

class PropertyValuationCreate(BaseModel):
    estimated_value: float
    valuation_method: str
    source: str | None = None
    confidence: float | None = None
    valuation_date: date | None = None


class PropertyValuationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    estimated_value: float
    valuation_method: str
    source: str | None
    confidence: float | None
    valuation_date: date

class MarketComparableCreate(BaseModel):
    address: str
    city: str | None = None
    locality: str | None = None
    property_type: str | None = None
    area_sqft: int
    sale_price: float
    sale_date: date | None = None
    source: str
    source_url: str | None = None


class MarketComparableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    address: str
    city: str | None
    locality: str | None
    property_type: str | None
    area_sqft: int
    sale_price: float
    sale_date: date | None
    source: str
    source_url: str | None