import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models import User, Property
from app.security import get_current_user
from app.schemas import PropertyAIAnalysis
from app.services.llm import LLMProvider


class FakeLLMProvider(LLMProvider):

    def generate(self, prompt: str) -> PropertyAIAnalysis:
        return PropertyAIAnalysis(
            summary="Test property analysis.",
            strengths=["Good discount"],
            risks=["Foreclosure risk"],
            due_diligence=["Review foreclosure documents"],
            recommendation="Investigate further.",
        )

TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(bind=test_engine)#In Python database code (specifically using SQLAlchemy), bind means connecting or linking a session creator to a specific database engine.

def override_get_db():
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()

def override_get_current_user():
    return User(
        id=1,
        email="test@example.com",
        password_hash="test-hash",
        role="user",
    )

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

@pytest.fixture
def client():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

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

    with TestClient(app) as client:
        yield client

@pytest.fixture
def fake_llm_provider():
    return FakeLLMProvider()        

@pytest.fixture
def db():
    db = TestingSessionLocal()
    yield db
    db.close()