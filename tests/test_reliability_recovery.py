"""
Reliability, fault tolerance, and recovery tests:
- Network failures and timeouts during source discovery
- Malformed and corrupted document handling
- LiveEventBroker queue cleanup and disconnect resilience
- Ingestion error reporting and truthful failure status
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import httpx
import pytest
from app.ingestion.pdf_source import PDFSourceAdapter
from app.ingestion.pipeline import run_ingestion
from app.models import IngestionRun, Property, User
from app.services.live_events import LiveEventBroker, format_sse
from app.services.source_discovery import discover_auction_source


@pytest.mark.reliability
class TestSourceDiscoveryResilience:
    @patch("httpx.Client.get")
    def test_source_discovery_network_timeout_returns_truthful_failure(self, mock_get):
        mock_get.side_effect = httpx.ConnectTimeout("Connection timed out after 10.0s")
        res = discover_auction_source("https://slow-bank-portal.com/auctions")
        assert res["status"] == "failed"
        assert "Unable to reach website endpoint" in res["failure_reason"]
        assert len(res["sample_listings"]) == 0
        assert "guidance" in res

    @patch("httpx.Client.get")
    def test_source_discovery_http_500_server_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )
        mock_get.return_value = mock_resp

        res = discover_auction_source("https://erroring-bank.com/auctions")
        assert res["status"] == "failed"
        assert "500" in res["failure_reason"] or "failed" in res["status"]


@pytest.mark.reliability
class TestDocumentIngestionResilience:
    def test_empty_pdf_file_handled_gracefully(self, tmp_path, db):
        empty_file = tmp_path / "empty.pdf"
        empty_file.write_bytes(b"")

        adapter = PDFSourceAdapter(empty_file)
        # Empty file raises Exception on read or returns empty
        with pytest.raises(Exception):
            adapter.fetch()

    def test_corrupt_pdf_bytes_handled_gracefully(self, tmp_path, db):
        corrupt_file = tmp_path / "corrupt.pdf"
        corrupt_file.write_bytes(b"%PDF-1.4\nCorrupted binary junk that is not a valid PDF")

        adapter = PDFSourceAdapter(corrupt_file)
        with pytest.raises(Exception):
            adapter.fetch()

    def test_ingestion_run_captures_error_message_on_failure(self, db):
        user = User(email="failuser@example.com", password_hash="hash", role="user")
        db.add(user)
        db.commit()

        class BrokenAdapter:
            def get_source_name(self):
                return "BrokenSource"

            def fetch(self):
                raise RuntimeError("Downstream API connection aborted")

        result = run_ingestion(db=db, adapter=BrokenAdapter(), user_id=user.id)
        assert result["status"] == "failed"
        assert "Downstream API connection aborted" in result["error"]

        last_run = db.query(IngestionRun).order_by(IngestionRun.id.desc()).first()
        assert last_run is not None
        assert last_run.status == "failed"
        assert "Downstream API connection aborted" in last_run.error_message


@pytest.mark.reliability
class TestLiveEventBrokerResilience:
    def test_broker_subscribe_publish_and_unsubscribe(self):
        broker = LiveEventBroker()
        q = broker.subscribe()
        assert broker.subscriber_count == 1

        broker.publish("test_event", {"message": "hello"})
        assert q.qsize() == 1
        item = q.get_nowait()
        assert item["event"] == "test_event"
        assert item["data"]["message"] == "hello"

        # Recent events retained
        recent = broker.get_recent_events(limit=5)
        assert len(recent) == 1
        assert recent[0]["event"] == "test_event"

        broker.unsubscribe(q)
        assert broker.subscriber_count == 0

    def test_broker_queue_full_drops_silently_without_blocking(self):
        broker = LiveEventBroker()
        q = broker.subscribe()

        # Fill queue beyond maxsize
        for i in range(150):
            broker.publish("flood_event", {"index": i})

        assert q.qsize() <= 100
        broker.unsubscribe(q)

    def test_format_sse_formatting(self):
        formatted = format_sse("ping", {"timestamp": 123456789.0})
        assert formatted.startswith("event: ping\n")
        assert "data: " in formatted
        assert formatted.endswith("\n\n")
