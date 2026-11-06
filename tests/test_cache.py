import time
import threading
from app.services.cache import InMemoryCache, cached


def test_in_memory_cache_basic_ops():
    cache = InMemoryCache(default_ttl=2.0)
    assert cache.get("key1") is None

    cache.set("key1", "val1")
    assert cache.get("key1") == "val1"

    # Delete
    assert cache.delete("key1") is True
    assert cache.get("key1") is None
    assert cache.delete("key1") is False


def test_cache_ttl_expiration():
    cache = InMemoryCache(default_ttl=0.1)
    cache.set("expiring", "data", ttl=0.05)
    assert cache.get("expiring") == "data"
    time.sleep(0.08)
    assert cache.get("expiring") is None

    stats = cache.get_stats()
    assert stats["evictions"] >= 1
    assert stats["misses"] >= 1


def test_cache_prefix_invalidation():
    cache = InMemoryCache(default_ttl=10.0)
    cache.set("property:1", "prop1")
    cache.set("property:2", "prop2")
    cache.set("property:summary", "sum")
    cache.set("user:1", "user1")

    assert cache.invalidate_prefix("property:") == 3
    assert cache.get("property:1") is None
    assert cache.get("property:2") is None
    assert cache.get("property:summary") is None
    assert cache.get("user:1") == "user1"


def test_cache_telemetry_metrics():
    cache = InMemoryCache()
    cache.set("item", "123")
    cache.get("item")  # hit
    cache.get("item")  # hit
    cache.get("missing")  # miss

    stats = cache.get_stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["total_requests"] == 3
    assert stats["hit_ratio_percent"] == 66.67


def test_cache_concurrent_access():
    cache = InMemoryCache()
    errors = []

    def writer(worker_id):
        for i in range(100):
            cache.set(f"k_{worker_id}_{i}", i)

    def reader(worker_id):
        for i in range(100):
            cache.get(f"k_{worker_id}_{i}")

    threads = []
    for w in range(5):
        t1 = threading.Thread(target=writer, args=(w,))
        t2 = threading.Thread(target=reader, args=(w,))
        threads.extend([t1, t2])

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    stats = cache.get_stats()
    assert stats["sets"] == 500
