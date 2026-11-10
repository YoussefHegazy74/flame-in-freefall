"""Canonical metadata builders and dataset-version tests."""

from __future__ import annotations

import copy
import json

import pytest

from src.data_pipeline.canonical import (
    DATASET_MANIFEST_JSON,
    CanonicalBuildError,
    _iso_date,
    _require,
    _source_digest,
    build_experimental_table,
    build_psi_file,
    build_psi_investigation,
)
from src.data_pipeline.config import ET_SCHEMAS_JSON, PROCESSING_REPORT_JSON, REGISTRY_JSON
from src.data_pipeline.manifest import build_manifest
from src.data_pipeline.provenance import load_acquisition_index


def test_psi_investigation_builder_covers_the_registry():
    records = build_psi_investigation()
    registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    assert len(records) == 24
    assert len(records) == len(registry["investigations"])
    assert {record["accession"] for record in records} == {
        item["accession"] for item in registry["investigations"]
    }
    for record in records:
        assert record["title"]
        assert record["research_area"]
        assert isinstance(json.loads(record["limitations_json"]), list)
        if record["start_date"] is not None:
            assert len(record["start_date"]) == 10


def test_psi_file_builder_marks_selected_and_unselected_files():
    records = build_psi_file()
    assert len(records) == 16_354
    assert len({record["file_id"] for record in records}) == 16_354
    acquisition = load_acquisition_index()
    inventory_keys = {(record["accession"], record["file_name"]) for record in records}
    overlap = set(acquisition) & inventory_keys
    selected = [record for record in records if record["access_status"] != "not_selected"]
    assert len(selected) == len(overlap) == 58
    assert {(record["accession"], record["file_name"]) for record in selected} == overlap
    assert all(record["sha256"] for record in selected)
    assert all(record["retrieved_at"] for record in selected)
    assert all(record["source_url"] for record in selected)
    assert any(record["access_status"] == "not_selected" for record in records)

    # Fourteen selected experimental tables are not in the current inventory.
    # They remain covered by the experimental_table provenance table instead of
    # being silently forced into psi_file with invented inventory metadata.
    acquisition_only = set(acquisition) - inventory_keys
    assert len(acquisition_only) == 14
    experimental_tables = {
        (record["accession"], record["file_name"])
        for record in build_experimental_table()
    }
    assert acquisition_only <= experimental_tables


def test_experimental_table_builder_matches_the_committed_schema_registry():
    records = build_experimental_table()
    schemas = json.loads(ET_SCHEMAS_JSON.read_text(encoding="utf-8"))["tables"]
    assert len(records) == 22
    assert {record["table_id"] for record in records} == set(schemas)
    for record in records:
        schema = schemas[record["table_id"]]
        assert record["sha256"] == schema["sha256"]
        assert record["data_rows"] == schema["data_rows"]
        assert record["physical_rows"] == schema["physical_rows"]
        assert record["columns"] == schema["columns"]
        assert record["parser_version"]


def test_iso_date_normalizes_source_date_formats():
    assert _iso_date("01-14-1999") == "1999-01-14"
    assert _iso_date("2021-05-06") == "2021-05-06"
    assert _iso_date("5/6/2021") == "2021-05-06"
    assert _iso_date("") is None
    assert _iso_date(None) is None
    assert _iso_date("not a date") is None


def test_source_digest_is_deterministic_and_changes_with_acquisition_checksums():
    manifest = build_manifest()
    acquisition = load_acquisition_index()
    digest, expected_bytes = _source_digest(manifest, acquisition)
    assert len(digest) == 64
    int(digest, 16)
    assert expected_bytes == 56_238_344
    assert _source_digest(manifest, acquisition) == (digest, expected_bytes)

    tampered = copy.deepcopy(acquisition)
    key = next(iter(tampered))
    tampered[key] = dict(tampered[key])
    tampered[key]["sha256_actual"] = "0" * 64
    changed, _ = _source_digest(manifest, tampered)
    assert changed != digest


def test_require_fails_closed_for_a_missing_interim_table(tmp_path):
    missing = tmp_path / "missing.parquet"
    with pytest.raises(CanonicalBuildError, match="required interim table is missing"):
        _require(missing)


@pytest.mark.integration
def test_dataset_manifest_and_processing_report_are_consistent():
    dataset = json.loads(DATASET_MANIFEST_JSON.read_text(encoding="utf-8"))
    report = json.loads(PROCESSING_REPORT_JSON.read_text(encoding="utf-8"))
    assert dataset["schema_version"] == "1.0.0"
    assert len(dataset["dataset_version"]) == 64
    assert dataset["dataset_version"] == report["dataset_version"]
    assert dataset["source_file_count"] == 72
    assert dataset["source_expected_bytes"] == 56_238_344
    assert len(dataset["source_checksums"]) == 72
    assert dataset["tables"] == report["tables"]
    assert report["table_count"] == 13
    assert report["total_rows"] == 8_058_206
    expected_rows = {
        "psi_investigation": 24,
        "psi_file": 16_354,
        "experimental_table": 22,
        "gas_flame_test": 660,
        "telemetry_run": 5,
        "telemetry_point": 1_762_436,
        "smoke_run": 44,
        "smoke_point": 6_251_427,
        "smoke_test_log": 119,
        "material_test": 259,
        "droplet_test": 274,
        "experimental_table_cell": 24_573,
        "source_row": 2_009,
    }
    assert {name: table["rows"] for name, table in dataset["tables"].items()} == expected_rows
    for table in dataset["tables"].values():
        assert table["bytes"] > 0
        assert table["path"].startswith("data/processed/")
