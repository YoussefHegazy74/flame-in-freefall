"""Build the processed canonical tables from the interim Parquet outputs.

Metadata tables come from the committed registry and the authenticated
acquisition record. Domain tables come from the interim parsers. Telemetry and
smoke points are concatenated run by run; the run boundary is preserved in
``run_id`` and the per-run tables are never collapsed into one export.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from .config import (
    CANONICAL_SCHEMA_JSON,
    CANONICAL_SCHEMA_VERSION,
    ET_SCHEMAS_JSON,
    FILE_INVENTORY_CSV,
    INTERIM_DIR,
    PARSER_VERSION,
    PROCESSED_DIR,
    PROCESSING_REPORT_JSON,
    REGISTRY_JSON,
    ensure_directories,
)
from .manifest import read_manifest
from .provenance import load_acquisition_index
from .schemas import (
    TABLE_SCHEMAS,
    concat_parquet,
    write_parquet,
    write_schema_report,
)

PIPELINE_VERSION = "1.0.0"
DATASET_MANIFEST_JSON = PROCESSED_DIR / "dataset_manifest.json"
TELEMETRY_POINTS_DIR = INTERIM_DIR / "telemetry_points"
SMOKE_POINTS_DIR = INTERIM_DIR / "smoke_points"


class CanonicalBuildError(RuntimeError):
    """Raised when a required interim table is missing or inconsistent."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _relative(path: Path) -> str:
    from .config import ROOT

    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _iso_date(value: str | None) -> str | None:
    if not value or not str(value).strip():
        return None
    text = str(value).strip()
    for fmt in ("%m-%d-%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _read_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))


def _read_et_schemas() -> dict[str, Any]:
    return json.loads(ET_SCHEMAS_JSON.read_text(encoding="utf-8"))


def _restricted_by_table() -> dict[tuple[str, str], bool]:
    registry = _read_registry()
    result: dict[tuple[str, str], bool] = {}
    for investigation in registry["investigations"]:
        accession = investigation["accession"]
        for item in investigation.get("experimental_tables", []):
            result[(accession, item["file_name"])] = bool(item.get("restricted", False))
    return result


def build_psi_investigation() -> list[dict[str, Any]]:
    registry = _read_registry()
    records: list[dict[str, Any]] = []
    for investigation in registry["investigations"]:
        records.append(
            {
                "accession": investigation["accession"],
                "acronym": investigation.get("acronym") or None,
                "title": investigation.get("title") or None,
                "doi": investigation.get("doi") or None,
                "research_area": investigation.get("research_area") or None,
                "sub_research_area": investigation.get("sub_research_area") or None,
                "project_type": investigation.get("project_type") or None,
                "start_date": _iso_date(investigation.get("start_date")),
                "end_date": _iso_date(investigation.get("end_date")),
                "version": investigation.get("version"),
                "public": investigation.get("public"),
                "restricted": investigation.get("restricted"),
                "file_count": investigation.get("file_count"),
                "removed_file_count": investigation.get("removed_file_count"),
                "experimental_table_count": investigation.get("experimental_table_count"),
                "experimental_table_bytes": investigation.get("experimental_table_bytes"),
                "experimental_table_only_count": investigation.get("experimental_table_only_count"),
                "archive_status": investigation.get("archive_status") or None,
                "registered_total_bytes": investigation.get("registered_total_bytes"),
                "mvp_role": investigation.get("mvp_role") or None,
                "rationale": investigation.get("mvp_rationale") or None,
                "limitations_json": json.dumps(
                    investigation.get("limitations", []), ensure_ascii=False
                ),
            }
        )
    return records


def build_psi_file() -> list[dict[str, Any]]:
    acquisition = load_acquisition_index()
    records: list[dict[str, Any]] = []
    with FILE_INVENTORY_CSV.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            accession = row["accession"]
            file_name = row["file_name"]
            acquisition_row = acquisition.get((accession, file_name))
            selected = acquisition_row is not None
            records.append(
                {
                    "file_id": f"{accession}::{file_name}",
                    "accession": accession,
                    "file_name": file_name,
                    "file_size_bytes": int(float(row["file_size_bytes"])),
                    "format": row["format"] or None,
                    "category": row["category"] or None,
                    "restricted": row["restricted"].strip().lower() == "true",
                    "visible": row["visible"].strip().lower() == "true",
                    "version": int(row["version"]) if row["version"] else None,
                    "sha256": (acquisition_row.get("sha256_actual") or None) if selected else None,
                    "retrieved_at": (acquisition_row.get("retrieved_at") or None) if selected else None,
                    "access_status": (acquisition_row.get("status") or "unknown") if selected else "not_selected",
                    "source_url": (acquisition_row.get("source_url") or None) if selected else None,
                }
            )
    return records


def build_experimental_table() -> list[dict[str, Any]]:
    schemas = _read_et_schemas()
    restricted = _restricted_by_table()
    acquisition = load_acquisition_index()
    records: list[dict[str, Any]] = []
    for table_id, schema in sorted(schemas["tables"].items()):
        acquisition_row = acquisition.get((schema["accession"], schema["file_name"]), {})
        records.append(
            {
                "table_id": table_id,
                "accession": schema["accession"],
                "file_name": schema["file_name"],
                "file_size_bytes": schema["size_bytes"],
                "in_added": schema["in_added"],
                "restricted": restricted.get(
                    (schema["accession"], schema["file_name"]), False
                ),
                "data_rows": schema["data_rows"],
                "physical_rows": schema["physical_rows"],
                "columns": schema["columns"],
                "sha256": schema["sha256"],
                "notes": schema.get("notes") or None,
                "encoding": schema.get("encoding") or None,
                "encoding_fallback": schema.get("encoding_fallback"),
                "retrieved_at": acquisition_row.get("retrieved_at") or None,
                "source_url": acquisition_row.get("source_url") or None,
                "parser_version": PARSER_VERSION,
            }
        )
    return records


def _require(path: Path) -> Path:
    if not path.exists():
        raise CanonicalBuildError(
            f"required interim table is missing: {path}; run `python -m src.data_pipeline parse` first"
        )
    return path


def _copy_table(table_name: str, source: Path) -> dict[str, Any]:
    destination = PROCESSED_DIR / f"{table_name}.parquet"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    metadata = pq.ParquetFile(destination).metadata
    return {
        "table_name": table_name,
        "path": _relative(destination),
        "rows": metadata.num_rows,
        "bytes": destination.stat().st_size,
        "row_groups": metadata.num_row_groups,
        "source": _relative(source),
    }


def _concat_table(table_name: str, inputs: list[Path]) -> dict[str, Any]:
    if not inputs:
        raise CanonicalBuildError(f"no interim inputs for {table_name}")
    for path in inputs:
        _require(path)
    destination = PROCESSED_DIR / f"{table_name}.parquet"
    result = concat_parquet(inputs, table_name, destination)
    return {
        "table_name": table_name,
        "path": _relative(destination),
        "rows": result.rows,
        "bytes": result.bytes,
        "row_groups": pq.ParquetFile(destination).metadata.num_row_groups,
        "inputs": [_relative(path) for path in inputs],
    }


def _source_digest(
    manifest: dict[str, Any],
    acquisition: dict[tuple[str, str], dict[str, str]],
) -> tuple[str, int]:
    pairs = [
        [
            item["file_id"],
            acquisition.get((item["accession"], item["file_name"]), {}).get("sha256_actual")
            or item.get("sha256_expected")
            or "",
        ]
        for item in manifest["files"]
    ]
    payload = json.dumps(
        {
            "sources": pairs,
            "parser_version": PARSER_VERSION,
            "pipeline_version": PIPELINE_VERSION,
            "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), sum(
        int(item["expected_bytes"]) for item in manifest["files"]
    )


def build_canonical() -> dict[str, Any]:
    """Build every processed table and write the dataset manifest/report."""

    ensure_directories()
    manifest = read_manifest()
    acquisition = load_acquisition_index()
    started_at = utc_now_iso()

    write_schema_report(CANONICAL_SCHEMA_JSON)

    metadata_tables = {
        "psi_investigation": build_psi_investigation(),
        "psi_file": build_psi_file(),
        "experimental_table": build_experimental_table(),
    }
    table_results: dict[str, dict[str, Any]] = {}
    for table_name, records in metadata_tables.items():
        destination = PROCESSED_DIR / f"{table_name}.parquet"
        result = write_parquet(records, table_name, destination)
        table_results[table_name] = {
            "table_name": table_name,
            "path": _relative(destination),
            "rows": result.rows,
            "bytes": result.bytes,
            "row_groups": pq.ParquetFile(destination).metadata.num_row_groups,
            "source": "committed registry",
        }

    single_tables = {
        "gas_flame_test": INTERIM_DIR / "gas_flame_test.parquet",
        "telemetry_run": INTERIM_DIR / "telemetry_run.parquet",
        "smoke_run": INTERIM_DIR / "smoke_run.parquet",
        "smoke_test_log": INTERIM_DIR / "smoke_test_log.parquet",
        "material_test": INTERIM_DIR / "material_test.parquet",
        "droplet_test": INTERIM_DIR / "droplet_test.parquet",
        "experimental_table_cell": INTERIM_DIR / "experimental_table_cell.parquet",
        "source_row": INTERIM_DIR / "source_row.parquet",
    }
    for table_name, source in single_tables.items():
        _require(source)
        table_results[table_name] = _copy_table(table_name, source)

    from .parsers.telemetry import TELEMETRY_SPECS
    from .provenance import slugify

    telemetry_inputs = [
        TELEMETRY_POINTS_DIR / f"{slugify(spec.run_id, max_length=120)}.parquet"
        for spec in TELEMETRY_SPECS
    ]
    table_results["telemetry_point"] = _concat_table("telemetry_point", telemetry_inputs)

    smoke_inputs = []
    for item in sorted(
        (entry for entry in manifest["files"] if entry["kind"] == "smoke_telemetry_csv"),
        key=lambda entry: entry["file_name"],
    ):
        run_id = "PSI-101::" + Path(item["file_name"]).stem
        smoke_inputs.append(SMOKE_POINTS_DIR / (slugify(run_id, max_length=120) + ".parquet"))
    table_results["smoke_point"] = _concat_table("smoke_point", smoke_inputs)

    missing = sorted(set(TABLE_SCHEMAS) - set(table_results))
    if missing:
        raise CanonicalBuildError(f"canonical build did not produce: {missing}")

    dataset_version, expected_bytes = _source_digest(manifest, acquisition)
    selected_checksums = {
        item["file_id"]: (
            acquisition.get((item["accession"], item["file_name"]), {}).get("sha256_actual")
            or item.get("sha256_expected")
        )
        for item in manifest["files"]
    }
    dataset_manifest = {
        "schema_version": "1.0.0",
        "dataset_version": dataset_version,
        "generated_at": utc_now_iso(),
        "started_at": started_at,
        "pipeline_version": PIPELINE_VERSION,
        "parser_version": PARSER_VERSION,
        "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
        "source_manifest": "data/registry/download_manifest.json",
        "source_file_count": len(manifest["files"]),
        "source_expected_bytes": expected_bytes,
        "source_checksums": selected_checksums,
        "acquisition_records": len(acquisition),
        "tables": table_results,
    }
    DATASET_MANIFEST_JSON.write_text(
        json.dumps(dataset_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    report = {
        "schema_version": "1.0.0",
        "dataset_version": dataset_version,
        "generated_at": utc_now_iso(),
        "started_at": started_at,
        "pipeline_version": PIPELINE_VERSION,
        "parser_version": PARSER_VERSION,
        "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
        "tables": table_results,
        "table_count": len(table_results),
        "total_rows": sum(item["rows"] for item in table_results.values()),
        "total_bytes": sum(item["bytes"] for item in table_results.values()),
        "notes": [
            "PSI-100 raw CSV, cleaned CSV, and XLSX sheets remain separate runs.",
            "PSI-101 HKP runs remain separate runs.",
            "No BASS/BASS-II flame-spread rate is derived.",
            "No SAME/SAME-R device state is relabeled as a physical measurement.",
        ],
    }
    PROCESSING_REPORT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report
