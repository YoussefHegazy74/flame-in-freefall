"""Configuration tests for the assistant provider settings."""

from __future__ import annotations

import pytest

from src.assistant.config import (
    AssistantConfigError,
    AssistantSettings,
    safe_settings_from_env,
)


def test_defaults_are_deterministic_and_secret_free():
    settings = AssistantSettings.from_env({})
    assert settings.enabled is True
    assert settings.provider == "deterministic"
    assert settings.llm_configured is False
    assert settings.max_tool_calls == 6
    assert settings.timeout_seconds == 20.0
    status = settings.public_status()
    assert status["mode"] == "deterministic"
    assert "api_key" not in status


def test_openai_compatible_requires_base_url_model_and_key():
    with pytest.raises(AssistantConfigError):
        AssistantSettings.from_env({"FLAME_LLM_PROVIDER": "openai_compatible"})


def test_openai_compatible_configures_without_exposing_the_key():
    settings = AssistantSettings.from_env(
        {
            "FLAME_LLM_PROVIDER": "openai_compatible",
            "FLAME_LLM_BASE_URL": "https://example.test/v1/",
            "FLAME_LLM_MODEL": "test-model",
            "FLAME_LLM_API_KEY": "super-secret-value",
        }
    )
    assert settings.llm_configured is True
    assert settings.base_url == "https://example.test/v1"
    assert "super-secret-value" not in repr(settings)
    assert "super-secret-value" not in str(settings.public_status())


def test_invalid_provider_is_rejected():
    with pytest.raises(AssistantConfigError):
        AssistantSettings.from_env({"FLAME_LLM_PROVIDER": "unknown"})


def test_invalid_boolean_is_rejected():
    with pytest.raises(AssistantConfigError):
        AssistantSettings.from_env({"FLAME_ASSISTANT_ENABLED": "maybe"})


def test_invalid_base_url_is_rejected():
    with pytest.raises(AssistantConfigError):
        AssistantSettings.from_env(
            {
                "FLAME_LLM_PROVIDER": "openai_compatible",
                "FLAME_LLM_BASE_URL": "ftp://example.test",
                "FLAME_LLM_MODEL": "test",
                "FLAME_LLM_API_KEY": "secret",
            }
        )


def test_base_url_credentials_are_rejected():
    with pytest.raises(AssistantConfigError):
        AssistantSettings.from_env(
            {
                "FLAME_LLM_PROVIDER": "openai_compatible",
                "FLAME_LLM_BASE_URL": "https://user:pass@example.test/v1",
                "FLAME_LLM_MODEL": "test",
                "FLAME_LLM_API_KEY": "secret",
            }
        )


def test_numeric_bounds_are_enforced():
    with pytest.raises(AssistantConfigError):
        AssistantSettings.from_env({"FLAME_ASSISTANT_MAX_TOOL_CALLS": "99"})
    with pytest.raises(AssistantConfigError):
        AssistantSettings.from_env({"FLAME_ASSISTANT_TIMEOUT_SECONDS": "0"})
    with pytest.raises(AssistantConfigError):
        AssistantSettings.from_env({"FLAME_LLM_MAX_RETRIES": "6"})
    with pytest.raises(AssistantConfigError):
        AssistantSettings.from_env({"FLAME_LLM_INPUT_COST_PER_MILLION": "-1"})


def test_provider_retry_and_pricing_settings_parse():
    settings = AssistantSettings.from_env(
        {
            "FLAME_LLM_PROVIDER": "openai_compatible",
            "FLAME_LLM_BASE_URL": "https://example.test/v1",
            "FLAME_LLM_MODEL": "test-model",
            "FLAME_LLM_API_KEY": "secret",
            "FLAME_LLM_MAX_RETRIES": "3",
            "FLAME_LLM_RETRY_BACKOFF_SECONDS": "0.25",
            "FLAME_LLM_INPUT_COST_PER_MILLION": "2.5",
            "FLAME_LLM_OUTPUT_COST_PER_MILLION": "10",
        }
    )
    assert settings.max_retries == 3
    assert settings.retry_backoff_seconds == 0.25
    assert settings.input_cost_per_million == 2.5
    assert settings.output_cost_per_million == 10.0
    assert "secret" not in repr(settings)


def test_safe_settings_degrades_to_deterministic_on_invalid_config():
    settings, error = safe_settings_from_env(
        {"FLAME_LLM_PROVIDER": "openai_compatible"}
    )
    assert settings.provider == "deterministic"
    assert settings.enabled is True
    assert settings.config_error
    assert error
    assert "secret" not in error.lower()


def test_disabled_assistant_reports_disabled_mode():
    settings = AssistantSettings.from_env({"FLAME_ASSISTANT_ENABLED": "false"})
    assert settings.public_status()["mode"] == "disabled"


def test_legacy_environment_names_are_supported():
    settings = AssistantSettings.from_env({"ASSISTANT_ENABLED": "false"})
    assert settings.enabled is False
    settings = AssistantSettings.from_env(
        {
            "LLM_PROVIDER": "openai_compatible",
            "LLM_BASE_URL": "https://example.test/v1",
            "LLM_MODEL": "test-model",
            "LLM_API_KEY": "legacy-secret",
            "LLM_TIMEOUT_SECONDS": "30",
        }
    )
    assert settings.llm_configured is True
    assert settings.timeout_seconds == 30.0
    assert "legacy-secret" not in repr(settings)


def test_flame_names_take_precedence_over_legacy_names():
    settings = AssistantSettings.from_env(
        {
            "ASSISTANT_ENABLED": "false",
            "FLAME_ASSISTANT_ENABLED": "true",
            "LLM_PROVIDER": "openai_compatible",
            "FLAME_LLM_PROVIDER": "deterministic",
        }
    )
    assert settings.enabled is True
    assert settings.provider == "deterministic"
