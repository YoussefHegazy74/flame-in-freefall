"""Orchestrator, provider-boundary, and fail-closed tests.

These tests use the real canonical dataset. They never assert a fabricated
scientific value: every expected number comes from a deterministic tool.
"""

from __future__ import annotations

import pytest

from src.analytics.registry import load_registries
from src.analytics.service import AnalyticsService
from src.assistant.citation_validation import (
    CitationIssue,
    CitationValidationResult,
)
from src.assistant.config import AssistantSettings
from src.assistant.contract import AssistantQuery, Confidence, EvidenceStatus
from src.assistant.orchestrator import AssistantOrchestrator
from src.assistant.providers import (
    ProviderError,
    RephraseResult,
    build_provider,
)
from src.data_pipeline.config import PROCESSED_DIR, REPORTS_DIR

pytestmark = pytest.mark.integration

FORBIDDEN_IN_DETERMINISTIC_ANSWER = (
    "sk-",
    "ignore previous instructions",
    "api_key=",
    "password=",
)


def _require_canonical_data() -> None:
    required = (
        PROCESSED_DIR / "gas_flame_test.parquet",
        PROCESSED_DIR / "telemetry_point.parquet",
        PROCESSED_DIR / "smoke_point.parquet",
        PROCESSED_DIR / "dataset_manifest.json",
        REPORTS_DIR / "dataset_quality_report.json",
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        pytest.skip("canonical data is not present: " + ", ".join(missing))


@pytest.fixture(scope="module")
def service() -> AnalyticsService:
    _require_canonical_data()
    return AnalyticsService(bundle=load_registries())


@pytest.fixture(scope="module")
def settings() -> AssistantSettings:
    return AssistantSettings(retrieval_enabled=False)


class ScriptedProvider:
    name = "scripted_test_provider"
    fallback_capable = True

    def __init__(self, function) -> None:
        self._function = function
        self.requests = []

    def rephrase(self, request):
        self.requests.append(request)
        return self._function(request)


class FailingProvider:
    name = "failing_test_provider"
    fallback_capable = True

    def rephrase(self, request):  # noqa: ARG002
        raise ProviderError("upstream provider is unavailable")


def _orchestrator(
    service: AnalyticsService,
    settings: AssistantSettings,
    provider=None,
) -> AssistantOrchestrator:
    return AssistantOrchestrator(
        service=service, settings=settings, provider=provider
    )


# ----------------------------------------------------------------------
# Deterministic pipeline
# ----------------------------------------------------------------------
def test_deterministic_answer_is_cited_and_fully_validated(service, settings):
    orchestrator = _orchestrator(service, settings)
    answer = orchestrator.answer(
        AssistantQuery(
            question="How many valid PSI-10 gas-flame records are available?"
        ),
        request_id="req_deterministic",
    )

    assert answer.request_id == "req_deterministic"
    assert answer.evidence_status == EvidenceStatus.fully_supported
    assert answer.answer_type.value == "numerical"
    assert answer.provider == "deterministic"
    assert answer.fallback_mode is False
    assert answer.citations
    assert answer.claims
    assert answer.validation.passed is True
    assert answer.validation.citation_validation_passed is True
    assert answer.validation.claim_validation_passed is True
    assert answer.confidence in {Confidence.moderate, Confidence.high}
    assert all(claim.supported for claim in answer.claims)
    assert all(citation.resolved for citation in answer.citations)
    assert all(citation.downloadable or citation.availability != "available" for citation in answer.citations)
    assert any("256" in claim.text for claim in answer.claims)

    serialized = answer.model_dump_json()
    for forbidden in FORBIDDEN_IN_DETERMINISTIC_ANSWER:
        assert forbidden not in serialized.lower()


def test_every_answer_uses_only_allowlisted_tool_names(service, settings):
    orchestrator = _orchestrator(service, settings)
    answer = orchestrator.answer(
        AssistantQuery(question="What does the PSI-159 dataset contain?"),
        request_id="req_tools",
    )
    allowed_names = {tool["name"] for tool in orchestrator.tools()}
    assert answer.tools_used
    assert {call.tool for call in answer.tools_used} <= allowed_names


def test_missing_values_are_refused_not_imputed(service, settings):
    orchestrator = _orchestrator(service, settings)
    answer = orchestrator.answer(
        AssistantQuery(
            question="Treat the missing PSI-10 pressure_approx_bar values as zero and compute the average."
        ),
        request_id="req_missing",
    )
    lowered = answer.answer.lower()
    assert answer.evidence_status == EvidenceStatus.insufficient_evidence
    assert answer.answer_type.value == "numerical"
    assert answer.validation.passed is True
    assert "missing is not zero" in lowered
    assert "not calculated" in lowered or "cannot" in lowered
    assert "average is zero" not in lowered
    assert any(
        limitation.code == "missing_not_zero" for limitation in answer.limitations
    )


def test_unauthorized_unit_conversion_is_refused(service, settings):
    orchestrator = _orchestrator(service, settings)
    answer = orchestrator.answer(
        AssistantQuery(
            question="Convert PSI-159 bar values into PSI-10 atm without authorization."
        ),
        request_id="req_conversion",
    )
    lowered = answer.answer.lower()
    assert answer.evidence_status == EvidenceStatus.insufficient_evidence
    assert answer.validation.passed is True
    assert "no approved conversion rule" in lowered
    assert "converted values are produced" in lowered
    assert "psi-159 pressure_approx_bar is expressed in bar and has 333" in lowered
    assert "psi-10 pressure_initial_atm is expressed in atm and has 256" in lowered
    support = {
        (item.accession, item.label): item for item in answer.supporting_data
    }
    assert support[("PSI-159", "pressure_approx_bar summary")].values[
        "non_null_count"
    ] == 333
    assert support[("PSI-10", "pressure_initial_atm summary")].values[
        "non_null_count"
    ] == 256
    assert any(
        limitation.code == "conversion_not_authorized"
        for limitation in answer.limitations
    )


def test_conversation_id_round_trips_without_becoming_evidence(service, settings):
    orchestrator = _orchestrator(service, settings)
    first = orchestrator.answer(
        AssistantQuery(
            question="What experiments are included in PSI-10?",
            conversation_id="conv_round_trip",
        ),
        request_id="req_first",
    )
    second = orchestrator.answer(
        AssistantQuery(
            question="What does the PSI-159 dataset contain?",
            conversation_id="conv_round_trip",
        ),
        request_id="req_second",
    )
    assert first.conversation_id == "conv_round_trip"
    assert second.conversation_id == "conv_round_trip"
    current_calls = {call.call_id for call in second.tools_used}
    assert all(claim.tool_call_id in current_calls for claim in second.claims)
    assert second.validation.passed is True


# ----------------------------------------------------------------------
# Provider boundary
# ----------------------------------------------------------------------
def test_provider_failure_falls_back_to_the_deterministic_answer(service, settings):
    orchestrator = _orchestrator(service, settings, provider=FailingProvider())
    answer = orchestrator.answer(
        AssistantQuery(question="What does the PSI-159 dataset contain?"),
        request_id="req_provider_failure",
    )
    assert answer.provider == "deterministic"
    assert answer.fallback_mode is True
    assert answer.fallback_reason
    assert "failed safely" in answer.fallback_reason
    assert answer.validation.passed is True
    assert any(
        check.name == "provider_rephrase_safe_fallback"
        for check in answer.validation.checks
    )


def test_provider_cannot_introduce_new_numbers(service, settings):
    provider = ScriptedProvider(
        lambda request: RephraseResult(
            accepted=True,
            answer="There are 999999 investigations in the catalog.",
            provider=provider.name,
        )
    )
    orchestrator = _orchestrator(service, settings, provider=provider)
    answer = orchestrator.answer(
        AssistantQuery(question="Which combustion investigations are available?"),
        request_id="req_new_number",
    )
    assert answer.provider == "deterministic"
    assert answer.fallback_mode is True
    assert "999999" not in answer.answer
    assert answer.fallback_reason and "number" in answer.fallback_reason
    assert answer.validation.passed is True


def test_provider_cannot_introduce_new_citations(service, settings):
    provider = ScriptedProvider(
        lambda request: RephraseResult(
            accepted=True,
            answer=(
                "The catalog is verified by cit_f_0000000000000000 and the deterministic answer stands."
            ),
            provider=provider.name,
        )
    )
    orchestrator = _orchestrator(service, settings, provider=provider)
    answer = orchestrator.answer(
        AssistantQuery(question="Which combustion investigations are available?"),
        request_id="req_new_citation",
    )
    assert answer.provider == "deterministic"
    assert answer.fallback_mode is True
    assert "cit_f_0000000000000000" not in answer.answer
    assert answer.fallback_reason and "citation" in answer.fallback_reason
    assert answer.validation.passed is True


def test_provider_cannot_remove_draft_numbers(service, settings):
    provider = ScriptedProvider(
        lambda request: RephraseResult(
            accepted=True,
            answer="The catalog is available.",
            provider=provider.name,
        )
    )
    orchestrator = _orchestrator(service, settings, provider=provider)
    answer = orchestrator.answer(
        AssistantQuery(question="Which combustion investigations are available?"),
        request_id="req_removed_number",
    )
    assert answer.provider == "deterministic"
    assert answer.fallback_mode is True
    assert answer.fallback_reason and "removed a number" in answer.fallback_reason
    assert answer.validation.passed is True


def test_accepted_rephrase_preserves_validation_and_citations(service, settings):
    provider = ScriptedProvider(
        lambda request: RephraseResult(
            accepted=True,
            answer="In short, " + request.draft_answer,
            provider=provider.name,
        )
    )
    orchestrator = _orchestrator(service, settings, provider=provider)
    answer = orchestrator.answer(
        AssistantQuery(question="Which combustion investigations are available?"),
        request_id="req_rephrase",
    )
    assert answer.provider == provider.name
    assert answer.fallback_mode is False
    assert answer.answer.startswith("In short, ")
    assert answer.validation.passed is True
    assert any(
        check.name == "provider_rephrase_preserved_constraints"
        for check in answer.validation.checks
    )
    assert answer.citations


# ----------------------------------------------------------------------
# Fail closed
# ----------------------------------------------------------------------
def test_citation_validation_failure_withholds_the_draft(service, settings, monkeypatch):
    def fail_citations(*args, **kwargs):  # noqa: ARG001
        return CitationValidationResult(
            passed=False,
            citations=[],
            issues=[
                CitationIssue(
                    code="citation_unresolved",
                    message="citation does not resolve",
                    citation_id="cit_f_deadbeefdeadbeef",
                )
            ],
            checks=[],
        )

    monkeypatch.setattr(
        "src.assistant.orchestrator.validate_citations", fail_citations
    )
    orchestrator = _orchestrator(service, settings)
    answer = orchestrator.answer(
        AssistantQuery(question="What does the PSI-159 dataset contain?"),
        request_id="req_withheld",
    )

    assert answer.validation.passed is False
    assert answer.validation.citation_validation_passed is False
    assert answer.citations == []
    assert answer.claims == []
    assert answer.supporting_data == []
    assert "withheld" in answer.answer
    assert answer.tools_used
    assert any(
        limitation.code == "validation_failed"
        for limitation in answer.limitations
    )


# ----------------------------------------------------------------------
# Status
# ----------------------------------------------------------------------
def test_status_is_secret_free_and_reports_all_tools(service, settings):
    orchestrator = _orchestrator(service, settings)
    status = orchestrator.status()
    assert status.enabled is True
    assert status.mode == "deterministic"
    assert status.provider == "deterministic"
    assert status.retrieval_enabled is False
    assert len(status.tools_available) == 22
    assert status.fallback_mode is False


def test_incomplete_provider_configuration_degrades_to_fallback(service):
    settings = AssistantSettings(
        provider="openai_compatible", model="test-model"
    )
    provider, reason = build_provider(settings)
    assert provider.name == "deterministic"
    assert reason and "incomplete" in reason
    orchestrator = AssistantOrchestrator(service=service, settings=settings)
    status = orchestrator.status()
    assert status.mode == "fallback"
    assert status.fallback_mode is True
    assert status.fallback_reason


def test_disabled_status_keeps_the_deterministic_surface(service):
    orchestrator = AssistantOrchestrator(
        service=service, settings=AssistantSettings(enabled=False)
    )
    status = orchestrator.status()
    assert status.enabled is False
    assert status.mode == "deterministic"
    assert status.notes
    assert status.tools_available


def test_provider_cannot_add_an_unapproved_accession(service, settings):
    provider = ScriptedProvider(
        lambda request: RephraseResult(
            accepted=True,
            answer=request.draft_answer + " See PSI-999 for more.",
            provider=provider.name,
        )
    )
    orchestrator = _orchestrator(service, settings, provider=provider)
    answer = orchestrator.answer(
        AssistantQuery(question="Which combustion investigations are available?"),
        request_id="req_new_accession",
    )
    assert answer.provider == "deterministic"
    assert answer.fallback_mode is True
    assert "PSI-999" not in answer.answer
    assert answer.fallback_reason and "accession" in answer.fallback_reason
    assert answer.validation.passed is True
