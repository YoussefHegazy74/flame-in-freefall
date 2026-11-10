"""Golden evaluation of the Phase 5 assistant.

Every question in ``golden_questions.json`` runs end to end through the
deterministic orchestrator against the real canonical dataset. The evaluation
checks the expected evidence status, answer type, limitation codes, required
tools and citation types, resolved citations, grounded numbers, and forbidden
claims.

This is not a model benchmark. No model answer is generated or scored.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

import pytest

from src.analytics.registry import load_registries
from src.analytics.service import AnalyticsService
from src.assistant.claim_validation import NEGATION_RE
from src.assistant.config import AssistantSettings
from src.assistant.contract import AssistantQuery
from src.assistant.orchestrator import AssistantOrchestrator
from src.data_pipeline.config import PROCESSED_DIR, REPORTS_DIR

pytestmark = pytest.mark.integration

GOLDEN_PATH = Path(__file__).with_name("golden_questions.json")


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
def golden() -> dict[str, Any]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def orchestrator(service) -> AssistantOrchestrator:
    return AssistantOrchestrator(
        service=service, settings=AssistantSettings()
    )


def _numbers(value: Any, depth: int = 0) -> Iterable[float]:
    if depth > 8:
        return
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        yield float(value)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _numbers(item, depth + 1)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _numbers(item, depth + 1)


def _answer_numbers(answer) -> list[float]:
    found: list[float] = []
    for item in answer.supporting_data:
        found.extend(_numbers(item.values))
    for claim in answer.claims:
        if claim.value is not None:
            found.extend(_numbers(claim.value))
    return found


def _contains_expected_value(answer, value: float, tolerance: float) -> bool:
    return any(
        math.isclose(candidate, value, rel_tol=0.0, abs_tol=tolerance)
        for candidate in _answer_numbers(answer)
    )


def _positive_phrase(answer_text: str, phrase: str) -> bool:
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", answer_text):
        for match in re.finditer(re.escape(phrase), sentence, re.IGNORECASE):
            prefix = sentence[max(0, match.start() - 90) : match.start()]
            if not NEGATION_RE.search(prefix):
                return True
    return False


def test_golden_questions_end_to_end(service, golden, orchestrator):
    failures: list[str] = []
    allowlisted_tools = {tool["name"] for tool in orchestrator.tools()}

    for question in golden["questions"]:
        question_id = question["question_id"]
        try:
            answer = orchestrator.answer(
                AssistantQuery(question=question["question"]),
                request_id=f"req_{question_id}",
            )
        except Exception as exc:  # one failure should not hide the rest
            failures.append(f"{question_id}: raised {type(exc).__name__}: {exc}")
            continue

        if answer.evidence_status.value != question["expected_evidence_status"]:
            failures.append(
                f"{question_id}: evidence status {answer.evidence_status.value} != "
                f"{question['expected_evidence_status']}"
            )
        if answer.answer_type.value != question["expected_answer_type"]:
            failures.append(
                f"{question_id}: answer type {answer.answer_type.value} != "
                f"{question['expected_answer_type']}"
            )
        if not answer.validation.passed:
            failures.append(
                f"{question_id}: validation failed: {answer.validation.errors[:3]}"
            )
        if answer.fallback_mode:
            failures.append(f"{question_id}: unexpected fallback mode")
        if not answer.answer.strip():
            failures.append(f"{question_id}: empty answer")

        limitation_codes = {item.code for item in answer.limitations}
        missing_limitations = set(question.get("expected_limitation_codes", [])) - limitation_codes
        if missing_limitations:
            failures.append(
                f"{question_id}: missing limitation codes {sorted(missing_limitations)}"
            )

        tool_names = {call.tool for call in answer.tools_used}
        missing_tools = set(question.get("required_tools", [])) - tool_names
        if missing_tools:
            failures.append(
                f"{question_id}: missing required tools {sorted(missing_tools)}"
            )
        unknown_tools = tool_names - allowlisted_tools
        if unknown_tools:
            failures.append(
                f"{question_id}: used non-allowlisted tools {sorted(unknown_tools)}"
            )

        citation_types = {citation.citation_type for citation in answer.citations}
        for required_type in question.get("required_citation_types", []):
            if required_type not in citation_types:
                failures.append(
                    f"{question_id}: missing {required_type} citation"
                )
        if any(not citation.resolved for citation in answer.citations):
            failures.append(f"{question_id}: unresolved citation in answer")

        for expected in question.get("expected_numeric", []):
            if not _contains_expected_value(
                answer, expected["value"], expected["tolerance"]
            ):
                failures.append(
                    f"{question_id}: expected {expected['field']}={expected['value']} "
                    f"{expected['unit']} is absent from supporting data"
                )

        for forbidden in question.get("forbidden_claims", []):
            if _positive_phrase(answer.answer, forbidden):
                failures.append(
                    f"{question_id}: answer asserted forbidden claim {forbidden!r}"
                )

    assert not failures, "\n".join(failures)
