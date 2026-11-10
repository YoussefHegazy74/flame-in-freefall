"""Environment-driven configuration for the Phase 5 assistant.

Configuration is validated before the assistant is used. Secrets are never
included in ``repr``, status payloads, logs, or error messages. A missing or
invalid optional LLM configuration degrades to the deterministic provider
instead of breaking the rest of the platform.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import urlparse

DETERMINISTIC_PROVIDER = "deterministic"
OPENAI_COMPATIBLE_PROVIDER = "openai_compatible"
SUPPORTED_PROVIDERS = {DETERMINISTIC_PROVIDER, OPENAI_COMPATIBLE_PROVIDER}

DETERMINISTIC_EMBEDDING = "deterministic"
NO_EMBEDDING = "none"
OPENAI_COMPATIBLE_EMBEDDING = "openai_compatible"
SUPPORTED_EMBEDDING_PROVIDERS = {
    DETERMINISTIC_EMBEDDING,
    NO_EMBEDDING,
    OPENAI_COMPATIBLE_EMBEDDING,
}


class AssistantConfigError(ValueError):
    """Raised when assistant configuration is invalid."""


def _first(
    source: Mapping[str, str], *names: str, default: str | None = None
) -> str | None:
    """Return the first non-empty value, honoring FLAME_* precedence."""

    for name in names:
        value = source.get(name)
        if value is not None and value.strip() != "":
            return value
    return default


def _parse_bool(name: str, value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise AssistantConfigError(
        f"{name} must be one of true/false, 1/0, yes/no, or on/off"
    )


def _parse_int(
    name: str, value: str | None, default: int, *, minimum: int, maximum: int
) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise AssistantConfigError(f"{name} must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise AssistantConfigError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return parsed


def _parse_float(
    name: str, value: str | None, default: float, *, minimum: float, maximum: float
) -> float:
    if value is None or value.strip() == "":
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise AssistantConfigError(f"{name} must be a number") from exc
    if parsed < minimum or parsed > maximum:
        raise AssistantConfigError(
            f"{name} must be between {minimum:g} and {maximum:g}"
        )
    return parsed


def _parse_optional_float(
    name: str,
    value: str | None,
    *,
    minimum: float,
    maximum: float,
) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        parsed = float(value)
    except ValueError as exc:
        raise AssistantConfigError(f"{name} must be a number") from exc
    if parsed < minimum or parsed > maximum:
        raise AssistantConfigError(
            f"{name} must be between {minimum:g} and {maximum:g}"
        )
    return parsed


def _validate_base_url(value: str | None) -> str | None:
    if value is None or value.strip() == "":
        return None
    candidate = value.strip().rstrip("/")
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise AssistantConfigError(
            "FLAME_LLM_BASE_URL must be an absolute http(s) URL"
        )
    if parsed.username or parsed.password:
        raise AssistantConfigError(
            "FLAME_LLM_BASE_URL must not contain credentials"
        )
    if parsed.query or parsed.fragment:
        raise AssistantConfigError(
            "FLAME_LLM_BASE_URL must not contain a query or fragment"
        )
    return candidate


@dataclass(frozen=True)
class AssistantSettings:
    """Validated assistant settings. ``api_key`` is never serialized."""

    enabled: bool = True
    provider: str = DETERMINISTIC_PROVIDER
    model: str | None = None
    api_key: str | None = field(default=None, repr=False)
    base_url: str | None = None
    embedding_provider: str = DETERMINISTIC_EMBEDDING
    embedding_model: str = "tfidf-hash-v1"
    retrieval_enabled: bool = True
    max_tool_calls: int = 6
    timeout_seconds: float = 20.0
    max_context_turns: int = 4
    max_question_chars: int = 1000
    max_retries: int = 2
    retry_backoff_seconds: float = 0.5
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    config_error: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AssistantSettings":
        source = os.environ if env is None else env

        enabled = _parse_bool(
            "FLAME_ASSISTANT_ENABLED",
            _first(source, "FLAME_ASSISTANT_ENABLED", "ASSISTANT_ENABLED"),
            True,
        )
        provider = (
            _first(
                source,
                "FLAME_LLM_PROVIDER",
                "LLM_PROVIDER",
                default=DETERMINISTIC_PROVIDER,
            )
            or DETERMINISTIC_PROVIDER
        ).strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise AssistantConfigError(
                "FLAME_LLM_PROVIDER must be deterministic or openai_compatible"
            )

        model = (_first(source, "FLAME_LLM_MODEL", "LLM_MODEL") or "").strip() or None
        api_key = (
            _first(source, "FLAME_LLM_API_KEY", "LLM_API_KEY") or ""
        ).strip() or None
        base_url = _validate_base_url(
            _first(source, "FLAME_LLM_BASE_URL", "LLM_BASE_URL")
        )

        embedding_provider = (
            _first(
                source,
                "FLAME_EMBEDDING_PROVIDER",
                default=DETERMINISTIC_EMBEDDING,
            )
            or DETERMINISTIC_EMBEDDING
        ).strip().lower()
        if embedding_provider not in SUPPORTED_EMBEDDING_PROVIDERS:
            raise AssistantConfigError(
                "FLAME_EMBEDDING_PROVIDER must be deterministic, none, or openai_compatible"
            )
        embedding_model = (
            _first(source, "FLAME_EMBEDDING_MODEL", default="tfidf-hash-v1")
            or "tfidf-hash-v1"
        ).strip() or "tfidf-hash-v1"

        settings = cls(
            enabled=enabled,
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            retrieval_enabled=_parse_bool(
                "FLAME_RETRIEVAL_ENABLED",
                source.get("FLAME_RETRIEVAL_ENABLED"),
                True,
            ),
            max_tool_calls=_parse_int(
                "FLAME_ASSISTANT_MAX_TOOL_CALLS",
                source.get("FLAME_ASSISTANT_MAX_TOOL_CALLS"),
                6,
                minimum=1,
                maximum=12,
            ),
            timeout_seconds=_parse_float(
                "FLAME_ASSISTANT_TIMEOUT_SECONDS",
                _first(
                    source,
                    "FLAME_ASSISTANT_TIMEOUT_SECONDS",
                    "LLM_TIMEOUT_SECONDS",
                ),
                20.0,
                minimum=1.0,
                maximum=120.0,
            ),
            max_context_turns=_parse_int(
                "FLAME_ASSISTANT_MAX_CONTEXT_TURNS",
                source.get("FLAME_ASSISTANT_MAX_CONTEXT_TURNS"),
                4,
                minimum=0,
                maximum=10,
            ),
            max_question_chars=_parse_int(
                "FLAME_ASSISTANT_MAX_QUESTION_CHARS",
                source.get("FLAME_ASSISTANT_MAX_QUESTION_CHARS"),
                1000,
                minimum=64,
                maximum=4000,
            ),
            max_retries=_parse_int(
                "FLAME_LLM_MAX_RETRIES",
                source.get("FLAME_LLM_MAX_RETRIES"),
                2,
                minimum=0,
                maximum=5,
            ),
            retry_backoff_seconds=_parse_float(
                "FLAME_LLM_RETRY_BACKOFF_SECONDS",
                source.get("FLAME_LLM_RETRY_BACKOFF_SECONDS"),
                0.5,
                minimum=0.0,
                maximum=30.0,
            ),
            input_cost_per_million=_parse_optional_float(
                "FLAME_LLM_INPUT_COST_PER_MILLION",
                source.get("FLAME_LLM_INPUT_COST_PER_MILLION"),
                minimum=0.0,
                maximum=1_000_000.0,
            ),
            output_cost_per_million=_parse_optional_float(
                "FLAME_LLM_OUTPUT_COST_PER_MILLION",
                source.get("FLAME_LLM_OUTPUT_COST_PER_MILLION"),
                minimum=0.0,
                maximum=1_000_000.0,
            ),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.provider == OPENAI_COMPATIBLE_PROVIDER:
            missing = [
                name
                for name, value in (
                    ("FLAME_LLM_BASE_URL", self.base_url),
                    ("FLAME_LLM_MODEL", self.model),
                    ("FLAME_LLM_API_KEY", self.api_key),
                )
                if not value
            ]
            if missing:
                raise AssistantConfigError(
                    "openai_compatible provider requires " + ", ".join(missing)
                )
        if self.embedding_provider == OPENAI_COMPATIBLE_EMBEDDING:
            if not self.embedding_model:
                raise AssistantConfigError(
                    "openai_compatible embeddings require FLAME_EMBEDDING_MODEL"
                )
            if not self.base_url:
                raise AssistantConfigError(
                    "openai_compatible embeddings require FLAME_LLM_BASE_URL"
                )

    @property
    def llm_configured(self) -> bool:
        return (
            self.enabled
            and self.provider == OPENAI_COMPATIBLE_PROVIDER
            and bool(self.base_url)
            and bool(self.model)
            and bool(self.api_key)
        )

    def public_status(self) -> dict[str, object]:
        """Secret-free status fields safe for logs, health, and the frontend."""

        if not self.enabled:
            mode = "disabled"
        elif self.llm_configured:
            mode = "provider"
        else:
            mode = "deterministic"
        return {
            "enabled": self.enabled,
            "mode": mode,
            "provider": self.provider,
            "model": self.model,
            "retrieval_enabled": self.retrieval_enabled,
            "fallback_mode": False,
            "fallback_reason": self.config_error,
        }


def safe_settings_from_env(
    env: Mapping[str, str] | None = None,
) -> tuple[AssistantSettings, str | None]:
    """Return settings plus a safe configuration error.

    Invalid optional provider configuration does not crash the API. The
    assistant runs deterministically and reports why the provider is not in
    use. The error string never includes the secret value.
    """

    try:
        return AssistantSettings.from_env(env), None
    except AssistantConfigError as exc:
        fallback = AssistantSettings(
            enabled=True,
            provider=DETERMINISTIC_PROVIDER,
            model=None,
            api_key=None,
            base_url=None,
            retrieval_enabled=True,
            config_error=str(exc),
        )
        return fallback, str(exc)
