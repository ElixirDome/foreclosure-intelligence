from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.models import User, Property
from app.main import app
from app.database import Base, get_db
from app.security import get_current_user

TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
)


def override_get_db():
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

Base.metadata.create_all(bind=test_engine)
#----------------------------------------------------
db = TestingSessionLocal()

test_user = User(
    id=1,
    email="test@example.com",
    password_hash="test-hash",
    role="user",
)

db.add(test_user)
db.commit()
db.close()
#---------------------------------------------
def override_get_current_user():
    return User(
        id=1,
        email="test@example.com",
        password_hash="test-hash",
        role="user",
    )
#register the override:
app.dependency_overrides[get_current_user] = override_get_current_user
#---------------------------------------------
client = TestClient(app)

def test_create_property():
    response = client.post(
        "/properties/",
        json={
            "address": "123 Test Street",
            "price": 500000,
            "bedrooms": 3,
            "bathrooms": 2,
            "area_sqft": 1800,
            "auction_date": "2026-08-22",
            "foreclosure_status": "active",
            "opening_bid": 300000,
            "estimated_value": 500000,
            "property_type": "single_family",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["address"] == "123 Test Street"
    assert data["foreclosure_status"] == "active"
    assert data["opening_bid"] == 300000
    assert data["estimated_value"] == 500000

    def test_create_property_invalid_foreclosure_status():
        response = client.post(
            "/properties/",
            json={
                "address": "123 Invalid Street",
                "price": 500000,
                "bedrooms": 3,
                "bathrooms": 2,
                "area_sqft": 1800,
                "auction_date": "2026-08-22",
                "foreclosure_status": "banana",
                "opening_bid": 300000,
                "estimated_value": 500000,
                "property_type": "single_family",
            },
        )

        assert response.status_code == 422