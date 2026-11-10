"""Operational controls for the read-only API.

Caching and rate limiting are deliberately simple and process-local. They are
abuse controls for a public, read-only dataset, not an authentication or
authorization mechanism.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


@dataclass(frozen=True)
class CacheSettings:
    enabled: bool = True
    max_age_seconds: int = 60
    control: str | None = None

    @classmethod
    def from_env(cls) -> "CacheSettings":
        return cls(
            enabled=_env_bool("FLAME_CACHE_ENABLED", True),
            max_age_seconds=_env_int("FLAME_CACHE_MAX_AGE", 60, minimum=0),
            control=os.environ.get("FLAME_CACHE_CONTROL") or None,
        )

    def header_value(self) -> str:
        if self.control:
            return self.control
        return f"public, max-age={self.max_age_seconds}, must-revalidate"


@dataclass(frozen=True)
class RateLimitSettings:
    enabled: bool = True
    requests: int = 600
    window_seconds: int = 60
    trust_proxy: bool = False

    @classmethod
    def from_env(cls) -> "RateLimitSettings":
        return cls(
            enabled=_env_bool("FLAME_RATE_LIMIT_ENABLED", True),
            requests=_env_int("FLAME_RATE_LIMIT_REQUESTS", 600, minimum=1),
            window_seconds=_env_int("FLAME_RATE_LIMIT_WINDOW_SECONDS", 60, minimum=1),
            trust_proxy=_env_bool("FLAME_TRUST_PROXY", False),
        )


@dataclass(frozen=True)
class RequestLimitSettings:
    """Bound the request body before a handler parses it."""

    max_body_bytes: int = 1_048_576

    @classmethod
    def from_env(cls) -> "RequestLimitSettings":
        return cls(
            max_body_bytes=_env_int(
                "FLAME_MAX_REQUEST_BYTES", 1_048_576, minimum=1024
            )
        )


@dataclass(frozen=True)
class ReadinessSettings:
    """Deployment gates for the readiness endpoint.

    A production deployment should have every canonical table and a usable
    retrieval index when the assistant is enabled. Tests and partial
    deployments can relax either gate explicitly.
    """

    require_full_dataset: bool = True
    require_assistant_index: bool = True

    @classmethod
    def from_env(cls) -> "ReadinessSettings":
        return cls(
            require_full_dataset=_env_bool(
                "FLAME_READINESS_REQUIRE_FULL_DATASET", True
            ),
            require_assistant_index=_env_bool(
                "FLAME_READINESS_REQUIRE_ASSISTANT_INDEX", True
            ),
        )


@dataclass(frozen=True)
class MetricsSettings:
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "MetricsSettings":
        return cls(enabled=_env_bool("FLAME_METRICS_ENABLED", True))


class MetricsRegistry:
    """Bounded, process-local operational counters.

    No user question, answer text, citation identifier, or credential is
    stored. Route keys use the FastAPI route template rather than raw paths so
    arbitrary 404 paths cannot grow the dictionary without bound.
    """

    _LATENCY_SAMPLE_LIMIT = 4096

    def __init__(self, settings: MetricsSettings | None = None):
        self.settings = settings or MetricsSettings()
        self.started_at = datetime.now(timezone.utc).isoformat()
        self._lock = threading.Lock()
        self._requests_total = 0
        self._by_method: Counter[str] = Counter()
        self._by_status: Counter[str] = Counter()
        self._by_route: Counter[str] = Counter()
        self._rate_limited_total = 0
        self._latencies: deque[float] = deque(maxlen=self._LATENCY_SAMPLE_LIMIT)
        self._assistant_queries_total = 0
        self._assistant_fallback_total = 0
        self._assistant_disabled_total = 0
        self._assistant_validation_failures_total = 0
        self._assistant_evidence_status: Counter[str] = Counter()
        self._assistant_answer_type: Counter[str] = Counter()
        self._tool_calls_total = 0
        self._tool_failures_total = 0
        self._provider_calls_total = 0
        self._provider_errors_total = 0
        self._provider_tokens_prompt = 0
        self._provider_tokens_completion = 0
        self._provider_cost_usd = 0.0

    def record_request(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        if not self.settings.enabled:
            return
        with self._lock:
            self._requests_total += 1
            self._by_method[method.upper()] += 1
            self._by_status[str(status_code)] += 1
            self._by_route[route] += 1
            self._latencies.append(max(0.0, float(duration_ms)))

    def record_rate_limit(self) -> None:
        if not self.settings.enabled:
            return
        with self._lock:
            self._rate_limited_total += 1

    def record_assistant(
        self,
        *,
        provider: str,
        fallback: bool,
        evidence_status: str,
        answer_type: str,
        validation_passed: bool,
        tools: Iterable[tuple[str, str]],
        usage: Mapping[str, Any] | None = None,
        disabled: bool = False,
    ) -> None:
        if not self.settings.enabled:
            return
        tool_list = list(tools)
        with self._lock:
            self._assistant_queries_total += 1
            if disabled:
                self._assistant_disabled_total += 1
            if fallback:
                self._assistant_fallback_total += 1
            if not validation_passed:
                self._assistant_validation_failures_total += 1
            self._assistant_evidence_status[evidence_status] += 1
            self._assistant_answer_type[answer_type] += 1
            self._tool_calls_total += len(tool_list)
            self._tool_failures_total += sum(
                1 for _, status in tool_list if status not in {"ok", "empty"}
            )
            if provider not in {"deterministic", "mock_provider"}:
                self._provider_calls_total += 1
            if usage:
                prompt = usage.get("prompt_tokens")
                completion = usage.get("completion_tokens")
                cost = usage.get("estimated_cost_usd")
                if isinstance(prompt, int) and not isinstance(prompt, bool):
                    self._provider_tokens_prompt += prompt
                if isinstance(completion, int) and not isinstance(completion, bool):
                    self._provider_tokens_completion += completion
                if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                    self._provider_cost_usd += float(cost)

    def record_provider_error(self) -> None:
        if not self.settings.enabled:
            return
        with self._lock:
            self._provider_errors_total += 1

    @staticmethod
    def _percentile(values: list[float], fraction: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        if len(ordered) == 1:
            return ordered[0]
        position = (len(ordered) - 1) * fraction
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (
            position - lower
        )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            latencies = list(self._latencies)
            return {
                "enabled": self.settings.enabled,
                "started_at": self.started_at,
                "requests": {
                    "total": self._requests_total,
                    "by_method": dict(sorted(self._by_method.items())),
                    "by_status": dict(sorted(self._by_status.items())),
                    "by_route": dict(sorted(self._by_route.items())),
                },
                "rate_limited_total": self._rate_limited_total,
                "latency_ms": {
                    "samples": len(latencies),
                    "mean": round(sum(latencies) / len(latencies), 3)
                    if latencies
                    else None,
                    "p95": round(self._percentile(latencies, 0.95) or 0.0, 3)
                    if latencies
                    else None,
                    "max": round(max(latencies), 3) if latencies else None,
                },
                "assistant": {
                    "queries_total": self._assistant_queries_total,
                    "fallback_total": self._assistant_fallback_total,
                    "disabled_total": self._assistant_disabled_total,
                    "validation_failures_total": self._assistant_validation_failures_total,
                    "evidence_status": dict(
                        sorted(self._assistant_evidence_status.items())
                    ),
                    "answer_type": dict(sorted(self._assistant_answer_type.items())),
                    "tool_calls_total": self._tool_calls_total,
                    "tool_failures_total": self._tool_failures_total,
                    "provider_calls_total": self._provider_calls_total,
                    "provider_errors_total": self._provider_errors_total,
                    "provider_tokens": {
                        "prompt": self._provider_tokens_prompt,
                        "completion": self._provider_tokens_completion,
                        "total": self._provider_tokens_prompt
                        + self._provider_tokens_completion,
                    },
                    "provider_estimated_cost_usd": round(
                        self._provider_cost_usd, 8
                    ),
                },
            }


class RateLimiter:
    """Thread-safe fixed-window limiter keyed by client identity."""

    def __init__(self, settings: RateLimitSettings):
        self.settings = settings
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> dict[str, object]:
        if not self.settings.enabled:
            return {
                "allowed": True,
                "limit": self.settings.requests,
                "remaining": self.settings.requests,
                "reset_after": 0.0,
            }
        now = time.monotonic()
        cutoff = now - self.settings.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.settings.requests:
                reset_after = max(0.0, hits[0] + self.settings.window_seconds - now)
                return {
                    "allowed": False,
                    "limit": self.settings.requests,
                    "remaining": 0,
                    "reset_after": reset_after,
                }
            hits.append(now)
            return {
                "allowed": True,
                "limit": self.settings.requests,
                "remaining": self.settings.requests - len(hits),
                "reset_after": float(self.settings.window_seconds),
            }

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def etag_for_body(body: bytes) -> str:
    """Return a strong ETag for a stable representation of a response body.

    The success envelope carries a per-request ``request_id`` and a
    ``generated_at`` timestamp. Hashing those would make every ETag unique and
    conditional requests useless, so they are removed before hashing. The
    response body itself is still returned unchanged.
    """

    canonical = body
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        payload = None
    if isinstance(payload, dict):
        meta = payload.get("meta")
        if isinstance(meta, dict):
            stable_meta = {
                key: value
                for key, value in meta.items()
                if key not in {"request_id", "generated_at"}
            }
            payload = {**payload, "meta": stable_meta}
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    return '"' + hashlib.sha256(canonical).hexdigest()[:32] + '"'


def if_none_match_matches(header: str | None, etag: str) -> bool:
    if not header:
        return False
    for candidate in header.split(","):
        value = candidate.strip()
        if value == "*" or value == etag:
            return True
        if value.startswith("W/") and value[2:] == etag:
            return True
    return False
