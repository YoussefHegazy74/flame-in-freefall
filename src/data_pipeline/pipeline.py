"""Parse every selected source into interim Parquet tables.

The pipeline is deliberately explicit about what it reads. It never scans
``data/raw`` for arbitrary files; every source comes from the committed
manifest. Each SAFFIRE-III export and each SAME-R HKP file is written as its
own point table so that runs are never silently concatenated.

The parse stage is resumable. A previously written run is reused only when its
recorded source checksum, parser version, and output path still match. Use
``--force`` to rebuild everything.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence

import pyarrow.parquet as pq

from .config import (
    ET_SCHEMAS_JSON,
    INTERIM_DIR,
    PARSER_VERSION,
    PROCESSING_REPORT_JSON,
    ensure_directories,
)
from .manifest import read_manifest
from .parsers.droplet import parse_droplet
from .parsers.gas_flame import SPECS as GAS_SPECS, parse_gas_flame
from .parsers.material import parse_psi25, parse_psi26
from .parsers.smoke import iter_smoke_points, scan_smoke
from .parsers.summary_table import parse_summary_tables
from .parsers.telemetry import (
    TELEMETRY_SPECS,
    iter_telemetry_points,
    scan_telemetry,
)
from .parsers.test_log import parse_test_log
from .provenance import (
    SourceFile,
    load_acquisition_index,
    sha256_file,
    slugify,
    source_from_entry,
)
from .schemas import write_parquet, write_parquet_batches

PIPELINE_VERSION = "1.0.0"
PARSE_REPORT_JSON = INTERIM_DIR / "parse_report.json"
TELEMETRY_POINTS_DIR = INTERIM_DIR / "telemetry_points"
SMOKE_POINTS_DIR = INTERIM_DIR / "smoke_points"


class PipelineError(RuntimeError):
    """Raised when an interim table cannot be produced safely."""


@dataclass
class ParseEntry:
    key: str
    accession: str
    file_name: str
    sheet: str | None
    kind: str
    parser: str
    table_name: str
    source_sha256: str
    parser_version: str
    output: str
    output_rows: int
    physical_rows: int | None = None
    data_rows: int | None = None
    issue_count: int = 0
    issues: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float | None = None
    reused: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "accession": self.accession,
            "file_name": self.file_name,
            "sheet": self.sheet,
            "kind": self.kind,
            "parser": self.parser,
            "table_name": self.table_name,
            "source_sha256": self.source_sha256,
            "parser_version": self.parser_version,
            "output": self.output,
            "output_rows": self.output_rows,
            "physical_rows": self.physical_rows,
            "data_rows": self.data_rows,
            "issue_count": self.issue_count,
            "issues": self.issues,
            "metadata": self.metadata,
            "duration_seconds": self.duration_seconds,
            "reused": self.reused,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _relative(path: Path) -> str:
    from .config import ROOT

    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _key(kind: str, accession: str, file_name: str, sheet: str | None = None) -> str:
    return "::".join([kind, accession, file_name, sheet or ""])


def _artifact_name(run_id: str) -> str:
    return slugify(run_id, max_length=120) + ".parquet"


def _load_previous_report() -> dict[str, dict[str, Any]]:
    if not PARSE_REPORT_JSON.exists():
        return {}
    try:
        report = json.loads(PARSE_REPORT_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    entries = {}
    for entry in report.get("sources", []):
        if isinstance(entry, dict) and entry.get("key"):
            entries[entry["key"]] = entry
    return entries


def _is_reusable(
    previous: dict[str, Any] | None,
    source: SourceFile,
    output: Path,
    table_name: str,
    parser: str,
) -> bool:
    if previous is None or not output.exists():
        return False
    return (
        previous.get("source_sha256") == source.sha256
        and previous.get("parser_version") == PARSER_VERSION
        and previous.get("table_name") == table_name
        and previous.get("parser") == parser
        and previous.get("output") == _relative(output)
        and previous.get("pipeline_version", PIPELINE_VERSION) == PIPELINE_VERSION
    )


def _batches(
    iterator: Iterable[dict[str, Any]], size: int = 50_000
) -> Iterator[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for item in iterator:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _source_index() -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, str]], dict[str, dict[str, Any]]]:
    manifest = read_manifest()
    acquisition = load_acquisition_index()
    by_id = {item["file_id"]: item for item in manifest["files"]}
    return manifest, acquisition, by_id


def _source(
    entry: dict[str, Any],
    acquisition: dict[tuple[str, str], dict[str, str]],
) -> SourceFile:
    return source_from_entry(entry, index=acquisition)


def _entry_from_parse_result(
    *,
    key: str,
    entry: dict[str, Any],
    source: SourceFile,
    result: Any,
    output: Path,
    output_rows: int,
    duration: float,
) -> ParseEntry:
    return ParseEntry(
        key=key,
        accession=source.accession,
        file_name=source.file_name,
        sheet=source.sheet,
        kind=entry["kind"],
        parser=result.parser_name,
        table_name=result.table_name,
        source_sha256=source.sha256,
        parser_version=result.parser_version,
        output=_relative(output),
        output_rows=output_rows,
        physical_rows=result.physical_rows,
        data_rows=result.data_rows,
        issue_count=len(result.issues),
        issues=[issue.as_dict() for issue in result.issues],
        metadata=result.metadata,
        duration_seconds=round(duration, 3),
    )


def _parse_gas_flame_sources(
    by_id: dict[str, dict[str, Any]],
    acquisition: dict[tuple[str, str], dict[str, str]],
) -> tuple[list[dict[str, Any]], list[ParseEntry], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    entries: list[ParseEntry] = []
    issues: list[dict[str, Any]] = []
    for (accession, file_name), spec in sorted(GAS_SPECS.items()):
        entry = by_id[f"{accession}::{file_name}"]
        source = _source(entry, acquisition)
        started = time.perf_counter()
        result = parse_gas_flame(source, spec)
        duration = time.perf_counter() - started
        records.extend(result.records)
        issues.extend(result.issues)
        entries.append(
            _entry_from_parse_result(
                key=_key("experimental_table", accession, file_name),
                entry=entry,
                source=source,
                result=result,
                output=INTERIM_DIR / "gas_flame_test.parquet",
                output_rows=len(result.records),
                duration=duration,
            )
        )
    output = INTERIM_DIR / "gas_flame_test.parquet"
    write_parquet(records, "gas_flame_test", output)
    for item in entries:
        item.output_rows = len(records)
    return records, entries, issues


def _parse_material_sources(
    by_id: dict[str, dict[str, Any]],
    acquisition: dict[tuple[str, str], dict[str, str]],
) -> tuple[list[ParseEntry], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    entries: list[ParseEntry] = []
    issues: list[dict[str, Any]] = []
    specs = (
        ("PSI-25", "PSI-25_Science Documents_BASS-II_Test.Matrices.xlsx", parse_psi25),
        ("PSI-26", "PSI-26_Science Documents_As Run_Test Matrix.xlsx", parse_psi26),
    )
    for accession, file_name, parser in specs:
        entry = by_id[f"{accession}::{file_name}"]
        source = _source(entry, acquisition)
        started = time.perf_counter()
        result = parser(source)
        duration = time.perf_counter() - started
        records.extend(result.records)
        issues.extend(result.issues)
        entries.append(
            _entry_from_parse_result(
                key=_key("material_workbook", accession, file_name),
                entry=entry,
                source=source,
                result=result,
                output=INTERIM_DIR / "material_test.parquet",
                output_rows=len(result.records),
                duration=duration,
            )
        )
    output = INTERIM_DIR / "material_test.parquet"
    write_parquet(records, "material_test", output)
    for item in entries:
        item.output_rows = len(records)
    return entries, issues


def _parse_single_source(
    *,
    key_kind: str,
    accession: str,
    file_name: str,
    table_name: str,
    output_name: str,
    parser: Callable[[SourceFile], Any],
    by_id: dict[str, dict[str, Any]],
    acquisition: dict[tuple[str, str], dict[str, str]],
) -> tuple[ParseEntry, list[dict[str, Any]]]:
    entry = by_id[f"{accession}::{file_name}"]
    source = _source(entry, acquisition)
    started = time.perf_counter()
    result = parser(source)
    duration = time.perf_counter() - started
    output = INTERIM_DIR / output_name
    write_parquet(result.records, table_name, output)
    parse_entry = _entry_from_parse_result(
        key=_key(key_kind, accession, file_name),
        entry=entry,
        source=source,
        result=result,
        output=output,
        output_rows=len(result.records),
        duration=duration,
    )
    return parse_entry, result.issues


def _parse_summary_sources(
    by_id: dict[str, dict[str, Any]],
    acquisition: dict[tuple[str, str], dict[str, str]],
) -> tuple[list[ParseEntry], list[dict[str, Any]]]:
    sources: dict[tuple[str, str], SourceFile] = {}
    entries: list[ParseEntry] = []
    for file_id, entry in by_id.items():
        if entry["kind"] != "experimental_table":
            continue
        sources[(entry["accession"], entry["file_name"])] = _source(entry, acquisition)
    started = time.perf_counter()
    result = parse_summary_tables(sources)
    duration = time.perf_counter() - started
    cells_path = INTERIM_DIR / "experimental_table_cell.parquet"
    rows_path = INTERIM_DIR / "source_row.parquet"
    write_parquet(result.cells, "experimental_table_cell", cells_path)
    write_parquet(result.source_rows, "source_row", rows_path)
    for table_id, schema in json.loads(
        ET_SCHEMAS_JSON.read_text(encoding="utf-8")
    )["tables"].items():
        source = sources[(schema["accession"], schema["file_name"])]
        table_issues = result.table_issues.get(table_id, [])
        entries.append(
            ParseEntry(
                key=_key(
                    "experimental_table",
                    schema["accession"],
                    schema["file_name"],
                ),
                accession=schema["accession"],
                file_name=schema["file_name"],
                sheet=None,
                kind="experimental_table",
                parser="summary_table",
                table_name="experimental_table_cell",
                source_sha256=source.sha256,
                parser_version=PARSER_VERSION,
                output=_relative(cells_path),
                output_rows=result.cell_count,
                physical_rows=schema["physical_rows"],
                data_rows=schema["data_rows"],
                issue_count=len(table_issues),
                issues=[issue.as_dict() for issue in table_issues],
                metadata={
                    "table_id": f"{schema['accession']}::{schema['file_name']}",
                    "cell_count": result.cell_count,
                    "source_row_count": result.source_row_count,
                    "source_row_output": _relative(rows_path),
                },
                duration_seconds=round(duration, 3),
            )
        )
    return entries, result.issues


def _parse_telemetry_sources(
    by_id: dict[str, dict[str, Any]],
    acquisition: dict[tuple[str, str], dict[str, str]],
    previous: dict[str, dict[str, Any]],
    force: bool,
) -> tuple[list[ParseEntry], list[dict[str, Any]]]:
    entries: list[ParseEntry] = []
    issues: list[dict[str, Any]] = []
    TELEMETRY_POINTS_DIR.mkdir(parents=True, exist_ok=True)
    run_records: list[dict[str, Any]] = []
    for spec in TELEMETRY_SPECS:
        entry = by_id[f"{spec.accession}::{spec.file_name}"]
        source = _source(entry, acquisition)
        key = _key("telemetry", spec.accession, spec.file_name, spec.sheet)
        output = TELEMETRY_POINTS_DIR / _artifact_name(spec.run_id)
        if (
            not force
            and previous.get(key, {}).get("metadata", {}).get("run_record_json")
            and _is_reusable(
                previous.get(key), source, output, "telemetry_point", "telemetry"
            )
        ):
            item = dict(previous[key])
            item["reused"] = True
            entries.append(ParseEntry(**{k: item[k] for k in ParseEntry.__dataclass_fields__ if k in item}))
            run_path = INTERIM_DIR / "telemetry_run.parquet"
            if run_path.exists():
                run_records.append(
                    json.loads(item.get("metadata", {}).get("run_record_json", "{}"))
                )
            continue
        started = time.perf_counter()
        scan = scan_telemetry(spec, source)
        result = write_parquet_batches(
            _batches(iter_telemetry_points(scan)),
            "telemetry_point",
            output,
        )
        duration = time.perf_counter() - started
        run_record = scan.as_run_record()
        run_records.append(run_record)
        parse_entry = ParseEntry(
            key=key,
            accession=spec.accession,
            file_name=spec.file_name,
            sheet=spec.sheet,
            kind="telemetry",
            parser="telemetry",
            table_name="telemetry_point",
            source_sha256=source.sha256,
            parser_version=PARSER_VERSION,
            output=_relative(output),
            output_rows=result.rows,
            physical_rows=scan.physical_rows,
            data_rows=scan.valid_rows,
            issue_count=0,
            issues=[],
            metadata={
                "export_kind": spec.export_kind,
                "run_id": spec.run_id,
                "channel_count": len(scan.channel_indices),
                "constant_channel_count": len(scan.constant_channels),
                "time_min_ms": scan.time_min_ms,
                "time_max_ms": scan.time_max_ms,
                "run_record_json": json.dumps(run_record, ensure_ascii=False),
            },
            duration_seconds=round(duration, 3),
        )
        entries.append(parse_entry)
    if run_records:
        write_parquet(run_records, "telemetry_run", INTERIM_DIR / "telemetry_run.parquet")
    return entries, issues


def _parse_smoke_sources(
    by_id: dict[str, dict[str, Any]],
    acquisition: dict[tuple[str, str], dict[str, str]],
    previous: dict[str, dict[str, Any]],
    force: bool,
) -> tuple[list[ParseEntry], list[dict[str, Any]]]:
    entries: list[ParseEntry] = []
    issues: list[dict[str, Any]] = []
    SMOKE_POINTS_DIR.mkdir(parents=True, exist_ok=True)
    run_records: list[dict[str, Any]] = []
    smoke_entries = [
        entry
        for entry in by_id.values()
        if entry["kind"] == "smoke_telemetry_csv"
    ]
    for entry in sorted(smoke_entries, key=lambda item: item["file_name"]):
        source = _source(entry, acquisition)
        key = _key("smoke", entry["accession"], entry["file_name"])
        output = SMOKE_POINTS_DIR / _artifact_name(f"PSI-101::{Path(entry['file_name']).stem}")
        if (
            not force
            and previous.get(key, {}).get("metadata", {}).get("run_record_json")
            and _is_reusable(
                previous.get(key), source, output, "smoke_point", "smoke"
            )
        ):
            item = dict(previous[key])
            item["reused"] = True
            entries.append(ParseEntry(**{k: item[k] for k in ParseEntry.__dataclass_fields__ if k in item}))
            issues.extend(item.get("issues", []))
            if item.get("metadata", {}).get("run_record_json"):
                run_records.append(json.loads(item["metadata"]["run_record_json"]))
            continue
        started = time.perf_counter()
        scan = scan_smoke(source)
        issues.extend(issue.as_dict() for issue in scan.issues)
        result = write_parquet_batches(
            _batches(iter_smoke_points(scan)),
            "smoke_point",
            output,
        )
        duration = time.perf_counter() - started
        run_record = scan.as_run_record()
        run_records.append(run_record)
        entries.append(
            ParseEntry(
                key=key,
                accession=entry["accession"],
                file_name=entry["file_name"],
                sheet=None,
                kind="smoke_telemetry_csv",
                parser="smoke",
                table_name="smoke_point",
                source_sha256=source.sha256,
                parser_version=PARSER_VERSION,
                output=_relative(output),
                output_rows=result.rows,
                physical_rows=scan.physical_rows,
                data_rows=scan.valid_rows,
                issue_count=len(scan.issues),
                issues=[issue.as_dict() for issue in scan.issues],
                metadata={
                    "run_id": scan.run_id,
                    "malformed_rows": scan.malformed_rows,
                    "channel_count": len(scan.stats),
                    "constant_channel_count": len(scan.constant_channels),
                    "sentinel_channel_count": len(scan.sentinel_channels),
                    "time_min_unix_s": scan.time_min_unix_s,
                    "time_max_unix_s": scan.time_max_unix_s,
                    "run_record_json": json.dumps(run_record, ensure_ascii=False),
                },
                duration_seconds=round(duration, 3),
            )
        )
    if run_records:
        write_parquet(run_records, "smoke_run", INTERIM_DIR / "smoke_run.parquet")
    return entries, issues


def parse_all(force: bool = False) -> dict[str, Any]:
    """Parse all selected sources and write interim Parquet tables."""

    ensure_directories()
    manifest, acquisition, by_id = _source_index()
    previous = _load_previous_report()
    started_at = utc_now_iso()
    started = time.perf_counter()
    all_entries: list[ParseEntry] = []
    all_issues: list[dict[str, Any]] = []

    gas_records, gas_entries, gas_issues = _parse_gas_flame_sources(by_id, acquisition)
    all_entries.extend(gas_entries)
    all_issues.extend(gas_issues)

    material_entries, material_issues = _parse_material_sources(by_id, acquisition)
    all_entries.extend(material_entries)
    all_issues.extend(material_issues)

    droplet_entry, droplet_issues = _parse_single_source(
        key_kind="experimental_table",
        accession="PSI-69",
        file_name="PSI-69_Experimental table_FLEX.csv",
        table_name="droplet_test",
        output_name="droplet_test.parquet",
        parser=parse_droplet,
        by_id=by_id,
        acquisition=acquisition,
    )
    all_entries.append(droplet_entry)
    all_issues.extend(droplet_issues)

    log_entry, log_issues = _parse_single_source(
        key_kind="test_log_xls",
        accession="PSI-102",
        file_name="PSI-102_Analyzed Data_Run 1 GMT252 testlog.xls",
        table_name="smoke_test_log",
        output_name="smoke_test_log.parquet",
        parser=parse_test_log,
        by_id=by_id,
        acquisition=acquisition,
    )
    all_entries.append(log_entry)
    all_issues.extend(log_issues)

    summary_entries, summary_issues = _parse_summary_sources(by_id, acquisition)
    all_entries.extend(summary_entries)
    all_issues.extend(summary_issues)

    telemetry_entries, telemetry_issues = _parse_telemetry_sources(
        by_id, acquisition, previous, force
    )
    all_entries.extend(telemetry_entries)
    all_issues.extend(telemetry_issues)

    smoke_entries, smoke_issues = _parse_smoke_sources(
        by_id, acquisition, previous, force
    )
    all_entries.extend(smoke_entries)
    all_issues.extend(smoke_issues)

    output_tables: dict[str, dict[str, Any]] = {}
    for path in sorted(INTERIM_DIR.glob("*.parquet")):
        metadata = pq.ParquetFile(path).metadata
        output_tables[path.name] = {
            "path": _relative(path),
            "rows": metadata.num_rows,
            "row_groups": metadata.num_row_groups,
            "bytes": path.stat().st_size,
        }
    for directory in (TELEMETRY_POINTS_DIR, SMOKE_POINTS_DIR):
        for path in sorted(directory.glob("*.parquet")):
            metadata = pq.ParquetFile(path).metadata
            output_tables[_relative(path)] = {
                "path": _relative(path),
                "rows": metadata.num_rows,
                "row_groups": metadata.num_row_groups,
                "bytes": path.stat().st_size,
            }

    report = {
        "schema_version": "1.0.0",
        "pipeline_version": PIPELINE_VERSION,
        "parser_version": PARSER_VERSION,
        "generated_at": utc_now_iso(),
        "started_at": started_at,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "manifest": "data/registry/download_manifest.json",
        "source_count": len(all_entries),
        "source_file_count": len(manifest["files"]),
        "reused_count": sum(1 for entry in all_entries if getattr(entry, "reused", False)),
        "issue_count": sum(entry.issue_count for entry in all_entries),
        "sources": [entry.as_dict() for entry in all_entries],
        "outputs": output_tables,
    }
    PARSE_REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    PARSE_REPORT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    PROCESSING_REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    return report
