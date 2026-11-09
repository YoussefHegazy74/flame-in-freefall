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
from collections import defaultdict, deque
from dataclasses import dataclass


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
