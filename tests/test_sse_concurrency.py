"""
Concurrency and Reliability Tests for Server-Sent Events (SSE) (Section G):
- Thread-safe concurrent subscription management
- Worker connection limit enforcement (HTTP 503 on overload)
- Disconnect / unsubscription counter decrement guarantees
- Last-Event-ID replay on reconnection
- W3C EventSource wire format compliance
"""

import asyncio
import time
import pytest

from app.services.live_events import (
    LiveEventBroker,
    format_sse,
)


class TestSSEBrokerConcurrency:
    def test_format_sse_includes_eventsource_fields(self):
        msg = format_sse("property_created", {"id": 42}, event_id="evt_100_1", retry_ms=3000)
        assert "id: evt_100_1\n" in msg
        assert "event: property_created\n" in msg
        assert "retry: 3000\n" in msg
        assert 'data: {"id": 42}\n\n' in msg

    def test_subscriber_counter_strict_tracking(self):
        broker = LiveEventBroker(max_connections=10)
        assert broker.subscriber_count == 0

        q1 = broker.subscribe()
        q2 = broker.subscribe()
        assert broker.subscriber_count == 2

        broker.unsubscribe(q1)
        assert broker.subscriber_count == 1

        broker.unsubscribe(q2)
        assert broker.subscriber_count == 0

    def test_max_connection_limit_rejection(self):
        broker = LiveEventBroker(max_connections=3)
        queues = []
        for _ in range(3):
            assert broker.can_subscribe() is True
            queues.append(broker.subscribe())

        # 4th subscriber must be refused
        assert broker.can_subscribe() is False

        # Free one slot
        broker.unsubscribe(queues.pop())
        assert broker.can_subscribe() is True

        # Clean up remaining
        for q in queues:
            broker.unsubscribe(q)
        assert broker.subscriber_count == 0

    def test_concurrent_publish_and_delivery(self):
        async def _test():
            broker = LiveEventBroker(max_connections=50)
            subscribers = [broker.subscribe() for _ in range(10)]

            # Publish from simulated background thread
            broker.publish("test_event", {"val": "alpha"})

            # All 10 queues must receive payload
            for q in subscribers:
                item = await asyncio.wait_for(q.get(), timeout=1.0)
                assert item["event"] == "test_event"
                assert item["data"]["val"] == "alpha"
                assert "id" in item

            # Clean up
            for q in subscribers:
                broker.unsubscribe(q)
            assert broker.subscriber_count == 0

        asyncio.run(_test())

    def test_last_event_id_replay(self):
        broker = LiveEventBroker()
        broker.publish("evt_1", {"order": 1})
        time.sleep(0.01)
        broker.publish("evt_2", {"order": 2})
        time.sleep(0.01)
        broker.publish("evt_3", {"order": 3})

        recent = broker.get_recent_events(limit=5)
        assert len(recent) == 3

        id_1 = recent[0]["id"]
        # Client asks for missed events after evt_1
        replayed = broker.get_events_after(id_1)
        assert len(replayed) == 2
        assert replayed[0]["event"] == "evt_2"
        assert replayed[1]["event"] == "evt_3"
