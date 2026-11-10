"""Tests for the Phase 5 evaluation harness itself."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.analytics.registry import load_registries
from src.analytics.service import AnalyticsService
from src.assistant.config import AssistantSettings
from src.assistant.contract import AssistantQuery
from src.assistant.evaluation import (
    evaluate_provider_boundary,
    evaluate_question,
    evaluate_retrieval,
    run_golden_evaluation,
)
from src.assistant.orchestrator import AssistantOrchestrator
from src.assistant.retrieval import get_default_index
from src.data_pipeline.config import PROCESSED_DIR, REPORTS_DIR

pytestmark = pytest.mark.integration

GOLDEN_PATH = Path(__file__).with_name("golden_questions.json")
RETRIEVAL_PATH = Path(__file__).with_name("retrieval_golden.json")


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
def golden() -> dict:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def retrieval_cases() -> dict:
    return json.loads(RETRIEVAL_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def index(service):
    return get_default_index(service=service)


def test_golden_evaluation_metrics_pass(service, golden):
    report = run_golden_evaluation(
        service=service,
        settings=AssistantSettings(),
        questions=golden["questions"],
        provider_checks=False,
    )
    summary = report["summary"]
    assert summary["questions_total"] == len(golden["questions"])
    assert summary["questions_passed"] == summary["questions_total"]
    assert summary["contract_pass_rate"] == 1.0
    assert summary["citation_validity_rate"] == 1.0
    assert summary["supported_claim_rate"] == 1.0
    assert summary["claim_tool_link_rate"] == 1.0
    assert summary["numerical_exact_match_rate"] == 1.0
    assert summary["unit_consistency_rate"] == 1.0
    assert summary["tool_selection_accuracy"] == 1.0
    assert summary["correct_refusal_rate"] == 1.0
    assert summary["required_evidence_source_coverage_rate"] == 1.0
    assert summary["failed_questions"] == []
    assert summary["failure_categories"] == {}
    assert report["real_model_evaluated"] is False
    assert report["provider"]["name"] == "deterministic"
    assert report["dataset_version"] == golden["dataset_version"]


def test_retrieval_golden_labels_and_recall(service, index, retrieval_cases):
    report = evaluate_retrieval(
        index,
        retrieval_cases["cases"],
        default_k=retrieval_cases["default_k"],
    )
    assert report["cases_usable"] == len(retrieval_cases["cases"])
    assert report["label_errors"] == 0
    assert report["mean_recall_at_k"] == 1.0
    assert report["mean_reciprocal_rank"] is not None
    assert report["mean_reciprocal_rank"] >= 0.5
    assert report["mean_precision_at_k"] is not None
    assert report["mean_precision_at_k"] >= 0.4
    assert report["index_version"] == index.manifest.index_version


def test_provider_boundary_checks_pass(service, golden):
    settings = AssistantSettings()
    orchestrator = AssistantOrchestrator(service=service, settings=settings)
    selected = [
        question
        for question in golden["questions"]
        if question["question_id"] in {"dq-009", "dq-020", "dq-033"}
    ]
    baseline = [
        orchestrator.answer(
            AssistantQuery(question=question["question"]),
            request_id=f"req_baseline_{question['question_id']}",
        )
        for question in selected
    ]
    report = evaluate_provider_boundary(
        service, settings, selected, baseline
    )
    assert report["failing_provider"]["passed"] is True
    assert report["failing_provider"]["fallback_rate"] == 1.0
    assert report["mock_rephrase_provider"]["passed"] is True
    assert (
        report["mock_rephrase_provider"]["accepted_without_fallback_rate"] == 1.0
    )
    assert report["real_model_evaluated"] is False


def test_evaluation_rejects_wrong_number_and_unit(service, golden):
    question = next(
        item for item in golden["questions"] if item["question_id"] == "dq-009"
    )
    orchestrator = AssistantOrchestrator(
        service=service, settings=AssistantSettings()
    )
    answer = orchestrator.answer(
        AssistantQuery(question=question["question"]), request_id="req_eval_wrong"
    )

    wrong_value = dict(question)
    wrong_value["expected_numeric"] = [
        {
            "label": "included_rows",
            "field": "included_rows",
            "value": 999,
            "unit": "rows",
            "tolerance": 0,
        }
    ]
    result = evaluate_question(
        wrong_value, answer, service, latency_ms=1.0
    )
    assert result["passed"] is False
    assert "numeric_grounding" in result["failure_categories"]

    wrong_unit = dict(question)
    wrong_unit["expected_numeric"] = [
        {
            "label": "included_rows",
            "field": "included_rows",
            "value": 256,
            "unit": "bar",
            "tolerance": 0,
        }
    ]
    result = evaluate_question(
        wrong_unit, answer, service, latency_ms=1.0
    )
    assert result["passed"] is False
    assert "numeric_unit" in result["failure_categories"]


def test_evaluation_rejects_unresolved_citation_and_forbidden_claim(service, golden):
    question = next(
        item for item in golden["questions"] if item["question_id"] == "dq-009"
    )
    orchestrator = AssistantOrchestrator(
        service=service, settings=AssistantSettings()
    )
    answer = orchestrator.answer(
        AssistantQuery(question=question["question"]), request_id="req_eval_citation"
    )
    mutated = answer.model_copy(
        update={
            "citations": [
                citation.model_copy(update={"resolved": False})
                for citation in answer.citations
            ]
        }
    )
    result = evaluate_question(
        question, mutated, service, latency_ms=1.0
    )
    assert result["passed"] is False
    assert "citation_integrity" in result["failure_categories"]

    forbidden = dict(question)
    forbidden["forbidden_claims"] = ["256 valid included gas-flame records"]
    result = evaluate_question(
        forbidden, answer, service, latency_ms=1.0
    )
    assert result["passed"] is False
    assert "forbidden_claim" in result["failure_categories"]
