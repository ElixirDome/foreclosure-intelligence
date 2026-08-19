from pydantic import BaseModel
#Pydantic is a library for validating and shaping data — specifically, checking that Python objects (usually built from JSON) match a schema you define, and converting/rejecting them accordingly



#This class defines the shape of incoming/outgoing JSON, separate from your database table
class PropertyCreate(BaseModel):#inheriting from BaseModel means that Pydantic will automatically generate validation logic for this class based on the type hints you provide.
    address: str
    price: float | None = None# field: type | None,without = None means the field is required but nullable — the client must include it in the request body, but can send null as its value. That's a common trip-up: people expect | None alone to make it optional to omit, but it doesn't.
#To make a field genuinely optional (can be omitted entirely), you need a default:
    bedrooms: int | None = None
    bathrooms: float | None = None#default value is none
    area_sqft: int | None = None

class PropertyResponse(BaseModel):
    id: int
    address: str
    price: float | None
    bedrooms: int | None
    bathrooms: float | None
    area_sqft: int | None

class PropertyUpdate(BaseModel):
    address: str | None = None
    price: float | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None
    area_sqft: int | None = None

class UserCreate(BaseModel):
    email: str
    password: str

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