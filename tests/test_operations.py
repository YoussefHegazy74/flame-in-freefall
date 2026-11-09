"""Operational-control tests: ETags, caching, and rate limiting.

These tests use the synthetic canonical fixture. They exercise HTTP behavior,
not scientific values, so they do not need the real canonical dataset.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import API_PREFIX, create_app
from backend.operations import CacheSettings, RateLimitSettings
from src.analytics.registry import load_registries
from src.analytics.service import AnalyticsService


def make_client(synthetic_analytics, *, cache=None, rate=None) -> TestClient:
    service = AnalyticsService(
        database=synthetic_analytics["db"], bundle=load_registries()
    )
    return TestClient(
        create_app(
            service=service,
            cache_settings=cache or CacheSettings(max_age_seconds=30),
            rate_limit_settings=rate or RateLimitSettings(enabled=False),
        ),
        raise_server_exceptions=False,
    )


def test_etag_is_stable_and_conditional_requests_return_304(synthetic_analytics):
    client = make_client(synthetic_analytics)
    first = client.get(f"{API_PREFIX}/investigations?limit=2")
    second = client.get(f"{API_PREFIX}/investigations?limit=2")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.headers["ETag"] == second.headers["ETag"]
    assert first.json()["meta"]["request_id"] != second.json()["meta"]["request_id"]
    assert first.headers["Cache-Control"] == "public, max-age=30, must-revalidate"

    conditional = client.get(
        f"{API_PREFIX}/investigations?limit=2",
        headers={"If-None-Match": first.headers["ETag"]},
    )
    assert conditional.status_code == 304
    assert conditional.content == b""
    assert conditional.headers["ETag"] == first.headers["ETag"]
    assert conditional.headers["X-Request-ID"].startswith("req_")


def test_health_and_error_responses_are_not_cached(synthetic_analytics):
    client = make_client(synthetic_analytics)
    health = client.get(f"{API_PREFIX}/health")
    assert health.status_code == 200
    assert health.headers["Cache-Control"] == "no-store"
    assert "ETag" not in health.headers

    missing = client.get(f"{API_PREFIX}/not-a-route")
    assert missing.status_code == 404
    assert missing.headers["Cache-Control"] == "no-store"
    assert "ETag" not in missing.headers


def test_cache_can_be_disabled_or_overridden(synthetic_analytics):
    disabled = make_client(
        synthetic_analytics, cache=CacheSettings(enabled=False, max_age_seconds=30)
    )
    response = disabled.get(f"{API_PREFIX}/investigations?limit=2")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert "ETag" not in response.headers

    custom = make_client(
        synthetic_analytics, cache=CacheSettings(control="private, max-age=5")
    )
    response = custom.get(f"{API_PREFIX}/investigations?limit=2")
    assert response.headers["Cache-Control"] == "private, max-age=5"
    assert response.headers["ETag"]


def test_rate_limit_returns_a_safe_error_and_headers(synthetic_analytics):
    client = make_client(
        synthetic_analytics,
        rate=RateLimitSettings(requests=3, window_seconds=60),
    )
    for expected_remaining in ("2", "1", "0"):
        response = client.get(f"{API_PREFIX}/health")
        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == "3"
        assert response.headers["X-RateLimit-Remaining"] == expected_remaining

    blocked = client.get(f"{API_PREFIX}/health")
    assert blocked.status_code == 429
    payload = blocked.json()
    assert set(payload) == {"error"}
    assert payload["error"]["code"] == "rate_limited"
    assert payload["error"]["details"] == {
        "limit": 3,
        "window_seconds": 60,
        "retry_after_seconds": 60,
    }
    assert payload["error"]["request_id"] == blocked.headers["X-Request-ID"]
    assert blocked.headers["Retry-After"] == "60"
    assert blocked.headers["X-RateLimit-Remaining"] == "0"
    assert blocked.headers["Cache-Control"] == "no-store"


def test_rate_limit_can_be_disabled(synthetic_analytics):
    client = make_client(
        synthetic_analytics,
        rate=RateLimitSettings(enabled=False, requests=1),
    )
    for _ in range(5):
        response = client.get(f"{API_PREFIX}/health")
        assert response.status_code == 200


def test_forwarded_client_identity_is_used_only_when_trusted(synthetic_analytics):
    client = make_client(
        synthetic_analytics,
        rate=RateLimitSettings(requests=1, window_seconds=60, trust_proxy=True),
    )
    first = client.get(
        f"{API_PREFIX}/health", headers={"X-Forwarded-For": "203.0.113.10"}
    )
    second = client.get(
        f"{API_PREFIX}/health", headers={"X-Forwarded-For": "203.0.113.11"}
    )
    assert first.status_code == 200
    assert second.status_code == 200
    blocked = client.get(
        f"{API_PREFIX}/health", headers={"X-Forwarded-For": "203.0.113.10"}
    )
    assert blocked.status_code == 429


def test_untrusted_forwarded_header_cannot_bypass_the_limit(synthetic_analytics):
    client = make_client(
        synthetic_analytics,
        rate=RateLimitSettings(requests=1, window_seconds=60, trust_proxy=False),
    )
    first = client.get(
        f"{API_PREFIX}/health", headers={"X-Forwarded-For": "203.0.113.10"}
    )
    second = client.get(
        f"{API_PREFIX}/health", headers={"X-Forwarded-For": "203.0.113.11"}
    )
    assert first.status_code == 200
    assert second.status_code == 429
