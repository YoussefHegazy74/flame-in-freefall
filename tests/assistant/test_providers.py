"""Provider-boundary unit tests: no network and no model calls."""

from __future__ import annotations

import httpx
import pytest

from src.assistant.config import AssistantSettings
from src.assistant.providers import (
    DeterministicProvider,
    OpenAICompatibleProvider,
    ProviderError,
    RephraseRequest,
    build_provider,
    extract_numbers,
    validate_rephrase,
)

DRAFT = (
    "PSI-10 has 256 valid records and 71 excluded rows "
    "(cit_f_21df4ec92db1eca0)."
)
REQUEST = RephraseRequest(
    question="How many valid PSI-10 records are available?",
    draft_answer=DRAFT,
    allowed_citation_ids=("cit_f_21df4ec92db1eca0",),
    allowed_numbers=tuple(sorted(extract_numbers(DRAFT))),
)


def test_number_extraction_ignores_identifiers_and_accessions():
    numbers = extract_numbers(
        "PSI-10 rows: 256, citation cit_f_21df4ec92db1eca0, value 0.4953817"
    )
    assert numbers == {"256", "0.4953817"}


def test_rephrase_preserving_numbers_and_citations_is_accepted():
    accepted, reason = validate_rephrase(
        REQUEST, "In summary, " + DRAFT
    )
    assert accepted is True
    assert reason is None


def test_rephrase_with_new_number_is_rejected():
    accepted, reason = validate_rephrase(
        REQUEST, DRAFT + " The total is 327."
    )
    assert accepted is False
    assert reason and "number" in reason


def test_rephrase_with_removed_number_is_rejected():
    accepted, reason = validate_rephrase(
        REQUEST,
        "PSI-10 has valid records (cit_f_21df4ec92db1eca0).",
    )
    assert accepted is False
    assert reason and "removed a number" in reason


def test_rephrase_with_new_citation_is_rejected():
    accepted, reason = validate_rephrase(
        REQUEST, DRAFT + " See cit_f_deadbeefdeadbeef."
    )
    assert accepted is False
    assert reason and "citation" in reason


@pytest.mark.parametrize(
    "candidate",
    [
        DRAFT + " api_key=sk-live-secret-value",
        DRAFT + " sk-abcdefghijklmnop",
        DRAFT + " -----BEGIN PRIVATE KEY-----",
        DRAFT + "\x00hidden",
        "",
        "As an AI language model, " + DRAFT,
        DRAFT + " See PSI-999 for details.",
        DRAFT + " See https://evil.example/data.csv.",
        DRAFT + " The result proves that fuel causes the effect.",
        DRAFT + " The fire-risk score is higher for this material.",
    ],
)
def test_unsafe_rephrase_is_rejected(candidate):
    accepted, reason = validate_rephrase(REQUEST, candidate)
    assert accepted is False
    assert reason


def test_overgrown_rephrase_is_rejected():
    accepted, reason = validate_rephrase(
        REQUEST, DRAFT + " extra" * 2000
    )
    assert accepted is False
    assert reason and ("length" in reason or "expansion" in reason)


def test_default_provider_is_deterministic_and_needs_no_network():
    provider, reason = build_provider(AssistantSettings())
    assert isinstance(provider, DeterministicProvider)
    assert reason is None
    result = provider.rephrase(REQUEST)
    assert result.accepted is True
    assert result.answer == DRAFT
    assert result.provider == "deterministic"


def test_incomplete_provider_configuration_degrades_without_a_secret():
    provider, reason = build_provider(
        AssistantSettings(provider="openai_compatible", model="test-model")
    )
    assert provider.name == "deterministic"
    assert reason and "incomplete" in reason


def test_complete_provider_configuration_builds_without_exposing_the_key():
    settings = AssistantSettings(
        provider="openai_compatible",
        model="test-model",
        api_key="sk-test-secret-value-not-real",
        base_url="https://provider.example/v1",
    )
    provider, reason = build_provider(settings)
    assert isinstance(provider, OpenAICompatibleProvider)
    assert reason is None
    assert "sk-test-secret-value-not-real" not in repr(provider)
    assert "sk-test-secret-value-not-real" not in repr(settings)
    assert "api_key" not in settings.public_status()


def _provider(handler, **overrides) -> OpenAICompatibleProvider:
    options = {
        "max_retries": 0,
        "retry_backoff_seconds": 0.0,
        "sleep": lambda _seconds: None,
    }
    options.update(overrides)
    return OpenAICompatibleProvider(
        model="test-model",
        base_url="https://provider.example/v1",
        api_key="sk-test-secret-value-not-real",
        timeout_seconds=5,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        **options,
    )


def _completion(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
    )


def test_provider_returns_a_validated_rephrase():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization")
        return _completion("In summary, " + DRAFT)

    result = _provider(handler).rephrase(REQUEST)
    assert result.accepted is True
    assert result.answer == "In summary, " + DRAFT
    assert result.provider == "openai_compatible"
    assert seen["authorization"] == "Bearer sk-test-secret-value-not-real"


def test_provider_rejects_unsafe_model_output():
    provider = _provider(
        lambda request: _completion(DRAFT + " The total is 999999.")
    )
    result = provider.rephrase(REQUEST)
    assert result.accepted is False
    assert result.answer == DRAFT
    assert result.reason and "number" in result.reason


@pytest.mark.parametrize(
    ("status_code", "message"),
    [(500, "HTTP 500"), (429, "HTTP 429")],
)
def test_provider_http_error_fails_safely(status_code, message):
    provider = _provider(
        lambda request: httpx.Response(status_code, json={"error": "upstream"})
    )
    with pytest.raises(ProviderError) as excinfo:
        provider.rephrase(REQUEST)
    assert message in str(excinfo.value)
    assert "sk-test-secret-value-not-real" not in str(excinfo.value)


def test_provider_timeout_fails_safely():
    def handler(request):
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(ProviderError) as excinfo:
        _provider(handler).rephrase(REQUEST)
    assert "timed out" in str(excinfo.value)
    assert "sk-test-secret-value-not-real" not in str(excinfo.value)


def test_provider_invalid_json_and_missing_choices_fail_safely():
    invalid = _provider(
        lambda request: httpx.Response(200, content=b"not-json")
    )
    with pytest.raises(ProviderError):
        invalid.rephrase(REQUEST)

    empty = _provider(
        lambda request: httpx.Response(200, json={"choices": []})
    )
    with pytest.raises(ProviderError):
        empty.rephrase(REQUEST)


def test_provider_urgent_response_size_is_bounded():
    provider = _provider(
        lambda request: httpx.Response(
            200, content=b"x" * 300_000
        )
    )
    with pytest.raises(ProviderError):
        provider.rephrase(REQUEST)


def test_provider_retries_rate_limit_and_returns_usage_and_cost():
    calls = {"count": 0}
    waits: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        assert request.headers["X-Request-ID"] == "req_provider_test"
        if calls["count"] == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "0.25"},
                json={"error": "rate limited"},
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "In summary, " + DRAFT}}],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 30,
                    "total_tokens": 150,
                },
            },
        )

    provider = _provider(
        handler,
        max_retries=1,
        input_cost_per_million=2.0,
        output_cost_per_million=8.0,
        sleep=waits.append,
    )
    request = RephraseRequest(
        question=REQUEST.question,
        draft_answer=REQUEST.draft_answer,
        allowed_citation_ids=REQUEST.allowed_citation_ids,
        allowed_numbers=REQUEST.allowed_numbers,
        request_id="req_provider_test",
    )
    result = provider.rephrase(request)
    assert result.accepted is True
    assert result.attempts == 2
    assert waits == [0.25]
    assert result.usage is not None
    assert result.usage.prompt_tokens == 120
    assert result.usage.completion_tokens == 30
    assert result.usage.total_tokens == 150
    assert result.usage.pricing_configured is True
    assert result.usage.estimated_cost_usd == pytest.approx(0.00048)
    assert "sk-test-secret-value-not-real" not in repr(result)


def test_provider_retries_transport_error_before_success():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ConnectError("temporary failure", request=request)
        return _completion("In summary, " + DRAFT)

    provider = _provider(handler, max_retries=1)
    result = provider.rephrase(REQUEST)
    assert result.accepted is True
    assert result.attempts == 2
    assert calls["count"] == 2


def test_provider_stops_after_bounded_retries():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(503, json={"error": "unavailable"})

    provider = _provider(handler, max_retries=2)
    with pytest.raises(ProviderError) as excinfo:
        provider.rephrase(REQUEST)
    assert calls["count"] == 3
    assert "HTTP 503" in str(excinfo.value)
    assert "sk-test-secret-value-not-real" not in str(excinfo.value)
