"""Integration tests over the authenticated raw files and built tables.

These tests skip when the non-committed raw or processed data is absent.
They are marked ``integration`` so the unit suite can run independently.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from src.data_pipeline.config import (
    PROCESSED_DIR,
    RAW_DIR,
    ROOT,
)
from src.data_pipeline.parsers.droplet import parse_droplet
from src.data_pipeline.parsers.gas_flame import SPECS, parse_gas_flame
from src.data_pipeline.parsers.material import parse_psi25, parse_psi26
from src.data_pipeline.parsers.smoke import scan_smoke
from src.data_pipeline.parsers.summary_table import parse_summary_tables
from src.data_pipeline.parsers.telemetry import TELEMETRY_SPECS, scan_telemetry
from src.data_pipeline.parsers.test_log import parse_test_log
from src.data_pipeline.provenance import load_acquisition_index, source_from_path
from src.data_pipeline.validation import validate_canonical

pytestmark = pytest.mark.integration


def require_raw(*relative_paths: str) -> None:
    for relative in relative_paths:
        if not (RAW_DIR / relative).exists():
            pytest.skip(f"raw file is not present: {relative}")


def source_for(accession: str, file_name: str):
    path = RAW_DIR / accession / file_name
    if not path.exists():
        pytest.skip(f"raw file is not present: {path}")
    record = load_acquisition_index().get((accession, file_name), {})
    return source_from_path(
        accession,
        file_name,
        path,
        sha256=record.get("sha256_actual"),
        retrieved_at=record.get("retrieved_at"),
        source_url=record.get("source_url", ""),
    )


def test_full_gas_flame_tables_have_the_expected_rows():
    expected = {
        ("PSI-10", "PSI-10_Experimental table_Flame Design_Normal Flame.csv"): (207, 207),
        ("PSI-10", "PSI-10_Experimental table_Flame Design_Inverse Flame.csv"): (120, 120),
        ("PSI-159", "PSI-159_Experimental table_CFI-G_Normal Flames.csv"): (179, 179),
        ("PSI-159", "PSI-159_Experimental table_CFI-G_Inverse Flames.csv"): (1015, 154),
    }
    for (accession, file_name), (physical, data) in expected.items():
        source = source_for(accession, file_name)
        result = parse_gas_flame(source, SPECS[(accession, file_name)])
        assert (result.physical_rows, result.data_rows) == (physical, data)
        assert len(result.records) == data


def test_full_smoke_run_scan_preserves_the_98_column_header():
    source = source_for("PSI-101", "PSI-101_Raw Data_HKPData_gmt250_1.csv")
    scan = scan_smoke(source)
    assert len(scan.header) == 98
    assert scan.physical_rows > 0
    assert scan.valid_rows > 0
    assert scan.run_id.startswith("PSI-101::")


def test_full_telemetry_raw_scan_counts_rows_and_time_range():
    source = source_for("PSI-100", "PSI-100_Raw Data_Raw telemetry file.csv")
    spec = next(spec for spec in TELEMETRY_SPECS if spec.export_kind == "raw_csv")
    scan = scan_telemetry(spec, source)
    assert (scan.physical_rows, scan.valid_rows) == (3972, 3966)
    assert scan.sentinel_rows == 6
    assert scan.time_min_ms == 0
    assert scan.time_max_ms == 9_573_373


def test_full_material_workbooks_have_the_expected_rows_and_record_types():
    psi25 = parse_psi25(
        source_for("PSI-25", "PSI-25_Science Documents_BASS-II_Test.Matrices.xlsx")
    )
    assert len(psi25.records) == 129
    assert psi25.metadata["total_rows"] == 129

    psi26 = parse_psi26(
        source_for("PSI-26", "PSI-26_Science Documents_As Run_Test Matrix.xlsx")
    )
    assert len(psi26.records) == 130
    assert psi26.metadata["test_rows"] == 122
    assert psi26.metadata["note_rows"] == 8
    assert all("o2_pct" in record for record in psi26.records)


def test_full_droplet_table_and_legacy_test_log():
    droplet = parse_droplet(
        source_for("PSI-69", "PSI-69_Experimental table_FLEX.csv")
    )
    assert (droplet.physical_rows, droplet.data_rows) == (274, 274)
    assert len(droplet.records) == 274
    assert droplet.metadata["encoding_fallback"] is True

    test_log = parse_test_log(
        source_for("PSI-102", "PSI-102_Analyzed Data_Run 1 GMT252 testlog.xls")
    )
    assert (test_log.physical_rows, test_log.data_rows) == (119, 119)
    assert len(test_log.records) == 119
    assert test_log.metadata["header_present"] is False


def test_full_summary_tables_preserve_every_nonempty_cell():
    from src.data_pipeline.manifest import read_manifest

    manifest = read_manifest()
    sources = {}
    for entry in manifest["files"]:
        if entry["kind"] != "experimental_table":
            continue
        sources[(entry["accession"], entry["file_name"])] = source_for(
            entry["accession"], entry["file_name"]
        )
    result = parse_summary_tables(sources)
    assert result.table_count == 22
    assert result.cell_count == 24_573
    assert result.source_row_count == 2_009


def test_full_canonical_validation_passes():
    if not PROCESSED_DIR.exists() or not any(PROCESSED_DIR.glob("*.parquet")):
        pytest.skip("processed tables are not built")
    report = validate_canonical()
    assert report["status"] == "pass"
    assert report["summary"]["failed"] == 0


@pytest.mark.parametrize(
    "script",
    [
        "scripts/build_download_manifest.py",
        "scripts/build_et_schemas.py",
        "scripts/build_fixtures.py",
    ],
)
def test_registry_and_fixture_checks_are_reproducible(script):
    result = subprocess.run(
        [sys.executable, str(ROOT / script), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr + result.stdout
