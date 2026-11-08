"""Authenticity tests for the committed fixture excerpts."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

from src.data_pipeline.config import RAW_DIR
from src.data_pipeline.provenance import load_acquisition_index


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_rows(path: Path, encoding: str) -> tuple[list[str], list[list[str]]]:
    text = path.read_bytes().decode(encoding)
    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader)
    return header, [list(row) for row in reader]


def test_fixture_manifest_is_present_and_well_formed(fixtures_manifest):
    assert fixtures_manifest["schema_version"] == "1.0.0"
    assert len(fixtures_manifest["fixtures"]) == 7
    names = [item["fixture"] for item in fixtures_manifest["fixtures"]]
    assert len(names) == len(set(names))
    for item in fixtures_manifest["fixtures"]:
        assert item["data_rows"] > 0
        assert len(item["source_rows"]) == item["data_rows"]
        assert item["purpose"]
        assert len(item["source_sha256"]) == 64
        assert len(item["fixture_sha256"]) == 64


def test_fixture_files_match_manifest_checksums(repo_root, fixtures_manifest):
    for item in fixtures_manifest["fixtures"]:
        path = repo_root / item["fixture"]
        assert path.exists(), item["fixture"]
        payload = path.read_bytes()
        assert len(payload) == item["fixture_bytes"]
        assert sha256_bytes(payload) == item["fixture_sha256"]


def test_fixtures_contain_no_replacement_characters(repo_root, fixtures_manifest):
    for item in fixtures_manifest["fixtures"]:
        path = repo_root / item["fixture"]
        text = path.read_bytes().decode(item["encoding"])
        assert "\ufffd" not in text
        assert "\ufffd" not in path.read_bytes().decode("utf-8", errors="ignore")


def test_cp1252_fixture_preserves_the_en_dash_byte(repo_root, fixtures_manifest):
    item = next(
        entry
        for entry in fixtures_manifest["fixtures"]
        if entry["fixture"].endswith("psi69_flex_cp1252.csv")
    )
    payload = (repo_root / item["fixture"]).read_bytes()
    assert payload.count(b"\x96") == 1
    text = payload.decode("cp1252")
    assert "–" in text
    assert "\ufffd" not in text


@pytest.mark.integration
def test_fixtures_are_exact_excerpts_of_authenticated_sources(repo_root, fixtures_manifest):
    acquisition = load_acquisition_index()
    for item in fixtures_manifest["fixtures"]:
        source_path = RAW_DIR / item["source"]
        assert source_path.exists(), f"missing raw source: {source_path}"
        source_bytes = source_path.read_bytes()
        assert sha256_bytes(source_bytes) == item["source_sha256"]

        accession, file_name = item["source"].split("/", 1)
        record = acquisition.get((accession, file_name))
        if record:
            assert record.get("sha256_actual") == item["source_sha256"]

        source_header, source_rows = read_rows(source_path, item["encoding"])
        fixture_header, fixture_rows = read_rows(
            repo_root / item["fixture"], item["encoding"]
        )
        assert fixture_header == source_header
        assert len(fixture_rows) == item["data_rows"]
        for fixture_row, source_row_number in zip(fixture_rows, item["source_rows"]):
            assert fixture_row == source_rows[source_row_number - 1]


@pytest.mark.integration
def test_fixture_generator_reproduces_the_committed_manifest(repo_root, fixtures_manifest):
    script = repo_root / "scripts" / "build_fixtures.py"
    spec = importlib.util.spec_from_file_location("build_fixtures", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    regenerated = module.build(write=False)
    assert regenerated["fixtures"] == fixtures_manifest["fixtures"]
