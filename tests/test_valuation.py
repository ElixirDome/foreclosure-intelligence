"""
Unit tests for market valuation service.
Verifies that unverified automated valuation estimates are removed,
and that the system explicitly returns the market valuation unavailable message.
"""

from unittest.mock import MagicMock
import pytest
from app.domain.auction_intelligence import MARKET_VALUATION_UNAVAILABLE_MESSAGE
from app.services.valuation import (
    calculate_market_valuation,
)


@pytest.mark.unit
class TestMarketValuationUnavailable:
    def test_market_valuation_returns_unavailable_status(self):
        db = MagicMock()
        prop = MagicMock()
        prop.id = 1
        prop.area_sqft = 1000
        prop.city = "Pathankot"

        res = calculate_market_valuation(db=db, property_obj=prop)
        assert res["status"] == "unavailable"
        assert res["message"] == MARKET_VALUATION_UNAVAILABLE_MESSAGE
        assert res["estimated_value"] is None
        assert res["confidence"] is None

    def test_does_not_manufacture_dummy_estimates(self):
        db = MagicMock()
        prop = MagicMock()
        prop.area_sqft = 2500
        prop.city = "Ludhiana"

        res = calculate_market_valuation(db=db, property_obj=prop)
        assert res["estimated_value"] is None
        assert "verified comparable transaction data is not available" in res["message"]
