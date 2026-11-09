import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES = ROOT / "data" / "fixtures" / "csv"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def fixtures_manifest() -> dict:
    return json.loads((ROOT / "data" / "fixtures" / "fixtures_manifest.json").read_text())


@pytest.fixture
def source_factory():
    """Build a SourceFile from a fixture without inventing provenance."""

    from src.data_pipeline.provenance import source_from_path

    def _make(
        path: Path,
        accession: str = "TEST",
        file_name: str | None = None,
        sheet: str | None = None,
    ):
        return source_from_path(
            accession,
            file_name or path.name,
            path,
            source_url=f"https://psi.nasa.gov/example/{accession}/{path.name}",
            retrieved_at="2026-11-09T00:00:00Z",
            sheet=sheet,
        )

    return _make


def _write_table(directory: Path, name: str, rows: list[dict]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    from src.data_pipeline.schemas import TABLE_SCHEMAS

    table = pa.Table.from_pylist(rows, schema=TABLE_SCHEMAS[name])
    pq.write_table(table, directory / f"{name}.parquet")


def _channel_profile(
    index: int,
    raw_name: str,
    canonical_name: str,
    unit: str,
    *,
    count: int = 3,
    missing: int = 0,
    sentinel: int = 0,
    uncalibrated: bool = False,
    constant: bool = False,
) -> dict:
    return {
        "index": index,
        "raw_name": raw_name,
        "canonical_name": canonical_name,
        "unit": unit,
        "uncalibrated": uncalibrated,
        "note": "",
        "count": count,
        "missing": missing,
        "sentinel": sentinel,
        "nonnumeric": 0,
        "min": 0.0,
        "max": 100.0,
        "constant": constant,
        "excluded_as_time": False,
    }


@pytest.fixture
def synthetic_analytics(tmp_path: Path):
    """A tiny canonical dataset with every structure the query layer needs.

    The rows are synthetic software fixtures. They exist only to exercise
    filtering, bounds, and provenance logic; they are never presented as
    measured values.
    """

    processed = tmp_path / "processed"
    reports = tmp_path / "reports"
    processed.mkdir()
    reports.mkdir()

    provenance = {
        "source_sha256": "a" * 64,
        "retrieved_at": "2026-01-01T00:00:00Z",
        "source_url": "https://psi.nasa.gov/example",
        "parser_version": "test",
    }

    _write_table(
        processed,
        "psi_investigation",
        [
            {
                "accession": "PSI-10",
                "acronym": "ACME/Flame Design",
                "title": "Advanced Combustion via Microgravity Experiments",
                "doi": "10.0000/test",
                "research_area": "Combustion Science",
                "sub_research_area": "Flames of Gaseous Fuels",
                "project_type": "Microgravity Investigation",
                "version": 1,
                "public": True,
                "restricted": False,
                "file_count": 10,
                "removed_file_count": 0,
                "experimental_table_count": 2,
                "experimental_table_bytes": 1000,
                "experimental_table_only_count": 0,
                "archive_status": "available",
                "registered_total_bytes": 10000,
                "mvp_role": "primary",
                "rationale": "Synthetic fixture.",
                "limitations_json": "[\"Synthetic fixture only.\"]",
            },
            {
                "accession": "PSI-100",
                "acronym": "SAFFIRE-III",
                "title": "Spacecraft Fire Experiment III",
                "doi": "10.0000/test2",
                "research_area": "Combustion Science",
                "sub_research_area": "Spacecraft Fire Safety",
                "project_type": "Microgravity Investigation",
                "version": 1,
                "public": True,
                "restricted": False,
                "file_count": 5,
                "removed_file_count": 0,
                "experimental_table_count": 0,
                "experimental_table_bytes": 0,
                "experimental_table_only_count": 0,
                "archive_status": "available",
                "registered_total_bytes": 5000,
                "mvp_role": "primary",
                "rationale": "Synthetic fixture.",
                "limitations_json": "[]",
            },
        ],
    )

    gas_rows = [
        {
            "observation_id": "g1",
            "accession": "PSI-10",
            "source_file": "gas.csv",
            "source_row": 2,
            "flame_type": "Normal",
            "fuel": "C2H4",
            "oxygen_mole_fraction": 0.21,
            "pressure_initial_atm": 1.0,
            "adiabatic_flame_temp_k": 2300.0,
            "quality_flags": "[]",
            **provenance,
        },
        {
            "observation_id": "g2",
            "accession": "PSI-10",
            "source_file": "gas.csv",
            "source_row": 3,
            "flame_type": "Inverse",
            "fuel": "C2H4",
            "oxygen_mole_fraction": 0.15,
            "pressure_initial_atm": 2.0,
            "adiabatic_flame_temp_k": 2100.0,
            "quality_flags": "[{\"flag\": \"ramped_condition\"}]",
            **provenance,
        },
        {
            "observation_id": "g3",
            "accession": "PSI-159",
            "source_file": "gas159.csv",
            "source_row": 2,
            "flame_type": "Normal",
            "fuel": "ethane",
            "oxygen_mole_fraction": 0.23,
            "pressure_approx_bar": 1.0,
            "quality_flags": "[{\"flag\": \"low_oxygen_condition\"}]",
            **provenance,
        },
        {
            "observation_id": "g4",
            "accession": "PSI-159",
            "source_file": "gas159.csv",
            "source_row": 3,
            "flame_type": "Normal",
            "fuel": "propane",
            "oxygen_mole_fraction": 0.18,
            "pressure_approx_bar": 3.0,
            "quality_flags": "[]",
            **provenance,
        },
    ]
    _write_table(processed, "gas_flame_test", gas_rows)

    _write_table(
        processed,
        "material_test",
        [
            {
                "observation_id": "m1",
                "accession": "PSI-25",
                "source_file": "material25.csv",
                "source_row": 2,
                "material": "Nomex",
                "flow_restrictor": "FR-1",
                "initial_o2_pct": 21.0,
                "pressure_atm": 1.0,
                "quality_flags": "[]",
                **provenance,
            },
            {
                "observation_id": "m2",
                "accession": "PSI-26",
                "source_file": "material26.csv",
                "source_row": 2,
                "material": "Nomex",
                "flow_restrictor": "FR-2",
                "o2_pct": 0.22,
                "quality_flags": "[{\"flag\": \"over_range\"}]",
                **provenance,
            },
        ],
    )

    _write_table(
        processed,
        "droplet_test",
        [
            {
                "observation_id": "d1",
                "accession": "PSI-69",
                "source_file": "droplet.csv",
                "source_row": 2,
                "fuel": "Heptane",
                "ambient_pressure_mm_hg": 760.0,
                "burning_rate_mm_as_labeled": 0.5,
                "quality_flags": "[]",
                **provenance,
            },
            {
                "observation_id": "d2",
                "accession": "PSI-69",
                "source_file": "droplet.csv",
                "source_row": 3,
                "fuel": "Decane",
                "ambient_pressure_mm_hg": 500.0,
                "burning_rate_mm_as_labeled": 0.4,
                "quality_flags": "[{\"flag\": \"unit_ambiguity\"}]",
                **provenance,
            },
        ],
    )

    telemetry_profiles = [
        _channel_profile(0, "RelativeSeconds", "relative_time_ms", "ms"),
        _channel_profile(1, "PCM Air Temp", "pcm_air_temp_c", "C"),
        _channel_profile(
            2, "Radiometer1value", "radiometer_1_raw", "not stated", uncalibrated=True
        ),
        _channel_profile(3, "Constant", "constant_chan", "not stated", constant=True),
        _channel_profile(4, "Missing", "missing_chan", "not stated", missing=2),
    ]
    _write_table(
        processed,
        "telemetry_run",
        [
            {
                "run_id": "run-a",
                "accession": "PSI-100",
                "source_file": "telemetry.csv",
                "source_sheet": None,
                "export_kind": "raw_csv",
                "physical_rows": 4,
                "empty_rows": 0,
                "invalid_time_rows": 0,
                "sentinel_rows": 1,
                "valid_rows": 3,
                "time_min_ms": 0.0,
                "time_max_ms": 3000.0,
                "column_count": 5,
                "channel_count": 5,
                "constant_channels_json": "[\"Constant\"]",
                "channel_profiles_json": json.dumps(telemetry_profiles),
                "sha256": "b" * 64,
                "retrieved_at": "2026-01-01T00:00:00Z",
                "source_url": "https://psi.nasa.gov/example/telemetry.csv",
                "parser_version": "test",
                "notes": None,
            },
            {
                "run_id": "run-b",
                "accession": "PSI-100",
                "source_file": "telemetry-b.csv",
                "export_kind": "xlsx_rawdata",
                "physical_rows": 2,
                "valid_rows": 2,
                "time_min_ms": 0.0,
                "time_max_ms": 1000.0,
                "column_count": 2,
                "channel_count": 1,
                "channel_profiles_json": json.dumps([telemetry_profiles[1]]),
                "sha256": "c" * 64,
                "retrieved_at": "2026-01-02T00:00:00Z",
                "source_url": "https://psi.nasa.gov/example/telemetry-b.csv",
                "parser_version": "test",
            },
        ],
    )

    telemetry_points = []
    for index, time_ms in enumerate((0.0, 1000.0, 2000.0)):
        for channel, raw, value, unit, flag in (
            ("pcm_air_temp_c", "PCM Air Temp", 20.0 + index, "C", "ok"),
            ("radiometer_1_raw", "Radiometer1value", 1.0 + index / 10, "not stated", "ok"),
            ("constant_chan", "Constant", 5.0, "not stated", "constant"),
            ("missing_chan", "Missing", None, "not stated", "missing"),
        ):
            telemetry_points.append(
                {
                    "observation_id": f"t{index}-{channel}",
                    "run_id": "run-a",
                    "accession": "PSI-100",
                    "source_file": "telemetry.csv",
                    "source_row": index + 2,
                    "relative_time_ms": time_ms,
                    "relative_time_s": time_ms / 1000,
                    "channel_name_raw": raw,
                    "channel_name_canonical": channel,
                    "raw_value": str(value),
                    "value": value,
                    "unit": unit,
                    "quality_flag": flag,
                    **{k: v for k, v in provenance.items() if k != "parser_version"},
                }
            )
    telemetry_points.append(
        {
            "observation_id": "t3-sentinel",
            "run_id": "run-a",
            "accession": "PSI-100",
            "source_file": "telemetry.csv",
            "source_row": 5,
            "relative_time_ms": 3000.0,
            "relative_time_s": 3.0,
            "channel_name_raw": "Radiometer1value",
            "channel_name_canonical": "radiometer_1_raw",
            "raw_value": "-999",
            "value": None,
            "unit": "not stated",
            "quality_flag": "sentinel",
            **{k: v for k, v in provenance.items() if k != "parser_version"},
        }
    )
    _write_table(processed, "telemetry_point", telemetry_points)

    smoke_profiles = [
        _channel_profile(0, "GasPlumeTemp", "gas_plume_temp_c", "C"),
        _channel_profile(1, "Detector1", "detector_1_v", "V", uncalibrated=True),
        _channel_profile(2, "P-Trak", "ptrak_count", "not stated", sentinel=1),
    ]
    _write_table(
        processed,
        "smoke_run",
        [
            {
                "run_id": "smoke-a",
                "accession": "PSI-101",
                "source_file": "smoke.csv",
                "test_number": 1,
                "sample_number": 2,
                "carousel_number": 3,
                "test_numbers_json": "[1]",
                "sample_numbers_json": "[2]",
                "carousel_numbers_json": "[3]",
                "run_mode_codes_json": "[1]",
                "time_min_unix_s": 1000,
                "time_max_unix_s": 1002,
                "elapsed_test_time_min_s": 0.0,
                "elapsed_test_time_max_s": 4.0,
                "physical_rows": 3,
                "empty_rows": 0,
                "malformed_rows": 0,
                "invalid_time_rows": 0,
                "sentinel_time_rows": 0,
                "valid_rows": 3,
                "column_count": 3,
                "channel_count": 3,
                "channel_profiles_json": json.dumps(smoke_profiles),
                "issues_json": "[]",
                "sha256": "d" * 64,
                "retrieved_at": "2026-01-01T00:00:00Z",
                "source_url": "https://psi.nasa.gov/example/smoke.csv",
                "parser_version": "test",
            }
        ],
    )
    smoke_points = []
    for index, elapsed in enumerate((0.0, 1.0, 2.0)):
        for channel, raw, value, unit, flag in (
            ("gas_plume_temp_c", "GasPlumeTemp", 23.0 + index, "C", "ok"),
            ("detector_1_v", "Detector1", 0.5, "V", "ok"),
        ):
            smoke_points.append(
                {
                    "observation_id": f"s{index}-{channel}",
                    "run_id": "smoke-a",
                    "accession": "PSI-101",
                    "source_file": "smoke.csv",
                    "source_row": index + 2,
                    "unix_time_s": 1000 + index,
                    "elapsed_test_time_s": elapsed,
                    "channel_name_raw": raw,
                    "channel_name_canonical": channel,
                    "raw_value": str(value),
                    "value": value,
                    "unit": unit,
                    "quality_flag": flag,
                    **{k: v for k, v in provenance.items() if k != "parser_version"},
                }
            )
    smoke_points.append(
        {
            "observation_id": "s3-sentinel",
            "run_id": "smoke-a",
            "accession": "PSI-101",
            "source_file": "smoke.csv",
            "source_row": 5,
            "unix_time_s": 1003,
            "elapsed_test_time_s": 3.0,
            "channel_name_raw": "P-Trak",
            "channel_name_canonical": "ptrak_count",
            "raw_value": "-999",
            "value": None,
            "unit": "not stated",
            "quality_flag": "sentinel",
            **{k: v for k, v in provenance.items() if k != "parser_version"},
        }
    )
    smoke_points.append(
        {
            "observation_id": "s3-invalid",
            "run_id": "smoke-a",
            "accession": "PSI-101",
            "source_file": "smoke.csv",
            "source_row": 6,
            "unix_time_s": 1004,
            "elapsed_test_time_s": 4.0,
            "channel_name_raw": "P-Trak",
            "channel_name_canonical": "ptrak_count",
            "raw_value": "indefinite",
            "value": None,
            "unit": "not stated",
            "quality_flag": "invalid_indefinite",
            **{k: v for k, v in provenance.items() if k != "parser_version"},
        }
    )
    _write_table(processed, "smoke_point", smoke_points)

    _write_table(
        processed,
        "experimental_table",
        [
            {
                "table_id": "table-1",
                "accession": "PSI-10",
                "file_name": "gas.csv",
                "file_size_bytes": 1234,
                "sha256": "e" * 64,
                "retrieved_at": "2026-01-01T00:00:00Z",
                "source_url": "https://psi.nasa.gov/example/gas.csv",
                "parser_version": "test",
            }
        ],
    )
    _write_table(
        processed,
        "psi_file",
        [
            {
                "file_id": "file-1",
                "accession": "PSI-100",
                "file_name": "telemetry.csv",
                "file_size_bytes": 5678,
                "sha256": None,
                "retrieved_at": "2026-01-01T00:00:00Z",
                "access_status": "available",
                "source_url": "https://psi.nasa.gov/example/telemetry.csv",
            }
        ],
    )
    _write_table(
        processed,
        "source_row",
        [
            {
                "source_row_id": "row-1",
                "table_id": "table-1",
                "accession": "PSI-10",
                "source_file": "gas.csv",
                "source_row": 2,
                "source_sha256": "e" * 64,
                "retrieved_at": "2026-01-01T00:00:00Z",
                "source_url": "https://psi.nasa.gov/example/gas.csv",
                "parser_version": "test",
            }
        ],
    )
    _write_table(
        processed,
        "experimental_table_cell",
        [
            {
                "cell_id": "cell-1",
                "table_id": "table-1",
                "accession": "PSI-10",
                "source_file": "gas.csv",
                "source_row": 2,
                "source_column_index": 1,
                "source_column_name": "Fuel",
                "raw_value": "C2H4",
                "value_flag": "ok",
                "source_sha256": "e" * 64,
                "retrieved_at": "2026-01-01T00:00:00Z",
                "source_url": "https://psi.nasa.gov/example/gas.csv",
                "parser_version": "test",
            }
        ],
    )
    _write_table(
        processed,
        "smoke_test_log",
        [
            {
                "log_id": "log-1",
                "accession": "PSI-101",
                "source_file": "smoke.csv",
                "source_sheet": None,
                "source_row": 2,
                "event_type": "test_start",
                "source_sha256": "d" * 64,
                "retrieved_at": "2026-01-01T00:00:00Z",
                "source_url": "https://psi.nasa.gov/example/smoke.csv",
                "parser_version": "test",
            }
        ],
    )

    (processed / "dataset_manifest.json").write_text(
        json.dumps({"dataset_version": "synthetic-version", "generated_at": "2026-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    quality_report = {
        "generated_at": "2026-01-01T00:00:00Z",
        "pipeline_version": "test",
        "status": "ok",
        "summary": {"tables": 13, "total_rows": 20, "issues": 2, "errors": 0, "warnings": 2},
        "tables": {
            "gas_flame_test": {
                "table_name": "gas_flame_test",
                "path": "data/processed/gas_flame_test.parquet",
                "rows": 4,
                "columns": 45,
                "primary_key": "observation_id",
                "column_missingness": [
                    {
                        "name": "fuel",
                        "type": "string",
                        "null_count": 1,
                        "null_rate": 0.25,
                        "empty_string_count": 0,
                    }
                ],
            }
        },
        "point_tables": {"gas_flame_test": {"points": 4, "runs": 4}},
        "flag_tables": {"gas_flame_test": {"ramped_condition": 1}},
        "provenance": {"gas_flame_test": {"sources": 1}},
        "issues": [
            {
                "code": "unit_ambiguity",
                "message": "Synthetic PSI-26 oxygen unit ambiguity.",
                "details": {"accession": "PSI-26"},
            },
            {
                "code": "sentinel_dash",
                "message": "Synthetic PSI-10 sentinel.",
                "details": {"accession": "PSI-10"},
            },
        ],
    }
    (reports / "dataset_quality_report.json").write_text(
        json.dumps(quality_report), encoding="utf-8"
    )

    from src.analytics.db import AnalyticsDatabase

    database = AnalyticsDatabase(
        processed_dir=processed,
        reports_dir=reports,
        timeout_seconds=5,
    )
    return {
        "db": database,
        "processed": processed,
        "reports": reports,
        "quality_report": quality_report,
    }
