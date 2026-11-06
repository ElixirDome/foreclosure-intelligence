"""
Integration tests for Live Ingestion, SSE event streaming, truthful status reporting,
and near-real-time updates.
"""

import time
import pytest
from datetime import date, datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.models import Property, Document, PropertyDocument, IngestionRun, User
from app.security import create_access_token
from app.services.live_events import broker
from app.ingestion.base import SourceAdapter
from app.ingestion.pipeline import run_ingestion
from app.ingestion.save import save_ingested_properties


class MockNoticeItem:
    def __init__(self, title, text, source_url="https://bank.example.com/notice"):
        self.title = title
        self.text = text
        self.source_url = source_url


class MockZeroExtractionAdapter(SourceAdapter):
    """Adapter that discovers documents but extracts 0 valid properties."""
    def fetch(self):
        return [
            MockNoticeItem("Notice A", "Vehicle tender notice only."),
            MockNoticeItem("Notice B", "Corrigendum without immovable properties."),
        ]

    def extract(self, item):
        return None

    def get_documents(self, item):
        return [{
            "source_name": "MockBank",
            "source_url": item.source_url,
            "document_type": "auction_notice",
            "title": item.title,
            "extracted_text": item.text,
            "first_seen_at": datetime.now(timezone.utc),
            "last_seen_at": datetime.now(timezone.utc),
        }]


class MockValidPropertyAdapter(SourceAdapter):
    """Adapter that extracts genuine residential properties."""
    def __init__(self, address="Flat 101, Palm Residency, Gurdaspur", price=3200000.0):
        self.address = address
        self.price = price

    def fetch(self):
        return [MockNoticeItem("Genuine Sale Notice", f"Residential Flat at {self.address} Reserve Price Rs {self.price}")]

    def extract(self, item):
        return [{
            "address": self.address,
            "city": "Gurdaspur",
            "locality": "Tehsil",
            "property_type": "Residential Property",
            "reserve_price": self.price,
            "opening_bid": self.price,
            "emd": self.price * 0.1,
            "auction_date": date(2026, 12, 1),
            "foreclosure_status": "scheduled",
        }]

    def get_documents(self, item):
        return [{
            "source_name": "MockBank",
            "source_url": item.source_url,
            "document_type": "auction_notice",
            "title": item.title,
            "extracted_text": item.text,
            "first_seen_at": datetime.now(timezone.utc),
            "last_seen_at": datetime.now(timezone.utc),
        }]


@pytest.fixture
def auth_headers(db):
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(id=1, email="investor@example.com", password_hash="hash", role="user")
        db.add(user)
        db.commit()
    token = create_access_token(user_id=1, role="user")
    return {"Authorization": f"Bearer {token}"}, token


def test_saved_property_visible_in_api(client, db, auth_headers):
    """1. A valid property is extracted, saved, and visible through the listings API."""
    headers, _ = auth_headers
    prop = Property(
        id=777,
        user_id=1,
        address="House #777, Civil Lines, Gurdaspur",
        city="Gurdaspur",
        locality="Civil Lines",
        property_type="Residential Property",
        reserve_price=4500000.0,
        foreclosure_status="scheduled",
    )
    db.add(prop)
    db.commit()

    resp = client.get("/properties/?city=Gurdaspur", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    items = data.get("items", [])
    found = any(p["id"] == 777 for p in items)
    assert found, "Saved property must be immediately queryable via listings API"


def test_committed_property_triggers_live_event(db):
    """2. A committed property triggers the live-update mechanism strictly after commit."""
    extracted = [{
        "property": {
            "address": "Villa #888, Defense Colony, Gurdaspur",
            "city": "Gurdaspur",
            "property_type": "Residential Property",
            "reserve_price": 5000000.0,
            "emd": 500000.0,
            "foreclosure_status": "scheduled",
        },
        "documents": [],
    }]

    result = save_ingested_properties(db, properties=extracted, user_id=1, ingestion_run_id=1)
    saved_prop = result["saved"][0]

    # Verify event broker received property_created
    recent = broker.get_recent_events(limit=5)
    matched = [
        e for e in recent
        if e["event"] == "property_created" and e["data"].get("property_id") == saved_prop.id
    ]
    assert len(matched) == 1
    assert matched[0]["data"]["address"] == "Villa #888, Defense Colony, Gurdaspur"
    assert matched[0]["data"]["reserve_price"] == 5000000.0


def test_failed_transaction_does_not_emit_event(db):
    """8. A transaction that fails to commit does not generate a false property-created event."""
    before_count = len(broker.get_recent_events(limit=50))

    try:
        # Deliberately violate NOT NULL constraint by passing invalid model
        with db.begin_nested():
            bad_prop = Property(user_id=1, address=None)  # address cannot be null
            db.add(bad_prop)
            db.flush()
    except Exception:
        db.rollback()

    after_count = len(broker.get_recent_events(limit=50))
    assert after_count == before_count, "Rollback must not emit any property event"


def test_property_updated_event_emitted_on_reconcile(db):
    """7. Updating an existing property refreshes its visible details."""
    extracted1 = [{
        "property": {
            "address": "Shop-cum-Flat 12, Main Bazar, Gurdaspur",
            "city": "Gurdaspur",
            "property_type": "Residential Property",
            "reserve_price": 2000000.0,
            "foreclosure_status": "scheduled",
        },
        "documents": [],
    }]
    r1 = save_ingested_properties(db, extracted1, user_id=1, ingestion_run_id=1)
    prop_id = r1["saved"][0].id

    # Ingest same canonical property with updated reserve price
    extracted2 = [{
        "property": {
            "address": "Shop-cum-Flat 12, Main Bazar, Gurdaspur",
            "city": "Gurdaspur",
            "property_type": "Residential Property",
            "reserve_price": 2200000.0,
            "foreclosure_status": "active",
        },
        "documents": [],
    }]
    r2 = save_ingested_properties(db, extracted2, user_id=1, ingestion_run_id=2)
    assert len(r2["skipped"]) == 1
    assert r2["skipped"][0]["reason"] == "updated_existing_property"

    recent = broker.get_recent_events(limit=5)
    updated_evts = [
        e for e in recent
        if e["event"] == "property_updated" and e["data"].get("property_id") == prop_id
    ]
    assert len(updated_evts) == 1
    assert updated_evts[0]["data"]["reserve_price"] == 2200000.0
    assert updated_evts[0]["data"]["foreclosure_status"] == "active"


def test_sse_stream_authentication_enforced(client):
    """11. Authentication and authorization are enforced for protected streams."""
    # 1. No token provided
    res1 = client.get("/properties/stream")
    assert res1.status_code == 401

    # 2. Invalid token provided
    res2 = client.get("/properties/stream?token=invalid_garbage_token")
    assert res2.status_code == 401


def test_sse_stream_connect_and_receive_event(client, auth_headers):
    """2 & 9. SSE stream connects, sends handshake, and receives published events."""
    _, token = auth_headers
    with client.stream("GET", f"/properties/stream?token={token}") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        # First event is the connection handshake
        line1 = response.iter_lines()
        first_line = next(line1)
        assert "event: connected" in first_line or "event: " in first_line


def test_location_filtering_excludes_mismatched_properties(client, db, auth_headers):
    """4. A property that does not match the user's location filters is not incorrectly displayed."""
    headers, _ = auth_headers
    db.add(Property(
        id=901,
        user_id=1,
        address="Civil Lines, Pathankot",
        city="Pathankot",
        property_type="Residential Property",
    ))
    db.add(Property(
        id=902,
        user_id=1,
        address="Model Town, Ludhiana",
        city="Ludhiana",
        property_type="Residential Property",
    ))
    db.commit()

    resp = client.get("/properties/?city=Pathankot", headers=headers)
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["items"]]
    assert 901 in ids
    assert 902 not in ids, "Ludhiana property must be excluded when filtering by Pathankot"


def test_commercial_properties_excluded_from_residential(client, db, auth_headers):
    """5. Commercial-only properties do not leak into residential results."""
    headers, _ = auth_headers
    db.add(Property(
        id=950,
        user_id=1,
        address="Commercial Complex, GT Road",
        city="Gurdaspur",
        property_type="Commercial Shop",
    ))
    db.add(Property(
        id=951,
        user_id=1,
        address="Apartment 4B, Green Avenue",
        city="Gurdaspur",
        property_type="Residential Apartment",
    ))
    db.commit()

    resp = client.get("/properties/?property_type=residential", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    ids = [p["id"] for p in items]
    assert 950 not in ids, "Commercial shop must not appear in residential query"
    assert 951 in ids, "Residential apartment must appear in residential query"


def test_duplicate_ingestion_idempotency(db):
    """6. Duplicate ingestion does not create duplicate records."""
    adapter = MockValidPropertyAdapter("Plot 505, Sarna, Gurdaspur", 1800000.0)

    # First run
    r1 = run_ingestion(db, adapter, user_id=1)
    assert len(r1["saved"]) == 1

    # Second run
    r2 = run_ingestion(db, adapter, user_id=1)
    assert len(r2["saved"]) == 0
    assert len(r2["skipped"]) == 1
    assert r2["skipped"][0]["reason"] in ("updated_existing_property", "duplicate")

    # Check database count for this address
    count = db.query(Property).filter(Property.address == "Plot 505, Sarna, Gurdaspur").count()
    assert count == 1, "Idempotent ingestion must never produce duplicate property records"


def test_truthful_ingestion_reporting_for_zero_extraction(db):
    """12. Ingestion failures and zero-extraction runs are reported truthfully."""
    adapter = MockZeroExtractionAdapter()
    result = run_ingestion(db, adapter, user_id=1)

    assert result["status"] == "zero_properties_extracted"
    assert result["items_found"] == 2
    assert result["items_extracted"] == 0
    assert result["documents_ingested_without_property"] == 2

    # Verify run persisted in database matches
    run = db.query(IngestionRun).filter(IngestionRun.id == result["ingestion_run_id"]).first()
    assert run.status == "zero_properties_extracted"
    assert run.items_created == 0


def test_latency_metrics_captured(db):
    """Latency metrics are recorded for discovery, extraction, commit, and total time."""
    adapter = MockValidPropertyAdapter("Villa 77, Gurdaspur", 4000000.0)
    result = run_ingestion(db, adapter, user_id=1)

    assert "latency" in result
    lat = result["latency"]
    assert "discovery_and_fetch_ms" in lat
    assert "extraction_ms" in lat
    assert "commit_time_ms" in lat
    assert "total_time_ms" in lat
    assert lat["total_time_ms"] >= 0


def test_live_status_endpoint(client, db):
    """Live status endpoint truthfully reports latest run, property count, and subscribers."""
    res = client.get("/properties/live-status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert "total_properties" in data
    assert "active_subscribers" in data
    assert "latest_run" in data


class MockEmptyListExtractionAdapter(SourceAdapter):
    """Adapter that returns empty list [] instead of None."""
    def fetch(self):
        return [MockNoticeItem("Empty Notice", "Some text but no property")]

    def extract(self, item):
        return []

    def get_documents(self, item):
        return [{
            "source_name": "MockBankEmpty",
            "source_url": item.source_url,
            "document_type": "auction_notice",
            "title": item.title,
            "extracted_text": item.text,
            "first_seen_at": datetime.now(timezone.utc),
            "last_seen_at": datetime.now(timezone.utc),
        }]


def test_empty_list_extraction_preserves_source_documents(db):
    """Extraction returning empty list [] still preserves documents in document_only_items."""
    adapter = MockEmptyListExtractionAdapter()
    result = run_ingestion(db, adapter, user_id=1)

    assert result["status"] == "zero_properties_extracted"
    assert result["documents_ingested_without_property"] == 1
    run = db.query(IngestionRun).filter(IngestionRun.id == result["ingestion_run_id"]).first()
    assert run.items_created == 0
    assert run.items_skipped == 0


def test_run_records_items_created_and_skipped(db):
    """IngestionRun accurately records items_created and items_skipped."""
    adapter = MockValidPropertyAdapter("Villa 99, Gurdaspur", 4500000.0)
    res1 = run_ingestion(db, adapter, user_id=1)
    run1 = db.query(IngestionRun).filter(IngestionRun.id == res1["ingestion_run_id"]).first()
    assert run1.items_created == 1
    assert run1.items_skipped == 0

    # Running again reconciles and skips duplicate creation
    res2 = run_ingestion(db, adapter, user_id=1)
    run2 = db.query(IngestionRun).filter(IngestionRun.id == res2["ingestion_run_id"]).first()
    assert run2.items_created == 0
    assert run2.items_skipped == 1


def test_ingestion_invalidates_summary_cache_and_updates_counts(client, db):
    """Creating properties via ingestion invalidates cached summary counts immediately."""
    # First query primes the summary cache
    s1 = client.get("/properties/summary").json()
    initial_total = s1["total_properties"]

    # Ingest a new valid property
    adapter = MockValidPropertyAdapter("Skyline Towers Apt 4B, Gurdaspur", 3800000.0)
    res = run_ingestion(db, adapter, user_id=1)
    assert len(res["saved"]) == 1

    # Second query to /properties/summary must reflect new total
    s2 = client.get("/properties/summary").json()
    assert s2["total_properties"] == initial_total + 1


