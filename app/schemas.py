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

class PropertySourceInfo(BaseModel):
    source_name: str
    source_url: str | None = None
    document_type: str | None = None
    title: str | None = None
    filename: str | None = None


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
    sources: list[PropertySourceInfo] = []

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


# --- Document architecture (Phase 1) ---


class DocumentChunkCreate(BaseModel):
    chunk_index: int
    text: str
    page_number: int | None = None
    metadata_json: dict | None = None


class DocumentChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    chunk_index: int
    page_number: int | None
    text: str
    metadata_json: dict | None


class DocumentCreate(BaseModel):
    source_name: str
    source_url: str
    document_type: str
    title: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    storage_path: str | None = None
    extracted_text: str | None = None
    content_hash: str | None = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_name: str
    source_url: str
    document_type: str
    title: str | None
    filename: str | None
    mime_type: str | None
    storage_path: str | None
    content_hash: str | None
    first_seen_at: datetime
    last_seen_at: datetime


class EvidenceCreate(BaseModel):
    property_id: int
    document_id: int
    field: str
    value: str
    page_number: int | None = None
    source_text: str | None = None
    extraction_method: str | None = None
    confidence: float | None = None
    document_chunk_id: int | None = None


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    document_id: int
    document_chunk_id: int | None
    field: str
    value: str
    page_number: int | None
    source_text: str | None
    extraction_method: str | None
    confidence: float | None


# --- Retrieval / RAG / Deal intelligence ---


class RetrieveRequest(BaseModel):
    query: str
    mode: Literal["keyword", "vector", "hybrid"] = "hybrid"
    document_id: int | None = None
    limit: int = 8


class RetrievedChunkResponse(BaseModel):
    chunk_id: int
    document_id: int
    chunk_index: int
    page_number: int | None
    text: str
    score: float
    method: str
    document_title: str | None = None
    source_name: str | None = None
    filename: str | None = None


class RAGRequest(BaseModel):
    question: str
    mode: Literal["keyword", "vector", "hybrid"] = "hybrid"
    document_id: int | None = None
    property_id: int | None = None
    limit: int = 6
    # None = auto (investment questions / property_id → multi-source)
    multi_source: bool | None = None


class CitationResponse(BaseModel):
    kind: str = "document"
    source_id: str | None = None
    title: str | None = None
    excerpt: str
    score: float
    document_id: int | None = None
    chunk_id: int | None = None
    page_number: int | None = None
    property_id: int | None = None
    filename: str | None = None
    source_name: str | None = None


class StructuredAnalysisResponse(BaseModel):
    summary: str
    strengths: list[str] = []
    risks: list[str] = []
    due_diligence: list[str] = []
    recommendation: str = ""
    deal_score: float | None = None
    deal_rating: str | None = None


class RAGResponse(BaseModel):
    question: str
    answer: str
    citations: list[CitationResponse]
    structured: StructuredAnalysisResponse | None = None
    context_kinds: list[str] = []
    property_ids: list[int] = []
    document_ids: list[int] = []
    chunks_used: int
    method: str
    mode: str


class InvestmentAnalysisRequest(BaseModel):
    property_id: int
    question: str | None = None
    mode: Literal["keyword", "vector", "hybrid"] = "hybrid"



class DealFactorResponse(BaseModel):
    direction: str
    label: str
    detail: str | None = None


class DealIntelligenceResponse(BaseModel):
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
    factors: list[DealFactorResponse]
    explanation: str


class StructuredFieldEvidence(BaseModel):
    field: str
    value: str
    page_number: int | None = None
    source_text: str | None = None
    document_id: int | None = None
    document_chunk_id: int | None = None
    extraction_method: str = "regex"
    confidence: float | None = None


class StructuredExtractionResponse(BaseModel):
    property: ExtractedProperty
    evidence: list[StructuredFieldEvidence]
    validation_errors: list[str]
    valid: bool
    method: str

