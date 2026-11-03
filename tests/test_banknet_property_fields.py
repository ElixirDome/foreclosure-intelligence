from datetime import datetime
from app.ingestion.banknet_source import BankNetSourceAdapter


def test_banknet_extract_preserves_source_listing_fields_and_gallery():
    adapter = BankNetSourceAdapter(download_documents=False)
    item = {"_source": {
        "address": "Plot 14, Sector 8", "cityName": "Chandigarh",
        "propertyUniqueId": "BN-1001", "auctionId": "AUC-2001",
        "propertyDetailId": "detail-3001", "propertyBankName": "Example Bank",
        "branchName": "Chandigarh Branch", "propertyPossessionType": "Physical",
        "propertyImages": [
            {"imageUrl": "https://cdn.example.com/one.jpg"},
            {"filepath": "auction/two.jpg"},
            {"imageUrl": "https://cdn.example.com/one.jpg"},
            {"imageUrl": "javascript:alert(1)"},
        ],
        "auctionFrom": "2026-12-01T11:00:00", "auctionTo": "2026-12-01T14:00:00",
        "inspectionFrom": "2026-11-20T10:00:00", "inspectionTo": "2026-11-25T16:00:00",
        "emdSubmissionDeadline": "2026-11-28T17:00:00",
        "reservePrice": 5000000, "emd": 500000, "incrementPrice": 50000,
        "auctionStatus": "upcoming",
    }}
    result = adapter.extract(item)
    assert result["property_unique_id"] == "BN-1001"
    assert result["auction_id"] == "AUC-2001"
    assert result["bank_name"] == "Example Bank"
    assert result["possession_type"] == "Physical"
    assert result["reserve_price"] == 5000000
    assert result["emd"] == 500000
    assert result["opening_bid"] is None
    assert result["inspection_start"] == datetime(2026, 11, 20, 10, 0)
    assert result["emd_deadline"] == datetime(2026, 11, 28, 17, 0)
    assert result["listing_url"].endswith("/detail-3001")
    assert result["property_images"] == ["https://cdn.example.com/one.jpg", "https://cdn.baanknet.com/auction/two.jpg"]
