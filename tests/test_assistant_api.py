"""HTTP contract tests for the Phase 5 assistant routes.

These tests exercise transport, envelope, configuration, and error handling.
They deliberately use a stub assistant where the answer content is irrelevant;
scientific answer behavior is covered by ``tests/assistant`` against the real
canonical dataset.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app import API_PREFIX, create_app
from backend.models import Envelope
from src.analytics.registry import load_registries
from src.analytics.service import AnalyticsService
from src.assistant.config import AssistantSettings
from src.assistant.contract import (
    AnswerType,
    AssistantAnswer,
    AssistantStatus,
    Confidence,
    EvidenceStatus,
    ValidationReport,
)
from src.assistant.orchestrator import AssistantOrchestrator


def make_service(synthetic_analytics) -> AnalyticsService:
    return AnalyticsService(
        database=synthetic_analytics["db"], bundle=load_registries()
    )


def make_client(service, *, assistant=None) -> TestClient:
    return TestClient(
        create_app(
            service=service,
            assistant=assistant,
            cors_origins=["http://example.test"],
        ),
        raise_server_exceptions=False,
    )


def assert_envelope(response, expected_status: int = 200) -> dict:
    assert response.status_code == expected_status, response.text
    payload = response.json()
    Envelope.model_validate(payload)
    assert set(payload) == {"data", "meta", "provenance", "quality"}
    assert payload["meta"]["request_id"]
    assert payload["meta"]["generated_at"]
    return payload


class StubAssistant:
    """Minimal assistant surface for API transport tests."""

    def __init__(self, answer: AssistantAnswer | None = None) -> None:
        self.answer_value = answer
        self.last_query = None
        self.last_request_id = None
        self.calls: list[str] = []

    def answer(self, query, *, request_id):
        self.calls.append("answer")
        self.last_query = query
        self.last_request_id = request_id
        assert self.answer_value is not None
        return self.answer_value.model_copy(update={"request_id": request_id})

    def status(self, *, load_index: bool = False) -> AssistantStatus:
        return AssistantStatus(
            enabled=True,
            mode="deterministic",
            provider="deterministic",
            retrieval_enabled=True,
            notes=["test status"],
        )

    def suggestions(self, limit: int = 9):
        return []

    def tools(self):
        return []


def stub_answer(**overrides) -> AssistantAnswer:
    payload = {
        "request_id": "req_stub",
        "conversation_id": "conv_stub",
        "answer": "A deterministic test answer.",
        "evidence_status": EvidenceStatus.partially_supported,
        "answer_type": AnswerType.factual,
        "confidence": Confidence.low,
        "confidence_basis": "Stub answer used only for transport tests.",
        "provider": "deterministic",
        "validation": ValidationReport(
            passed=True,
            citation_validation_passed=True,
            claim_validation_passed=True,
        ),
    }
    payload.update(overrides)
    return AssistantAnswer(**payload)


# ----------------------------------------------------------------------
# Status, suggestions, and tools
# ----------------------------------------------------------------------
def test_assistant_status_is_safe_and_secret_free(synthetic_analytics):
    service = make_service(synthetic_analytics)
    settings = AssistantSettings(
        provider="openai_compatible",
        model="test-model",
        api_key="sk-test-secret-value-not-real",
        base_url="https://provider.example/v1",
    )
    assistant = AssistantOrchestrator(service=service, settings=settings)
    client = make_client(service, assistant=assistant)

    response = client.get(f"{API_PREFIX}/assistant/status")
    payload = assert_envelope(response)
    data = payload["data"]
    assert data["enabled"] is True
    assert data["mode"] in {"deterministic", "provider", "fallback"}
    assert data["provider"] == "openai_compatible"
    assert data["contract_version"]
    assert data["tools_available"]
    assert "sk-test-secret-value-not-real" not in json.dumps(payload)


def test_assistant_status_reports_disabled_mode(synthetic_analytics):
    service = make_service(synthetic_analytics)
    assistant = AssistantOrchestrator(
        service=service, settings=AssistantSettings(enabled=False)
    )
    client = make_client(service, assistant=assistant)
    payload = assert_envelope(client.get(f"{API_PREFIX}/assistant/status"))
    assert payload["data"]["enabled"] is False
    assert payload["data"]["notes"]
    assert payload["quality"]["status"] == "partial"


def test_assistant_suggestions_are_bounded_golden_questions(synthetic_analytics):
    client = make_client(make_service(synthetic_analytics))
    payload = assert_envelope(
        client.get(f"{API_PREFIX}/assistant/suggestions?limit=5")
    )
    assert payload["data"]["count"] == 5
    assert len(payload["data"]["suggestions"]) == 5
    golden = json.loads(
        open("tests/assistant/golden_questions.json", encoding="utf-8").read()
    )
    known = {item["question_id"] for item in golden["questions"]}
    for suggestion in payload["data"]["suggestions"]:
        assert suggestion["question_id"] in known
        assert suggestion["question"]


def test_assistant_suggestions_reject_out_of_range_limit(synthetic_analytics):
    client = make_client(make_service(synthetic_analytics))
    response = client.get(f"{API_PREFIX}/assistant/suggestions?limit=10")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_assistant_tools_are_allowlisted_and_described(synthetic_analytics):
    client = make_client(make_service(synthetic_analytics))
    payload = assert_envelope(client.get(f"{API_PREFIX}/assistant/tools"))
    tools = payload["data"]["tools"]
    assert payload["data"]["count"] == len(tools) == 22
    names = {tool["name"] for tool in tools}
    assert "gas_flame_statistics" in names
    assert "search_scientific_documents" in names
    for tool in tools:
        assert tool["description"]
        assert tool["category"]
        assert tool["arguments_schema"]["type"] == "object"


# ----------------------------------------------------------------------
# Query transport and validation
# ----------------------------------------------------------------------
def test_assistant_query_returns_the_contract_envelope(synthetic_analytics):
    assistant = StubAssistant(stub_answer())
    client = make_client(make_service(synthetic_analytics), assistant=assistant)

    response = client.post(
        f"{API_PREFIX}/assistant/query",
        json={"question": "What is in PSI-10?", "max_tool_calls": 4},
        headers={"X-Request-ID": "req_assistant_test"},
    )
    payload = assert_envelope(response)
    assert response.headers["Cache-Control"] == "no-store"
    data = payload["data"]
    assert data["contract_version"]
    assert data["request_id"] == "req_assistant_test"
    assert data["answer"]
    assert "validation" in data
    assert payload["meta"]["assistant_contract_version"] == data["contract_version"]
    assert payload["meta"]["conversation_id"] == "conv_stub"
    assert payload["quality"]["status"] == "partial"
    assert assistant.last_query.question == "What is in PSI-10?"
    assert assistant.last_query.max_tool_calls == 4
    assert assistant.last_request_id == "req_assistant_test"


def test_assistant_query_rejects_invalid_bodies(synthetic_analytics):
    client = make_client(
        make_service(synthetic_analytics), assistant=StubAssistant(stub_answer())
    )
    endpoint = f"{API_PREFIX}/assistant/query"

    missing_question = client.post(endpoint, json={})
    assert missing_question.status_code == 422
    assert missing_question.json()["error"]["code"] == "validation_error"

    empty_question = client.post(endpoint, json={"question": "   "})
    assert empty_question.status_code == 422

    too_many_tools = client.post(
        endpoint, json={"question": "test", "max_tool_calls": 13}
    )
    assert too_many_tools.status_code == 422

    unknown_field = client.post(
        endpoint, json={"question": "test", "sql": "select * from gas_flame_test"}
    )
    assert unknown_field.status_code == 422


def test_assistant_query_fail_closed_answer_keeps_partial_quality(synthetic_analytics):
    answer = stub_answer(
        answer="The application withheld the draft.",
        evidence_status=EvidenceStatus.insufficient_evidence,
        confidence=Confidence.low,
        validation=ValidationReport(
            passed=False,
            citation_validation_passed=False,
            claim_validation_passed=False,
            errors=["claim validation failed"],
        ),
    )
    client = make_client(
        make_service(synthetic_analytics), assistant=StubAssistant(answer)
    )
    payload = assert_envelope(
        client.post(
            f"{API_PREFIX}/assistant/query", json={"question": "test question"}
        )
    )
    assert payload["data"]["validation"]["passed"] is False
    assert payload["quality"]["status"] == "partial"


def test_disabled_assistant_never_runs_tools(synthetic_analytics):
    service = make_service(synthetic_analytics)
    assistant = AssistantOrchestrator(
        service=service, settings=AssistantSettings(enabled=False)
    )
    client = make_client(service, assistant=assistant)

    payload = assert_envelope(
        client.post(
            f"{API_PREFIX}/assistant/query",
            json={"question": "Which combustion investigations are available?"},
        )
    )
    data = payload["data"]
    assert data["tools_used"] == []
    assert data["citations"] == []
    assert data["fallback_mode"] is True
    assert any(
        limitation["code"] == "assistant_disabled"
        for limitation in data["limitations"]
    )
    health = assert_envelope(client.get(f"{API_PREFIX}/health"))
    assert health["data"]["assistant"] == "disabled"


def test_cors_preflight_allows_assistant_post(synthetic_analytics):
    client = make_client(make_service(synthetic_analytics))
    response = client.options(
        f"{API_PREFIX}/assistant/query",
        headers={
            "Origin": "http://example.test",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert "POST" in response.headers["access-control-allow-methods"]
    assert response.headers["access-control-allow-origin"] == "http://example.test"
