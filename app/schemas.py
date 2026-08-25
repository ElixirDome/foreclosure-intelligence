from pydantic import BaseModel
from datetime import date
from typing import Literal
#Pydantic is a library for validating and shaping data — specifically, checking that Python objects (usually built from JSON) match a schema you define, and converting/rejecting them accordingly



#This class defines the shape of incoming/outgoing JSON, separate from your database table
class PropertyCreate(BaseModel):#inheriting from BaseModel means that Pydantic will automatically generate validation logic for this class based on the type hints you provide.
    address: str
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

class PropertyResponse(BaseModel):
    id: int
    address: str
    price: float | None
    bedrooms: int | None
    bathrooms: float | None
    area_sqft: int | None
    auction_date: date | None #It can be date or None, but the field itself is required.
    foreclosure_status: str | None
    opening_bid: float | None
    estimated_value: float | None
    property_type: str | None
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
    deal_rating: str | None
    deal_score: float | None

class PropertyAIAnalysis(BaseModel):
    summary: str
    strengths: list[str]
    risks: list[str]
    due_diligence: list[str]
    recommendation: str

