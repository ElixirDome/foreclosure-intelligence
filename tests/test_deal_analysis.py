"""
Unit tests for deterministic financial calculations and transparent auction assessments.
Verifies EMD percentage, reserve price per square foot, and deterministic assessment labels.
No arbitrary numerical deal scores or unverified AVM discounts.
"""

import pytest
from app.domain.auction_intelligence import (
    LABEL_FURTHER_INVESTIGATION,
    LABEL_IMPORTANT_RISKS,
    LABEL_INSUFFICIENT_INFO,
    LABEL_NO_MAJOR_CONCERNS,
    MARKET_VALUATION_UNAVAILABLE_MESSAGE,
    AuctionAssessment,
    AuctionIntelligenceDetails,
    FinancialIntelligence,
    PropertyLegalIntelligence,
    calculate_emd_percentage,
    calculate_reserve_price_per_sqft,
    evaluate_auction_assessment,
)


@pytest.mark.unit
class TestCalculateEMDPercentage:
    def test_standard_statutory_ten_percent(self):
        emd_pct = calculate_emd_percentage(emd=500_000, reserve_price=5_000_000)
        assert emd_pct == pytest.approx(10.0)

    def test_non_standard_emd_percentage(self):
        emd_pct = calculate_emd_percentage(emd=750_000, reserve_price=5_000_000)
        assert emd_pct == pytest.approx(15.0)

    def test_none_inputs_return_none_safely(self):
        assert calculate_emd_percentage(None, 5_000_000) is None
        assert calculate_emd_percentage(500_000, None) is None
        assert calculate_emd_percentage(None, None) is None

    def test_zero_or_negative_reserve_returns_none(self):
        # Never divides by zero
        assert calculate_emd_percentage(100_000, 0) is None
        assert calculate_emd_percentage(100_000, -1_000_000) is None

    def test_negative_emd_returns_none(self):
        assert calculate_emd_percentage(-50_000, 1_000_000) is None

    def test_never_assumes_missing_is_zero(self):
        assert calculate_emd_percentage(None, 1_000_000) is not 0.0


@pytest.mark.unit
class TestCalculateReservePricePerSqft:
    def test_standard_reserve_price_per_sqft(self):
        rate = calculate_reserve_price_per_sqft(reserve_price=3_000_000, area_sqft=1_000)
        assert rate == pytest.approx(3_000.0)

    def test_fractional_area_and_precision(self):
        rate = calculate_reserve_price_per_sqft(reserve_price=2_500_000, area_sqft=850.5)
        assert rate == pytest.approx(round(2_500_000 / 850.5, 2))

    def test_missing_area_returns_none(self):
        assert calculate_reserve_price_per_sqft(3_000_000, None) is None

    def test_missing_reserve_returns_none(self):
        assert calculate_reserve_price_per_sqft(None, 1_000) is None

    def test_zero_or_negative_area_returns_none(self):
        assert calculate_reserve_price_per_sqft(3_000_000, 0) is None
        assert calculate_reserve_price_per_sqft(3_000_000, -500) is None


@pytest.mark.unit
class TestTransparentAuctionAssessment:
    def test_insufficient_information_when_reserve_missing(self):
        financial = FinancialIntelligence(reserve_price=None, emd=None)
        auction = AuctionIntelligenceDetails()
        legal = PropertyLegalIntelligence()

        assessment = evaluate_auction_assessment(financial, auction, legal)
        assert assessment.assessment_label == LABEL_INSUFFICIENT_INFO
        assert any("Reserve price" in m for m in assessment.missing_information)

    def test_important_risks_identified_when_litigation_disclosed(self):
        financial = FinancialIntelligence(
            reserve_price=5_000_000,
            emd=500_000,
            emd_percentage=10.0,
            property_area=1200,
            reserve_price_per_sqft=4166.67,
        )
        auction = AuctionIntelligenceDetails(auction_status="scheduled")
        legal = PropertyLegalIntelligence(
            possession_type="physical",
            pending_litigation=["SA 123/2025 pending before DRT Chandigarh"],
        )

        assessment = evaluate_auction_assessment(financial, auction, legal)
        assert assessment.assessment_label == LABEL_IMPORTANT_RISKS
        assert any("DRT" in c for c in assessment.important_concerns)

    def test_further_investigation_required_on_symbolic_possession(self):
        financial = FinancialIntelligence(
            reserve_price=4_000_000,
            emd=400_000,
            emd_percentage=10.0,
            property_area=1000,
            reserve_price_per_sqft=4000.0,
        )
        auction = AuctionIntelligenceDetails(auction_status="scheduled")
        legal = PropertyLegalIntelligence(
            possession_type="symbolic",
        )

        assessment = evaluate_auction_assessment(financial, auction, legal)
        assert assessment.assessment_label == LABEL_FURTHER_INVESTIGATION
        assert any("Section 14" in p for p in assessment.possession_concerns)
        assert any("Symbolic" in c for c in assessment.important_concerns)

    def test_no_major_concerns_when_clean_and_physical_possession(self):
        financial = FinancialIntelligence(
            reserve_price=3_500_000,
            emd=350_000,
            emd_percentage=10.0,
            property_area=1000,
            reserve_price_per_sqft=3500.0,
        )
        auction = AuctionIntelligenceDetails(
            auction_status="scheduled",
            inspection_window="10-Nov-2026 11:00 AM to 02:00 PM",
        )
        legal = PropertyLegalIntelligence(
            possession_type="physical",
            disclosed_encumbrances=[],
            pending_litigation=[],
        )

        assessment = evaluate_auction_assessment(financial, auction, legal)
        assert assessment.assessment_label == LABEL_NO_MAJOR_CONCERNS

    def test_auction_status_is_procedural_not_risk(self):
        financial = FinancialIntelligence(
            reserve_price=3_000_000,
            emd=300_000,
            emd_percentage=10.0,
            property_area=900,
            reserve_price_per_sqft=3333.33,
        )
        auction = AuctionIntelligenceDetails(
            auction_status="active",
            inspection_window="Scheduled",
        )
        legal = PropertyLegalIntelligence(
            possession_type="physical",
        )

        assessment = evaluate_auction_assessment(financial, auction, legal)
        # Status 'active' or 'scheduled' is procedural, not converted into arbitrary risk score
        assert any("active" in p for p in assessment.procedural_considerations)
        assert assessment.assessment_label == LABEL_NO_MAJOR_CONCERNS

    def test_market_valuation_explicitly_unavailable(self):
        financial = FinancialIntelligence()
        assert financial.market_valuation_status == MARKET_VALUATION_UNAVAILABLE_MESSAGE
