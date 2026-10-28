"""
Live Event Broker for Near-Real-Time Updates via Server-Sent Events (SSE).

Thread-safe publication engine supporting background tasks (APScheduler,
ThreadPoolExecutor) and asynchronous streaming HTTP consumers.
Features:
- Thread-safe subscriber registration and connection limiting per worker
- EventSource-compatible message structure (id, event, retry, data)
- Disconnect and cancellation cleanup with strict connection counter tracking
- Reconnection replay using Last-Event-ID headers
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONNECTIONS = 100
DEFAULT_RETRY_MS = 3000


class LiveEventBroker:
    """Thread-safe publisher and async subscriber manager for SSE."""

    def __init__(self, max_connections: int = DEFAULT_MAX_CONNECTIONS) -> None:
        self._lock = threading.Lock()
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._recent_events: list[dict[str, Any]] = []
        self._max_recent: int = 50
        self._last_event_time: float = 0.0
        self._seq_counter: int = 0
        self.max_connections = max_connections

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def can_subscribe(self) -> bool:
        """Check whether worker has connection headroom."""
        with self._lock:
            return len(self._subscribers) < self.max_connections

    def subscribe(self) -> asyncio.Queue:
        """Register a new consumer queue thread-safely."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove a disconnected consumer queue thread-safely."""
        with self._lock:
            self._subscribers.discard(q)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    @property
    def last_event_time(self) -> float:
        return self._last_event_time

    def get_recent_events(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._recent_events[-limit:])

    def get_events_after(self, last_event_id: str) -> list[dict[str, Any]]:
        """Return events that occurred after the given event ID for seamless reconnection."""
        with self._lock:
            missed = []
            found = False
            for evt in self._recent_events:
                if found:
                    missed.append(evt)
                elif evt.get("id") == last_event_id:
                    found = True
            return missed

    def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """
        Thread-safe publication. Safe to invoke from background threads, worker pools,
        or synchronous route handlers.
        """
        now = time.time()
        with self._lock:
            self._seq_counter += 1
            event_id = f"evt_{int(now * 1000)}_{self._seq_counter}"
            payload = {
                "id": event_id,
                "event": event_type,
                "data": data,
                "timestamp": now,
            }

            self._recent_events.append(payload)
            if len(self._recent_events) > self._max_recent:
                self._recent_events = self._recent_events[-self._max_recent:]
            self._last_event_time = now
            subscribers_snapshot = list(self._subscribers)

        if not subscribers_snapshot:
            return

        def _deliver():
            for q in subscribers_snapshot:
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        q.put_nowait(payload)
                    except Exception:
                        pass

        # If an event loop has been registered and is running, deliver via threadsafe callback
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(_deliver)
        else:
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(_deliver)
            except RuntimeError:
                # No running event loop in caller thread (e.g. sync test or worker thread)
                _deliver()


broker = LiveEventBroker()


def format_sse(
    event_type: str,
    data: dict[str, Any],
    event_id: str | None = None,
    retry_ms: int = DEFAULT_RETRY_MS,
) -> str:
    """Format payload according to the W3C Server-Sent Events specification."""
    payload_json = json.dumps(data)
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_type}")
    lines.append(f"retry: {retry_ms}")
    lines.append(f"data: {payload_json}")
    return "\n".join(lines) + "\n\n"
