"""
Unit and integration tests for:
1. Auction Date Intelligence (Asia/Kolkata timezone, distinguishing auction vs deed/demand dates, latest date selection).
2. Historical auction notice ingestion gating (expired notices archived without creating active listings; postponements reactivate existing listings).
3. Authoritative backend visibility rules (sold and expired listings hidden from active queries unless requested).
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import pytest

from app.models import Document, Property, PropertyDocument, User
from app.services.auction_date import (
    IST_TIMEZONE,
    extract_latest_auction_date,
    extract_verified_auction_dates,
    get_current_ist_date,
    is_auction_current,
    parse_indian_date_string,
)
from app.services.properties import get_properties, save_extracted_properties
from app.schemas import ExtractedProperty


class TestAuctionDateIntelligence:
    def test_timezone_is_kolkata(self):
        assert IST_TIMEZONE == ZoneInfo("Asia/Kolkata")
        today_ist = get_current_ist_date()
        assert isinstance(today_ist, date)

    def test_parse_indian_date_formats(self):
        assert parse_indian_date_string("26.11.2026") == date(2026, 11, 26)
        assert parse_indian_date_string("15/12/2026") == date(2026, 12, 15)
        assert parse_indian_date_string("05-01-2027") == date(2027, 1, 5)
        assert parse_indian_date_string("26 November 2026") == date(2026, 11, 26)
        assert parse_indian_date_string("26 Nov 2026") == date(2026, 11, 26)

    def test_distinguishes_auction_date_from_sale_deeds_and_demand_notices(self):
        text = (
            "Property mortgaged vide Sale Deed No. 4186 dated 10.09.2008. "
            "Demand Notice under section 13(2) issued on 14.04.2024. "
            "Possession notice dated 20.08.2024. "
            "Date and time of e-auction: 26.11.2026 from 11:00 AM to 04:00 PM. "
            "Last date of submission of EMD: 24.11.2026."
        )
        verified_dates = extract_verified_auction_dates(text)
        assert date(2026, 11, 26) in verified_dates
        assert date(2008, 9, 10) not in verified_dates
        assert date(2024, 4, 14) not in verified_dates
        assert date(2024, 8, 20) not in verified_dates
        assert extract_latest_auction_date(text) == date(2026, 11, 26)

    def test_rescheduled_date_takes_precedence(self):
        text = (
            "Initial Auction Date: 15.10.2026. "
            "Corrigendum / Rescheduled Date of E-Auction: 28.11.2026 from 11:00 AM to 04:00 PM."
        )
        latest = extract_latest_auction_date(text)
        assert latest == date(2026, 11, 28)

    def test_is_auction_current_logic(self):
        as_of = date(2026, 11, 6)
        assert is_auction_current(date(2026, 11, 26), as_of_date=as_of) is True
        assert is_auction_current(date(2026, 11, 6), as_of_date=as_of) is True
        assert is_auction_current(date(2026, 10, 20), as_of_date=as_of) is False
        assert is_auction_current(None, as_of_date=as_of) is True


class TestHistoricalListingIngestionGating:
    def test_save_extracted_properties_skips_past_auctions(self, db):
        user = db.query(User).first()
        if not user:
            user = User(email="ingestgate@example.com", password_hash="pw")
            db.add(user)
            db.flush()

        today_ist = get_current_ist_date()
        past_dt = datetime.combine(today_ist - timedelta(days=30), datetime.min.time())
        future_dt = datetime.combine(today_ist + timedelta(days=30), datetime.min.time())

        extracted_items = [
            ExtractedProperty(
                address="Past Property 101, Test Street",
                opening_bid=500000.0,
                auction_start=past_dt,
                property_type="residential",
            ),
            ExtractedProperty(
                address="Future Property 202, Test Street",
                opening_bid=750000.0,
                auction_start=future_dt,
                property_type="residential",
            ),
        ]

        result = save_extracted_properties(db, extracted_items, user_id=user.id)

        # Past property must be skipped without creating an active listing
        assert any(item.get("reason") == "historical_expired_auction_archived" for item in result["skipped"])
        # Future property must be saved
        assert len(result["saved"]) == 1
        assert result["saved"][0].address == "Future Property 202, Test Street"

        # Cleanup
        db.query(Property).filter(Property.address.in_([
            "Past Property 101, Test Street",
            "Future Property 202, Test Street",
        ])).delete(synchronize_session=False)
        db.commit()


class TestBackendListingVisibilityRules:
    def test_get_properties_hides_sold_and_expired_by_default(self, db):
        user = db.query(User).first()
        if not user:
            user = User(email="visibilitytest@example.com", password_hash="pw")
            db.add(user)
            db.flush()

        today_ist = get_current_ist_date()
        past_date = today_ist - timedelta(days=10)
        future_date = today_ist + timedelta(days=20)

        # 1. Active future property
        prop_active = Property(
            user_id=user.id,
            address="Active Future Villa 701, Test Road",
            city="Bengaluru",
            auction_date=future_date,
            foreclosure_status="scheduled",
            reserve_price=8000000.0,
            property_type="residential",
            property_key="test:active:701",
        )
        # 2. Expired past auction date property
        prop_expired = Property(
            user_id=user.id,
            address="Expired Past Villa 702, Test Road",
            city="Bengaluru",
            auction_date=past_date,
            foreclosure_status="scheduled",
            reserve_price=6000000.0,
            property_type="residential",
            property_key="test:expired:702",
        )
        # 3. Sold property
        prop_sold = Property(
            user_id=user.id,
            address="Sold Villa 703, Test Road",
            city="Bengaluru",
            auction_date=future_date,
            foreclosure_status="sold",
            reserve_price=9000000.0,
            property_type="residential",
            property_key="test:sold:703",
        )
        # 4. Cancelled property
        prop_cancelled = Property(
            user_id=user.id,
            address="Cancelled Villa 704, Test Road",
            city="Bengaluru",
            auction_date=future_date,
            foreclosure_status="cancelled",
            reserve_price=7000000.0,
            property_type="residential",
            property_key="test:cancelled:704",
        )

        db.add_all([prop_active, prop_expired, prop_sold, prop_cancelled])
        db.commit()

        # Query default active listings
        res_default = get_properties(db, search="Villa 70", limit=10)
        item_addresses = [item["address"] for item in res_default["items"]]

        # Authoritative rule: only active future lot is visible
        assert "Active Future Villa 701, Test Road" in item_addresses
        assert "Expired Past Villa 702, Test Road" not in item_addresses
        assert "Sold Villa 703, Test Road" not in item_addresses
        assert "Cancelled Villa 704, Test Road" not in item_addresses

        # Query with include_expired=True returns the expired auction lot, but keeps sold/cancelled excluded
        res_with_expired = get_properties(db, search="Villa 70", include_expired=True, limit=10)
        exp_addresses = [item["address"] for item in res_with_expired["items"]]
        assert "Active Future Villa 701, Test Road" in exp_addresses
        assert "Expired Past Villa 702, Test Road" in exp_addresses
        assert "Sold Villa 703, Test Road" not in exp_addresses

        # Query explicitly for sold returns the sold lot
        res_sold = get_properties(db, search="Villa 70", foreclosure_status="sold", limit=10)
        sold_addresses = [item["address"] for item in res_sold["items"]]
        assert "Sold Villa 703, Test Road" in sold_addresses
        assert "Active Future Villa 701, Test Road" not in sold_addresses

        # Teardown
        db.query(Property).filter(Property.property_key.in_([
            "test:active:701",
            "test:expired:702",
            "test:sold:703",
            "test:cancelled:704",
        ])).delete(synchronize_session=False)
        db.commit()
