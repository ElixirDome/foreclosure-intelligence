"""
Unit tests for extraction edge cases in app.services.pnb_extraction.
Tests date patterns, Indian land units (Kanal/Marla), currency formatting, and OCR quirks.
No database or external network access required.
"""

from datetime import date
import pytest
from app.services.pnb_extraction import (
    _clean_amount,
    _parse_area_sqft,
    _parse_date,
    _parse_price,
)


@pytest.mark.unit
class TestParseDate:
    def test_explicit_auction_date_labels(self):
        cases = [
            ("Auction Date: 27.10.2026", date(2026, 10, 27)),
            ("Date of Auction : 15/11/2026", date(2026, 11, 15)),
            ("Date & Time of E-Auction : 05-12-2026", date(2026, 12, 5)),
            ("Date and Time of EAuction: 22.09.2026", date(2026, 9, 22)),
        ]
        for text, expected in cases:
            assert _parse_date(text) == expected, f"Failed for: {text}"

    def test_date_with_time_hours_context(self):
        text = "E-auction on 28/10/2026 From 11:00 AM to 04:00 PM"
        assert _parse_date(text) == date(2026, 10, 28)

    def test_fallback_first_date_found(self):
        text = "Notice published under SARFAESI on 14.10.2026 by authorized officer"
        assert _parse_date(text) == date(2026, 10, 14)

    def test_invalid_or_missing_date_returns_none(self):
        assert _parse_date("No dates mentioned in this text") is None
        assert _parse_date("Notice dated 99/99/9999 invalid") is None
        assert _parse_date("") is None


@pytest.mark.unit
class TestParseAreaSqft:
    def test_square_meters_conversion(self):
        # 100 sq.m * 10.7639 = 1076 sq.ft
        assert _parse_area_sqft("Built-up area 100 Sq.Mtr") == 1076
        assert _parse_area_sqft("Land measuring 156 Sq. Mtr.") == round(156 * 10.7639)
        assert _parse_area_sqft("Plot 50 Sq.Meter") == round(50 * 10.7639)

    def test_square_feet_direct_parsing(self):
        assert _parse_area_sqft("Total carpet area 1250 Sq.Ft.") == 1250
        assert _parse_area_sqft("Measuring 2,500 Sq. Feet") == 2500

    def test_square_yards_conversion(self):
        # 100 sq yards * 9 = 900 sq ft
        assert _parse_area_sqft("Plot size 100 Sq. Yards") == 900
        assert _parse_area_sqft("Area measuring 250 Square Yards") == 2250

    def test_kanal_and_marla_punjab_measurements(self):
        # 1 Kanal = 20 Marlas, 1 Marla = 272.25 sq ft
        # 1 Kanal = 20 * 272.25 = 5445 sq ft
        assert _parse_area_sqft("Land 1 Kanal") == 5445
        # 1 Kanal 2 Marla = (20 + 2) * 272.25 = 5989.5 -> round to 5990
        assert _parse_area_sqft("Measuring 1 Kanal 2 Marlas") == 5990
        # 4 Marlas only = 4 * 272.25 = 1089
        assert _parse_area_sqft("Plot measuring 4 Marlas") == 1089

    def test_no_area_returns_none(self):
        assert _parse_area_sqft("Flat no 10, no area specified") is None
        assert _parse_area_sqft("") is None


@pytest.mark.unit
class TestParsePrice:
    def test_standard_reserve_price(self):
        assert _parse_price("Reserve Price: Rs. 34,38,000/-") == 3_438_000.0
        assert _parse_price("R.P. : Rs 12,50,000") == 1_250_000.0
        assert _parse_price("Reserve Price : ₹ 50,00,000") == 5_000_000.0

    def test_lakh_multiplier(self):
        assert _parse_price("Reserve Price: Rs. 15.50 Lakh") == 1_550_000.0
        assert _parse_price("R.P. Rs 45 lac") == 4_500_000.0

    def test_tabular_item_a_format(self):
        assert _parse_price("A) Rs. 28,00,000/-") == 2_800_000.0

    def test_no_price_returns_none(self):
        assert _parse_price("Auction notice without financial numbers") is None
        assert _parse_price("") is None


@pytest.mark.unit
class TestCleanAmount:
    def test_standard_cleaning(self):
        assert _clean_amount("1,00,000") == 100_000.0
        assert _clean_amount("5000000") == 5_000_000.0
        assert _clean_amount("25.75", has_lakh=True) == 2_575_000.0
