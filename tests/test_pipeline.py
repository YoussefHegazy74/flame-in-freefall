"""Pipeline orchestration helpers and interim parse-report invariants."""

from __future__ import annotations

import dataclasses
import json

import pytest

import src.data_pipeline.pipeline as pipeline
from src.data_pipeline.config import PARSER_VERSION
from src.data_pipeline.pipeline import (
    PIPELINE_VERSION,
    _artifact_name,
    _batches,
    _is_reusable,
    _key,
    _load_previous_report,
    _source,
)
from src.data_pipeline.provenance import ProvenanceError, SourceFile


def test_batches_preserve_order_and_size():
    assert list(_batches(range(5), size=2)) == [[0, 1], [2, 3], [4]]
    assert list(_batches([], size=2)) == []
    assert list(_batches(range(4), size=10)) == [[0, 1, 2, 3]]


def test_artifact_names_are_filesystem_safe():
    assert _artifact_name("PSI-100::a b/c") == "psi-100-a-b-c.parquet"
    assert _artifact_name("") == "unknown.parquet"


def test_source_keys_include_the_sheet_when_present():
    assert _key("telemetry", "PSI-100", "file.csv", None) == "telemetry::PSI-100::file.csv::"
    assert _key("telemetry", "PSI-100", "file.xlsx", "RawData") == (
        "telemetry::PSI-100::file.xlsx::RawData"
    )


def test_reuse_requires_matching_checksum_version_table_and_output(tmp_path):
    output = tmp_path / "run.parquet"
    output.write_bytes(b"parquet")
    source = SourceFile(
        accession="PSI-100",
        file_name="file.csv",
        path=tmp_path / "file.csv",
        sha256="a" * 64,
        retrieved_at="2026-11-09T00:00:00Z",
        source_url="https://psi.nasa.gov/example",
    )
    previous = {
        "source_sha256": source.sha256,
        "parser_version": PARSER_VERSION,
        "table_name": "telemetry_point",
        "parser": "telemetry",
        "output": str(output),
        "pipeline_version": PIPELINE_VERSION,
    }
    assert _is_reusable(previous, source, output, "telemetry_point", "telemetry") is True
    assert _is_reusable(None, source, output, "telemetry_point", "telemetry") is False
    assert _is_reusable(previous, dataclasses.replace(source, sha256="b" * 64), output, "telemetry_point", "telemetry") is False
    assert _is_reusable(previous, source, output, "smoke_point", "telemetry") is False
    output.unlink()
    assert _is_reusable(previous, source, output, "telemetry_point", "telemetry") is False


def test_load_previous_report_handles_missing_and_corrupt_files(tmp_path, monkeypatch):
    report_path = tmp_path / "parse_report.json"
    monkeypatch.setattr(pipeline, "PARSE_REPORT_JSON", report_path)
    assert _load_previous_report() == {}

    report_path.write_text("{not json", encoding="utf-8")
    assert _load_previous_report() == {}

    report_path.write_text(
        json.dumps({"sources": [{"key": "a"}, {"key": "b"}, {"no_key": True}]}),
        encoding="utf-8",
    )
    assert set(_load_previous_report()) == {"a", "b"}


def test_source_lookup_fails_closed_for_a_missing_file():
    entry = {
        "accession": "PSI-999",
        "file_name": "definitely-missing.csv",
        "source_url": "https://psi.nasa.gov/example",
        "expected_bytes": 1,
    }
    with pytest.raises(ProvenanceError, match="source file is missing"):
        _source(entry, {})


def test_parse_report_describes_every_selected_source_and_output():
    from src.data_pipeline.pipeline import PARSE_REPORT_JSON

    report = json.loads(PARSE_REPORT_JSON.read_text(encoding="utf-8"))
    assert report["schema_version"] == "1.0.0"
    assert report["pipeline_version"] == PIPELINE_VERSION
    assert report["parser_version"] == PARSER_VERSION
    assert report["source_count"] == 79
    assert report["source_file_count"] == 72
    assert report["reused_count"] == 0
    assert report["issue_count"] == 4
    assert len(report["sources"]) == 79
    assert len(report["outputs"]) == 57

    kinds: dict[str, int] = {}
    for source in report["sources"]:
        kinds[source["kind"]] = kinds.get(source["kind"], 0) + 1
        assert source["source_sha256"]
        assert len(source["source_sha256"]) == 64
        assert source["parser"]
        assert source["table_name"]
        assert source["output_rows"] >= 0
    assert kinds["experimental_table"] == 27
    assert kinds["telemetry"] == 5
    assert kinds["smoke_telemetry_csv"] == 44
    assert kinds["material_workbook"] == 2
    assert kinds["test_log_xls"] == 1

    from src.data_pipeline.config import ROOT

    for output in report["outputs"].values():
        assert (ROOT / output["path"]).exists()
        assert output["rows"] >= 0
        assert output["bytes"] > 0

    telemetry = [source for source in report["sources"] if source["kind"] == "telemetry"]
    smoke = [source for source in report["sources"] if source["kind"] == "smoke_telemetry_csv"]
    assert sum(source["output_rows"] for source in telemetry) == 1_762_436
    assert sum(source["output_rows"] for source in smoke) == 6_251_427
    assert any(source["issue_count"] == 1 for source in smoke)

    summary_sources = [
        source for source in report["sources"] if source["parser"] == "summary_table"
    ]
    flagged = [source for source in summary_sources if source["issue_count"]]
    assert len(flagged) == 1
    assert flagged[0]["file_name"] == "PSI-69_Experimental table_FLEX.csv"
    assert [issue["code"] for issue in flagged[0]["issues"]] == ["encoding_fallback"]
