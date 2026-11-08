"""Dataset-quality report over the processed canonical tables.

The report describes what is actually in the tables: row counts, nullness,
quality-flag distributions, constant channels, sentinel counts, unit coverage,
and provenance completeness. It never turns a sentinel into a measurement.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .config import (
    PROCESSED_DIR,
    QUALITY_REPORT_JSON,
    ensure_directories,
)
from .schemas import PRIMARY_KEYS, TABLE_SCHEMAS
from .validation import _duckdb_connection, _sql_path, utc_now_iso

PIPELINE_VERSION = "1.0.0"


def _relative(path: Path) -> str:
    from .config import ROOT

    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _null_counts(path: Path) -> dict[str, int]:
    parquet_file = pq.ParquetFile(path)
    counts = {name: 0 for name in parquet_file.schema_arrow.names}
    for row_group_index in range(parquet_file.metadata.num_row_groups):
        row_group = parquet_file.metadata.row_group(row_group_index)
        for column_index in range(row_group.num_columns):
            column = row_group.column(column_index)
            statistics = column.statistics
            name = column.path_in_schema
            if statistics is not None and statistics.null_count is not None:
                counts[name] = counts.get(name, 0) + int(statistics.null_count)
    return counts


def _empty_string_counts(path: Path, columns: list[str]) -> dict[str, int]:
    if not columns:
        return {}
    connection = _duckdb_connection()
    try:
        expressions = ", ".join(
            f"SUM(CASE WHEN {column} = '' THEN 1 ELSE 0 END) AS {column}"
            for column in columns
        )
        row = connection.execute(
            f"SELECT {expressions} FROM read_parquet('{_sql_path(path)}')"
        ).fetchone()
        return {column: int(value or 0) for column, value in zip(columns, row)}
    finally:
        connection.close()


def _group_counts(path: Path, column: str, limit: int = 100) -> dict[str, int]:
    connection = _duckdb_connection()
    try:
        rows = connection.execute(
            f"SELECT {column}, COUNT(*) FROM read_parquet('{_sql_path(path)}') "
            f"GROUP BY {column} ORDER BY COUNT(*) DESC LIMIT {limit}"
        ).fetchall()
        return {str(value): int(count) for value, count in rows}
    finally:
        connection.close()


def _table_quality(table_name: str, path: Path) -> dict[str, Any]:
    parquet_file = pq.ParquetFile(path)
    schema = parquet_file.schema_arrow
    rows = parquet_file.metadata.num_rows
    null_counts = _null_counts(path)
    string_columns = [field.name for field in schema if field.type == pa.string()]
    empty_counts: dict[str, int] = {}
    if rows <= 100_000 and string_columns:
        try:
            empty_counts = _empty_string_counts(path, string_columns)
        except Exception:
            empty_counts = {}
    columns = []
    for field in schema:
        null_count = null_counts.get(field.name, 0)
        empty_count = empty_counts.get(field.name)
        columns.append(
            {
                "name": field.name,
                "type": str(field.type),
                "null_count": null_count,
                "null_rate": round(null_count / rows, 6) if rows else None,
                "empty_string_count": empty_count,
            }
        )
    return {
        "table_name": table_name,
        "path": _relative(path),
        "rows": rows,
        "columns": len(schema),
        "primary_key": PRIMARY_KEYS.get(table_name),
        "column_missingness": columns,
    }


def _quality_flag_counts(table_name: str, path: Path) -> dict[str, int]:
    if table_name in {"telemetry_point", "smoke_point"}:
        return _group_counts(path, "quality_flag")
    if table_name in {"gas_flame_test", "material_test", "droplet_test"}:
        counts: dict[str, int] = {}
        parquet_file = pq.ParquetFile(path)
        for batch in parquet_file.iter_batches(columns=["quality_flags"], batch_size=10_000):
            for value in batch.column(0).to_pylist():
                if not value:
                    continue
                for flag in json.loads(value):
                    name = flag.get("flag", "unknown")
                    counts[name] = counts.get(name, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
    return {}


def _channel_profile_summary(table_name: str, path: Path) -> dict[str, Any]:
    parquet_file = pq.ParquetFile(path)
    constant_channels: list[str] = []
    sentinel_channels: list[str] = []
    channels: set[str] = set()
    runs = 0
    for batch in parquet_file.iter_batches(
        columns=["constant_channels_json", "channel_profiles_json"],
        batch_size=100,
    ):
        constant_values = batch.column(0).to_pylist()
        profile_values = batch.column(1).to_pylist()
        for constant_json, profile_json in zip(constant_values, profile_values):
            runs += 1
            if constant_json:
                constant_channels.extend(json.loads(constant_json))
            if profile_json:
                for profile in json.loads(profile_json):
                    channels.add(profile.get("raw_name", ""))
                    if profile.get("sentinel"):
                        sentinel_channels.append(profile.get("raw_name", ""))
    return {
        "runs": runs,
        "channel_count": len(channels),
        "constant_channel_count": len(set(constant_channels)),
        "constant_channels": sorted(set(constant_channels)),
        "sentinel_channel_count": len(set(sentinel_channels)),
        "sentinel_channels": sorted(set(sentinel_channels)),
    }


def _experimental_table_summary(path: Path) -> dict[str, Any]:
    connection = _duckdb_connection()
    try:
        rows = connection.execute(
            f"SELECT accession, COUNT(*) FROM read_parquet('{_sql_path(path)}') "
            f"GROUP BY accession ORDER BY accession"
        ).fetchall()
        return {str(accession): int(count) for accession, count in rows}
    finally:
        connection.close()


def _material_unit_ambiguity(path: Path) -> dict[str, Any] | None:
    connection = _duckdb_connection()
    try:
        row = connection.execute(
            f"SELECT COUNT(*), MIN(o2_pct), MAX(o2_pct) FROM read_parquet('{_sql_path(path)}') "
            f"WHERE accession = 'PSI-26' AND o2_pct IS NOT NULL"
        ).fetchone()
        count, minimum, maximum = row
        if not count:
            return None
        return {
            "accession": "PSI-26",
            "column": "o2_pct",
            "header": "O2 % by volume",
            "non_null_count": int(count),
            "min": minimum,
            "max": maximum,
            "issue": (
                "The source header says percent but the observed values are around 0.22. "
                "The values are preserved as o2_pct and are not relabeled as initial/final O2."
            ),
        }
    finally:
        connection.close()


def build_quality_report() -> dict[str, Any]:
    ensure_directories()
    if not PROCESSED_DIR.exists():
        raise FileNotFoundError("data/processed does not exist; run build-canonical first")

    tables: dict[str, Any] = {}
    for table_name in TABLE_SCHEMAS:
        path = PROCESSED_DIR / f"{table_name}.parquet"
        if not path.exists():
            continue
        tables[table_name] = _table_quality(table_name, path)

    point_tables: dict[str, Any] = {}
    for table_name in ("telemetry_point", "smoke_point"):
        path = PROCESSED_DIR / f"{table_name}.parquet"
        if not path.exists():
            continue
        point_tables[table_name] = {
            "rows": pq.ParquetFile(path).metadata.num_rows,
            "quality_flag_counts": _quality_flag_counts(table_name, path),
            "unit_counts": _group_counts(path, "unit"),
            "accessions": _group_counts(path, "accession"),
        }

    run_tables: dict[str, Any] = {}
    for table_name in ("telemetry_run", "smoke_run"):
        path = PROCESSED_DIR / f"{table_name}.parquet"
        if not path.exists():
            continue
        run_tables[table_name] = _channel_profile_summary(table_name, path)

    flag_tables: dict[str, Any] = {}
    for table_name in ("gas_flame_test", "material_test", "droplet_test"):
        path = PROCESSED_DIR / f"{table_name}.parquet"
        if not path.exists():
            continue
        flag_tables[table_name] = _quality_flag_counts(table_name, path)

    experimental_tables: dict[str, Any] = {}
    cells_path = PROCESSED_DIR / "experimental_table_cell.parquet"
    if cells_path.exists():
        experimental_tables["cell_count"] = pq.ParquetFile(cells_path).metadata.num_rows
        experimental_tables["value_flag_counts"] = _group_counts(cells_path, "value_flag")
        experimental_tables["table_cell_counts"] = _experimental_table_summary(cells_path)
    rows_path = PROCESSED_DIR / "source_row.parquet"
    if rows_path.exists():
        experimental_tables["source_row_count"] = pq.ParquetFile(rows_path).metadata.num_rows

    issues: list[dict[str, Any]] = []
    material_path = PROCESSED_DIR / "material_test.parquet"
    if material_path.exists():
        ambiguity = _material_unit_ambiguity(material_path)
        if ambiguity is not None:
            issues.append(
                {
                    "severity": "warning",
                    "code": "unit_ambiguity",
                    "message": ambiguity["issue"],
                    "details": ambiguity,
                }
            )

    droplet_path = PROCESSED_DIR / "droplet_test.parquet"
    if droplet_path.exists():
        droplet_flags = _quality_flag_counts("droplet_test", droplet_path)
        if droplet_flags.get("unit_ambiguity"):
            issues.append(
                {
                    "severity": "warning",
                    "code": "unit_ambiguity",
                    "message": (
                        "PSI-69 `Burning rate; mm` is preserved as labeled. "
                        "It is not converted to mm/s without source confirmation."
                    ),
                    "details": {
                        "column": "burning_rate_mm_as_labeled",
                        "count": droplet_flags["unit_ambiguity"],
                    },
                }
            )

    gas_path = PROCESSED_DIR / "gas_flame_test.parquet"
    if gas_path.exists():
        gas_flags = _quality_flag_counts("gas_flame_test", gas_path)
        if gas_flags.get("has_missing_final_state"):
            issues.append(
                {
                    "severity": "warning",
                    "code": "missing_final_state",
                    "message": "Some gas-flame tests have a missing final O2/pressure state.",
                    "details": {"count": gas_flags["has_missing_final_state"]},
                }
            )
        if gas_flags.get("spreadsheet_error"):
            issues.append(
                {
                    "severity": "warning",
                    "code": "spreadsheet_error",
                    "message": "Spreadsheet error tokens are preserved as non-numeric values.",
                    "details": {"count": gas_flags["spreadsheet_error"]},
                }
            )

    if "telemetry_point" in point_tables:
        counts = point_tables["telemetry_point"]["quality_flag_counts"]
        if counts.get("sentinel"):
            issues.append(
                {
                    "severity": "warning",
                    "code": "sentinel_points",
                    "message": "Telemetry sentinel cells are preserved with null values.",
                    "details": {"count": counts["sentinel"]},
                }
            )
        if counts.get("uncalibrated"):
            issues.append(
                {
                    "severity": "info",
                    "code": "uncalibrated_channels",
                    "message": "Some telemetry channels are raw/uncalibrated and are labeled as such.",
                    "details": {"count": counts["uncalibrated"]},
                }
            )

    if "smoke_point" in point_tables:
        counts = point_tables["smoke_point"]["quality_flag_counts"]
        if counts.get("sentinel"):
            issues.append(
                {
                    "severity": "warning",
                    "code": "sentinel_points",
                    "message": "SAME-R -999 sentinels are preserved with null values.",
                    "details": {"count": counts["sentinel"]},
                }
            )

    provenance: dict[str, Any] = {}
    for table_name, table in tables.items():
        path = PROCESSED_DIR / f"{table_name}.parquet"
        schema = pq.ParquetFile(path).schema_arrow
        if "source_sha256" in schema.names:
            connection = _duckdb_connection()
            try:
                row = connection.execute(
                    f"SELECT COUNT(*), COUNT(source_sha256), COUNT(DISTINCT source_sha256) "
                    f"FROM read_parquet('{_sql_path(path)}')"
                ).fetchone()
                provenance[table_name] = {
                    "rows": int(row[0]),
                    "source_sha256_nonnull": int(row[1]),
                    "distinct_source_sha256": int(row[2]),
                    "complete": int(row[0]) == int(row[1]),
                }
            finally:
                connection.close()

    summary = {
        "tables": len(tables),
        "total_rows": sum(table["rows"] for table in tables.values()),
        "point_rows": sum(table["rows"] for table in point_tables.values()),
        "issues": len(issues),
        "errors": sum(1 for issue in issues if issue["severity"] == "error"),
        "warnings": sum(1 for issue in issues if issue["severity"] == "warning"),
    }
    report = {
        "schema_version": "1.0.0",
        "generated_at": utc_now_iso(),
        "pipeline_version": PIPELINE_VERSION,
        "status": "pass" if summary["errors"] == 0 else "fail",
        "summary": summary,
        "tables": tables,
        "point_tables": point_tables,
        "run_tables": run_tables,
        "flag_tables": flag_tables,
        "experimental_tables": experimental_tables,
        "provenance": provenance,
        "issues": issues,
    }
    QUALITY_REPORT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report
