"""
Unit tests for pure calculation logic in app.services.valuation.
Tests statistical median pricing, comparable count thresholds, and confidence scoring.
No database or external network access required.
"""

from unittest.mock import MagicMock
import pytest
from app.services.valuation import (
    MIN_COMPARABLES,
    calculate_valuation_confidence,
    calculate_valuation_from_comparables,
)


def _make_comparable(area_sqft: float, sale_price: float) -> MagicMock:
    comp = MagicMock()
    comp.area_sqft = area_sqft
    comp.sale_price = sale_price
    return comp


@pytest.mark.unit
class TestCalculateValuationFromComparables:
    def test_three_comparables_odd_median(self):
        # 1000 sqft with comps at 3000, 3500, 4000 per sqft
        comps = [
            _make_comparable(1000, 3_000_000),  # 3000/sqft
            _make_comparable(1000, 3_500_000),  # 3500/sqft (median)
            _make_comparable(1000, 4_000_000),  # 4000/sqft
        ]
        res = calculate_valuation_from_comparables(area_sqft=1200, comparables=comps)
        assert res["median_price_per_sqft"] == pytest.approx(3500.0)
        assert res["estimated_value"] == pytest.approx(3500.0 * 1200)
        assert res["comparables_used"] == 3
        assert res["valuation_method"] == "residential_comparable_sales"
        assert 0.0 <= res["confidence"] <= 1.0

    def test_four_comparables_even_median(self):
        # Prices: 3000, 3200, 3600, 4000 -> median = (3200 + 3600) / 2 = 3400
        comps = [
            _make_comparable(1000, 3_000_000),
            _make_comparable(1000, 3_200_000),
            _make_comparable(1000, 3_600_000),
            _make_comparable(1000, 4_000_000),
        ]
        res = calculate_valuation_from_comparables(area_sqft=1000, comparables=comps)
        assert res["median_price_per_sqft"] == pytest.approx(3400.0)
        assert res["estimated_value"] == pytest.approx(3_400_000.0)
        assert res["comparables_used"] == 4

    def test_invalid_zero_price_or_area_filtered_out(self):
        # 4 comps, but 1 has 0 price -> 3 valid comps remain (satisfies MIN_COMPARABLES=3)
        comps = [
            _make_comparable(1000, 3_000_000),
            _make_comparable(1000, 0),          # invalid price
            _make_comparable(1000, 3_400_000),
            _make_comparable(1000, 3_800_000),
        ]
        res = calculate_valuation_from_comparables(area_sqft=1000, comparables=comps)
        assert res["median_price_per_sqft"] == pytest.approx(3400.0)
        assert res["comparables_used"] == 3

    def test_insufficient_comparables_raises_value_error(self):
        comps = [
            _make_comparable(1000, 3_000_000),
            _make_comparable(1000, 3_500_000),
        ]
        with pytest.raises(ValueError, match="Insufficient comparable properties"):
            calculate_valuation_from_comparables(area_sqft=1000, comparables=comps)

    def test_fewer_than_three_valid_comparables_raises_value_error(self):
        # 3 comps, but 2 have 0 price -> only 1 valid
        comps = [
            _make_comparable(1000, 3_000_000),
            _make_comparable(1000, 0),
            _make_comparable(0, 3_500_000),
        ]
        with pytest.raises(ValueError, match="Insufficient valid comparable properties"):
            calculate_valuation_from_comparables(area_sqft=1000, comparables=comps)

    def test_zero_or_negative_target_area_raises_value_error(self):
        comps = [
            _make_comparable(1000, 3_000_000),
            _make_comparable(1000, 3_500_000),
            _make_comparable(1000, 4_000_000),
        ]
        with pytest.raises(ValueError, match="area_sqft must be greater than 0"):
            calculate_valuation_from_comparables(area_sqft=0, comparables=comps)
        with pytest.raises(ValueError, match="area_sqft must be greater than 0"):
            calculate_valuation_from_comparables(area_sqft=-50, comparables=comps)


@pytest.mark.unit
class TestCalculateValuationConfidence:
    def test_empty_list_returns_zero(self):
        assert calculate_valuation_confidence([], 0) == 0.0

    def test_zero_or_negative_mean_returns_zero(self):
        assert calculate_valuation_confidence([0.0, 0.0], 2) == 0.0

    def test_identical_prices_give_high_confidence(self):
        # Variance = 0, CV = 0 -> consistency_score = 1.0
        # 6 comparables -> count_score = 1.0 -> confidence = 0.4*1.0 + 0.6*1.0 = 1.0
        prices = [3500.0] * 6
        assert calculate_valuation_confidence(prices, 6) == pytest.approx(1.0)

    def test_moderate_variance_reduces_confidence(self):
        prices = [2500.0, 3000.0, 3500.0, 4000.0, 4500.0]
        conf = calculate_valuation_confidence(prices, 5)
        assert 0.4 <= conf <= 0.9

    def test_confidence_clamped_between_zero_and_one(self):
        # Extreme dispersion
        wild_prices = [100.0, 10_000.0, 50_000.0]
        conf = calculate_valuation_confidence(wild_prices, 3)
        assert 0.0 <= conf <= 1.0
