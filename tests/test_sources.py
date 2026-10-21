import pytest
from pydantic import ValidationError

from app.ingestion.custom_source import CustomHtmlSourceAdapter
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


def test_custom_source_accepts_distinct_financial_extraction_rules():
    request = ConnectSourceRequest(
        name="Test source",
        base_url="https://example.com/auctions",
        rules={
            "opening_bid": r"Opening Bid:\s*₹?([\d,]+)",
            "reserve": r"Reserve Price:\s*₹?([\d,]+)",
            "emd": r"EMD:\s*₹?([\d,]+)",
        },
    )
    adapter = CustomHtmlSourceAdapter(
        name=request.name,
        listing_url=request.base_url,
        rules=request.rules,
    )

    result = adapter.extract({
        "text": "Opening Bid: ₹450,000 Reserve Price: ₹500,000 EMD: ₹50,000",
        "title": "Test property",
        "url": request.base_url,
    })

    assert result["opening_bid"] == 450000
    assert result["reserve_price"] == 500000
    assert result["emd"] == 50000
    assert result["price"] == 450000


def test_custom_source_does_not_guess_opening_bid_from_reserve():
    adapter = CustomHtmlSourceAdapter(
        name="Test source",
        listing_url="https://example.com/auctions",
        rules={"reserve": r"Reserve Price:\s*₹?([\d,]+)"},
    )

    result = adapter.extract({
        "text": "Reserve Price: ₹500,000",
        "title": "Test property",
        "url": adapter.listing_url,
    })

    assert result["reserve_price"] == 500000
    assert result["opening_bid"] is None
    assert result["price"] is None
