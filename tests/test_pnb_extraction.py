from datetime import date, datetime, timezone
from pathlib import Path

from app.services.property_classifier import is_residential_property
from app.services.pnb_extraction import (
    _parse_area_sqft,
    _parse_date,
    _parse_emd,
    _parse_opening_bid,
    _parse_price,
    _parse_survey_number,
    extract_location,
    extract_pnb_properties,
    extract_pnb_property,
)
from app.models import Document, Evidence, IngestionRun, Property, PropertyDocument, User
from app.ingestion.save import save_ingested_properties


def test_pnb_area_parser_ignores_punctuation_without_digits():
    assert _parse_area_sqft("Area: , Sq Ft") is None
    assert _parse_area_sqft("Area: . Sq Mtr") is None
    assert _parse_area_sqft("Area: , Square Yards") is None


def test_pnb_area_parser_still_converts_valid_measurements():
    assert _parse_area_sqft("Area: 1,250 Sq Ft") == 1250
    assert _parse_area_sqft("Area: 100 Sq Mtr") == 1076
    assert _parse_area_sqft("Area: 100 Sq Yards") == 900


def test_pnb_area_parser_converts_kanal_and_marla():
    # 1 Kanal = 20 Marla = 5,445 sq ft; 1 Marla = 272.25 sq ft
    # 5 Kanal 17 Marla = (5*20 + 17) * 272.25 = 117 * 272.25 = 31,853 sq ft
    assert _parse_area_sqft("plot measuring 5 Kanal 17 Marla") == 31853
    assert _parse_area_sqft("measuring 1 Kanal 12 Marla") == 8712
    assert _parse_area_sqft("area 8 Marla") == 2178


def test_pnb_price_and_emd_parsing():
    # Malformed comma-only should return None safely
    assert _parse_price("Reserve Price: ,") is None
    assert _parse_price("Reserve Price: -") is None
    assert _parse_emd("EMD: ,") is None

    # Standard inline pricing
    assert _parse_price("Reserve Price: Rs. 12,50,000") == 1250000.0
    assert _parse_price("Reserve Price: Rs. 35.50 Lakh") == 3550000.0
    assert _parse_emd("EMD: Rs. 1,25,000") == 125000.0

    # Table formatted pricing
    table_sample = "A) Rs 35,52,000/-\nB) Rs 3,55,200/-\nC) Rs 50,000/-"
    assert _parse_price(table_sample) == 3552000.0
    assert _parse_emd(table_sample, reserve_price=3552000.0) == 355200.0

    # Outstanding dues must not be misidentified as EMD
    dues_sample = "B) Rs. 58,24,092.50 as on 31.03.2026\nEMD: Rs. 3,44,000/-"
    assert _parse_emd(dues_sample, reserve_price=3438000.0) == 344000.0


def test_pnb_auction_date_parsing():
    sample = "A. 17.05.2022\nC. 13.06.2024\nAuction Date: 27/10/2026 From 11AM to 4 PM"
    # Should prioritize the actual auction date, not demand notice dates
    assert _parse_date(sample) == date(2026, 10, 27)


def test_pnb_survey_number_parsing():
    assert _parse_survey_number("KhasraNo.31R/25/2(1-17)") == "31R/25/2(1-17)"
    assert _parse_survey_number("Khasra No. 144") == "144"
    assert _parse_survey_number("Survey No. 42/1A") == "42/1A"


def _get_armb_sample_path() -> Path:
    candidates = [
        Path(__file__).parent / "fixtures" / "armb_pathankot_doc45.txt",
        Path("tests/fixtures/armb_pathankot_doc45.txt"),
        Path("armb_pathankot_doc45.txt"),
        Path("C:/Dev/foreclosure-ui-review/armb_pathankot_doc45.txt"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def test_armb_pathankot_notice_extraction():
    sample_path = _get_armb_sample_path()
    assert sample_path.exists(), "ARMB Pathankot sample fixture must exist"
    text = sample_path.read_text(encoding="utf-8")
    assert is_residential_property(text) is True

    properties = extract_pnb_properties(text)
    assert len(properties) >= 1

    lot1 = properties[0]
    assert "Tugalwal" in lot1["address"]
    assert lot1["city"] == "Gurdaspur"
    assert lot1["reserve_price"] == 3552000.0
    assert lot1["opening_bid"] is None
    assert lot1["emd"] == 355200.0
    assert lot1["auction_date"] == date(2026, 10, 27)
    assert lot1["area_sqft"] == 31853
    assert lot1["property_type"] == "Residential Property"


def test_pnb_ocr_notice_extraction():
    sample_path = Path("pnb_test_ocr.txt")
    if not sample_path.exists():
        sample_path = Path("C:/Dev/foreclosure-ui-review/pnb_test_ocr.txt")

    if sample_path.exists():
        text = sample_path.read_text(encoding="utf-8")
        assert is_residential_property(text) is True

        properties = extract_pnb_properties(text)
        assert len(properties) >= 1

        flat = properties[0]
        assert "16/43" in flat["address"]
        assert flat["city"] == "Ghaziabad"
        assert flat["reserve_price"] == 3438000.0
        assert flat["emd"] == 344000.0
        assert flat["auction_date"] == date(2026, 10, 22)
        assert flat["property_type"] == "Residential Property"


def test_armb_pathankot_end_to_end_idempotency(db, monkeypatch):
    import app.services.auction_date
    monkeypatch.setattr(app.services.auction_date, "get_current_ist_date", lambda: date(2026, 10, 20))
    monkeypatch.setattr("app.ingestion.save.get_current_ist_date", lambda: date(2026, 10, 20))

    from app.database import Base
    Base.metadata.create_all(bind=db.get_bind())

    sample_path = _get_armb_sample_path()

    if not sample_path.exists():
        return

    text = sample_path.read_text(encoding="utf-8")
    props = extract_pnb_properties(text)
    assert len(props) == 1
    extracted_prop = props[0]

    run = IngestionRun(
        source_name="PNBSourceAdapter",
        started_at=datetime.now(timezone.utc),
        status="running",
    )
    db.add(run)
    db.commit()

    doc_payload = {
        "source_name": "PNB",
        "source_url": "https://www.pnb.bank.in/ViewTenderEauction.aspx?test=armb_pathankot",
        "document_type": "auction_notice",
        "title": "ARMB Pathankot E-Auction Notice",
        "content": text.encode("utf-8"),
    }

    rp_str = str(extracted_prop["reserve_price"])
    emd_str = str(extracted_prop["emd"])
    evidence = [
        {"field": "address", "value": extracted_prop["address"], "source_text": extracted_prop["address"], "extraction_method": "regex", "confidence": 0.95},
        {"field": "reserve_price", "value": rp_str, "source_text": f"Reserve Price: {rp_str}", "extraction_method": "regex", "confidence": 0.95},
        {"field": "emd", "value": emd_str, "source_text": f"EMD: {emd_str}", "extraction_method": "regex", "confidence": 0.95},
    ]

    items = [{
        "property": extracted_prop,
        "documents": [doc_payload],
        "evidence": evidence,
    }]

    # Run 1: initial ingestion
    res1 = save_ingested_properties(db, items, user_id=1, ingestion_run_id=run.id)
    assert len(res1["saved"]) == 1
    assert len(res1["skipped"]) == 0
    assert db.query(Property).count() == 1
    assert db.query(Document).count() == 1
    assert db.query(PropertyDocument).count() == 1
    assert db.query(Evidence).count() == 3

    # Run 2: repeated ingestion must be idempotent
    res2 = save_ingested_properties(db, items, user_id=1, ingestion_run_id=run.id)
    assert len(res2["saved"]) == 0
    assert len(res2["skipped"]) == 1
    assert db.query(Property).count() == 1
    assert db.query(Document).count() == 1
    assert db.query(PropertyDocument).count() == 1
    assert db.query(Evidence).count() == 3


def test_armb_property_visible_via_api(client, db, monkeypatch):
    import app.services.auction_date
    monkeypatch.setattr(app.services.auction_date, "get_current_ist_date", lambda: date(2026, 10, 20))
    monkeypatch.setattr("app.ingestion.save.get_current_ist_date", lambda: date(2026, 10, 20))
    monkeypatch.setattr("app.services.properties.get_current_ist_date", lambda: date(2026, 10, 20))

    sample_path = _get_armb_sample_path()

    if not sample_path.exists():
        return

    text = sample_path.read_text(encoding="utf-8")
    props = extract_pnb_properties(text)
    assert len(props) == 1
    extracted_prop = props[0]

    run = IngestionRun(
        source_name="PNBSourceAdapter",
        started_at=datetime.now(timezone.utc),
        status="running",
    )
    db.add(run)
    db.commit()

    doc_payload = {
        "source_name": "PNB",
        "source_url": "https://www.pnb.bank.in/ViewTenderEauction.aspx?test=armb_pathankot_api",
        "document_type": "auction_notice",
        "title": "ARMB Pathankot Notice",
        "content": text.encode("utf-8"),
    }

    items = [{
        "property": extracted_prop,
        "documents": [doc_payload],
        "evidence": [],
    }]

    save_ingested_properties(db, items, user_id=1, ingestion_run_id=run.id)

    response = client.get("/properties/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    addresses = [item["address"] for item in data["items"]]
    assert any("Tugalwal" in addr for addr in addresses)


def test_pnb_reserve_price_is_not_misreported_as_opening_bid():
    extracted = extract_pnb_property(
        "Reserve Price: Rs. 30,00,000/- EMD: Rs. 3,00,000/-"
    )
    assert extracted["reserve_price"] == 3000000.0
    assert extracted["opening_bid"] is None


def test_pnb_opening_bid_is_parsed_only_when_explicitly_labelled():
    assert _parse_opening_bid("Opening Bid: Rs. 25,00,000/-") == 2500000.0
    assert _parse_opening_bid("Starting Bid: ₹ 12.5 lakh") == 1250000.0
    assert _parse_opening_bid("Reserve Price: Rs. 30,00,000/-") is None


def test_pnb_emd_is_extracted_independently_from_reserve_price():
    extracted = extract_pnb_property(
        "Reserve Price: Rs. 30,00,000/- EMD: Rs. 3,00,000/-"
    )
    assert extracted["reserve_price"] == 3000000.0
    assert extracted["emd"] == 300000.0
    assert _parse_emd("Earnest Money Deposit: Rs. 2.5 lakh") == 250000.0
    assert _parse_emd("Reserve Price: Rs. 30,00,000/-") is None


def test_pnb_extraction_repairs_ocr_typos_and_recognizes_residential_plot():
    text = (
        "Auction Notice\n"
        "All that piece and parcel of Res1dentia1 Plot situated at "
        "Plot No. 14, Sector 8, Chandigarh measuring 120 Sq Yards. "
        "Reserve Price: Rs. 45,00,000/-"
    )
    properties = extract_pnb_properties(text)
    assert len(properties) == 1
    assert properties[0]["address"]
    assert properties[0]["reserve_price"] == 4500000.0
