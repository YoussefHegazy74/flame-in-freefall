"""Manifest selection, checksum, and safety-invariant tests."""

from __future__ import annotations

import copy
import csv
import json

import pytest

from src.data_pipeline.config import (
    ANNOTATIONS_JSON,
    DOWNLOAD_MANIFEST_CSV,
    DOWNLOAD_MANIFEST_JSON,
)
from src.data_pipeline.manifest import (
    CSV_COLUMNS,
    ManifestError,
    build_manifest,
    download_url,
    read_manifest,
    validate_manifest,
    write_manifest_csv,
)


@pytest.fixture(scope="module")
def manifest() -> dict:
    return build_manifest()


def test_selection_totals_and_required_counts(manifest):
    assert manifest["totals"]["selected_files"] == 72
    assert manifest["totals"]["selected_bytes"] == 56_238_344
    assert manifest["totals"]["experimental_tables"] == 22
    assert manifest["totals"]["primary_files"] + manifest["totals"]["supporting_files"] == 72
    assert len(manifest["files"]) == 72
    assert len(manifest["known_unavailable"]) == 2


def test_required_dataset_kinds(manifest):
    by_kind: dict[str, list[dict]] = {}
    for item in manifest["files"]:
        by_kind.setdefault(item["kind"], []).append(item)
    assert len(by_kind["experimental_table"]) == 22
    assert len(by_kind["smoke_telemetry_csv"]) == 44
    assert len(by_kind["telemetry_csv"]) == 2
    assert len(by_kind["telemetry_xlsx"]) == 1
    assert len(by_kind["material_workbook"]) == 2
    assert len(by_kind["test_log_xls"]) == 1
    assert all(
        item["file_name"].startswith("PSI-101_Raw Data_HKPData_")
        for item in by_kind["smoke_telemetry_csv"]
    )
    assert all(
        item["file_name"].endswith(".csv")
        for item in by_kind["smoke_telemetry_csv"]
    )


def test_file_ids_and_pairs_are_unique(manifest):
    file_ids = [item["file_id"] for item in manifest["files"]]
    pairs = [(item["accession"], item["file_name"]) for item in manifest["files"]]
    assert len(file_ids) == len(set(file_ids))
    assert len(pairs) == len(set(pairs))
    assert all(item["file_id"] == f"{item['accession']}::{item['file_name']}" for item in manifest["files"])


def test_every_file_has_a_verified_download_url(manifest):
    for item in manifest["files"]:
        assert item["source_url"].startswith(
            f"https://psi.nasa.gov/geode-py/ws/studies/{item['accession']}/download?file="
        )
        assert item["source_url"] == download_url(item["accession"], item["file_name"])


def test_experimental_table_checksums_match_annotations(manifest):
    annotations = json.loads(ANNOTATIONS_JSON.read_text(encoding="utf-8"))
    tables = [item for item in manifest["files"] if item["kind"] == "experimental_table"]
    assert len(tables) == 22
    for item in tables:
        expected = annotations[item["accession"]]["table_stats"][item["file_name"]]["sha256"]
        assert item["sha256_expected"] == expected
        assert len(item["sha256_expected"]) == 64
        int(item["sha256_expected"], 16)


def test_known_unavailable_are_separate_and_documented(manifest):
    for item in manifest["known_unavailable"]:
        assert item["expected_status"] == 404
        assert item["reason"]
        assert not any(
            selected["file_name"] == item["file_name"]
            for selected in manifest["files"]
        )


def test_committed_manifest_matches_fresh_build(manifest):
    committed = json.loads(DOWNLOAD_MANIFEST_JSON.read_text(encoding="utf-8"))
    assert committed == manifest
    assert read_manifest() == manifest


def test_manifest_csv_has_every_file_and_acquisition_columns(manifest, tmp_path):
    path = tmp_path / "download_manifest.csv"
    write_manifest_csv(manifest, path, status="pending")
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 72
    assert list(rows[0]) == CSV_COLUMNS
    assert all(row["status"] == "pending" for row in rows)
    assert all(row["sha256_actual"] == "" for row in rows)
    assert {row["file_id"] for row in rows} == {item["file_id"] for item in manifest["files"]}


def test_download_url_percent_encodes_the_exact_file_name():
    url = download_url("PSI-10", "a b&c+d.csv")
    assert url.endswith("?file=a%20b%26c%2Bd.csv")
    assert "PSI-10" in url


def test_validate_manifest_rejects_duplicate_file_id(manifest):
    tampered = copy.deepcopy(manifest)
    tampered["files"][1]["file_id"] = tampered["files"][0]["file_id"]
    with pytest.raises(ManifestError, match="duplicate file_id"):
        validate_manifest(tampered)


def test_validate_manifest_rejects_duplicate_accession_file_pair(manifest):
    tampered = copy.deepcopy(manifest)
    tampered["files"][1]["accession"] = tampered["files"][0]["accession"]
    tampered["files"][1]["file_name"] = tampered["files"][0]["file_name"]
    tampered["files"][1]["file_id"] = "PSI-10::duplicate-pair"
    tampered["files"][1]["source_url"] = tampered["files"][0]["source_url"]
    with pytest.raises(ManifestError, match="duplicate accession/file pair"):
        validate_manifest(tampered)


def test_validate_manifest_rejects_wrong_totals(manifest):
    tampered = copy.deepcopy(manifest)
    tampered["totals"]["selected_files"] += 1
    with pytest.raises(ManifestError, match="totals.selected_files"):
        validate_manifest(tampered)

    tampered = copy.deepcopy(manifest)
    tampered["totals"]["selected_bytes"] += 1
    with pytest.raises(ManifestError, match="totals.selected_bytes"):
        validate_manifest(tampered)


def test_validate_manifest_rejects_unverified_url(manifest):
    tampered = copy.deepcopy(manifest)
    tampered["files"][0]["source_url"] = "https://example.com/file.csv"
    with pytest.raises(ManifestError, match="verified PSI download endpoint"):
        validate_manifest(tampered)


def test_validate_manifest_rejects_bad_checksum(manifest):
    tampered = copy.deepcopy(manifest)
    tampered["files"][0]["sha256_expected"] = "not-a-checksum"
    with pytest.raises(ManifestError, match="sha256_expected"):
        validate_manifest(tampered)


def test_validate_manifest_rejects_et_checksum_drift(manifest):
    tampered = copy.deepcopy(manifest)
    table = next(item for item in tampered["files"] if item["kind"] == "experimental_table")
    table["sha256_expected"] = "0" * 64
    with pytest.raises(ManifestError, match="annotations.json"):
        validate_manifest(tampered)


def test_validate_manifest_rejects_unknown_accession(manifest):
    tampered = copy.deepcopy(manifest)
    tampered["files"][0]["accession"] = "PSI-999"
    tampered["files"][0]["file_id"] = "PSI-999::x"
    with pytest.raises(ManifestError, match="unknown accession"):
        validate_manifest(tampered)


def test_validate_manifest_rejects_unsafe_limits(manifest):
    tampered = copy.deepcopy(manifest)
    tampered["limits"]["max_files"] = 1
    with pytest.raises(ManifestError, match="max_files"):
        validate_manifest(tampered)

    tampered = copy.deepcopy(manifest)
    tampered["limits"]["max_total_bytes"] = 1
    with pytest.raises(ManifestError, match="max_total_bytes"):
        validate_manifest(tampered)


def test_validate_manifest_rejects_known_unavailable_wrong_status(manifest):
    tampered = copy.deepcopy(manifest)
    tampered["known_unavailable"][0]["expected_status"] = 200
    with pytest.raises(ManifestError, match="expected_status must be 404"):
        validate_manifest(tampered)
