"""
Unit tests for app.domain.deal_analysis.
Pure business rules: discount, deal score, risk level, confidence adjustment, and ratings.
No database or external network access required.
"""

import pytest
from app.domain.deal_analysis import (
    DEAL_SCORE_RISK_MULTIPLIER,
    FORECLOSURE_RISK_LEVELS,
    calculate_confidence_adjusted_score,
    calculate_deal_rating,
    calculate_deal_score,
    calculate_discount,
    calculate_price_per_sqft,
    get_risk_level,
)


@pytest.mark.unit
class TestCalculateDiscount:
    def test_standard_discount(self):
        estimated_value = 5_000_000.0
        opening_bid = 3_500_000.0
        amount, pct = calculate_discount(estimated_value, opening_bid)
        assert amount == pytest.approx(1_500_000.0)
        assert pct == pytest.approx(30.0)

    def test_negative_discount_overbid(self):
        estimated_value = 4_000_000.0
        opening_bid = 5_000_000.0
        amount, pct = calculate_discount(estimated_value, opening_bid)
        assert amount == pytest.approx(-1_000_000.0)
        assert pct == pytest.approx(-25.0)

    def test_zero_discount_equal_values(self):
        amount, pct = calculate_discount(2_000_000.0, 2_000_000.0)
        assert amount == pytest.approx(0.0)
        assert pct == pytest.approx(0.0)

    def test_zero_or_negative_estimated_value_returns_none(self):
        assert calculate_discount(0.0, 1_000_000.0) == (None, None)
        assert calculate_discount(-500_000.0, 1_000_000.0) == (None, None)

    def test_none_inputs_return_none(self):
        assert calculate_discount(None, 1_000_000.0) == (None, None)
        assert calculate_discount(5_000_000.0, None) == (None, None)
        assert calculate_discount(None, None) == (None, None)

    def test_zero_opening_bid(self):
        amount, pct = calculate_discount(5_000_000.0, 0.0)
        assert amount == pytest.approx(5_000_000.0)
        assert pct == pytest.approx(100.0)


@pytest.mark.unit
class TestCalculatePricePerSqft:
    def test_standard_price_per_sqft(self):
        price = 3_000_000.0
        area = 1_000.0
        assert calculate_price_per_sqft(price, area) == pytest.approx(3_000.0)

    def test_none_or_invalid_inputs(self):
        assert calculate_price_per_sqft(None, 1_000.0) is None
        assert calculate_price_per_sqft(3_000_000.0, None) is None
        assert calculate_price_per_sqft(3_000_000.0, 0.0) is None
        assert calculate_price_per_sqft(3_000_000.0, -100.0) is None

    def test_small_area_fractional_precision(self):
        res = calculate_price_per_sqft(250_000.0, 50.5)
        assert res == pytest.approx(250_000.0 / 50.5)


@pytest.mark.unit
class TestCalculateDealScore:
    def test_standard_score_calculation(self):
        # 40% discount, risk level 1 -> 40 - (1 * 5) = 35
        score = calculate_deal_score(40.0, 1)
        assert score == pytest.approx(35.0)

    def test_score_clamped_to_zero_on_high_risk_low_discount(self):
        # 5% discount, risk level 3 -> 5 - (3 * 5) = -10 -> clamped to 0
        score = calculate_deal_score(5.0, 3)
        assert score == 0.0

    def test_score_clamped_to_100_on_extreme_discount(self):
        # 120% discount, risk level 1 -> 120 - 5 = 115 -> clamped to 100
        score = calculate_deal_score(120.0, 1)
        assert score == 100.0

    def test_none_discount_returns_none(self):
        assert calculate_deal_score(None, 1) is None


@pytest.mark.unit
class TestConfidenceAdjustedScore:
    def test_perfect_confidence_leaves_score_unchanged(self):
        assert calculate_confidence_adjusted_score(80.0, 1.0) == pytest.approx(80.0)

    def test_reduced_confidence_scales_score(self):
        assert calculate_confidence_adjusted_score(80.0, 0.5) == pytest.approx(40.0)

    def test_none_confidence_returns_base_score(self):
        assert calculate_confidence_adjusted_score(75.0, None) == 75.0

    def test_none_base_score_returns_none(self):
        assert calculate_confidence_adjusted_score(None, 0.8) is None

    def test_zero_confidence_returns_zero(self):
        assert calculate_confidence_adjusted_score(75.0, 0.0) == 0.0


@pytest.mark.unit
class TestCalculateDealRating:
    def test_rating_thresholds(self):
        assert calculate_deal_rating(35.0) == "excellent"
        assert calculate_deal_rating(30.0) == "excellent"
        assert calculate_deal_rating(25.0) == "good"
        assert calculate_deal_rating(20.0) == "good"
        assert calculate_deal_rating(15.0) == "moderate"
        assert calculate_deal_rating(10.0) == "moderate"
        assert calculate_deal_rating(5.0) == "low"
        assert calculate_deal_rating(-10.0) == "low"

    def test_none_discount_rating(self):
        assert calculate_deal_rating(None) is None


@pytest.mark.unit
class TestGetRiskLevel:
    def test_known_statuses(self):
        assert get_risk_level("scheduled") == 1
        assert get_risk_level("upcoming") == 1
        assert get_risk_level("active") == 2
        assert get_risk_level("sold") == 3
        assert get_risk_level("cancelled") == 3

    def test_case_insensitivity(self):
        assert get_risk_level("SCHEDULED") == 1
        assert get_risk_level("Upcoming") == 1
        assert get_risk_level("AcTiVe") == 2

    def test_unknown_or_none_defaults_to_moderate_risk(self):
        assert get_risk_level(None) == 2
        assert get_risk_level("disputed") == 2
        assert get_risk_level("") == 2
