"""Acquisition and canonical validation tests, including failure paths."""

from __future__ import annotations

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import src.data_pipeline.validation as validation
from src.data_pipeline.config import (
    ACQUISITION_REPORT_JSON,
    VALIDATION_REPORT_JSON,
)
from src.data_pipeline.schemas import TABLE_SCHEMAS
from src.data_pipeline.validation import (
    _check_provenance,
    _duplicate_count,
    validate_acquisition,
    write_validation_report,
)


@pytest.mark.integration
def test_acquisition_validation_passes_for_every_selected_file():
    report = validate_acquisition()
    assert report["status"] == "pass"
    assert report["summary"]["selected_files"] == 72
    assert report["summary"]["present"] == 72
    assert report["summary"]["verified"] == 72
    assert report["summary"]["failed"] == 0
    assert report["summary"]["known_unavailable_verified"] == 2
    assert report["summary"]["known_unavailable_unexpected"] == 0
    assert report["summary"]["duplicate_checksum_groups"] == 0
    for item in report["files"]:
        assert item["status"] == "pass"
        assert item["actual_bytes"] == item["expected_bytes"]
        assert item["actual_sha256"]
        if item["expected_sha256"]:
            assert item["actual_sha256"] == item["expected_sha256"]
        assert item["retrieved_at"]


@pytest.mark.integration
def test_committed_validation_report_records_a_passing_canonical_build():
    report = json.loads(VALIDATION_REPORT_JSON.read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert report["acquisition"]["status"] == "pass"
    assert report["canonical"]["status"] == "pass"
    assert report["canonical"]["summary"]["failed"] == 0
    assert report["canonical"]["summary"]["tables"] >= 13
    for table in report["canonical"]["tables"]:
        assert table["status"] == "pass", table["table_name"]
        if table.get("schema_ok") is not None:
            assert table["schema_ok"] is True
        if table.get("provenance"):
            assert table["provenance"]["complete"] is True


def test_duplicate_primary_key_detection(tmp_path):
    path = tmp_path / "duplicates.parquet"
    table = pa.table({"observation_id": ["a", "a", "b", "c", "c", "c"]})
    pq.write_table(table, path)
    duplicates, method = _duplicate_count(path, "observation_id")
    assert duplicates == 3
    assert method in {"duckdb", "pyarrow"}


def test_provenance_completeness_detection(tmp_path):
    complete = tmp_path / "complete.parquet"
    pq.write_table(
        pa.table(
            {
                "source_sha256": ["a" * 64, "b" * 64],
                "source_url": ["https://example/1", "https://example/2"],
            }
        ),
        complete,
    )
    result = _check_provenance(complete)
    assert result["rows"] == 2
    assert result["complete"] is True

    incomplete = tmp_path / "incomplete.parquet"
    pq.write_table(
        pa.table(
            {
                "source_sha256": ["a" * 64, None],
                "source_url": ["https://example/1", None],
            }
        ),
        incomplete,
    )
    result = _check_provenance(incomplete)
    assert result["rows"] == 2
    assert result["source_sha256_nonnull"] == 1
    assert result["complete"] is False


def test_validate_canonical_reports_missing_tables(tmp_path, monkeypatch):
    monkeypatch.setattr(validation, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(
        validation, "TABLE_SCHEMAS", {"psi_investigation": TABLE_SCHEMAS["psi_investigation"]}
    )
    monkeypatch.setattr(validation, "PRIMARY_KEYS", {"psi_investigation": "accession"})
    monkeypatch.setattr(validation, "EXPECTED_ROWS", {})
    monkeypatch.setattr(validation, "JSON_COLUMNS", {})
    report = validation.validate_canonical()
    assert report["status"] == "fail"
    assert report["summary"]["failed"] == 1
    assert report["tables"][0]["issues"][0]["code"] == "missing_table"


def test_validate_canonical_reports_schema_mismatch(tmp_path, monkeypatch):
    path = tmp_path / "psi_investigation.parquet"
    pq.write_table(
        pa.table({"accession": ["PSI-10"], "unexpected": ["x"]}),
        path,
    )
    monkeypatch.setattr(validation, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(
        validation, "TABLE_SCHEMAS", {"psi_investigation": TABLE_SCHEMAS["psi_investigation"]}
    )
    monkeypatch.setattr(validation, "PRIMARY_KEYS", {"psi_investigation": "accession"})
    monkeypatch.setattr(validation, "EXPECTED_ROWS", {})
    monkeypatch.setattr(validation, "JSON_COLUMNS", {})
    report = validation.validate_canonical()
    assert report["status"] == "fail"
    codes = [
        issue["code"]
        for table in report["tables"]
        for issue in table.get("issues", [])
    ]
    assert "schema_mismatch" in codes


def test_validate_canonical_reports_row_count_mismatch(tmp_path, monkeypatch):
    path = tmp_path / "psi_investigation.parquet"
    schema = TABLE_SCHEMAS["psi_investigation"]
    pq.write_table(
        pa.Table.from_pylist([{name: None for name in schema.names}], schema=schema),
        path,
    )
    monkeypatch.setattr(validation, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(
        validation, "TABLE_SCHEMAS", {"psi_investigation": schema}
    )
    monkeypatch.setattr(validation, "PRIMARY_KEYS", {"psi_investigation": "accession"})
    monkeypatch.setattr(validation, "EXPECTED_ROWS", {"psi_investigation": 24})
    monkeypatch.setattr(validation, "JSON_COLUMNS", {})
    report = validation.validate_canonical()
    assert report["status"] == "fail"
    codes = [
        issue["code"]
        for table in report["tables"]
        for issue in table.get("issues", [])
    ]
    assert "row_count_mismatch" in codes


def test_write_validation_report_writes_even_when_checks_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(
        validation, "validate_acquisition", lambda: {"status": "pass", "summary": {}}
    )
    monkeypatch.setattr(
        validation, "validate_canonical", lambda: {"status": "fail", "summary": {}}
    )
    destination = tmp_path / "validation_report.json"
    monkeypatch.setattr(validation, "VALIDATION_REPORT_JSON", destination)
    report = write_validation_report()
    assert report["status"] == "fail"
    assert destination.exists()
    written = json.loads(destination.read_text(encoding="utf-8"))
    assert written["acquisition"]["status"] == "pass"
    assert written["canonical"]["status"] == "fail"


def test_acquisition_report_lists_the_documented_404s():
    report = json.loads(ACQUISITION_REPORT_JSON.read_text(encoding="utf-8"))
    known = report["known_unavailable"]
    assert len(known) == 2
    assert all(item["status"] == "listed_404" for item in known)
    assert all(item["expected_status"] == 404 for item in known)
