"""Phase 6 operational contract tests: readiness, metrics, limits, headers."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app import API_PREFIX, create_app
from backend.operations import (
    MetricsRegistry,
    MetricsSettings,
    RateLimitSettings,
    ReadinessSettings,
    RequestLimitSettings,
)
from src.analytics.registry import load_registries
from src.analytics.service import AnalyticsService


class StubAssistant:
    def __init__(self, *, index_version: str | None = "test-index"):
        self.settings = SimpleNamespace(enabled=True, llm_configured=False)
        self.index_version = index_version

    def status(self, *, load_index: bool = False):
        return SimpleNamespace(
            enabled=True,
            mode="deterministic",
            provider="deterministic",
            model=None,
            retrieval_enabled=True,
            index_version=self.index_version if load_index else None,
            fallback_mode=False,
            fallback_reason=None,
            notes=[],
        )


def make_client(
    synthetic_analytics,
    *,
    assistant=None,
    readiness=None,
    request_limit=None,
    metrics=None,
):
    service = AnalyticsService(
        database=synthetic_analytics["db"], bundle=load_registries()
    )
    return TestClient(
        create_app(
            service=service,
            assistant=assistant or StubAssistant(),
            rate_limit_settings=RateLimitSettings(enabled=False),
            readiness_settings=readiness
            or ReadinessSettings(
                require_full_dataset=False, require_assistant_index=False
            ),
            request_limit_settings=request_limit,
            metrics_settings=metrics,
        ),
        raise_server_exceptions=False,
    )


def test_readiness_reports_ready_with_relaxed_dataset_gate(synthetic_analytics):
    client = make_client(synthetic_analytics)
    response = client.get(f"{API_PREFIX}/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["status"] == "ready"
    assert payload["data"]["checks"]["dataset"]["ready"] is True
    assert payload["data"]["checks"]["assistant"]["ready"] is True
    assert response.headers["Cache-Control"] == "no-store"


def test_readiness_fails_closed_when_full_dataset_is_required(tmp_path):
    from src.analytics.db import AnalyticsDatabase

    service = AnalyticsService(
        database=AnalyticsDatabase(
            processed_dir=tmp_path / "processed", reports_dir=tmp_path
        ),
        bundle=load_registries(),
    )
    client = TestClient(
        create_app(
            service=service,
            assistant=StubAssistant(),
            rate_limit_settings=RateLimitSettings(enabled=False),
            readiness_settings=ReadinessSettings(
                require_full_dataset=True, require_assistant_index=False
            ),
        ),
        raise_server_exceptions=False,
    )
    response = client.get(f"{API_PREFIX}/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["data"]["status"] == "not_ready"
    assert "dataset_not_ready" in payload["quality"]["flags"]


def test_readiness_fails_closed_when_index_is_required_and_missing(
    synthetic_analytics,
):
    client = make_client(
        synthetic_analytics,
        assistant=StubAssistant(index_version=None),
        readiness=ReadinessSettings(
            require_full_dataset=False, require_assistant_index=True
        ),
    )
    response = client.get(f"{API_PREFIX}/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["data"]["checks"]["assistant"]["index_ready"] is False
    assert "assistant_index_not_ready" in payload["quality"]["flags"]


def test_security_headers_and_request_size_limit(synthetic_analytics):
    client = make_client(
        synthetic_analytics,
        request_limit=RequestLimitSettings(max_body_bytes=1024),
    )
    health = client.get(f"{API_PREFIX}/health")
    assert health.headers["X-Content-Type-Options"] == "nosniff"
    assert health.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in health.headers

    oversized = client.post(
        f"{API_PREFIX}/assistant/query",
        content=b"x" * 2048,
        headers={"Content-Type": "application/json"},
    )
    assert oversized.status_code == 413
    payload = oversized.json()
    assert payload["error"]["code"] == "request_too_large"
    assert payload["error"]["details"]["max_body_bytes"] == 1024
    assert oversized.headers["X-Content-Type-Options"] == "nosniff"


def test_metrics_are_bounded_aggregates_without_user_content(synthetic_analytics):
    client = make_client(synthetic_analytics)
    for _ in range(3):
        assert client.get(f"{API_PREFIX}/health").status_code == 200
    response = client.get(f"{API_PREFIX}/metrics")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    assert data["requests"]["total"] >= 3
    assert data["requests"]["by_route"][f"{API_PREFIX}/health"] >= 3
    assert data["requests"]["by_status"]["200"] >= 3
    assert data["latency_ms"]["samples"] >= 3
    assert data["latency_ms"]["p95"] is not None
    assert data["assistant"]["queries_total"] == 0
    assert "question" not in str(data).lower()


def test_metrics_registry_records_assistant_usage_without_secrets():
    registry = MetricsRegistry(MetricsSettings())
    registry.record_assistant(
        provider="openai_compatible",
        fallback=True,
        evidence_status="fully_supported",
        answer_type="numerical",
        validation_passed=True,
        tools=[("gas_flame_statistics", "ok"), ("resolve_citation", "failed")],
        usage={
            "prompt_tokens": 120,
            "completion_tokens": 30,
            "estimated_cost_usd": 0.00042,
        },
    )
    snapshot = registry.snapshot()
    assistant = snapshot["assistant"]
    assert assistant["queries_total"] == 1
    assert assistant["fallback_total"] == 1
    assert assistant["tool_calls_total"] == 2
    assert assistant["tool_failures_total"] == 1
    assert assistant["provider_calls_total"] == 1
    assert assistant["provider_tokens"]["total"] == 150
    assert assistant["provider_estimated_cost_usd"] == 0.00042
    assert "sk-" not in str(snapshot)
