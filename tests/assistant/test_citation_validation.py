"""Citation validator tests against the real Phase 4 citation records."""

from __future__ import annotations

import pytest

from src.analytics.service import AnalyticsService
from src.assistant.citation_validation import (
    citation_reference_from_payload,
    validate_citations,
)


@pytest.fixture(scope="module")
def service() -> AnalyticsService:
    return AnalyticsService()


def _row_citation_id(service: AnalyticsService) -> str:
    row = service.list_gas_flame_tests(accession="PSI-10", limit=1)["data"][0]
    citation_id = row.get("citation_id")
    assert isinstance(citation_id, str) and citation_id.startswith("cit_r_")
    return citation_id


def test_resolves_a_real_file_citation(service):
    result = validate_citations(["cit_f_2a9f8d907458d052"], service)
    assert result.passed, result.errors
    reference = result.citations[0]
    assert reference.citation_type == "file"
    assert reference.accession == "PSI-98"
    assert reference.verification_status == "verified"
    assert reference.availability == "available"
    assert reference.downloadable is True
    assert reference.sha256


def test_resolves_a_real_row_citation(service):
    citation_id = _row_citation_id(service)
    result = validate_citations([citation_id], service)
    assert result.passed, result.errors
    reference = result.citations[0]
    assert reference.citation_type == "row"
    assert reference.row is not None
    assert reference.verification_status == "verified"


def test_unavailable_file_is_valid_but_not_downloadable(service):
    result = validate_citations(["cit_f_1bb7e4fca123c465"], service)
    assert result.passed, result.errors
    reference = result.citations[0]
    assert reference.availability == "unavailable"
    assert reference.downloadable is False


def test_require_available_rejects_unavailable_file(service):
    result = validate_citations(
        ["cit_f_1bb7e4fca123c465"], service, require_available=True
    )
    assert not result.passed
    assert any(issue.code == "citation_unavailable" for issue in result.issues)


def test_unknown_citation_fails_closed(service):
    result = validate_citations(["cit_f_0000000000000000"], service)
    assert not result.passed
    assert any(issue.code == "citation_not_found" for issue in result.issues)


def test_malformed_citation_id_fails_closed(service):
    result = validate_citations(["not-a-citation"], service)
    assert not result.passed
    assert any(issue.code == "citation_id_invalid" for issue in result.issues)


def test_accession_mismatch_is_rejected(service):
    result = validate_citations(
        ["cit_f_2a9f8d907458d052"], service, expected_accession="PSI-10"
    )
    assert not result.passed
    assert any(
        issue.code == "citation_accession_mismatch" for issue in result.issues
    )


def test_dataset_mismatch_is_rejected(service):
    result = validate_citations(
        ["cit_f_2a9f8d907458d052"],
        service,
        expected_dataset_id="psi-10-gas-flame",
    )
    assert not result.passed
    assert any(
        issue.code == "citation_dataset_mismatch" for issue in result.issues
    )


def test_duplicate_citations_are_deduplicated(service):
    result = validate_citations(
        ["cit_f_2a9f8d907458d052", "cit_f_2a9f8d907458d052"], service
    )
    assert result.passed
    assert len(result.citations) == 1
    assert result.warnings


def test_row_citation_prefix_mismatch_is_rejected(service):
    citation_id = _row_citation_id(service)
    result = validate_citations([citation_id.replace("cit_r_", "cit_f_")], service)
    assert not result.passed


class FakeResolver:
    def __init__(self, payload):
        self.payload = payload

    def get_citation(self, citation_id, request_id=None):
        return {"data": self.payload}


def _payload(**overrides):
    payload = {
        "citation_id": "cit_f_2a9f8d907458d052",
        "kind": "file",
        "accession": "PSI-98",
        "dataset_ids": ["psi-98-metadata"],
        "file": {"name": "source.csv"},
        "locator": {"type": "file", "sheet": None, "row": None},
        "source": {
            "file_name": "source.csv",
            "source_url": "https://psi.nasa.gov/source.csv",
            "sha256": "a" * 64,
        },
        "verification": {"status": "verified"},
        "availability": {"status": "available", "downloadable": True},
    }
    payload.update(overrides)
    return payload


def test_unsafe_source_url_is_rejected():
    payload = _payload()
    payload["source"] = {**payload["source"], "source_url": "javascript:alert(1)"}
    result = validate_citations(["cit_f_2a9f8d907458d052"], FakeResolver(payload))
    assert not result.passed
    assert any(
        issue.code == "citation_source_url_unsafe" for issue in result.issues
    )


def test_unavailable_downloadable_payload_is_rejected():
    payload = _payload(
        verification={"status": "unavailable"},
        availability={"status": "unavailable", "downloadable": True},
    )
    result = validate_citations(["cit_f_2a9f8d907458d052"], FakeResolver(payload))
    assert not result.passed
    assert any(
        issue.code == "unavailable_marked_downloadable" for issue in result.issues
    )


def test_citation_reference_preserves_locator_and_checksum():
    payload = _payload(
        kind="row",
        citation_id="cit_r_abc",
        locator={"type": "row", "sheet": "Sheet1", "row": 7},
        row_verification={"row_verified": True},
    )
    reference = citation_reference_from_payload(payload)
    assert reference.citation_type == "row"
    assert reference.sheet == "Sheet1"
    assert reference.row == 7
    assert reference.sha256 == "a" * 64
