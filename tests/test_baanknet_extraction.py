"""
Tests for Baanknet source data extraction, financial field distinction,
and end-to-end persistence without value fabrication.
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path
import pytest

from app.ingestion.banknet_source import BankNetSourceAdapter
from app.ingestion.save import save_ingested_properties
from app.models import IngestionRun, Property, User


@pytest.fixture
def baanknet_hit():
    fixture_path = Path(__file__).parent / "fixtures" / "baanknet_listing_sample.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["data"]["data"][0]


class TestBaanknetExtraction:
    def test_extract_baanknet_fields_from_fixture(self, baanknet_hit):
        adapter = BankNetSourceAdapter(download_documents=False)
        extracted = adapter.extract(baanknet_hit)

        assert extracted is not None
        # Reserve price, EMD, and increment must be kept distinct
        assert extracted["reserve_price"] == 3438000.0
        assert extracted["emd"] == 344000.0
        assert extracted["increment_amount"] == 25000.0

        # Crucial requirement: opening_bid must NOT be fabricated from reservePrice
        assert extracted["opening_bid"] is None

        # Dates & times
        assert extracted["auction_date"] == date(2026, 11, 15)
        assert extracted["auction_start"] is not None
        assert extracted["auction_end"] is not None

        # Raw status preserved
        assert extracted["raw_status"] == "upcoming"
        assert extracted["foreclosure_status"] == "upcoming"

        # Property types & possession
        assert extracted["possession_type"] == "Physical"
        assert extracted["property_type"] == "residential"
        assert extracted["property_sub_type"] == "Apartment / Flat"

        # Location details
        assert extracted["city"] == "Pathankot"
        assert extracted["locality"] == "Defence Road"
        assert extracted["district"] == "Gurdaspur"
        assert extracted["state"] == "Punjab"
        assert extracted["pincode"] == "145001"

        # Bank and branch
        assert extracted["bank_name"] == "Punjab National Bank"
        assert extracted["branch_name"] == "Circle SASTRA Centre Pathankot"

        # Carpet area preferred
        assert extracted["area_sqft"] == 1250

        # Extra data preserved
        assert extracted["extra_data"]["inspectionFrom"] == "2026-11-05T10:00:00Z"
        assert extracted["extra_data"]["emdSubmissionDeadline"] == "2026-11-12T17:00:00Z"

    def test_get_evidence_preserves_distinct_financial_fields(self, baanknet_hit):
        adapter = BankNetSourceAdapter(download_documents=False)
        evidence = adapter.get_evidence(baanknet_hit)

        fields = {e["field"]: e["value"] for e in evidence}
        assert "reserve_price" in fields
        assert "emd" in fields
        assert "increment_amount" in fields
        assert fields["reserve_price"] == "3438000.0"
        assert fields["emd"] == "344000.0"
        assert fields["increment_amount"] == "25000.0"

    def test_persistence_stores_distinct_fields_without_fabrication(self, db, baanknet_hit):
        user = User(email="baanknet_tester@example.com", password_hash="hash", role="admin")
        db.add(user)
        run = IngestionRun(
            source_name="BankNet",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.commit()

        adapter = BankNetSourceAdapter(download_documents=False)
        extracted = adapter.extract(baanknet_hit)
        evidence = adapter.get_evidence(baanknet_hit)

        item = {
            "property": extracted,
            "documents": [],
            "evidence": evidence,
        }

        result = save_ingested_properties(
            db=db,
            properties=[item],
            user_id=user.id,
            ingestion_run_id=run.id,
        )
        db.commit()

        saved = result["saved"]
        assert len(saved) == 1
        prop = db.query(Property).filter(Property.id == saved[0].id).first()
        assert prop is not None

        # Verify distinct fields in database
        assert float(prop.reserve_price) == 3438000.0
        assert float(prop.emd) == 344000.0
        assert float(prop.increment_amount) == 25000.0
        assert prop.opening_bid is None  # NOT fabricated!
        assert prop.price is None
        assert prop.possession_type == "Physical"
        assert prop.district == "Gurdaspur"
        assert prop.state == "Punjab"
        assert prop.pincode == "145001"
        assert prop.raw_status == "upcoming"
