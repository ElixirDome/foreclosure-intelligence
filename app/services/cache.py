"""Small thread-safe in-process TTL cache for derived API responses."""

from __future__ import annotations

import threading
import time
from typing import Any


class TTLCache:
    def __init__(self) -> None:
        self._values: dict[str, tuple[float, Any]] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._lock:
            entry = self._values.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at <= now:
                self._values.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl: float = 30.0) -> None:
        expires_at = time.monotonic() + max(float(ttl), 0.0)
        with self._lock:
            self._values[key] = (expires_at, value)

    def invalidate_prefix(self, prefix: str) -> int:
        with self._lock:
            keys = [key for key in self._values if key.startswith(prefix)]
            for key in keys:
                self._values.pop(key, None)
            return len(keys)

    def delete(self, key: str) -> None:
        with self._lock:
            self._values.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()


cache = TTLCache()
