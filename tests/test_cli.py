"""CLI command routing and error-behavior tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.data_pipeline.__main__ as cli
from src.data_pipeline.canonical import CanonicalBuildError
from src.data_pipeline.downloader import DownloadError
from src.data_pipeline.manifest import ManifestError
from src.data_pipeline.pipeline import PipelineError


def test_help_lists_every_required_command():
    help_text = cli.build_parser().format_help()
    for command in (
        "download",
        "validate",
        "parse",
        "build-canonical",
        "report",
        "manifest",
        "all",
    ):
        assert command in help_text


def test_missing_command_is_a_usage_error():
    with pytest.raises(SystemExit) as excinfo:
        cli.main([])
    assert excinfo.value.code == 2


def test_manifest_check_matches_the_committed_manifest():
    assert cli.main(["manifest", "--check"]) == 0


def test_manifest_error_returns_one(monkeypatch):
    def fail():
        raise ManifestError("bad manifest")

    monkeypatch.setattr(cli, "build_manifest", fail)
    assert cli.main(["manifest", "--check"]) == 1


def test_download_without_a_selection_returns_two():
    assert cli.main(["download"]) == 2


def test_download_all_uses_the_selected_manifest(monkeypatch):
    calls = {}

    class FakeReport:
        def summary(self):
            return {
                "downloaded": 1,
                "already_present": 0,
                "listed_404": 0,
                "failed": 0,
                "approval_required": 0,
                "not_selected": 0,
                "total_bytes_downloaded": 10,
                "known_unavailable_verified": 0,
                "known_unavailable_unexpected": 0,
                "duplicate_checksum_groups": 0,
            }

    def fake_download_all(**kwargs):
        calls.update(kwargs)
        return FakeReport()

    monkeypatch.setattr(cli, "download_all", fake_download_all)
    assert cli.main(["download", "--all"]) == 0
    assert calls["datasets"] == ["all"]
    assert calls["dry_run"] is False
    assert calls["force"] is False


def test_download_error_returns_one(monkeypatch):
    def fail(**kwargs):
        raise DownloadError("network down")

    monkeypatch.setattr(cli, "download_all", fail)
    assert cli.main(["download", "--all"]) == 1


def test_parse_command_reports_counts(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "parse_all",
        lambda force=False: {
            "source_count": 3,
            "outputs": {"a.parquet": {"rows": 5, "bytes": 100}},
            "duration_seconds": 1.5,
            "reused_count": 2,
            "issue_count": 0,
        },
    )
    assert cli.main(["parse"]) == 0
    output = capsys.readouterr().out
    assert "Parsed 3 sources" in output
    assert "a.parquet: 5 rows" in output


def test_parse_error_returns_one(monkeypatch):
    def fail(force=False):
        raise PipelineError("bad source")

    monkeypatch.setattr(cli, "parse_all", fail)
    assert cli.main(["parse"]) == 1


def test_build_canonical_command_reports_counts(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "build_canonical",
        lambda: {
            "table_count": 2,
            "total_rows": 10,
            "total_bytes": 200,
            "dataset_version": "a" * 64,
            "tables": {"t": {"rows": 10, "bytes": 200}},
        },
    )
    assert cli.main(["build-canonical"]) == 0
    output = capsys.readouterr().out
    assert "Built 2 canonical tables" in output
    assert "t: 10 rows" in output


def test_build_canonical_error_returns_one(monkeypatch):
    def fail():
        raise CanonicalBuildError("missing interim")

    monkeypatch.setattr(cli, "build_canonical", fail)
    assert cli.main(["build-canonical"]) == 1


def test_validate_command_pass_and_fail(monkeypatch, capsys):
    passing = {
        "status": "pass",
        "acquisition": {"status": "pass", "summary": {"verified": 1, "selected_files": 1, "failed": 0}},
        "canonical": {"status": "pass", "summary": {"tables": 1, "failed": 0}},
    }
    monkeypatch.setattr(cli, "write_validation_report", lambda: passing)
    assert cli.main(["validate"]) == 0
    assert "Acquisition: pass" in capsys.readouterr().out

    failing = {
        "status": "fail",
        "acquisition": {"status": "pass", "summary": {"verified": 1, "selected_files": 1, "failed": 0}},
        "canonical": {"status": "fail", "summary": {"tables": 1, "failed": 1}},
    }
    monkeypatch.setattr(cli, "write_validation_report", lambda: failing)
    assert cli.main(["validate"]) == 1


def test_report_command_writes_reports(monkeypatch, tmp_path):
    processed = tmp_path / "processed"
    processed.mkdir()
    (processed / "dummy.parquet").write_bytes(b"")
    monkeypatch.setattr(cli, "PROCESSED_DIR", processed)
    monkeypatch.setattr(cli, "write_schema_report", lambda path: None)
    monkeypatch.setattr(
        cli,
        "build_quality_report",
        lambda: {"status": "pass", "summary": {"tables": 1, "issues": 0}},
    )
    monkeypatch.setattr(
        cli,
        "write_validation_report",
        lambda: {"status": "pass", "acquisition": {}, "canonical": {}},
    )
    assert cli.main(["report"]) == 0


def test_report_command_fails_when_processed_tables_are_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "PROCESSED_DIR", tmp_path / "empty")
    monkeypatch.setattr(cli, "write_schema_report", lambda path: None)
    monkeypatch.setattr(
        cli,
        "write_validation_report",
        lambda: {"status": "pass", "acquisition": {}, "canonical": {}},
    )
    assert cli.main(["report"]) == 1


def test_all_command_runs_steps_in_order(monkeypatch):
    order = []

    def step(name, code=0):
        def run(args):
            order.append(name)
            return code

        return run

    monkeypatch.setattr(cli, "_cmd_download", step("download"))
    monkeypatch.setattr(cli, "_cmd_parse", step("parse"))
    monkeypatch.setattr(cli, "_cmd_build_canonical", step("build-canonical"))
    monkeypatch.setattr(cli, "_cmd_report", step("report"))
    assert cli.main(["all"]) == 0
    assert order == ["download", "parse", "build-canonical", "report"]


def test_all_command_stops_at_the_first_failure(monkeypatch):
    order = []

    def download(args):
        order.append("download")
        return 1

    def parse(args):
        order.append("parse")
        return 0

    monkeypatch.setattr(cli, "_cmd_download", download)
    monkeypatch.setattr(cli, "_cmd_parse", parse)
    assert cli.main(["all"]) == 1
    assert order == ["download"]
