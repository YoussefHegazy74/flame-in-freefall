"""Curated download manifest for the Phase 1 MVP acquisition.

The manifest is a committed, reviewable selection. It deliberately excludes
the multi-terabyte raw archives. The selection is:

* all 22 public experimental summary tables;
* the three published SAFFIRE-III telemetry exports (raw CSV, cleaned CSV,
  1 Hz XLSX);
* the complete SAME-R HKP CSV telemetry series (44 runs);
* the BASS-II and BASS as-run test-matrix workbooks;
* one small SAME legacy ``.xls`` test log to exercise the legacy reader.

Known 404 files are kept in a separate ``known_unavailable`` list so that the
downloader can verify and report the failure without treating it as a
successful acquisition.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .config import (
    ANNOTATIONS_JSON,
    DEFAULT_MAX_FILES,
    DEFAULT_MAX_SINGLE_FILE_BYTES,
    DEFAULT_MAX_TOTAL_BYTES,
    DOWNLOAD_MANIFEST_JSON,
    ET_CSV,
    MANIFEST_SCHEMA_VERSION,
    PSI_DOWNLOAD_BASE,
    REGISTRY_JSON,
)

MANIFEST_DATE = "2026-11-09"

# Checksums observed on the authenticated NASA files during Phase 0/1
# inspection. They are optional for raw files; the downloader always records
# the checksum it actually observes. Experimental tables have a committed
# checksum in ``annotations.json`` and are checked strictly.
KNOWN_SHA256: dict[tuple[str, str], str] = {
    (
        "PSI-100",
        "PSI-100_Raw Data_Raw telemetry file.csv",
    ): "dfb204ce3bdf8b1749652549afcbad31d180902bc268dfbe782c70fa38d170a2",
    (
        "PSI-100",
        "PSI-100_Raw Data_Saffire_Data_Table2017.161.00.42.03-EU.csv",
    ): "71f8d11a2e040c22924b1c6320384cdcf58e945fe66c993876c44158bf6f57c5",
    (
        "PSI-100",
        "PSI-100_Raw Data_Saffire-III 1 Hz Telemetry Data.xlsx",
    ): "a7737c73b8c6fcc5c7598772ee4b367856777fef45e727d68074872e2bdcd161",
    (
        "PSI-25",
        "PSI-25_Science Documents_BASS-II_Test.Matrices.xlsx",
    ): "1a3b283dd0adec861793bbc4a454aab64d398cd32d6f37d7a1ad0f642879e686",
    (
        "PSI-26",
        "PSI-26_Science Documents_As Run_Test Matrix.xlsx",
    ): "850910541fc9c802d00aa9de14758205103642184249b419c09868df2fbea6e8",
    (
        "PSI-101",
        "PSI-101_Raw Data_HKPData_gmt250_1.csv",
    ): "69c25a566b6af6b43fb263ceadad82499b6e18e69e5fdad928e8088124ee43a3",
    (
        "PSI-102",
        "PSI-102_Analyzed Data_Run 1 GMT252 testlog.xls",
    ): "12c59e279ae624cc0b8b57599072796f6c9fa56d6b08f493ff7e65486f91bb5a",
}

KNOWN_UNAVAILABLE = [
    {
        "accession": "PSI-98",
        "file_name": "PSI-98_Raw Data_Saffire-I Telemetry Data Good Process Version.xlsx",
        "expected_status": 404,
        "reason": (
            "Listed in the PSI added inventory but returns HTTP 404. "
            "No public replacement was identified; no synthetic substitute is used."
        ),
    },
    {
        "accession": "PSI-98",
        "file_name": "PSI-98_Raw Data_Saffire-I Sample 1 Sensor Data Complete TM graphs.xlsx",
        "expected_status": 404,
        "reason": (
            "Listed in the PSI added inventory but returns HTTP 404. "
            "No public replacement was identified; no synthetic substitute is used."
        ),
    },
]

PRIMARY_ACCESSIONS = {"PSI-10", "PSI-100", "PSI-101", "PSI-159"}

# Explicit raw selections. PSI-101 HKP files are expanded from the registry.
RAW_SELECTIONS: list[tuple[str, str, str, str, str]] = [
    (
        "PSI-100",
        "PSI-100_Raw Data_Raw telemetry file.csv",
        "telemetry_csv",
        "telemetry",
        "Primary SAFFIRE-III raw telemetry export (47 columns, 3,972 physical rows).",
    ),
    (
        "PSI-100",
        "PSI-100_Raw Data_Saffire_Data_Table2017.161.00.42.03-EU.csv",
        "telemetry_csv",
        "telemetry",
        "Primary SAFFIRE-III cleaned telemetry export (47 columns, 11,450 physical rows).",
    ),
    (
        "PSI-100",
        "PSI-100_Raw Data_Saffire-III 1 Hz Telemetry Data.xlsx",
        "telemetry_xlsx",
        "telemetry",
        "Primary SAFFIRE-III 1 Hz workbook; parsed by named sheet, never concatenated with the CSV exports.",
    ),
    (
        "PSI-25",
        "PSI-25_Science Documents_BASS-II_Test.Matrices.xlsx",
        "material_workbook",
        "material",
        "BASS-II six-sheet test matrix; context only, no flame-spread rate is derived.",
    ),
    (
        "PSI-26",
        "PSI-26_Science Documents_As Run_Test Matrix.xlsx",
        "material_workbook",
        "material",
        "BASS as-run test matrix; context only, no flame-spread rate is derived.",
    ),
    (
        "PSI-102",
        "PSI-102_Analyzed Data_Run 1 GMT252 testlog.xls",
        "test_log_xls",
        "xls_test_log",
        "Small legacy .xls test log used to exercise the xlrd reader and preserve a context test log.",
    ),
]

ET_PARSER: dict[str, tuple[str, str]] = {
    "PSI-10": ("gas_flame", "gas_flame_test"),
    "PSI-159": ("gas_flame", "gas_flame_test"),
    "PSI-69": ("droplet", "droplet_test"),
    "PSI-101": ("smoke_test_log", "smoke_test_log"),
}


class ManifestError(ValueError):
    """Raised when the committed manifest is inconsistent or unsafe."""


@dataclass(frozen=True)
class SelectedFile:
    file_id: str
    accession: str
    file_name: str
    kind: str
    parser: str
    dataset: str
    priority: str
    in_added: bool
    expected_bytes: int
    sha256_expected: str | None
    source_url: str
    purpose: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "file_id": self.file_id,
            "accession": self.accession,
            "file_name": self.file_name,
            "kind": self.kind,
            "parser": self.parser,
            "dataset": self.dataset,
            "priority": self.priority,
            "in_added": self.in_added,
            "expected_bytes": self.expected_bytes,
            "sha256_expected": self.sha256_expected,
            "source_url": self.source_url,
            "purpose": self.purpose,
        }


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_url(accession: str, file_name: str) -> str:
    """Return the public PSI download URL for an exact file name."""

    encoded = urllib.parse.quote(file_name, safe="")
    return f"{PSI_DOWNLOAD_BASE}/{accession}/download?file={encoded}"


def load_registry() -> dict[str, Any]:
    with REGISTRY_JSON.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _records_by_accession(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["accession"]: item for item in registry["investigations"]}


def _tabular_lookup(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for item in record.get("tabular_files", []):
        lookup[item["file_name"]] = item
    for item in record.get("experimental_tables", []):
        lookup.setdefault(item["file_name"], item)
    return lookup


def _load_et_rows() -> list[dict[str, str]]:
    with ET_CSV.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _priority(accession: str) -> str:
    return "primary" if accession in PRIMARY_ACCESSIONS else "supporting"


def _et_parser(accession: str) -> tuple[str, str]:
    return ET_PARSER.get(accession, ("summary", "experimental_table_cell"))


def build_manifest() -> dict[str, Any]:
    """Build the deterministic manifest from the committed registry."""

    registry = load_registry()
    records = _records_by_accession(registry)
    et_rows = _load_et_rows()

    selected: list[SelectedFile] = []
    seen: set[str] = set()

    for row in et_rows:
        accession = row["accession"]
        file_name = row["file_name"]
        if accession not in records:
            raise ManifestError(f"{accession} is not in the registry")
        parser, dataset = _et_parser(accession)
        expected_bytes = int(row["file_size_bytes"])
        checksum = row.get("sha256") or None
        entry = SelectedFile(
            file_id=f"{accession}::{file_name}",
            accession=accession,
            file_name=file_name,
            kind="experimental_table",
            parser=parser,
            dataset=dataset,
            priority=_priority(accession),
            in_added=row["in_added"].strip().lower() == "true",
            expected_bytes=expected_bytes,
            sha256_expected=checksum,
            source_url=download_url(accession, file_name),
            purpose=(
                "Public experimental summary table. The exact source table is "
                "preserved; no archive files are implied for experimental_table_only records."
            ),
        )
        if entry.file_id in seen:
            raise ManifestError(f"duplicate manifest entry: {entry.file_id}")
        seen.add(entry.file_id)
        selected.append(entry)

    raw_candidates = list(RAW_SELECTIONS)
    for item in records["PSI-101"].get("tabular_files", []):
        name = item["file_name"]
        if name.startswith("PSI-101_Raw Data_HKPData_") and name.endswith(".csv"):
            raw_candidates.append(
                (
                    "PSI-101",
                    name,
                    "smoke_telemetry_csv",
                    "smoke",
                    "SAME-R HKP housekeeping/telemetry run; smoke and aerosol channels are parsed with sentinel and constant-channel flags.",
                )
            )

    for accession, file_name, kind, parser, purpose in raw_candidates:
        record = records.get(accession)
        if record is None:
            raise ManifestError(f"{accession} is not in the registry")
        tabular = _tabular_lookup(record)
        source = tabular.get(file_name)
        if source is None:
            raise ManifestError(f"{accession} does not list {file_name!r} as a tabular file")
        expected_bytes = int(source["bytes"])
        entry = SelectedFile(
            file_id=f"{accession}::{file_name}",
            accession=accession,
            file_name=file_name,
            kind=kind,
            parser=parser,
            dataset=(
                "telemetry_run,telemetry_point"
                if parser == "telemetry"
                else "smoke_run,smoke_point"
                if parser == "smoke"
                else "material_test"
                if parser == "material"
                else "source_row"
            ),
            priority=_priority(accession),
            in_added=True,
            expected_bytes=expected_bytes,
            sha256_expected=KNOWN_SHA256.get((accession, file_name)),
            source_url=download_url(accession, file_name),
            purpose=purpose,
        )
        if entry.file_id in seen:
            raise ManifestError(f"duplicate manifest entry: {entry.file_id}")
        seen.add(entry.file_id)
        selected.append(entry)

    selected.sort(key=lambda item: (item.priority != "primary", item.accession, item.file_name))
    total_bytes = sum(item.expected_bytes for item in selected)
    et_count = sum(1 for item in selected if item.kind == "experimental_table")

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_date": MANIFEST_DATE,
        "source": {
            "registry": "data/registry/psi_combustion_investigations.json",
            "annotations": "data/registry/annotations.json",
            "experimental_tables": "data/registry/psi_experimental_tables.csv",
            "nasa_psi": "https://psi.nasa.gov/physci/repo",
            "download_endpoint": f"{PSI_DOWNLOAD_BASE}/{{accession}}/download?file={{file_name}}",
        },
        "selection_policy": [
            "All 22 public experimental summary tables are selected.",
            "No raw archive file is selected unless it is explicitly listed in this manifest.",
            "The 13.5 TB registered archive is never downloaded wholesale.",
            "PSI-100 raw CSV, cleaned CSV, and 1 Hz XLSX are kept as separate exports and are never concatenated.",
            "All 44 SAME-R HKP CSV runs are selected as a coherent telemetry series; analyzed .xls files are excluded.",
            "BASS-II and BASS workbooks are experimental context only. No flame-spread rate is claimed.",
            "Files known to return HTTP 404 are listed under known_unavailable, not in files.",
            "Every selected file must pass an expected-size check and a SHA-256 record.",
        ],
        "limits": {
            "max_files": DEFAULT_MAX_FILES,
            "max_single_file_bytes": DEFAULT_MAX_SINGLE_FILE_BYTES,
            "max_total_bytes": DEFAULT_MAX_TOTAL_BYTES,
            "min_free_disk_multiplier": 1.2,
        },
        "totals": {
            "selected_files": len(selected),
            "selected_bytes": total_bytes,
            "selected_gb_decimal": round(total_bytes / 1_000_000_000, 6),
            "experimental_tables": et_count,
            "primary_files": sum(1 for item in selected if item.priority == "primary"),
            "supporting_files": sum(1 for item in selected if item.priority == "supporting"),
        },
        "files": [item.as_dict() for item in selected],
        "known_unavailable": KNOWN_UNAVAILABLE,
    }
    validate_manifest(manifest, registry=registry)
    return manifest


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_manifest(
    manifest: dict[str, Any], registry: dict[str, Any] | None = None
) -> None:
    """Validate manifest structure, selection, limits, and ET completeness."""

    errors: list[str] = []
    registry = registry or load_registry()
    records = _records_by_accession(registry)
    et_rows = _load_et_rows()

    _require(
        manifest.get("schema_version") == MANIFEST_SCHEMA_VERSION,
        "schema_version does not match the current manifest schema",
        errors,
    )
    files = manifest.get("files")
    _require(isinstance(files, list) and bool(files), "files must be a non-empty list", errors)
    if not isinstance(files, list):
        raise ManifestError("; ".join(errors))

    seen: set[str] = set()
    seen_pair: set[tuple[str, str]] = set()
    total_bytes = 0
    for item in files:
        required = {
            "file_id",
            "accession",
            "file_name",
            "kind",
            "parser",
            "dataset",
            "priority",
            "in_added",
            "expected_bytes",
            "sha256_expected",
            "source_url",
            "purpose",
        }
        missing = required - set(item)
        _require(not missing, f"{item.get('file_id', '?')}: missing keys {sorted(missing)}", errors)
        file_id = item.get("file_id", "")
        _require(file_id not in seen, f"duplicate file_id {file_id!r}", errors)
        seen.add(file_id)
        pair = (item.get("accession", ""), item.get("file_name", ""))
        _require(pair not in seen_pair, f"duplicate accession/file pair {pair!r}", errors)
        seen_pair.add(pair)
        accession = item.get("accession", "")
        _require(accession in records, f"{file_id}: unknown accession {accession!r}", errors)
        expected = item.get("expected_bytes")
        _require(
            isinstance(expected, int) and expected > 0,
            f"{file_id}: expected_bytes must be a positive integer",
            errors,
        )
        if isinstance(expected, int):
            total_bytes += expected
            _require(
                expected <= int(manifest["limits"]["max_single_file_bytes"]),
                f"{file_id}: expected_bytes {expected} exceeds max_single_file_bytes",
                errors,
            )
        checksum = item.get("sha256_expected")
        _require(
            checksum is None or (isinstance(checksum, str) and re.fullmatch(r"[0-9a-f]{64}", checksum) is not None),
            f"{file_id}: sha256_expected must be null or 64 lowercase hex characters",
            errors,
        )
        source_url = item.get("source_url", "")
        _require(
            source_url.startswith(f"{PSI_DOWNLOAD_BASE}/{accession}/download?file="),
            f"{file_id}: source_url does not use the verified PSI download endpoint",
            errors,
        )
        _require(item.get("priority") in {"primary", "supporting"}, f"{file_id}: invalid priority", errors)

    _require(
        len(files) <= int(manifest["limits"]["max_files"]),
        "selected file count exceeds max_files",
        errors,
    )
    _require(
        total_bytes <= int(manifest["limits"]["max_total_bytes"]),
        f"selected bytes {total_bytes} exceed max_total_bytes",
        errors,
    )
    _require(
        manifest.get("totals", {}).get("selected_files") == len(files),
        "totals.selected_files does not match the file list",
        errors,
    )
    _require(
        manifest.get("totals", {}).get("selected_bytes") == total_bytes,
        "totals.selected_bytes does not match the file list",
        errors,
    )

    expected_et_ids = {
        f"{row['accession']}::{row['file_name']}" for row in et_rows
    }
    actual_et_ids = {
        item["file_id"] for item in files if item.get("kind") == "experimental_table"
    }
    _require(
        expected_et_ids == actual_et_ids,
        "experimental_table selection does not match the 22-row ET registry",
        errors,
    )
    _require(
        len(actual_et_ids) == 22,
        f"expected 22 experimental tables, found {len(actual_et_ids)}",
        errors,
    )

    annotations = json.loads(ANNOTATIONS_JSON.read_text(encoding="utf-8"))
    for item in files:
        if item.get("kind") != "experimental_table":
            continue
        stats = annotations.get(item["accession"], {}).get("table_stats", {})
        expected_checksum = stats.get(item["file_name"], {}).get("sha256")
        _require(
            expected_checksum == item.get("sha256_expected"),
            f"{item['file_id']}: experimental-table checksum does not match annotations.json",
            errors,
        )

    known = manifest.get("known_unavailable", [])
    _require(isinstance(known, list), "known_unavailable must be a list", errors)
    for item in known if isinstance(known, list) else []:
        _require(
            item.get("expected_status") == 404,
            f"known_unavailable {item.get('file_name')}: expected_status must be 404",
            errors,
        )
        _require(
            item.get("accession") in records,
            f"known_unavailable {item.get('file_name')}: unknown accession",
            errors,
        )

    if errors:
        raise ManifestError("\n".join(errors))


def write_manifest_json(manifest: dict[str, Any], path: Path = DOWNLOAD_MANIFEST_JSON) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


CSV_COLUMNS = [
    "file_id",
    "accession",
    "file_name",
    "kind",
    "parser",
    "dataset",
    "priority",
    "expected_bytes",
    "sha256_expected",
    "source_url",
    "status",
    "http_status",
    "bytes_downloaded",
    "sha256_actual",
    "retrieved_at",
    "attempts",
    "error",
]


def write_manifest_csv(manifest: dict[str, Any], path: Path, status: str = "pending") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for item in manifest["files"]:
            row = {key: item.get(key, "") for key in CSV_COLUMNS}
            row["status"] = status
            row["http_status"] = ""
            row["bytes_downloaded"] = ""
            row["sha256_actual"] = ""
            row["retrieved_at"] = ""
            row["attempts"] = ""
            row["error"] = ""
            writer.writerow(row)


def read_manifest(path: Path = DOWNLOAD_MANIFEST_JSON) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    validate_manifest(manifest)
    return manifest


def iter_files(manifest: dict[str, Any]) -> Iterable[dict[str, Any]]:
    return iter(manifest["files"])
