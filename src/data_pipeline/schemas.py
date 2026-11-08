"""Canonical table schemas and Parquet I/O.

Every canonical table has an explicit Arrow schema. Records are normalized to
the schema before writing so that nullable fields from different source tables
are filled with nulls rather than silently omitted. JSON-bearing columns are
stored as strings; the JSON text is part of the contract and is validated by
the report stage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import pyarrow as pa
import pyarrow.parquet as pq


def _f(name: str, kind: pa.DataType = pa.string()) -> pa.field:
    return pa.field(name, kind, nullable=True)


PROVENANCE = [
    _f("source_file"),
    _f("source_sheet"),
    _f("source_row", pa.int64()),
    _f("source_sha256"),
    _f("retrieved_at"),
    _f("source_url"),
    _f("parser_version"),
]


TABLE_SCHEMAS: dict[str, pa.Schema] = {
    "psi_investigation": pa.schema(
        [
            _f("accession"),
            _f("acronym"),
            _f("title"),
            _f("doi"),
            _f("research_area"),
            _f("sub_research_area"),
            _f("project_type"),
            _f("start_date"),
            _f("end_date"),
            _f("version", pa.int64()),
            _f("public", pa.bool_()),
            _f("restricted", pa.bool_()),
            _f("file_count", pa.int64()),
            _f("removed_file_count", pa.int64()),
            _f("experimental_table_count", pa.int64()),
            _f("experimental_table_bytes", pa.int64()),
            _f("experimental_table_only_count", pa.int64()),
            _f("archive_status"),
            _f("registered_total_bytes", pa.int64()),
            _f("mvp_role"),
            _f("rationale"),
            _f("limitations_json"),
        ]
    ),
    "psi_file": pa.schema(
        [
            _f("file_id"),
            _f("accession"),
            _f("file_name"),
            _f("file_size_bytes", pa.int64()),
            _f("format"),
            _f("category"),
            _f("restricted", pa.bool_()),
            _f("visible", pa.bool_()),
            _f("version", pa.int64()),
            _f("sha256"),
            _f("retrieved_at"),
            _f("access_status"),
            _f("source_url"),
        ]
    ),
    "experimental_table": pa.schema(
        [
            _f("table_id"),
            _f("accession"),
            _f("file_name"),
            _f("file_size_bytes", pa.int64()),
            _f("in_added", pa.bool_()),
            _f("restricted", pa.bool_()),
            _f("data_rows", pa.int64()),
            _f("physical_rows", pa.int64()),
            _f("columns", pa.int64()),
            _f("sha256"),
            _f("notes"),
            _f("encoding"),
            _f("encoding_fallback", pa.bool_()),
            _f("retrieved_at"),
            _f("source_url"),
            _f("parser_version"),
        ]
    ),
    "gas_flame_test": pa.schema(
        [
            _f("observation_id"),
            _f("accession"),
            _f("table_id"),
            *PROVENANCE,
            _f("flame_type"),
            _f("day"),
            _f("fuel"),
            _f("test_code"),
            _f("fuel_mole_fraction", pa.float64()),
            _f("fuel_mass_flow_mg_s", pa.float64()),
            _f("diluent_mass_flow_mg_s", pa.float64()),
            _f("total_mass_flow_mg_s", pa.float64()),
            _f("oxygen_mole_fraction", pa.float64()),
            _f("oxygen_mole_fraction_initial", pa.float64()),
            _f("oxygen_mole_fraction_final", pa.float64()),
            _f("oxygen_mole_fraction_before", pa.float64()),
            _f("oxygen_mole_fraction_after", pa.float64()),
            _f("pressure_initial_atm", pa.float64()),
            _f("pressure_final_atm", pa.float64()),
            _f("pressure_mean_atm", pa.float64()),
            _f("pressure_approx_bar", pa.float64()),
            _f("oxidizer_mass_flow_mg_s", pa.float64()),
            _f("fuel_mole_fraction_initial", pa.float64()),
            _f("fuel_mole_fraction_final", pa.float64()),
            _f("fuel_mole_fraction_before", pa.float64()),
            _f("fuel_mole_fraction_after", pa.float64()),
            _f("fuel_burn_rate_mg_s", pa.float64()),
            _f("stoich_mixture_fraction", pa.float64()),
            _f("adiabatic_flame_temp_k", pa.float64()),
            _f("cool_flame_flag"),
            _f("tfp_flag"),
            _f("hot_ignition"),
            _f("burn_time_s", pa.float64()),
            _f("extinction_mode"),
            _f("peak_burner_temp_c", pa.float64()),
            _f("peak_burner_temp_k", pa.float64()),
            _f("color"),
            _f("comments"),
            _f("quality_flags"),
            _f("raw_row_json"),
        ]
    ),
    "telemetry_run": pa.schema(
        [
            _f("run_id"),
            _f("accession"),
            _f("source_file"),
            _f("source_sheet"),
            _f("export_kind"),
            _f("physical_rows", pa.int64()),
            _f("empty_rows", pa.int64()),
            _f("invalid_time_rows", pa.int64()),
            _f("sentinel_rows", pa.int64()),
            _f("valid_rows", pa.int64()),
            _f("time_min_ms", pa.float64()),
            _f("time_max_ms", pa.float64()),
            _f("column_count", pa.int64()),
            _f("channel_count", pa.int64()),
            _f("constant_channels_json"),
            _f("channel_profiles_json"),
            _f("sha256"),
            _f("retrieved_at"),
            _f("source_url"),
            _f("parser_version"),
            _f("notes"),
        ]
    ),
    "telemetry_point": pa.schema(
        [
            _f("observation_id"),
            _f("run_id"),
            _f("accession"),
            _f("source_file"),
            _f("source_sheet"),
            _f("source_row", pa.int64()),
            _f("relative_time_ms", pa.float64()),
            _f("relative_time_s", pa.float64()),
            _f("channel_name_raw"),
            _f("channel_name_canonical"),
            _f("raw_value"),
            _f("value", pa.float64()),
            _f("unit"),
            _f("quality_flag"),
            _f("source_sha256"),
            _f("retrieved_at"),
            _f("source_url"),
        ]
    ),
    "smoke_run": pa.schema(
        [
            _f("run_id"),
            _f("accession"),
            _f("source_file"),
            _f("test_number", pa.int64()),
            _f("sample_number", pa.int64()),
            _f("carousel_number", pa.int64()),
            _f("test_numbers_json"),
            _f("sample_numbers_json"),
            _f("carousel_numbers_json"),
            _f("run_mode_codes_json"),
            _f("time_min_unix_s", pa.int64()),
            _f("time_max_unix_s", pa.int64()),
            _f("elapsed_test_time_min_s", pa.float64()),
            _f("elapsed_test_time_max_s", pa.float64()),
            _f("physical_rows", pa.int64()),
            _f("empty_rows", pa.int64()),
            _f("malformed_rows", pa.int64()),
            _f("invalid_time_rows", pa.int64()),
            _f("sentinel_time_rows", pa.int64()),
            _f("valid_rows", pa.int64()),
            _f("column_count", pa.int64()),
            _f("channel_count", pa.int64()),
            _f("constant_channels_json"),
            _f("sentinel_channels_json"),
            _f("channel_profiles_json"),
            _f("issues_json"),
            _f("sha256"),
            _f("retrieved_at"),
            _f("source_url"),
            _f("parser_version"),
            _f("notes"),
        ]
    ),
    "smoke_point": pa.schema(
        [
            _f("observation_id"),
            _f("run_id"),
            _f("accession"),
            _f("source_file"),
            _f("source_row", pa.int64()),
            _f("unix_time_s", pa.int64()),
            _f("elapsed_test_time_s", pa.float64()),
            _f("source_time_string"),
            _f("channel_name_raw"),
            _f("channel_name_canonical"),
            _f("raw_value"),
            _f("value", pa.float64()),
            _f("unit"),
            _f("quality_flag"),
            _f("source_sha256"),
            _f("retrieved_at"),
            _f("source_url"),
        ]
    ),
    "smoke_test_log": pa.schema(
        [
            _f("log_id"),
            _f("accession"),
            _f("source_file"),
            _f("source_sheet"),
            _f("source_row", pa.int64()),
            _f("source_timestamp_string"),
            _f("event_type"),
            _f("event_detail"),
            _f("raw_row_json"),
            _f("source_sha256"),
            _f("retrieved_at"),
            _f("source_url"),
            _f("parser_version"),
        ]
    ),
    "material_test": pa.schema(
        [
            _f("observation_id"),
            _f("accession"),
            _f("table_id"),
            *PROVENANCE,
            _f("record_type"),
            _f("test_date"),
            _f("gmt_day"),
            _f("as_run_test_no"),
            _f("test_no"),
            _f("sample_no"),
            _f("material"),
            _f("flow_restrictor"),
            _f("fan_display"),
            _f("air_display"),
            _f("radiometer_gain"),
            _f("total_frames"),
            _f("initial_o2_pct", pa.float64()),
            _f("final_o2_pct", pa.float64()),
            _f("o2_pct", pa.float64()),
            _f("initial_co2_pct", pa.float64()),
            _f("final_co2_pct", pa.float64()),
            _f("initial_co_ppm", pa.float64()),
            _f("final_co_ppm", pa.float64()),
            _f("pressure_atm", pa.float64()),
            _f("co2_mm_hg", pa.float64()),
            _f("observations"),
            _f("context_json"),
            _f("quality_flags"),
            _f("raw_row_json"),
        ]
    ),
    "droplet_test": pa.schema(
        [
            _f("observation_id"),
            _f("accession"),
            _f("table_id"),
            *PROVENANCE,
            _f("flex_test_number", pa.int64()),
            _f("test_date"),
            _f("flex_identifier"),
            _f("test_gmt"),
            _f("fuel"),
            _f("ambient_pressure_mm_hg", pa.float64()),
            _f("o2_initial_mole_fraction", pa.float64()),
            _f("n2_initial_mole_fraction", pa.float64()),
            _f("co_initial_mole_fraction", pa.float64()),
            _f("he_initial_mole_fraction", pa.float64()),
            _f("droplet_initial_diameter_mm", pa.float64()),
            _f("visible_flame_extinction_diameter_mm", pa.float64()),
            _f("burning_rate_mm_as_labeled", pa.float64()),
            _f("burn_time_s", pa.float64()),
            _f("test_end"),
            _f("quality_flags"),
            _f("raw_row_json"),
        ]
    ),
    "experimental_table_cell": pa.schema(
        [
            _f("cell_id"),
            _f("table_id"),
            _f("accession"),
            _f("source_file"),
            _f("source_row", pa.int64()),
            _f("source_column_index", pa.int64()),
            _f("source_column_name"),
            _f("raw_value"),
            _f("numeric_value", pa.float64()),
            _f("value_flag"),
            _f("source_sha256"),
            _f("retrieved_at"),
            _f("source_url"),
            _f("parser_version"),
        ]
    ),
    "source_row": pa.schema(
        [
            _f("source_row_id"),
            _f("table_id"),
            _f("accession"),
            _f("source_file"),
            _f("source_row", pa.int64()),
            _f("nonempty_cell_count", pa.int64()),
            _f("numeric_cell_count", pa.int64()),
            _f("raw_row_json"),
            _f("source_sha256"),
            _f("retrieved_at"),
            _f("source_url"),
            _f("parser_version"),
        ]
    ),
}

PRIMARY_KEYS: dict[str, str] = {
    "psi_investigation": "accession",
    "psi_file": "file_id",
    "experimental_table": "table_id",
    "gas_flame_test": "observation_id",
    "telemetry_run": "run_id",
    "telemetry_point": "observation_id",
    "smoke_run": "run_id",
    "smoke_point": "observation_id",
    "smoke_test_log": "log_id",
    "material_test": "observation_id",
    "droplet_test": "observation_id",
    "experimental_table_cell": "cell_id",
    "source_row": "source_row_id",
}

TABLE_DESCRIPTIONS: dict[str, str] = {
    "psi_investigation": "One row per PSI investigation, from the committed registry and annotations.",
    "psi_file": "One row per current public PSI file in the added inventory, with selected-file acquisition status.",
    "experimental_table": "One row per public experimental summary table, with exact checksum and row counts.",
    "gas_flame_test": "One row per PSI-10 or PSI-159 gas-flame test summary row.",
    "telemetry_run": "One row per SAFFIRE-III telemetry export or workbook sheet; exports are never concatenated.",
    "telemetry_point": "Tidy long telemetry points with exact channel names, units, and quality flags.",
    "smoke_run": "One row per SAME-R HKP telemetry run.",
    "smoke_point": "Tidy long SAME-R points with exact channel names, units, and quality flags.",
    "smoke_test_log": "One row per legacy SAME test-log event.",
    "material_test": "One row per BASS-II or BASS as-run test-matrix row; context only.",
    "droplet_test": "One row per FLEX droplet-combustion test.",
    "experimental_table_cell": "One row per non-empty cell in the 22 public experimental summary tables.",
    "source_row": "One row per non-empty row in the 22 public experimental summary tables, preserving the raw row.",
}


@dataclass(frozen=True)
class TableWriteResult:
    table_name: str
    path: str
    rows: int
    bytes: int


def normalize_records(
    records: Iterable[dict[str, Any]], schema: pa.Schema
) -> list[dict[str, Any]]:
    """Fill missing schema fields with nulls and drop undeclared fields."""

    names = schema.names
    normalized: list[dict[str, Any]] = []
    for record in records:
        normalized.append({name: record.get(name) for name in names})
    return normalized


def write_parquet(
    records: Sequence[dict[str, Any]],
    table_name: str,
    path: Path,
    *,
    schema: pa.Schema | None = None,
    row_group_size: int = 100_000,
) -> TableWriteResult:
    schema = schema or TABLE_SCHEMAS[table_name]
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_records(records, schema)
    table = pa.Table.from_pylist(normalized, schema=schema)
    pq.write_table(table, path, compression="zstd", row_group_size=row_group_size)
    return TableWriteResult(
        table_name=table_name,
        path=str(path),
        rows=table.num_rows,
        bytes=path.stat().st_size,
    )


def write_parquet_batches(
    batches: Iterable[Sequence[dict[str, Any]]],
    table_name: str,
    path: Path,
    *,
    schema: pa.Schema | None = None,
    row_group_size: int = 100_000,
) -> TableWriteResult:
    schema = schema or TABLE_SCHEMAS[table_name]
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    writer = pq.ParquetWriter(path, schema, compression="zstd")
    try:
        for batch in batches:
            if not batch:
                continue
            normalized = normalize_records(batch, schema)
            table = pa.Table.from_pylist(normalized, schema=schema)
            writer.write_table(table, row_group_size=row_group_size)
            rows += table.num_rows
    finally:
        writer.close()
    return TableWriteResult(
        table_name=table_name,
        path=str(path),
        rows=rows,
        bytes=path.stat().st_size,
    )


def concat_parquet(
    inputs: Sequence[Path],
    table_name: str,
    path: Path,
    *,
    schema: pa.Schema | None = None,
    row_group_size: int = 100_000,
) -> TableWriteResult:
    """Concatenate Parquet files without loading all rows into Python memory."""

    schema = schema or TABLE_SCHEMAS[table_name]
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    writer = pq.ParquetWriter(path, schema, compression="zstd")
    try:
        for input_path in inputs:
            if not input_path.exists():
                raise FileNotFoundError(input_path)
            parquet_file = pq.ParquetFile(input_path)
            for batch in parquet_file.iter_batches(batch_size=row_group_size):
                table = pa.Table.from_batches([batch], schema=schema)
                writer.write_table(table)
                rows += table.num_rows
    finally:
        writer.close()
    return TableWriteResult(
        table_name=table_name,
        path=str(path),
        rows=rows,
        bytes=path.stat().st_size,
    )


def schema_report() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "tables": {
            name: {
                "description": TABLE_DESCRIPTIONS.get(name, ""),
                "primary_key": PRIMARY_KEYS.get(name),
                "columns": [
                    {
                        "name": field.name,
                        "type": str(field.type),
                        "nullable": field.nullable,
                    }
                    for field in schema
                ],
            }
            for name, schema in TABLE_SCHEMAS.items()
        },
    }


def write_schema_report(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(schema_report(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
