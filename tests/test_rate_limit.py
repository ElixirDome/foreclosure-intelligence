import time
from fastapi.testclient import TestClient
from app.main import app
from app.middleware.rate_limit import SlidingWindowRateLimiter, RateLimitMiddleware, default_rate_limiter


def test_sliding_window_rate_limiter_logic():
    limiter = SlidingWindowRateLimiter(window_seconds=2)
    ip = "192.168.1.100"
    tier = "test"
    limit = 3

    # First 3 allowed
    for _ in range(3):
        allowed, remaining, retry_after = limiter.is_allowed(ip, tier, limit)
        assert allowed is True
        assert retry_after == 0

    # 4th blocked
    allowed, remaining, retry_after = limiter.is_allowed(ip, tier, limit)
    assert allowed is False
    assert remaining == 0
    assert retry_after >= 1

    stats = limiter.get_stats()
    assert stats["total_passed"] == 3
    assert stats["total_blocked"] == 1

    # Wait for window to clear
    time.sleep(2.1)
    allowed, remaining, retry_after = limiter.is_allowed(ip, tier, limit)
    assert allowed is True


def test_rate_limit_headers_and_system_metrics():
    client = TestClient(app)

    # Health check is whitelisted and bypasses limiter
    resp = client.get("/health/live")
    assert resp.status_code == 200

    # System metrics endpoint returns operational status
    resp = client.get("/system/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "cache" in data
    assert "rate_limiter" in data
    assert "hit_ratio_percent" in data["cache"]


def test_custom_rate_limiter_enforcement():
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    custom_app = FastAPI()
    custom_limiter = SlidingWindowRateLimiter(window_seconds=5)
    custom_app.add_middleware(
        RateLimitMiddleware,
        default_limit=2,
        auth_limit=2,
        source_limit=2,
        window_seconds=5,
        limiter=custom_limiter,
    )

    @custom_app.get("/items")
    def get_items():
        return {"items": [1, 2, 3]}

    c = TestClient(custom_app)

    # First 2 requests succeed
    r1 = c.get("/items")
    assert r1.status_code == 200
    assert r1.headers.get("X-RateLimit-Limit") == "2"
    assert r1.headers.get("X-RateLimit-Remaining") == "1"

    r2 = c.get("/items")
    assert r2.status_code == 200
    assert r2.headers.get("X-RateLimit-Remaining") == "0"

    # 3rd request receives 429 Too Many Requests
    r3 = c.get("/items")
    assert r3.status_code == 429
    assert "Rate limit exceeded" in r3.json()["detail"]
    assert "Retry-After" in r3.headers
