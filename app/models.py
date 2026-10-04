from sqlalchemy import Integer, Numeric, String, ForeignKey, Date, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column,relationship
from app.database import Base
from datetime import date, datetime  

#SQLAlchemy model Represents the database.
#Python class that represents one table in your database. Each class attribute maps to one column. It's the bridge that lets you write Python code instead of raw SQL strings to interact with the database.


class Property(Base):
    __tablename__ = "properties"#__tablename__ is you explicitly telling it: "when you generate SQL for this class — SELECT, INSERT, UPDATE, whatever — target the table literally named properties."
    # Concretely, this line is what makes this SQL work when you later call db.query(Property):
    user_id: Mapped[int] = mapped_column("userid",Integer,ForeignKey("users.id"),nullable=False)

    user: Mapped["User"] = relationship(
        back_populates="properties")

    valuations: Mapped[list["PropertyValuation"]] = relationship(
    back_populates="property"#This lets SQLAlchemy naturally express “this property has many valuation records.”
)
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    address: Mapped[str] = mapped_column( String, nullable=False)

    address: Mapped[str] = mapped_column(String, nullable=False)

    city: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    locality: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    price: Mapped[float | None] = mapped_column(
        Numeric,
        index=True
    )

    bedrooms: Mapped[int | None] = mapped_column(
        Integer,
        index=True
    )

    bathrooms: Mapped[float | None] = mapped_column(
        Numeric
    )

    area_sqft: Mapped[int | None] = mapped_column(
        Integer
    )
    auction_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )##

    foreclosure_status: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    opening_bid: Mapped[float | None] = mapped_column(
        Numeric,
        nullable=True
    )

    estimated_value: Mapped[float | None] = mapped_column(
        Numeric,
        nullable=True
    )

    property_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )
    
    survey_number: Mapped[str | None] = mapped_column(
    String,
    nullable=True,
    )
    
    property_key: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        unique=True,
        index=True,
    )


class User(Base):
    __tablename__ = "users"

    properties: Mapped[list["Property"]] = relationship(
    back_populates="user"
    )
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    email: Mapped[str] = mapped_column(
        String,
        unique=True,# 2 users can't have the same email address. This is a common requirement for user accounts, and SQLAlchemy will enforce it at the database level.
        nullable=False
    )

    password_hash: Mapped[str] = mapped_column(
 # the db never receives the actual password, only the hash of it. This is a security best practice: if your database is ever compromised, the attacker won't have access to users' plaintext passwords.
        String,
        nullable=False
    )

    role: Mapped[str] = mapped_column(
        String,
        default="user",
        nullable=False
    )

class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    items_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    document_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)

    content_hash: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        unique=True,
        index=True,
    )

    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

class PropertyDocument(Base):
    __tablename__ = "property_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    property_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("properties.id"),
        nullable=False,
    )

    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id"),
        nullable=False,
    )

    relationship_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

class PropertyValuation(Base):
    __tablename__ = "property_valuations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    property_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("properties.id"),
        nullable=False,
        index=True,
    )

    property: Mapped["Property"] = relationship(
       back_populates="valuations"
    )
    estimated_value: Mapped[float] = mapped_column(
        Numeric,
        nullable=False,
    )

    valuation_method: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    source: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    confidence: Mapped[float | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    valuation_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )   

# Why this table?

# A Property represents the foreclosure/auction property.

# A MarketComparable represents a real residential property used as evidence of market value.
class MarketComparable(Base):
    __tablename__ = "market_comparables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    address: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    city: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        index=True,
    )

    locality: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        index=True,
    )

    property_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        index=True,
    )

    area_sqft: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    sale_price: Mapped[float] = mapped_column(
        Numeric,
        nullable=False,
    )

    sale_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    source_url: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )   

    comparable_key: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True,
        index=True,
    )