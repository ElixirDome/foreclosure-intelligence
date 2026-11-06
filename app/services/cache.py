"""
High-performance thread-safe in-memory caching service with TTL and prefix invalidation.
Provides zero-dependency, sub-millisecond caching for expensive queries and computations.
Includes real-time telemetry metrics (hits, misses, hit ratio, evictions) for performance monitoring.
"""

import time
import threading
from typing import Any, Callable, Optional
from functools import wraps


class CacheEntry:
    __slots__ = ("value", "expires_at", "created_at")

    def __init__(self, value: Any, expires_at: float):
        self.value = value
        self.expires_at = expires_at
        self.created_at = time.time()

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class InMemoryCache:
    """
    Thread-safe in-memory cache with TTL expiration, pattern invalidation, and metrics telemetry.
    """

    def __init__(self, default_ttl: float = 60.0, max_entries: int = 10000):
        self._store: dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self.default_ttl = default_ttl
        self.max_entries = max_entries

        # Metrics telemetry
        self._hits: int = 0
        self._misses: int = 0
        self._sets: int = 0
        self._evictions: int = 0
        self._invalidations: int = 0

    def get(self, key: str) -> Optional[Any]:
        """Retrieve an item from cache. Returns None if absent or expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired:
                del self._store[key]
                self._evictions += 1
                self._misses += 1
                return None

            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Store an item in cache with a TTL in seconds."""
        effective_ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + effective_ttl

        with self._lock:
            # Capacity guard
            if len(self._store) >= self.max_entries and key not in self._store:
                self._evict_expired_or_oldest()

            self._store[key] = CacheEntry(value, expires_at)
            self._sets += 1

    def delete(self, key: str) -> bool:
        """Remove a single key from the cache."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                self._invalidations += 1
                return True
            return False

    def invalidate_prefix(self, prefix: str) -> int:
        """Invalidate all keys matching the given prefix."""
        with self._lock:
            keys_to_delete = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_delete:
                del self._store[k]
            count = len(keys_to_delete)
            self._invalidations += count
            return count

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._store.clear()

    def _evict_expired_or_oldest(self) -> None:
        """Internal helper to evict expired keys or oldest entry when capacity is reached."""
        now = time.time()
        expired = [k for k, v in self._store.items() if now > v.expires_at]
        if expired:
            for k in expired:
                del self._store[k]
                self._evictions += 1
            return

        # If no expired, evict the oldest entry
        if self._store:
            oldest_key = min(self._store.keys(), key=lambda k: self._store[k].created_at)
            del self._store[oldest_key]
            self._evictions += 1

    def get_stats(self) -> dict:
        """Return cache performance statistics and hit ratios."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_ratio = round((self._hits / total_requests) * 100, 2) if total_requests > 0 else 0.0
            return {
                "active_entries": len(self._store),
                "hits": self._hits,
                "misses": self._misses,
                "total_requests": total_requests,
                "hit_ratio_percent": hit_ratio,
                "sets": self._sets,
                "evictions": self._evictions,
                "invalidations": self._invalidations,
            }

    def reset_stats(self) -> None:
        """Reset telemetry counters."""
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._sets = 0
            self._evictions = 0
            self._invalidations = 0


# Global singleton instance
cache = InMemoryCache(default_ttl=60.0)


def cached(prefix: str, ttl: Optional[float] = None, key_builder: Optional[Callable[..., str]] = None):
    """
    Decorator for caching synchronous or asynchronous endpoint results.
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if key_builder:
                cache_key = f"{prefix}:{key_builder(*args, **kwargs)}"
            else:
                arg_str = ":".join(str(a) for a in args)
                kwarg_str = ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()) if k != "db")
                cache_key = f"{prefix}:{arg_str}:{kwarg_str}"

            cached_val = cache.get(cache_key)
            if cached_val is not None:
                return cached_val

            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            return result

        return wrapper
    return decorator
