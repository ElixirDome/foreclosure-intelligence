"""
Unit tests for app.services.property_classifier.
Tests residential vs commercial classification, land-only rejection, and use-type labeling.
No database or external network access required.
"""

import pytest
from app.services.property_classifier import (
    classify_use_type,
    is_residential_property,
)


@pytest.mark.unit
class TestIsResidentialProperty:
    def test_strong_residential_terms(self):
        valid_cases = [
            "All that piece and parcel of residential flat no 302, Sector 15",
            "Independent house constructed on plot no 45",
            "Residential apartment in Prestige Palms, Bangalore",
            "Duplex villa situated at Green Acres",
            "Bungalow property with boundary wall",
            "Land and residential building constructed thereon",
        ]
        for desc in valid_cases:
            assert is_residential_property(desc) is True, f"Failed for: {desc}"

    def test_strong_non_residential_terms_rejected(self):
        invalid_cases = [
            "Commercial property shop no G-4, Shopping Complex",
            "Industrial premises with manufacturing plant and machinery",
            "Factory building measuring 500 sq yards",
            "Warehouse / Godown facility at Focal Point",
            "Commercial building with multi-tenant office space",
            "Agricultural land with tube-well installation",
        ]
        for desc in invalid_cases:
            assert is_residential_property(desc) is False, f"Failed for: {desc}"

    def test_land_measurement_patterns_treated_as_non_residential(self):
        land_cases = [
            "Land measuring 4 Bigha situated in revenue estate",
            "Agricultural plot 10 Biswas near canal",
            "Land area 2 Biswansi, Tehsil Dasuya",
        ]
        for desc in land_cases:
            assert is_residential_property(desc) is False, f"Failed for: {desc}"

    def test_residential_priority_over_land_or_commercial_mentions(self):
        # When explicit residential keyword is present, it takes precedence
        assert is_residential_property("Residential flat above commercial shop") is True
        assert is_residential_property("Residential house constructed on 1 Bigha land") is True

    def test_ambiguous_or_empty_text_rejected(self):
        assert is_residential_property("") is False
        assert is_residential_property("Plot no 14, Phase 2, Industrial Area") is False
        assert is_residential_property("General auction lot #4451") is False

    def test_case_insensitivity(self):
        assert is_residential_property("RESIDENTIAL FLAT NO 12") is True
        assert is_residential_property("commercial shop") is False


@pytest.mark.unit
class TestClassifyUseType:
    def test_pure_residential(self):
        assert classify_use_type("Residential flat in high-rise building") == "residential"
        assert classify_use_type("Independent bungalow with lawn") == "residential"

    def test_pure_commercial(self):
        assert classify_use_type("Commercial building with 6 shops") == "commercial"
        assert classify_use_type("Office space on 4th floor") == "commercial"
        assert classify_use_type("Industrial factory premises") == "commercial"
        assert classify_use_type("Warehouse and godown storage") == "commercial"

    def test_mixed_gives_residential_priority(self):
        assert classify_use_type("Residential apartment near commercial market") == "residential"

    def test_unclassified_returns_none(self):
        assert classify_use_type("") is None
        assert classify_use_type("Land parcel at Gurdaspur") is None
        assert classify_use_type("Survey no 124, Village Tugalwal") is None
