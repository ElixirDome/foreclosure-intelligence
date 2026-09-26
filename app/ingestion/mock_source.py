from app.ingestion.base import SourceAdapter


class MockAuctionSource(SourceAdapter):

    def fetch(self):
        return [
            {
                "auction_id": "MOCK-001",
                "property_address": "No 10 MG Road Bangalore",
                "area": "1500",
                "reserve_price": "12000000",
                "property_type": "Immovable Property",
                "survey_number": "123/4",
            },
            {
                "auction_id": "MOCK-002",
                "property_address": "No 20 Whitefield Road Bangalore",
            "area": "1800",
                "reserve_price": "15000000",
                "property_type": "Immovable Property",
                "survey_number": "567/8",
            },
        ]

    def extract(self, item):
        return {
            "external_id": item["auction_id"],
            "address": item["property_address"],
            "area_sqft": int(item["area"]),
            "opening_bid": float(item["reserve_price"]),
            "property_type": item["property_type"],
            "survey_number": item["survey_number"],
        }

    def get_documents(self, item):
        return [
            {
                "source_name": "MockAuctionSource",
                "source_url": "https://example.com/shared-auction-notice",
                "document_type": "auction_notice",
                "title": "Shared Auction Notice",
                "content": b"This is the exact same document content",
            }
        ]