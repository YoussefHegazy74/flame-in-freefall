"""Stable citation records for curated source files and source rows.

Citations are derived only from committed acquisition metadata and canonical
provenance. A citation never contains a filesystem path, and a file is only
marked downloadable when the acquisition record says it was retrieved and its
actual checksum matches the manifest checksum.

The two PSI-98 telemetry/sensor workbooks are retained as documented
``unavailable`` records because the public API returns HTTP 404 for them.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

from src.analytics.errors import AnalyticsError, InvalidQueryError, NotFoundError
from src.analytics.registry import RegistryBundle, repo_root

CITATION_SCHEMA_VERSION = "1.0.0"
AVAILABLE_DOWNLOAD_STATUSES = {"downloaded", "already_present"}


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise AnalyticsError(
            f"{label} is not available",
            details={"path": path.name},
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AnalyticsError(
            f"{label} could not be read",
            details={"path": path.name, "error_type": type(exc).__name__},
        ) from exc
    if not isinstance(payload, dict):
        raise AnalyticsError(f"{label} must be a JSON object", details={"path": path.name})
    return payload


def _sha16(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def file_citation_id(accession: str, file_name: str) -> str:
    """Deterministic, stable file-level citation identifier."""

    return f"cit_f_{_sha16(accession + chr(0) + file_name)}"


def row_citation_id(
    accession: str,
    file_name: str,
    sheet: str | None,
    row: int,
) -> str:
    """Deterministic, reversible row-level citation identifier."""

    payload = json.dumps(
        {"a": accession, "f": file_name, "s": sheet, "r": int(row)},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"cit_r_{encoded}"


def decode_row_citation_id(citation_id: str) -> dict[str, Any]:
    """Decode a row citation identifier, rejecting malformed values."""

    if not citation_id.startswith("cit_r_"):
        raise InvalidQueryError("not a row citation identifier")
    encoded = citation_id[len("cit_r_") :]
    padding = "=" * (-len(encoded) % 4)
    try:
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidQueryError("row citation identifier is malformed") from exc
    if not isinstance(payload, dict):
        raise InvalidQueryError("row citation identifier is malformed")
    accession = payload.get("a")
    file_name = payload.get("f")
    sheet = payload.get("s")
    row = payload.get("r")
    if (
        not isinstance(accession, str)
        or not accession
        or not isinstance(file_name, str)
        or not file_name
        or not isinstance(row, int)
        or row < 1
        or (sheet is not None and not isinstance(sheet, str))
    ):
        raise InvalidQueryError("row citation identifier is malformed")
    if any(token in file_name for token in ("/", "\\", "..")):
        raise InvalidQueryError("row citation identifier contains an unsafe file name")
    return {"accession": accession, "file": file_name, "sheet": sheet, "row": row}


@dataclass(frozen=True)
class CitationRegistry:
    """Index of file-level citations built from committed metadata."""

    files: dict[str, dict[str, Any]]
    by_accession_file: dict[tuple[str, str], str]
    manifest_version: str | None

    @property
    def citation_ids(self) -> list[str]:
        return sorted(self.files)

    def get(self, citation_id: str) -> dict[str, Any]:
        citation = self.files.get(citation_id)
        if citation is None:
            raise NotFoundError(
                "citation is not present in the curated source registry",
                details={"citation_id": citation_id},
            )
        return citation

    def for_file(self, accession: str, file_name: str) -> dict[str, Any] | None:
        citation_id = self.by_accession_file.get((accession, file_name))
        if citation_id is None:
            return None
        return self.files.get(citation_id)

    def list(
        self,
        *,
        accession: str | None = None,
        dataset_id: str | None = None,
        kind: str | None = None,
        verification_status: str | None = None,
        availability: str | None = None,
    ) -> list[dict[str, Any]]:
        result = []
        for citation in self.files.values():
            if accession and citation["accession"] != accession:
                continue
            if dataset_id and dataset_id not in citation.get("dataset_ids", []):
                continue
            if kind and citation["file"].get("kind") != kind:
                continue
            if (
                verification_status
                and citation["verification"]["status"] != verification_status
            ):
                continue
            if availability and citation["availability"]["status"] != availability:
                continue
            result.append(citation)
        return sorted(result, key=lambda item: (item["accession"], item["file"]["name"]))


def _dataset_links(
    accession: str,
    manifest_dataset: str | None,
    file_kind: str,
    bundle: RegistryBundle,
) -> list[str]:
    linked = []
    datasets = [d for d in bundle.datasets.values() if d["accession"] == accession]
    if not datasets:
        return []
    if file_kind in {"experimental_table", "raw_data"}:
        return sorted(dataset["dataset_id"] for dataset in datasets)
    requested = {part.strip() for part in (manifest_dataset or "").split(",") if part.strip()}
    for dataset in datasets:
        if requested & set(dataset.get("canonical_tables", [])):
            linked.append(dataset["dataset_id"])
    return sorted(linked)


def _checksum_verification(
    expected: str | None,
    actual: str | None,
    *,
    download_status: str,
) -> dict[str, Any]:
    checks = []
    if expected:
        checks.append("manifest_checksum_recorded")
    if actual:
        checks.append("retrieved_checksum_recorded")
    if expected and actual:
        checks.append(
            "checksum_matches_manifest"
            if expected == actual
            else "checksum_differs_from_manifest"
        )
    if download_status in AVAILABLE_DOWNLOAD_STATUSES:
        checks.append("acquisition_status_confirmed")
    if not expected:
        checks.append("manifest_checksum_missing")
    if not actual:
        checks.append("retrieved_checksum_missing")
    if expected and actual and expected == actual and download_status in AVAILABLE_DOWNLOAD_STATUSES:
        status = "verified"
    elif actual or expected:
        status = "partial"
    else:
        status = "unverified"
    return {"status": status, "checks": checks}


def load_citation_registry(
    bundle: RegistryBundle,
    *,
    root: Path | str | None = None,
) -> CitationRegistry:
    base = Path(root).expanduser().resolve() if root else repo_root()
    manifest = _load_json(base / "data" / "registry" / "download_manifest.json", "download manifest")
    acquisition = _load_json(
        base / "data" / "reports" / "acquisition_report.json",
        "acquisition report",
    )
    investigations = _load_json(
        base / "data" / "registry" / "psi_combustion_investigations.json",
        "investigation registry",
    )
    download_template = (
        (investigations.get("source") or {}).get("download_endpoint_template")
        or "https://psi.nasa.gov/geode-py/ws/studies/{accession}/download?file={filename}"
    )
    results = {
        result.get("file_id"): result
        for result in acquisition.get("results", [])
        if isinstance(result, dict) and result.get("file_id")
    }

    files: dict[str, dict[str, Any]] = {}
    by_accession_file: dict[tuple[str, str], str] = {}

    for entry in manifest.get("files", []):
        if not isinstance(entry, dict):
            continue
        accession = str(entry.get("accession") or "")
        file_name = str(entry.get("file_name") or "")
        if not accession or not file_name:
            continue
        result = results.get(entry.get("file_id")) or {}
        download_status = str(result.get("status") or "not_acquired")
        actual_sha = result.get("sha256_actual")
        expected_sha = entry.get("sha256_expected")
        verification = _checksum_verification(
            expected_sha, actual_sha, download_status=download_status
        )
        available = download_status in AVAILABLE_DOWNLOAD_STATUSES
        downloadable = bool(
            available
            and verification["status"] == "verified"
            and actual_sha
        )
        citation_id = file_citation_id(accession, file_name)
        dataset_ids = _dataset_links(
            accession, entry.get("dataset"), str(entry.get("kind") or ""), bundle
        )
        reason = None
        if not available:
            reason = "The acquisition report does not confirm a retrieved copy."
        elif verification["status"] != "verified":
            reason = "The retrieved checksum does not match the manifest checksum."
        citation = {
            "citation_id": citation_id,
            "kind": "file",
            "accession": accession,
            "dataset_ids": dataset_ids,
            "file": {
                "name": file_name,
                "kind": entry.get("kind"),
                "manifest_dataset": entry.get("dataset"),
                "priority": entry.get("priority"),
                "purpose": entry.get("purpose"),
                "in_added": entry.get("in_added"),
            },
            "locator": {"type": "file", "sheet": None, "row": None},
            "source": {
                "kind": "nasa_psi_file",
                "accession": accession,
                "file_name": file_name,
                "sha256": actual_sha or expected_sha,
                "source_url": entry.get("source_url")
                or download_template.format(
                    accession=accession, filename=quote(file_name, safe="")
                ),
            },
            "retrieval": {
                "retrieved_at": result.get("retrieved_at"),
                "http_status": result.get("http_status"),
                "download_status": download_status,
                "bytes": result.get("bytes_downloaded")
                if result.get("bytes_downloaded") is not None
                else entry.get("expected_bytes"),
                "expected_bytes": entry.get("expected_bytes"),
                "checksum_expected": expected_sha,
                "checksum_actual": actual_sha,
                "checksum_match": (
                    expected_sha == actual_sha
                    if expected_sha and actual_sha
                    else None
                ),
            },
            "verification": verification,
            "availability": {
                "status": "available" if available else "unavailable",
                "downloadable": downloadable,
                "reason": reason,
            },
            "provenance": [
                {
                    "kind": "nasa_psi_file",
                    "accession": accession,
                    "file_name": file_name,
                    "sha256": actual_sha or expected_sha,
                    "source_url": entry.get("source_url"),
                }
            ],
        }
        files[citation_id] = citation
        by_accession_file[(accession, file_name)] = citation_id

    known_unavailable = acquisition.get("known_unavailable", [])
    for item in known_unavailable:
        if not isinstance(item, dict):
            continue
        accession = str(item.get("accession") or "")
        file_name = str(item.get("file_name") or "")
        if not accession or not file_name:
            continue
        citation_id = file_citation_id(accession, file_name)
        if citation_id in files:
            continue
        source_url = download_template.format(
            accession=accession, filename=quote(file_name, safe="")
        )
        dataset_ids = _dataset_links(accession, None, "raw_data", bundle)
        files[citation_id] = {
            "citation_id": citation_id,
            "kind": "file",
            "accession": accession,
            "dataset_ids": dataset_ids,
            "file": {
                "name": file_name,
                "kind": "raw_data",
                "manifest_dataset": None,
                "priority": None,
                "purpose": "Listed by the public PSI inventory; the download endpoint returns HTTP 404.",
                "in_added": True,
            },
            "locator": {"type": "file", "sheet": None, "row": None},
            "source": {
                "kind": "nasa_psi_file",
                "accession": accession,
                "file_name": file_name,
                "sha256": None,
                "source_url": source_url,
            },
            "retrieval": {
                "retrieved_at": acquisition.get("generated_at"),
                "http_status": item.get("observed_status"),
                "download_status": "known_unavailable",
                "bytes": None,
                "expected_bytes": None,
                "checksum_expected": None,
                "checksum_actual": None,
                "checksum_match": None,
            },
            "verification": {
                "status": "unavailable",
                "checks": [
                    "public_inventory_listing_recorded",
                    "download_probe_returned_http_404",
                ],
            },
            "availability": {
                "status": "unavailable",
                "downloadable": False,
                "reason": "The public download endpoint returns HTTP 404; no file is available to download.",
            },
            "provenance": [
                {
                    "kind": "nasa_psi_file",
                    "accession": accession,
                    "file_name": file_name,
                    "sha256": None,
                    "source_url": source_url,
                }
            ],
        }
        by_accession_file[(accession, file_name)] = citation_id

    return CitationRegistry(
        files=files,
        by_accession_file=by_accession_file,
        manifest_version=str(manifest.get("manifest_version") or manifest.get("schema_version") or ""),
    )


def attach_file_citation_ids(citations: CitationRegistry, entries: Iterable[dict[str, Any]]) -> None:
    """Attach a file citation ID to provenance-style entries in place."""

    for entry in entries:
        accession = entry.get("accession")
        file_name = entry.get("file")
        if not accession or not file_name:
            continue
        citation = citations.for_file(str(accession), str(file_name))
        if citation is not None:
            entry["citation_id"] = citation["citation_id"]
