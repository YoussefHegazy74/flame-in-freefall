"""Acquisition and canonical-table validation.

Validation never repairs a source. A missing, truncated, or checksum-mismatched
file is reported as a failure. The report is written even when checks fail so
that the exact state is reviewable.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .config import (
    ACQUISITION_REPORT_JSON,
    ET_SCHEMAS_JSON,
    FILE_INVENTORY_CSV,
    PROCESSED_DIR,
    RAW_DIR,
    REGISTRY_JSON,
    VALIDATION_REPORT_JSON,
    ensure_directories,
)
from .manifest import read_manifest
from .provenance import load_acquisition_index, sha256_file
from .schemas import PRIMARY_KEYS, TABLE_SCHEMAS

PIPELINE_VERSION = "1.0.0"

EXPECTED_ROWS: dict[str, int] = {
    "psi_investigation": 24,
    "psi_file": 16354,
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

ALLOWED_QUALITY_FLAGS = {
    "ok",
    "constant",
    "uncalibrated",
    "not_stated_unit",
    "sentinel",
    "spreadsheet_error",
    "non_numeric",
    "invalid_indefinite",
    "range_text",
    "unit_text",
    "not_applicable",
    "not_measured",
    "inequality_text",
    "non_numeric_qualifier",
    "percent_text",
    "approximate",
    "boolean",
}

JSON_COLUMNS: dict[str, list[str]] = {
    "psi_investigation": ["limitations_json"],
    "gas_flame_test": ["quality_flags", "raw_row_json"],
    "telemetry_run": ["constant_channels_json", "channel_profiles_json"],
    "smoke_run": [
        "test_numbers_json",
        "sample_numbers_json",
        "carousel_numbers_json",
        "run_mode_codes_json",
        "constant_channels_json",
        "sentinel_channels_json",
        "channel_profiles_json",
    ],
    "smoke_test_log": ["raw_row_json"],
    "material_test": ["context_json", "quality_flags", "raw_row_json"],
    "droplet_test": ["quality_flags", "raw_row_json"],
    "source_row": ["raw_row_json"],
}


class ValidationError(RuntimeError):
    """Raised when the validator itself cannot run."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _relative(path: Path) -> str:
    from .config import ROOT

    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _duckdb_connection():
    import duckdb

    connection = duckdb.connect(database=":memory:")
    connection.execute("SET memory_limit='2GB'")
    connection.execute("SET threads=4")
    try:
        from .config import DATA_DIR

        temp = DATA_DIR / "tmp" / "duckdb"
        temp.mkdir(parents=True, exist_ok=True)
        connection.execute(f"SET temp_directory='{str(temp).replace(chr(39), chr(39) * 2)}'")
    except Exception:
        pass
    return connection


def _sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def _duplicate_count(path: Path, primary_key: str) -> tuple[int, str]:
    try:
        connection = _duckdb_connection()
        try:
            row = connection.execute(
                f"SELECT COUNT(*) - COUNT(DISTINCT {primary_key}) "
                f"FROM read_parquet('{_sql_path(path)}')"
            ).fetchone()
            return int(row[0] or 0), "duckdb"
        finally:
            connection.close()
    except Exception:
        # Fallback for environments without DuckDB. It streams batches and
        # keeps only the identifier set; this is acceptable for the smaller
        # tables and is reported as the fallback method.
        seen: set[str] = set()
        duplicates = 0
        parquet_file = pq.ParquetFile(path)
        for batch in parquet_file.iter_batches(columns=[primary_key], batch_size=100_000):
            for value in batch.column(0).to_pylist():
                if value is None:
                    continue
                if value in seen:
                    duplicates += 1
                else:
                    seen.add(value)
        return duplicates, "pyarrow"


def _parquet_schema(path: Path) -> pa.Schema:
    return pq.ParquetFile(path).schema_arrow


def _column_null_counts(path: Path) -> dict[str, int]:
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


def _json_column_errors(path: Path, column: str) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    parquet_file = pq.ParquetFile(path)
    row_index = 0
    for batch in parquet_file.iter_batches(columns=[column], batch_size=20_000):
        for value in batch.column(0).to_pylist():
            row_index += 1
            if value is None:
                continue
            try:
                json.loads(value)
            except (TypeError, json.JSONDecodeError) as exc:
                errors.append(
                    {
                        "column": column,
                        "row": row_index,
                        "error": str(exc),
                    }
                )
                if len(errors) >= 20:
                    return errors
    return errors


def validate_acquisition() -> dict[str, Any]:
    manifest = read_manifest()
    acquisition = load_acquisition_index()
    files: list[dict[str, Any]] = []
    failures = 0
    warnings = 0
    seen_checksums: dict[str, list[str]] = {}

    for entry in manifest["files"]:
        file_id = entry["file_id"]
        path = RAW_DIR / entry["accession"] / entry["file_name"]
        record = acquisition.get((entry["accession"], entry["file_name"]))
        issues: list[dict[str, Any]] = []
        actual_size: int | None = None
        actual_sha: str | None = None
        status = "pass"

        if not path.exists():
            status = "fail"
            issues.append({"severity": "error", "code": "missing_file", "message": str(path)})
        else:
            actual_size = path.stat().st_size
            actual_sha = sha256_file(path)
            if actual_size != int(entry["expected_bytes"]):
                status = "fail"
                issues.append(
                    {
                        "severity": "error",
                        "code": "size_mismatch",
                        "message": f"expected {entry['expected_bytes']} bytes, found {actual_size}",
                    }
                )
            expected_sha = entry.get("sha256_expected")
            if expected_sha and actual_sha != expected_sha:
                status = "fail"
                issues.append(
                    {
                        "severity": "error",
                        "code": "checksum_mismatch",
                        "message": f"expected {expected_sha}, found {actual_sha}",
                    }
                )
            if record is None:
                warnings += 1
                issues.append(
                    {
                        "severity": "warning",
                        "code": "no_acquisition_record",
                        "message": "file exists but is absent from data/manifests/download_manifest.csv",
                    }
                )
            else:
                recorded_sha = record.get("sha256_actual") or None
                if recorded_sha and recorded_sha != actual_sha:
                    status = "fail"
                    issues.append(
                        {
                            "severity": "error",
                            "code": "acquisition_record_mismatch",
                            "message": f"manifest records {recorded_sha}, found {actual_sha}",
                        }
                    )
                if record.get("status") not in {"downloaded", "already_present"}:
                    status = "fail"
                    issues.append(
                        {
                            "severity": "error",
                            "code": "acquisition_status",
                            "message": f"recorded status is {record.get('status')!r}",
                        }
                    )
            seen_checksums.setdefault(actual_sha, []).append(file_id)

        if status == "fail":
            failures += 1
        files.append(
            {
                "file_id": file_id,
                "accession": entry["accession"],
                "file_name": entry["file_name"],
                "kind": entry["kind"],
                "status": status,
                "expected_bytes": entry["expected_bytes"],
                "actual_bytes": actual_size,
                "expected_sha256": entry.get("sha256_expected"),
                "actual_sha256": actual_sha,
                "acquisition_status": record.get("status") if record else None,
                "retrieved_at": record.get("retrieved_at") if record else None,
                "issues": issues,
            }
        )

    duplicate_groups = [
        {"sha256": sha, "file_ids": ids}
        for sha, ids in sorted(seen_checksums.items())
        if len(ids) > 1
    ]
    if duplicate_groups:
        warnings += len(duplicate_groups)

    known: list[dict[str, Any]] = []
    if ACQUISITION_REPORT_JSON.exists():
        try:
            acquisition_report = json.loads(ACQUISITION_REPORT_JSON.read_text(encoding="utf-8"))
            known = acquisition_report.get("known_unavailable", [])
        except (OSError, json.JSONDecodeError):
            known = []
    known_verified = sum(1 for item in known if item.get("status") == "listed_404")
    known_unexpected = [
        item for item in known if item.get("status") not in {"listed_404", "failed"}
    ]

    summary = {
        "selected_files": len(files),
        "present": sum(1 for item in files if item["actual_bytes"] is not None),
        "verified": sum(1 for item in files if item["status"] == "pass"),
        "failed": failures,
        "warnings": warnings,
        "known_unavailable_verified": known_verified,
        "known_unavailable_unexpected": len(known_unexpected),
        "duplicate_checksum_groups": len(duplicate_groups),
    }
    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now_iso(),
        "manifest": "data/registry/download_manifest.json",
        "status": "pass" if failures == 0 else "fail",
        "summary": summary,
        "files": files,
        "known_unavailable": known,
        "duplicate_checksums": duplicate_groups,
    }


def _check_provenance(path: Path) -> dict[str, Any]:
    connection = _duckdb_connection()
    try:
        row = connection.execute(
            f"SELECT COUNT(*) AS rows, "
            f"COUNT(source_sha256) AS sha_nonnull, "
            f"COUNT(DISTINCT source_sha256) AS sha_distinct, "
            f"COUNT(source_url) AS url_nonnull "
            f"FROM read_parquet('{_sql_path(path)}')"
        ).fetchone()
        rows, sha_nonnull, sha_distinct, url_nonnull = row
        return {
            "rows": int(rows),
            "source_sha256_nonnull": int(sha_nonnull),
            "distinct_source_sha256": int(sha_distinct),
            "source_url_nonnull": int(url_nonnull),
            "complete": int(sha_nonnull) == int(rows) and int(url_nonnull) == int(rows),
        }
    finally:
        connection.close()


def _check_values(path: Path, query: str) -> Any:
    connection = _duckdb_connection()
    try:
        return connection.execute(query).fetchall()
    finally:
        connection.close()


def validate_canonical() -> dict[str, Any]:
    tables: list[dict[str, Any]] = []
    failures = 0
    warnings = 0
    if not PROCESSED_DIR.exists():
        return {
            "status": "not_built",
            "summary": {"tables": 0, "failed": 0, "warnings": 0},
            "tables": [],
            "message": "data/processed does not exist; run build-canonical first",
        }

    for table_name, expected_schema in TABLE_SCHEMAS.items():
        path = PROCESSED_DIR / f"{table_name}.parquet"
        issues: list[dict[str, Any]] = []
        status = "pass"
        rows: int | None = None
        schema_ok = False
        duplicate_count: int | None = None
        duplicate_method: str | None = None
        provenance: dict[str, Any] | None = None

        if not path.exists():
            status = "fail"
            issues.append({"severity": "error", "code": "missing_table", "message": str(path)})
            failures += 1
            tables.append(
                {
                    "table_name": table_name,
                    "path": _relative(path),
                    "status": status,
                    "rows": None,
                    "schema_ok": False,
                    "issues": issues,
                }
            )
            continue

        parquet_file = pq.ParquetFile(path)
        rows = parquet_file.metadata.num_rows
        actual_schema = parquet_file.schema_arrow
        schema_ok = actual_schema.equals(expected_schema, check_metadata=False)
        if not schema_ok:
            status = "fail"
            issues.append(
                {
                    "severity": "error",
                    "code": "schema_mismatch",
                    "message": "Parquet schema does not match the canonical Arrow schema",
                }
            )

        expected_rows = EXPECTED_ROWS.get(table_name)
        if expected_rows is not None and rows != expected_rows:
            status = "fail"
            issues.append(
                {
                    "severity": "error",
                    "code": "row_count_mismatch",
                    "message": f"expected {expected_rows} rows, found {rows}",
                }
            )

        primary_key = PRIMARY_KEYS[table_name]
        if primary_key in actual_schema.names:
            duplicate_count, duplicate_method = _duplicate_count(path, primary_key)
            if duplicate_count:
                status = "fail"
                issues.append(
                    {
                        "severity": "error",
                        "code": "duplicate_primary_key",
                        "message": f"{duplicate_count} duplicate {primary_key} values",
                    }
                )

        if "source_sha256" in actual_schema.names:
            provenance = _check_provenance(path)
            if not provenance["complete"]:
                status = "fail"
                issues.append(
                    {
                        "severity": "error",
                        "code": "incomplete_provenance",
                        "message": (
                            f"{provenance['rows']} rows, "
                            f"{provenance['source_sha256_nonnull']} with source_sha256, "
                            f"{provenance['source_url_nonnull']} with source_url"
                        ),
                    }
                )

        if table_name in {"telemetry_point", "smoke_point"}:
            allowed = ", ".join(f"'{flag}'" for flag in sorted(ALLOWED_QUALITY_FLAGS))
            bad_flags = _check_values(
                path,
                f"SELECT quality_flag, COUNT(*) FROM read_parquet('{_sql_path(path)}') "
                f"WHERE quality_flag IS NULL OR quality_flag NOT IN ({allowed}) "
                f"GROUP BY quality_flag",
            )
            if bad_flags:
                status = "fail"
                issues.append(
                    {
                        "severity": "error",
                        "code": "invalid_quality_flag",
                        "message": str(bad_flags),
                    }
                )

        if table_name == "telemetry_point":
            negative = _check_values(
                path,
                f"SELECT COUNT(*) FROM read_parquet('{_sql_path(path)}') WHERE relative_time_ms < 0",
            )[0][0]
            if negative:
                status = "fail"
                issues.append(
                    {
                        "severity": "error",
                        "code": "negative_time",
                        "message": f"{negative} rows have negative relative_time_ms",
                    }
                )
        if table_name == "smoke_point":
            negative = _check_values(
                path,
                f"SELECT COUNT(*) FROM read_parquet('{_sql_path(path)}') WHERE unix_time_s < 0",
            )[0][0]
            if negative:
                status = "fail"
                issues.append(
                    {
                        "severity": "error",
                        "code": "negative_time",
                        "message": f"{negative} rows have negative unix_time_s",
                    }
                )

        for column in JSON_COLUMNS.get(table_name, []):
            if column not in actual_schema.names:
                continue
            json_errors = _json_column_errors(path, column)
            if json_errors:
                status = "fail"
                issues.append(
                    {
                        "severity": "error",
                        "code": "invalid_json",
                        "message": f"{column}: {len(json_errors)} invalid JSON values",
                        "examples": json_errors[:5],
                    }
                )

        if status == "fail":
            failures += 1
        warnings += sum(1 for issue in issues if issue["severity"] == "warning")
        tables.append(
            {
                "table_name": table_name,
                "path": _relative(path),
                "status": status,
                "rows": rows,
                "expected_rows": expected_rows,
                "schema_ok": schema_ok,
                "primary_key": primary_key,
                "duplicate_count": duplicate_count,
                "duplicate_method": duplicate_method,
                "provenance": provenance,
                "issues": issues,
            }
        )

    # Registry consistency checks.
    registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    registry_accessions = {item["accession"] for item in registry["investigations"]}
    investigation_path = PROCESSED_DIR / "psi_investigation.parquet"
    if investigation_path.exists():
        table = pq.read_table(investigation_path, columns=["accession"])
        actual_accessions = set(table.column("accession").to_pylist())
        if actual_accessions != registry_accessions:
            failures += 1
            tables.append(
                {
                    "table_name": "psi_investigation::registry_check",
                    "status": "fail",
                    "issues": [
                        {
                            "severity": "error",
                            "code": "accession_mismatch",
                            "message": (
                                f"missing={sorted(registry_accessions - actual_accessions)}, "
                                f"extra={sorted(actual_accessions - registry_accessions)}"
                            ),
                        }
                    ],
                }
            )

    et_schemas = json.loads(ET_SCHEMAS_JSON.read_text(encoding="utf-8"))
    et_path = PROCESSED_DIR / "experimental_table.parquet"
    if et_path.exists():
        table = pq.read_table(et_path, columns=["table_id", "sha256", "data_rows", "physical_rows"])
        actual = {
            row["table_id"]: row
            for row in table.to_pylist()
        }
        for table_id, schema in et_schemas["tables"].items():
            row = actual.get(table_id)
            if row is None:
                failures += 1
                tables.append(
                    {
                        "table_name": f"experimental_table::{table_id}",
                        "status": "fail",
                        "issues": [
                            {
                                "severity": "error",
                                "code": "missing_experimental_table",
                                "message": table_id,
                            }
                        ],
                    }
                )
                continue
            if (
                row["sha256"] != schema["sha256"]
                or row["data_rows"] != schema["data_rows"]
                or row["physical_rows"] != schema["physical_rows"]
            ):
                failures += 1
                tables.append(
                    {
                        "table_name": f"experimental_table::{table_id}",
                        "status": "fail",
                        "issues": [
                            {
                                "severity": "error",
                                "code": "experimental_table_mismatch",
                                "message": f"{row} != {schema}",
                            }
                        ],
                    }
                )

    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now_iso(),
        "status": "pass" if failures == 0 else "fail",
        "summary": {
            "tables": len(tables),
            "failed": failures,
            "warnings": warnings,
        },
        "tables": tables,
    }


def write_validation_report() -> dict[str, Any]:
    ensure_directories()
    acquisition = validate_acquisition()
    canonical = validate_canonical()
    report = {
        "schema_version": "1.0.0",
        "generated_at": utc_now_iso(),
        "pipeline_version": PIPELINE_VERSION,
        "acquisition": acquisition,
        "canonical": canonical,
        "status": "pass"
        if acquisition["status"] == "pass" and canonical["status"] in {"pass", "not_built"}
        else "fail",
    }
    VALIDATION_REPORT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report
