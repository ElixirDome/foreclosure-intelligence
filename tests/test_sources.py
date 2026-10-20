import pytest
from pydantic import ValidationError

from app.routes.sources import ConnectSourceRequest


def test_source_management_requires_admin(client):
    response = client.get("/sources/")
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_connect_source_rejects_private_url():
    with pytest.raises(ValidationError):
        ConnectSourceRequest(
            name="Local test source",
            base_url="http://127.0.0.1:8000/internal",
        )


def test_custom_source_regex_requires_amount_capture_group():
    with pytest.raises(ValidationError):
        ConnectSourceRequest(
            name="Test source",
            base_url="https://example.com/auctions",
            rules={"reserve": r"Reserve Price:\s*\d+"},
        )
