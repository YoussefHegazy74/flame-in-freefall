"""Automated evaluation of the Phase 5 grounded research assistant.

The harness measures separate properties instead of a single misleading
"accuracy" score:

* contract conformance (status, type, validation, limitations, tools);
* independent citation resolution against the Phase 4 registry;
* claim-to-tool linkage and supported-claim rate;
* expected numerical matches and unit consistency;
* correct refusal for insufficient/unavailable evidence;
* required evidence-source coverage;
* retrieval precision@k, recall@k, and MRR on a small labelled set;
* latency distributions;
* provider-failure fallback and deterministic mock-provider behaviour.

No real language model is called by default. The deterministic orchestrator is
the system under test. A mock provider exercises the provider boundary without
pretending to be a model evaluation.
"""

from __future__ import annotations

import math
import re
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from src.analytics.service import AnalyticsService
from src.assistant.claim_validation import NEGATION_RE
from src.assistant.config import AssistantSettings
from src.assistant.contract import (
    AssistantAnswer,
    AssistantQuery,
    EvidenceStatus,
)
from src.assistant.orchestrator import AssistantOrchestrator
from src.assistant.providers import ProviderError, RephraseResult

DANGEROUS_TOOL_NAMES = {
    "sql",
    "sql_query",
    "read_file",
    "read_filesystem",
    "fetch_url",
    "http_get",
    "run_shell",
    "execute_code",
    "eval",
}

REFUSAL_STATUSES = {
    EvidenceStatus.insufficient_evidence,
    EvidenceStatus.unavailable_data,
}

SAFETY_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"/etc/passwd", re.IGNORECASE),
    re.compile(r"evil\.example", re.IGNORECASE),
    re.compile(r"select\s+\*\s+from", re.IGNORECASE),
    re.compile(r"FLAME_LLM_API_KEY\s*=", re.IGNORECASE),
)

SOURCE_TOOL_COVERAGE = {
    "investigation_registry": {
        "source_types": {"investigation"},
        "tools": {"search_investigations", "get_investigation"},
    },
    "dataset_card": {
        "source_types": {"dataset_card"},
        "tools": {"search_datasets", "get_dataset"},
    },
    "document": {
        "source_types": {"document"},
        "tools": {"search_scientific_documents"},
    },
}


class FailingProvider:
    """Provider stub that always fails, to exercise safe fallback."""

    name = "provider_failure_mock"
    fallback_capable = True

    def rephrase(self, request):  # noqa: ARG002
        raise ProviderError("simulated provider failure")


class MockRephraseProvider:
    """Deterministic mock provider. It is not a real model evaluation."""

    name = "mock_provider"
    fallback_capable = True

    def rephrase(self, request):
        return RephraseResult(
            accepted=True,
            answer="In summary, " + request.draft_answer,
            provider=self.name,
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


def _value_entries(answer: AssistantAnswer) -> list[tuple[float, str | None]]:
    entries: list[tuple[float, str | None]] = []
    for item in answer.supporting_data:
        entries.extend((value, item.unit) for value in _numbers(item.values))
    for claim in answer.claims:
        if claim.value is None or isinstance(claim.value, bool):
            continue
        if isinstance(claim.value, (int, float)):
            entries.append((float(claim.value), claim.unit))
    return entries


def _unit_key(unit: str | None) -> str | None:
    if unit is None:
        return None
    normalized = " ".join(unit.strip().lower().split())
    aliases = {
        "degrees celsius": "celsius",
        "degree celsius": "celsius",
        "degrees c": "celsius",
        "degree c": "celsius",
        "°c": "celsius",
        "celsius": "celsius",
        "kelvin": "kelvin",
        "kelvins": "kelvin",
        "k": "kelvin",
    }
    return aliases.get(normalized, normalized)


def _unit_matches(expected: str | None, actual: str | None) -> bool:
    if expected is None:
        return True
    return _unit_key(expected) == _unit_key(actual)


def _positive_phrase(answer_text: str, phrase: str) -> bool:
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", answer_text):
        for match in re.finditer(re.escape(phrase), sentence, re.IGNORECASE):
            prefix = sentence[max(0, match.start() - 90) : match.start()]
            if not NEGATION_RE.search(prefix):
                return True
    return False


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 6)


def _latency_summary(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {"mean_ms": None, "p50_ms": None, "p95_ms": None, "max_ms": None}
    ordered = sorted(values)

    def percentile(fraction: float) -> float:
        if len(ordered) == 1:
            return ordered[0]
        position = (len(ordered) - 1) * fraction
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return ordered[lower]
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    return {
        "mean_ms": round(statistics.fmean(ordered), 3),
        "p50_ms": round(percentile(0.50), 3),
        "p95_ms": round(percentile(0.95), 3),
        "max_ms": round(ordered[-1], 3),
    }


def _citation_checks(
    answer: AssistantAnswer,
    service: AnalyticsService,
) -> tuple[int, list[str]]:
    """Resolve every citation independently and compare its registry fields."""

    failures: list[str] = []
    valid = 0
    for citation in answer.citations:
        try:
            envelope = service.get_citation(
                citation.citation_id, request_id=f"req_eval_{citation.citation_id}"
            )
        except Exception as exc:  # registry lookup must fail closed
            failures.append(
                f"citation_integrity: {citation.citation_id} did not resolve "
                f"({type(exc).__name__})"
            )
            continue
        data = envelope.get("data") or {}
        file_payload = data.get("file") or {}
        source = data.get("source") or {}
        verification = data.get("verification") or {}
        availability = data.get("availability") or {}
        locator = data.get("locator") or {}
        problems: list[str] = []
        if data.get("citation_id") != citation.citation_id:
            problems.append("citation id mismatch")
        if data.get("kind") != citation.citation_type:
            problems.append("citation kind mismatch")
        if data.get("accession") != citation.accession:
            problems.append("accession mismatch")
        if file_payload.get("name") != citation.file_name:
            problems.append("file name mismatch")
        if set(citation.dataset_ids) != set(data.get("dataset_ids") or []):
            problems.append("dataset ids mismatch")
        if verification.get("status") != citation.verification_status:
            problems.append("verification status mismatch")
        if availability.get("status") != citation.availability:
            problems.append("availability status mismatch")
        if bool(availability.get("downloadable")) != citation.downloadable:
            problems.append("downloadable flag mismatch")
        if citation.sha256 != source.get("sha256"):
            problems.append("sha256 mismatch")
        if citation.source_url != source.get("source_url"):
            problems.append("source URL mismatch")
        if citation.citation_type == "row":
            if citation.row != locator.get("row"):
                problems.append("row locator mismatch")
            if citation.sheet != locator.get("sheet"):
                problems.append("sheet locator mismatch")
        if not citation.resolved:
            problems.append("citation is marked unresolved")
        if problems:
            failures.append(
                f"citation_integrity: {citation.citation_id}: "
                + "; ".join(dict.fromkeys(problems))
            )
        else:
            valid += 1
    return valid, failures


def _claim_checks(
    answer: AssistantAnswer,
) -> tuple[int, int, list[str]]:
    failures: list[str] = []
    call_ids = {call.call_id for call in answer.tools_used}
    citation_ids = {citation.citation_id for citation in answer.citations}
    supported = 0
    linked = 0
    for claim in answer.claims:
        if claim.tool_call_id in call_ids:
            linked += 1
        else:
            failures.append(
                f"claim_integrity: {claim.claim_id} has no current tool call"
            )
        missing = set(claim.citation_ids) - citation_ids
        if missing:
            failures.append(
                f"claim_integrity: {claim.claim_id} references unknown citations "
                f"{sorted(missing)}"
            )
        if claim.supported:
            supported += 1
        else:
            failures.append(f"claim_integrity: {claim.claim_id} is unsupported")
    for item in answer.supporting_data:
        if item.tool_call_id not in call_ids:
            failures.append(
                f"supporting_data_integrity: {item.data_id} has no current tool call"
            )
        missing = set(item.citation_ids) - citation_ids
        if missing:
            failures.append(
                f"supporting_data_integrity: {item.data_id} references unknown "
                f"citations {sorted(missing)}"
            )
    return supported, linked, failures


def _source_covered(source: str, answer: AssistantAnswer) -> bool:
    mapping = SOURCE_TOOL_COVERAGE.get(source)
    if mapping is None:
        return False
    evidence_types = {item.source_type.value for item in answer.evidence}
    tools = {call.tool for call in answer.tools_used}
    return bool(evidence_types & mapping["source_types"]) or bool(
        tools & mapping["tools"]
    )


def _scope_covered(answer: AssistantAnswer, scope: dict[str, Any] | None) -> bool | None:
    if not scope:
        return None
    accession = scope.get("accession")
    dataset_id = scope.get("dataset_id")
    if not answer.citations:
        return False
    for citation in answer.citations:
        if accession and citation.accession != accession:
            continue
        if dataset_id and dataset_id not in citation.dataset_ids:
            continue
        return True
    return False


def _numeric_checks(
    answer: AssistantAnswer, question: dict[str, Any]
) -> tuple[int, int, int, int, list[str]]:
    entries = _value_entries(answer)
    failures: list[str] = []
    total = 0
    matched = 0
    unit_total = 0
    unit_matched = 0
    for expected in question.get("expected_numeric", []):
        total += 1
        value = float(expected["value"])
        tolerance = float(expected.get("tolerance", 0))
        candidates = [
            (candidate, unit)
            for candidate, unit in entries
            if math.isclose(candidate, value, rel_tol=0.0, abs_tol=tolerance)
        ]
        if not candidates:
            failures.append(
                f"numeric_grounding: expected {expected.get('label', expected.get('field'))}"
                f"={expected['value']} {expected.get('unit')} is absent"
            )
            continue
        matched += 1
        if expected.get("unit") is not None:
            unit_total += 1
            if any(_unit_matches(expected["unit"], unit) for _, unit in candidates):
                unit_matched += 1
            else:
                observed = sorted(
                    {unit for _, unit in candidates if unit is not None}
                )
                failures.append(
                    f"numeric_unit: expected {expected['unit']} for "
                    f"{expected.get('label', expected.get('field'))}, observed {observed}"
                )
    return total, matched, unit_total, unit_matched, failures


def evaluate_question(
    question: dict[str, Any],
    answer: AssistantAnswer,
    service: AnalyticsService,
    *,
    latency_ms: float,
) -> dict[str, Any]:
    failures: list[str] = []
    question_id = question["question_id"]

    if not answer.answer.strip():
        failures.append("contract: answer is empty")
    if answer.evidence_status.value != question["expected_evidence_status"]:
        failures.append(
            "evidence_status: expected "
            f"{question['expected_evidence_status']}, got {answer.evidence_status.value}"
        )
    if answer.answer_type.value != question["expected_answer_type"]:
        failures.append(
            "answer_type: expected "
            f"{question['expected_answer_type']}, got {answer.answer_type.value}"
        )
    if not answer.validation.passed:
        failures.append(
            "validation: " + "; ".join(answer.validation.errors[:3])
        )
    if answer.fallback_mode:
        failures.append("fallback: unexpected deterministic fallback")

    limitation_codes = {item.code for item in answer.limitations}
    missing_limitations = (
        set(question.get("expected_limitation_codes", [])) - limitation_codes
    )
    if missing_limitations:
        failures.append(
            f"limitations: missing {sorted(missing_limitations)}"
        )

    required_tools = set(question.get("required_tools", []))
    used_tools = {call.tool for call in answer.tools_used}
    missing_tools = required_tools - used_tools
    if missing_tools:
        failures.append(f"tool_selection: missing {sorted(missing_tools)}")
    if used_tools & DANGEROUS_TOOL_NAMES:
        failures.append(
            f"tool_selection: dangerous tools {sorted(used_tools & DANGEROUS_TOOL_NAMES)}"
        )
    bad_statuses = {
        call.tool: call.status
        for call in answer.tools_used
        if call.status in {"failed", "rejected"}
    }
    if bad_statuses:
        failures.append(f"tool_execution: {bad_statuses}")

    citation_types = {citation.citation_type for citation in answer.citations}
    for required_type in question.get("required_citation_types", []):
        if required_type not in citation_types:
            failures.append(f"citation_type: missing {required_type} citation")

    valid_citations, citation_failures = _citation_checks(answer, service)
    failures.extend(citation_failures)
    if any(not citation.resolved for citation in answer.citations):
        failures.append("citation_integrity: an answer citation is unresolved")

    supported_claims, linked_claims, claim_failures = _claim_checks(answer)
    failures.extend(claim_failures)

    numeric_total, numeric_matched, unit_total, unit_matched, numeric_failures = (
        _numeric_checks(answer, question)
    )
    failures.extend(numeric_failures)

    for forbidden in question.get("forbidden_claims", []):
        if _positive_phrase(answer.answer, forbidden):
            failures.append(f"forbidden_claim: asserted {forbidden!r}")

    source_requirements = list(question.get("required_evidence_sources", []))
    sources_covered = sum(
        1 for source in source_requirements if _source_covered(source, answer)
    )
    missing_sources = [
        source for source in source_requirements if not _source_covered(source, answer)
    ]
    if missing_sources:
        failures.append(f"evidence_source: missing {missing_sources}")

    scope = question.get("expected_scope")
    scope_ok = _scope_covered(answer, scope)
    if scope_ok is False:
        failures.append("scope_coverage: no citation matches the expected scope")

    serialized = answer.model_dump_json()
    if any(pattern.search(serialized) for pattern in SAFETY_PATTERNS):
        failures.append("safety: secret, path, SQL, or URL leak detected")
    if any(item.trusted_as_instruction for item in answer.evidence):
        failures.append("safety: retrieved evidence was marked trusted as instruction")

    refusal_expected = answer.evidence_status in REFUSAL_STATUSES
    refused = (
        refusal_expected
        and answer.evidence_status.value == question["expected_evidence_status"]
        and answer.validation.passed
        and all(claim.supported for claim in answer.claims)
    )

    failure_categories = sorted(
        {failure.split(":", 1)[0] for failure in failures}
    )
    return {
        "question_id": question_id,
        "category": question["category"],
        "question": question["question"],
        "passed": not failures,
        "failures": failures,
        "failure_categories": failure_categories,
        "latency_ms": round(latency_ms, 3),
        "evidence_status": answer.evidence_status.value,
        "answer_type": answer.answer_type.value,
        "citations": len(answer.citations),
        "citations_valid": valid_citations,
        "claims": len(answer.claims),
        "claims_supported": supported_claims,
        "claims_linked": linked_claims,
        "numeric_checks": numeric_total,
        "numeric_matches": numeric_matched,
        "unit_checks": unit_total,
        "unit_matches": unit_matched,
        "required_tools": len(required_tools),
        "required_tools_present": len(required_tools & used_tools),
        "tool_calls": len(answer.tools_used),
        "refusal_expected": refusal_expected,
        "refused": refused,
        "required_sources": len(source_requirements),
        "sources_covered": sources_covered,
        "scope_expected": scope is not None,
        "scope_covered": scope_ok,
        "evidence_items": len(answer.evidence),
        "evidence_with_citation": sum(
            1 for item in answer.evidence if item.citation_id
        ),
    }


def summarize_results(results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for item in results if item["passed"])
    citation_total = sum(item["citations"] for item in results)
    citation_valid = sum(item["citations_valid"] for item in results)
    claims_total = sum(item["claims"] for item in results)
    claims_supported = sum(item["claims_supported"] for item in results)
    claims_linked = sum(item["claims_linked"] for item in results)
    numeric_total = sum(item["numeric_checks"] for item in results)
    numeric_matches = sum(item["numeric_matches"] for item in results)
    unit_total = sum(item["unit_checks"] for item in results)
    unit_matches = sum(item["unit_matches"] for item in results)
    tool_questions = sum(1 for item in results if item["required_tools"])
    tool_question_passes = sum(
        1
        for item in results
        if item["required_tools"]
        and item["required_tools_present"] == item["required_tools"]
    )
    refusal_total = sum(1 for item in results if item["refusal_expected"])
    refusal_passed = sum(1 for item in results if item["refused"])
    source_total = sum(item["required_sources"] for item in results)
    source_covered = sum(item["sources_covered"] for item in results)
    scope_total = sum(1 for item in results if item["scope_expected"])
    scope_covered = sum(
        1 for item in results if item["scope_expected"] and item["scope_covered"]
    )
    failure_categories = Counter(
        category
        for item in results
        for category in item["failure_categories"]
    )
    return {
        "questions_total": total,
        "questions_passed": passed,
        "contract_pass_rate": _rate(passed, total),
        "citation_references_total": citation_total,
        "citations_valid": citation_valid,
        "citation_validity_rate": _rate(citation_valid, citation_total),
        "claims_total": claims_total,
        "claims_supported": claims_supported,
        "supported_claim_rate": _rate(claims_supported, claims_total),
        "claims_linked_to_current_tool_call": claims_linked,
        "claim_tool_link_rate": _rate(claims_linked, claims_total),
        "numeric_checks_total": numeric_total,
        "numeric_matches": numeric_matches,
        "numerical_exact_match_rate": _rate(numeric_matches, numeric_total),
        "unit_checks_total": unit_total,
        "unit_matches": unit_matches,
        "unit_consistency_rate": _rate(unit_matches, unit_total),
        "tool_selection_questions": tool_questions,
        "tool_selection_passes": tool_question_passes,
        "tool_selection_accuracy": _rate(tool_question_passes, tool_questions),
        "refusal_questions_total": refusal_total,
        "correct_refusals": refusal_passed,
        "correct_refusal_rate": _rate(refusal_passed, refusal_total),
        "required_evidence_sources_total": source_total,
        "required_evidence_sources_covered": source_covered,
        "required_evidence_source_coverage_rate": _rate(
            source_covered, source_total
        ),
        "scope_checks_total": scope_total,
        "scope_checks_covered": scope_covered,
        "scope_coverage_rate": _rate(scope_covered, scope_total),
        "latency": _latency_summary([item["latency_ms"] for item in results]),
        "failure_categories": dict(sorted(failure_categories.items())),
        "failed_questions": [
            {
                "question_id": item["question_id"],
                "categories": item["failure_categories"],
                "failures": item["failures"],
            }
            for item in results
            if not item["passed"]
        ],
    }


def evaluate_retrieval(
    index,
    cases: Sequence[dict[str, Any]],
    *,
    default_k: int = 5,
) -> dict[str, Any]:
    known_documents = {chunk.document_id for chunk in index.chunks}
    results: list[dict[str, Any]] = []
    for case in cases:
        k = int(case.get("k", default_k))
        relevant = set(case["relevant_document_ids"])
        unknown = relevant - known_documents
        try:
            payload = index.search(
                case["query"],
                accession=case.get("accession"),
                dataset_id=case.get("dataset_id"),
                source_types=case.get("source_types"),
                limit=k,
            )
        except Exception as exc:
            results.append(
                {
                    "case_id": case["case_id"],
                    "query": case["query"],
                    "error": f"{type(exc).__name__}: {exc}",
                    "precision_at_k": 0.0,
                    "recall_at_k": 0.0,
                    "reciprocal_rank": 0.0,
                    "retrieved": [],
                    "relevant": sorted(relevant),
                    "unknown_labels": sorted(unknown),
                }
            )
            continue
        retrieved = [item["document_id"] for item in payload["results"]]
        retrieved_documents = list(dict.fromkeys(retrieved))
        hits = [doc for doc in retrieved_documents if doc in relevant]
        first_hit = next(
            (
                rank
                for rank, doc in enumerate(retrieved, start=1)
                if doc in relevant
            ),
            None,
        )
        results.append(
            {
                "case_id": case["case_id"],
                "query": case["query"],
                "k": k,
                "precision_at_k": round(len(hits) / len(retrieved_documents), 6)
                if retrieved_documents
                else 0.0,
                "recall_at_k": round(len(hits) / len(relevant), 6)
                if relevant
                else 0.0,
                "reciprocal_rank": round(1.0 / first_hit, 6) if first_hit else 0.0,
                "retrieved": retrieved,
                "retrieved_documents": retrieved_documents,
                "relevant": sorted(relevant),
                "hits": hits,
                "unknown_labels": sorted(unknown),
            }
        )

    usable = [item for item in results if "error" not in item]
    return {
        "cases_total": len(results),
        "cases_usable": len(usable),
        "mean_precision_at_k": round(
            statistics.fmean(item["precision_at_k"] for item in usable), 6
        )
        if usable
        else None,
        "mean_recall_at_k": round(
            statistics.fmean(item["recall_at_k"] for item in usable), 6
        )
        if usable
        else None,
        "mean_reciprocal_rank": round(
            statistics.fmean(item["reciprocal_rank"] for item in usable), 6
        )
        if usable
        else None,
        "label_errors": sum(len(item["unknown_labels"]) for item in results),
        "results": results,
        "index_version": index.manifest.index_version,
        "dataset_version": index.manifest.dataset_version,
        "notes": [
            "Relevance labels are minimal, not exhaustive; mean precision@k is a lower bound.",
            "The labelled set is intentionally small and is not a general retrieval benchmark.",
        ],
    }


def _run_questions(
    orchestrator: AssistantOrchestrator,
    questions: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[AssistantAnswer]]:
    results: list[dict[str, Any]] = []
    answers: list[AssistantAnswer] = []
    for question in questions:
        started = time.perf_counter()
        answer = orchestrator.answer(
            AssistantQuery(question=question["question"]),
            request_id=f"req_eval_{question['question_id']}",
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        answers.append(answer)
        results.append(
            evaluate_question(
                question,
                answer,
                orchestrator.service,
                latency_ms=elapsed_ms,
            )
        )
    return results, answers


def evaluate_provider_boundary(
    service: AnalyticsService,
    settings: AssistantSettings,
    questions: Sequence[dict[str, Any]],
    baseline_answers: Sequence[AssistantAnswer],
) -> dict[str, Any]:
    baseline = {
        question["question_id"]: answer
        for question, answer in zip(questions, baseline_answers)
    }

    def run(provider) -> dict[str, Any]:
        orchestrator = AssistantOrchestrator(
            service=service, settings=settings, provider=provider
        )
        checks: list[dict[str, Any]] = []
        for question in questions:
            baseline_answer = baseline[question["question_id"]]
            answer = orchestrator.answer(
                AssistantQuery(question=question["question"]),
                request_id=f"req_{provider.name}_{question['question_id']}",
            )
            baseline_citations = [
                citation.citation_id for citation in baseline_answer.citations
            ]
            answer_citations = [citation.citation_id for citation in answer.citations]
            checks.append(
                {
                    "question_id": question["question_id"],
                    "fallback_mode": answer.fallback_mode,
                    "provider": answer.provider,
                    "validation_passed": answer.validation.passed,
                    "answer_matches_deterministic": answer.answer
                    == baseline_answer.answer,
                    "citations_match": answer_citations == baseline_citations,
                    "fallback_reason": answer.fallback_reason,
                    "answer": answer,
                }
            )
        return {
            "provider": provider.name,
            "questions_total": len(checks),
            "fallback_rate": _rate(
                sum(1 for item in checks if item["fallback_mode"]), len(checks)
            ),
            "deterministic_provider_rate": _rate(
                sum(1 for item in checks if item["provider"] == "deterministic"),
                len(checks),
            ),
            "validation_pass_rate": _rate(
                sum(1 for item in checks if item["validation_passed"]), len(checks)
            ),
            "answer_match_rate": _rate(
                sum(1 for item in checks if item["answer_matches_deterministic"]),
                len(checks),
            ),
            "citation_match_rate": _rate(
                sum(1 for item in checks if item["citations_match"]), len(checks)
            ),
            "failures": [
                item["question_id"]
                for item in checks
                if not item["validation_passed"]
                or not item["citations_match"]
            ],
            "checks": [
                {key: value for key, value in item.items() if key != "answer"}
                for item in checks
            ],
        }

    failing = run(FailingProvider())
    failing["passed"] = (
        failing["fallback_rate"] == 1.0
        and failing["deterministic_provider_rate"] == 1.0
        and failing["validation_pass_rate"] == 1.0
        and failing["answer_match_rate"] == 1.0
        and failing["citation_match_rate"] == 1.0
    )

    mock = run(MockRephraseProvider())
    mock["accepted_without_fallback_rate"] = _rate(
        sum(1 for item in mock["checks"] if not item["fallback_mode"]),
        mock["questions_total"],
    )
    mock["provider_used_rate"] = _rate(
        sum(1 for item in mock["checks"] if item["provider"] == "mock_provider"),
        mock["questions_total"],
    )
    mock["passed"] = (
        mock["accepted_without_fallback_rate"] == 1.0
        and mock["provider_used_rate"] == 1.0
        and mock["validation_pass_rate"] == 1.0
        and mock["citation_match_rate"] == 1.0
    )
    return {
        "real_model_evaluated": False,
        "real_model_note": (
            "No real language model was called. These checks exercise the provider "
            "boundary with a failing stub and a deterministic mock. A real-model "
            "evaluation requires configured credentials and a separate run."
        ),
        "failing_provider": failing,
        "mock_rephrase_provider": mock,
    }


def run_golden_evaluation(
    *,
    service: AnalyticsService,
    settings: AssistantSettings,
    questions: Sequence[dict[str, Any]],
    retrieval_index=None,
    retrieval_cases: Sequence[dict[str, Any]] | None = None,
    retrieval_k: int = 5,
    provider_checks: bool = True,
) -> dict[str, Any]:
    orchestrator = AssistantOrchestrator(
        service=service, settings=settings, retrieval_index=retrieval_index
    )
    results, answers = _run_questions(orchestrator, questions)
    summary = summarize_results(results)
    status = orchestrator.status(load_index=retrieval_index is not None)

    real_model_evaluated = status.mode == "provider" and status.provider not in {
        "deterministic",
        "mock_provider",
    }
    report: dict[str, Any] = {
        "evaluation_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "golden_version": None,
        "contract_version": answers[0].contract_version if answers else None,
        "dataset_version": service.bundle.dataset_version,
        "mode": "deterministic" if not real_model_evaluated else "provider",
        "real_model_evaluated": real_model_evaluated,
        "provider": {
            "name": status.provider,
            "model": status.model,
            "assistant_mode": status.mode,
            "fallback_mode": status.fallback_mode,
            "fallback_reason": status.fallback_reason,
        },
        "index": {
            "version": status.index_version,
            "enabled": settings.retrieval_enabled,
        },
        "summary": summary,
        "questions": results,
        "retrieval": None,
        "provider_checks": None,
        "limitations": [
            "This is not a model benchmark. The default run uses the deterministic provider.",
            "The golden set is small and bound to one canonical dataset version.",
            "Passing software tests does not establish scientific validity.",
            "Numerical expectations cover only the fields explicitly listed in the golden set.",
            "Retrieval labels are minimal and do not represent exhaustive relevance judgments.",
        ],
    }

    if retrieval_cases is not None and retrieval_index is not None:
        report["retrieval"] = evaluate_retrieval(
            retrieval_index, retrieval_cases, default_k=retrieval_k
        )

    if provider_checks:
        report["provider_checks"] = evaluate_provider_boundary(
            service, settings, questions, answers
        )

    return report
