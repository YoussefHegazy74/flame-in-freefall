"""Contract tests for the Phase 5 answer schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.assistant.contract import (
    CONTRACT_VERSION,
    AnswerType,
    AssistantAnswer,
    CitationReference,
    Claim,
    ClaimType,
    Confidence,
    EvidenceStatus,
    Limitation,
    SupportingData,
    ToolCall,
    ToolStatus,
    ValidationCheck,
    ValidationReport,
    ValueKind,
)


def citation(**overrides) -> CitationReference:
    payload = {
        "citation_id": "cit_f_2a9f8d907458d052",
        "citation_type": "file",
        "accession": "PSI-98",
        "dataset_ids": ["psi-98-metadata"],
        "file_name": "PSI-98_Experimental table_SAFFIRE-1.csv",
        "source_url": "https://psi.nasa.gov/example.csv",
        "sha256": "a" * 64,
        "verification_status": "verified",
        "availability": "available",
        "downloadable": True,
        "resolved": True,
    }
    payload.update(overrides)
    return CitationReference(**payload)


def tool_call(**overrides) -> ToolCall:
    payload = {
        "call_id": "call_1",
        "tool": "gas_flame_statistics",
        "arguments": {"accession": "PSI-10"},
        "status": ToolStatus.ok,
        "duration_ms": 3.2,
        "result_summary": "256 included rows",
        "result_hash": "b" * 64,
    }
    payload.update(overrides)
    return ToolCall(**payload)


def numerical_claim(**overrides) -> Claim:
    payload = {
        "claim_id": "claim_1",
        "text": "PSI-10 has 256 included gas-flame rows.",
        "claim_type": ClaimType.numerical,
        "value": 256,
        "unit": "rows",
        "value_kind": ValueKind.measured,
        "dataset_id": "psi-10-gas-flame",
        "accession": "PSI-10",
        "tool_call_id": "call_1",
        "citation_ids": ["cit_f_2a9f8d907458d052"],
        "supported": True,
    }
    payload.update(overrides)
    return Claim(**payload)


def valid_answer(**overrides) -> AssistantAnswer:
    payload = {
        "contract_version": CONTRACT_VERSION,
        "request_id": "req_test",
        "answer": "PSI-10 has 256 included gas-flame rows.",
        "evidence_status": EvidenceStatus.fully_supported,
        "answer_type": AnswerType.numerical,
        "citations": [citation()],
        "supporting_data": [
            SupportingData(
                data_id="data_1",
                tool_call_id="call_1",
                label="PSI-10 gas-flame counts",
                value_kind=ValueKind.measured,
                unit="rows",
                dataset_id="psi-10-gas-flame",
                accession="PSI-10",
                summary="256 included rows and 71 excluded qualified rows.",
                values={"included_rows": 256, "excluded_qualified_rows": 71},
                citation_ids=["cit_f_2a9f8d907458d052"],
            )
        ],
        "claims": [numerical_claim()],
        "limitations": [
            Limitation(code="ramped_condition_rows", message="Ramped rows are excluded by default.")
        ],
        "tools_used": [tool_call()],
        "confidence": Confidence.high,
        "confidence_basis": "The count comes from a deterministic canonical-table query.",
        "dataset_version": "a" * 64,
        "provider": "deterministic",
        "validation": ValidationReport(
            passed=True,
            citation_validation_passed=True,
            claim_validation_passed=True,
            checks=[ValidationCheck(name="citation_ids_resolved", passed=True)],
        ),
    }
    payload.update(overrides)
    return AssistantAnswer(**payload)


def test_contract_version_is_frozen():
    assert CONTRACT_VERSION == "1.0.0"


def test_valid_answer_round_trips():
    answer = valid_answer()
    payload = answer.public_payload()
    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["citations"][0]["citation_id"] == "cit_f_2a9f8d907458d052"
    assert payload["validation"]["passed"] is True


def test_fully_supported_factual_answer_requires_citation():
    with pytest.raises(ValidationError):
        valid_answer(citations=[])


def test_high_confidence_requires_fully_supported_evidence():
    with pytest.raises(ValidationError):
        valid_answer(evidence_status=EvidenceStatus.partially_supported)


def test_insufficient_evidence_must_be_low_confidence():
    with pytest.raises(ValidationError):
        valid_answer(
            evidence_status=EvidenceStatus.insufficient_evidence,
            confidence=Confidence.moderate,
            claims=[],
            citations=[],
            supporting_data=[],
            validation=ValidationReport(),
        )


def test_numerical_claim_requires_tool_call_and_value_kind():
    with pytest.raises(ValidationError):
        numerical_claim(tool_call_id=None)
    with pytest.raises(ValidationError):
        numerical_claim(value_kind=None)


def test_numerical_claim_value_must_be_numeric():
    with pytest.raises(ValidationError):
        numerical_claim(value="256")


def test_unavailable_citation_must_not_be_downloadable():
    with pytest.raises(ValidationError):
        citation(availability="unavailable", downloadable=True)


def test_row_citation_requires_row():
    with pytest.raises(ValidationError):
        citation(citation_id="cit_r_abc", citation_type="row", row=None)


def test_file_citation_must_not_have_row():
    with pytest.raises(ValidationError):
        citation(row=4)


def test_duplicate_citation_ids_are_rejected():
    with pytest.raises(ValidationError):
        valid_answer(citations=[citation(), citation()])


def test_duplicate_claim_ids_are_rejected():
    with pytest.raises(ValidationError):
        valid_answer(claims=[numerical_claim(), numerical_claim()])


def test_passed_validation_requires_every_claim_supported():
    with pytest.raises(ValidationError):
        valid_answer(claims=[numerical_claim(supported=False)])


def test_passed_validation_requires_citation_validation():
    with pytest.raises(ValidationError):
        valid_answer(
            validation=ValidationReport(
                passed=True,
                citation_validation_passed=False,
                claim_validation_passed=True,
            )
        )


def test_passed_validation_rejects_unknown_citation_references():
    with pytest.raises(ValidationError):
        valid_answer(
            claims=[numerical_claim(citation_ids=["cit_f_unknown"])],
        )


def test_clarification_is_required_for_clarification_answers():
    with pytest.raises(ValidationError):
        valid_answer(
            answer_type=AnswerType.clarification_required,
            evidence_status=EvidenceStatus.insufficient_evidence,
            confidence=Confidence.low,
            citations=[],
            claims=[],
            supporting_data=[],
            validation=ValidationReport(),
        )


def test_clarification_is_rejected_for_other_answer_types():
    from src.assistant.contract import ClarificationRequest

    with pytest.raises(ValidationError):
        valid_answer(
            clarification=ClarificationRequest(question="Which dataset?")
        )


def test_evidence_status_values_are_stable():
    assert {item.value for item in EvidenceStatus} == {
        "fully_supported",
        "partially_supported",
        "insufficient_evidence",
        "unavailable_data",
        "conflicting_evidence",
    }


def test_answer_type_values_are_stable():
    assert {item.value for item in AnswerType} == {
        "factual",
        "numerical",
        "exploratory",
        "comparison",
        "methodology",
        "clarification_required",
    }


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError):
        AssistantAnswer(
            **{
                **valid_answer().model_dump(),
                "unexpected": True,
            }
        )
