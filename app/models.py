from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

#SQLAlchemy model Represents the database.
#Python class that represents one table in your database. Each class attribute maps to one column. It's the bridge that lets you write Python code instead of raw SQL strings to interact with the database.


class Base(DeclarativeBase):
    pass


class Property(Base):
    __tablename__ = "properties"#__tablename__ is you explicitly telling it: "when you generate SQL for this class — SELECT, INSERT, UPDATE, whatever — target the table literally named properties."
    # Concretely, this line is what makes this SQL work when you later call db.query(Property):

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    address: Mapped[str] = mapped_column( String, nullable=False)

    price: Mapped[float | None] = mapped_column(
        Numeric
    )

    bedrooms: Mapped[int | None] = mapped_column(
        Integer
    )

    bathrooms: Mapped[float | None] = mapped_column(
        Numeric
    )

    area_sqft: Mapped[int | None] = mapped_column(
        Integer
    )


class User(Base):
    __tablename__ = "users"

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