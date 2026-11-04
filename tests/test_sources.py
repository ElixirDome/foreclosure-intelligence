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


def test_discover_source_known_bank_portal():
    from app.services.source_discovery import discover_auction_source

    result = discover_auction_source("PNB")
    assert result["adapter_key"] == "pnb"
    assert "https://www.pnb.bank.in" in result["candidate_url"]
    assert len(result["evidence"]) >= 1


def test_discover_source_rejects_ssrf_safe():
    from app.services.source_discovery import discover_auction_source

    result = discover_auction_source("http://127.0.0.1:8000/internal")
    assert result["status"] == "failed"
    assert "Security restriction" in result["failure_reason"]
    assert len(result["guidance"]) > 0


def test_discover_source_unrecognized_input_fallback():
    from app.services.source_discovery import discover_auction_source

    result = discover_auction_source("completely_invalid_random_bank_name_xyz")
    assert result["status"] == "failed"
    assert "suggested_urls" in result
    assert len(result["guidance"]) > 0

