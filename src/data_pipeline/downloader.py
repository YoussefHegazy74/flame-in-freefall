"""Resumable, checksum-verifying downloader for the curated NASA PSI manifest.

Design rules:

* never download anything that is not in the committed manifest;
* stream to a ``.part`` file and rename atomically after verification;
* verify expected size, HTTP content length, and SHA-256;
* record 404s as ``listed_404`` instead of silently skipping them;
* never bypass authentication or access controls;
* never write outside ``data/raw/<accession>/``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import (
    ACQUISITION_REPORT_JSON,
    DEFAULT_BACKOFF_SECONDS,
    DEFAULT_MAX_FILES,
    DEFAULT_MAX_SINGLE_FILE_BYTES,
    DEFAULT_MAX_TOTAL_BYTES,
    DEFAULT_RATE_LIMIT_SECONDS,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT_SECONDS,
    DOWNLOAD_MANIFEST_CSV,
    MANIFESTS_DIR,
    MIN_FREE_DISK_MULTIPLIER,
    RAW_DIR,
    ensure_directories,
)
from .manifest import CSV_COLUMNS, read_manifest

USER_AGENT = "FlameInFreefall/1.0 (NASA Space Apps Challenge research; public PSI download)"
CHUNK_SIZE = 1024 * 1024
ACCESSION_RE = re.compile(r"^PSI-\d+$")


class DownloadError(RuntimeError):
    """Base class for acquisition failures."""


class DownloadLimitError(DownloadError):
    """Raised when the selection exceeds a hard safety limit."""


class InsufficientDiskSpace(DownloadError):
    """Raised when free disk space is below the required safety margin."""


class UnsafePathError(DownloadError):
    """Raised when a manifest file name could escape the raw directory."""


@dataclass
class DownloadResult:
    file_id: str
    accession: str
    file_name: str
    status: str
    http_status: int | None = None
    bytes_downloaded: int = 0
    sha256_actual: str | None = None
    retrieved_at: str | None = None
    attempts: int = 0
    error: str | None = None
    path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "file_id": self.file_id,
            "accession": self.accession,
            "file_name": self.file_name,
            "status": self.status,
            "http_status": self.http_status,
            "bytes_downloaded": self.bytes_downloaded,
            "sha256_actual": self.sha256_actual,
            "retrieved_at": self.retrieved_at,
            "attempts": self.attempts,
            "error": self.error,
            "path": self.path,
        }


@dataclass
class KnownUnavailableResult:
    accession: str
    file_name: str
    expected_status: int
    observed_status: int | None
    status: str
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "accession": self.accession,
            "file_name": self.file_name,
            "expected_status": self.expected_status,
            "observed_status": self.observed_status,
            "status": self.status,
            "error": self.error,
        }


@dataclass
class AcquisitionReport:
    schema_version: str
    generated_at: str
    manifest: str
    selected_datasets: list[str]
    selected_files: int
    selected_bytes: int
    limits: dict[str, Any]
    disk_free_before: int
    disk_free_after: int
    results: list[DownloadResult] = field(default_factory=list)
    known_unavailable: list[KnownUnavailableResult] = field(default_factory=list)
    duplicate_checksums: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for result in self.results:
            counts[result.status] = counts.get(result.status, 0) + 1
        total_bytes = sum(
            result.bytes_downloaded
            for result in self.results
            if result.status == "downloaded"
        )
        return {
            **{key: counts.get(key, 0) for key in (
                "downloaded",
                "already_present",
                "listed_404",
                "failed",
                "approval_required",
                "not_selected",
            )},
            "total_bytes_downloaded": total_bytes,
            "known_unavailable_verified": sum(
                1 for item in self.known_unavailable if item.status == "listed_404"
            ),
            "known_unavailable_unexpected": sum(
                1
                for item in self.known_unavailable
                if item.status not in {"listed_404", "failed"}
            ),
            "duplicate_checksum_groups": len(self.duplicate_checksums),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "manifest": self.manifest,
            "selection": {
                "datasets": self.selected_datasets,
                "selected_files": self.selected_files,
                "selected_bytes": self.selected_bytes,
            },
            "limits": self.limits,
            "disk": {
                "free_before_bytes": self.disk_free_before,
                "free_after_bytes": self.disk_free_after,
            },
            "summary": self.summary(),
            "results": [item.as_dict() for item in self.results],
            "known_unavailable": [item.as_dict() for item in self.known_unavailable],
            "duplicate_checksums": self.duplicate_checksums,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_target_path(raw_dir: Path, accession: str, file_name: str) -> Path:
    """Return a path under ``raw_dir/<accession>/`` or raise ``UnsafePathError``."""

    if not ACCESSION_RE.fullmatch(accession):
        raise UnsafePathError(f"invalid accession {accession!r}")
    if not file_name or file_name in {".", ".."}:
        raise UnsafePathError("empty file name")
    if "/" in file_name or "\\" in file_name or Path(file_name).name != file_name:
        raise UnsafePathError(f"file name contains a path separator: {file_name!r}")
    if ".." in Path(file_name).parts:
        raise UnsafePathError(f"file name contains a parent reference: {file_name!r}")
    target = (raw_dir / accession / file_name).resolve()
    root = (raw_dir / accession).resolve()
    if root not in target.parents and target != root:
        raise UnsafePathError(f"target escapes raw directory: {target}")
    return target


def select_entries(
    manifest: dict[str, Any], datasets: Iterable[str] | None = None
) -> list[dict[str, Any]]:
    """Select manifest entries by accession. ``None`` or ``all`` selects everything."""

    requested = [item.strip() for item in (datasets or []) if item and item.strip()]
    if not requested or "all" in requested:
        return list(manifest["files"])
    unknown = sorted(set(requested) - {item["accession"] for item in manifest["files"]})
    if unknown:
        raise DownloadError(f"datasets not present in the manifest: {', '.join(unknown)}")
    wanted = set(requested)
    return [item for item in manifest["files"] if item["accession"] in wanted]


def check_limits(
    entries: list[dict[str, Any]],
    max_single_file_bytes: int = DEFAULT_MAX_SINGLE_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    max_files: int = DEFAULT_MAX_FILES,
    allow_large: bool = False,
) -> list[dict[str, Any]]:
    """Check hard limits. Return entries requiring explicit approval.

    ``allow_large`` is the explicit approval switch for a single file above the
    default per-file cap. The total cap is still enforced.
    """

    if len(entries) > max_files:
        raise DownloadLimitError(
            f"selection has {len(entries)} files, above max_files={max_files}"
        )
    total = sum(int(item["expected_bytes"]) for item in entries)
    if total > max_total_bytes:
        raise DownloadLimitError(
            f"selection is {total} bytes, above max_total_bytes={max_total_bytes}; "
            "raise the limit only after reviewing the selection"
        )
    oversized = [
        item
        for item in entries
        if int(item["expected_bytes"]) > max_single_file_bytes
    ]
    if oversized and not allow_large:
        return oversized
    return []


def check_disk_space(raw_dir: Path, required_bytes: int) -> int:
    raw_dir.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(raw_dir).free
    required = int(required_bytes * MIN_FREE_DISK_MULTIPLIER)
    if free < required:
        raise InsufficientDiskSpace(
            f"free disk space {free} bytes is below the required {required} bytes "
            f"for a {required_bytes}-byte selection"
        )
    return free


def _parse_content_range(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"bytes\s+\d+-\d+/(\d+|\*)", value.strip())
    if not match or match.group(1) == "*":
        return None
    return int(match.group(1))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _existing_result(entry: dict[str, Any], target: Path) -> DownloadResult | None:
    if not target.exists():
        return None
    actual_size = target.stat().st_size
    actual_sha = _sha256_file(target)
    expected_size = int(entry["expected_bytes"])
    expected_sha = entry.get("sha256_expected")
    if actual_size != expected_size:
        return DownloadResult(
            file_id=entry["file_id"],
            accession=entry["accession"],
            file_name=entry["file_name"],
            status="failed",
            bytes_downloaded=actual_size,
            sha256_actual=actual_sha,
            error=(
                f"existing file size {actual_size} does not match expected {expected_size}; "
                "use --force to replace it"
            ),
            path=str(target),
        )
    if expected_sha and actual_sha != expected_sha:
        return DownloadResult(
            file_id=entry["file_id"],
            accession=entry["accession"],
            file_name=entry["file_name"],
            status="failed",
            bytes_downloaded=actual_size,
            sha256_actual=actual_sha,
            error=(
                "existing file checksum does not match the committed checksum; "
                "use --force to replace it"
            ),
            path=str(target),
        )
    return DownloadResult(
        file_id=entry["file_id"],
        accession=entry["accession"],
        file_name=entry["file_name"],
        status="already_present",
        http_status=None,
        bytes_downloaded=actual_size,
        sha256_actual=actual_sha,
        retrieved_at=datetime.fromtimestamp(
            target.stat().st_mtime, tz=timezone.utc
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        attempts=0,
        path=str(target),
    )


def _open_url(url: str, timeout: int, offset: int = 0):
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(url, headers=headers, method="GET")
    return urllib.request.urlopen(request, timeout=timeout)


def download_one(
    entry: dict[str, Any],
    raw_dir: Path = RAW_DIR,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF_SECONDS,
    rate_limit: float = DEFAULT_RATE_LIMIT_SECONDS,
    force: bool = False,
) -> DownloadResult:
    """Download one manifest entry with resume, retries, and verification."""

    target = safe_target_path(raw_dir, entry["accession"], entry["file_name"])
    target.parent.mkdir(parents=True, exist_ok=True)

    if not force:
        existing = _existing_result(entry, target)
        if existing is not None:
            return existing
    elif target.exists():
        target.unlink()

    part = target.with_name(target.name + ".part")
    if force and part.exists():
        part.unlink()

    expected_bytes = int(entry["expected_bytes"])
    expected_sha = entry.get("sha256_expected")
    last_error: str | None = None
    last_http: int | None = None
    attempts = 0

    for attempt in range(1, retries + 1):
        attempts = attempt
        offset = part.stat().st_size if part.exists() and not force else 0
        if offset > expected_bytes:
            part.unlink()
            offset = 0
        try:
            with _open_url(entry["source_url"], timeout=timeout, offset=offset) as response:
                http_status = getattr(response, "status", None) or response.getcode()
                last_http = http_status
                content_length = response.headers.get("Content-Length")
                content_range = response.headers.get("Content-Range")
                total_from_range = _parse_content_range(content_range)

                mode = "ab" if http_status == 206 and offset else "wb"
                if mode == "wb":
                    offset = 0
                digest = hashlib.sha256()
                if mode == "ab":
                    with part.open("rb") as existing:
                        for chunk in iter(lambda: existing.read(CHUNK_SIZE), b""):
                            digest.update(chunk)
                written = offset
                with part.open(mode) as handle:
                    while True:
                        chunk = response.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        handle.write(chunk)
                        digest.update(chunk)
                        written += len(chunk)

                actual_sha = digest.hexdigest()
                if content_length is not None and mode == "wb":
                    declared = int(content_length)
                    if written != declared:
                        raise DownloadError(
                            f"short read: wrote {written} bytes, Content-Length was {declared}"
                        )
                if total_from_range is not None and written != total_from_range:
                    raise DownloadError(
                        f"incomplete download: wrote {written} bytes, Content-Range total was {total_from_range}"
                    )
                if written != expected_bytes:
                    raise DownloadError(
                        f"size mismatch: downloaded {written} bytes, expected {expected_bytes}"
                    )
                if expected_sha and actual_sha != expected_sha:
                    raise DownloadError(
                        "checksum mismatch: downloaded SHA-256 "
                        f"{actual_sha} does not match expected {expected_sha}"
                    )

                os.replace(part, target)
                try:
                    target.chmod(0o444)
                except OSError:
                    pass
                retrieved_at = utc_now_iso()
                os.utime(target, None)
                return DownloadResult(
                    file_id=entry["file_id"],
                    accession=entry["accession"],
                    file_name=entry["file_name"],
                    status="downloaded",
                    http_status=http_status,
                    bytes_downloaded=written,
                    sha256_actual=actual_sha,
                    retrieved_at=retrieved_at,
                    attempts=attempts,
                    path=str(target),
                )
        except urllib.error.HTTPError as exc:
            last_http = exc.code
            last_error = f"HTTP {exc.code}: {exc.reason}"
            if exc.code == 404:
                return DownloadResult(
                    file_id=entry["file_id"],
                    accession=entry["accession"],
                    file_name=entry["file_name"],
                    status="listed_404",
                    http_status=404,
                    attempts=attempts,
                    error=last_error,
                    path=str(target),
                )
            if exc.code in {401, 403}:
                return DownloadResult(
                    file_id=entry["file_id"],
                    accession=entry["accession"],
                    file_name=entry["file_name"],
                    status="failed",
                    http_status=exc.code,
                    attempts=attempts,
                    error=(
                        f"{last_error}; access is not public or the endpoint rejected the request. "
                        "Do not bypass access controls."
                    ),
                    path=str(target),
                )
            if exc.code not in {408, 425, 429, 500, 502, 503, 504}:
                return DownloadResult(
                    file_id=entry["file_id"],
                    accession=entry["accession"],
                    file_name=entry["file_name"],
                    status="failed",
                    http_status=exc.code,
                    attempts=attempts,
                    error=last_error,
                    path=str(target),
                )
        except (urllib.error.URLError, socket.timeout, TimeoutError, ssl.SSLError, OSError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        except DownloadError as exc:
            last_error = str(exc)
            if part.exists():
                try:
                    part.unlink()
                except OSError:
                    pass

        if attempt < retries:
            sleep_for = backoff * (2 ** (attempt - 1))
            time.sleep(sleep_for)

    return DownloadResult(
        file_id=entry["file_id"],
        accession=entry["accession"],
        file_name=entry["file_name"],
        status="failed",
        http_status=last_http,
        attempts=attempts,
        error=last_error or "download failed after retries",
        path=str(target),
    )


def verify_known_unavailable(
    manifest: dict[str, Any], timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> list[KnownUnavailableResult]:
    """Check that documented 404 files still return 404, without downloading them."""

    results: list[KnownUnavailableResult] = []
    for item in manifest.get("known_unavailable", []):
        url = (
            f"https://psi.nasa.gov/geode-py/ws/studies/{item['accession']}/download"
            f"?file={urllib.parse.quote(item['file_name'], safe='')}"
        )
        observed: int | None = None
        error: str | None = None
        try:
            with _open_url(url, timeout=timeout, offset=0) as response:
                observed = getattr(response, "status", None) or response.getcode()
                # A 200/206 means the file is available now; do not read the body.
                response.close()
            status = "unexpectedly_available"
            error = "documented unavailable file returned a successful response"
        except urllib.error.HTTPError as exc:
            observed = exc.code
            if exc.code == item["expected_status"]:
                status = "listed_404"
            else:
                status = "failed"
                error = f"expected HTTP {item['expected_status']}, observed HTTP {exc.code}"
        except (urllib.error.URLError, socket.timeout, TimeoutError, ssl.SSLError, OSError) as exc:
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"
        results.append(
            KnownUnavailableResult(
                accession=item["accession"],
                file_name=item["file_name"],
                expected_status=int(item["expected_status"]),
                observed_status=observed,
                status=status,
                error=error,
            )
        )
    return results


def write_acquisition_manifest(
    manifest: dict[str, Any],
    results: list[DownloadResult],
    path: Path = DOWNLOAD_MANIFEST_CSV,
) -> None:
    """Write the acquisition manifest with a status for every selected file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    by_id = {result.file_id: result for result in results}
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = __import__("csv").DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for item in manifest["files"]:
            result = by_id.get(item["file_id"])
            row = {key: item.get(key, "") for key in CSV_COLUMNS}
            if result is None:
                row["status"] = "not_selected"
            else:
                row.update(
                    {
                        "status": result.status,
                        "http_status": result.http_status if result.http_status is not None else "",
                        "bytes_downloaded": result.bytes_downloaded,
                        "sha256_actual": result.sha256_actual or "",
                        "retrieved_at": result.retrieved_at or "",
                        "attempts": result.attempts,
                        "error": result.error or "",
                    }
                )
            writer.writerow(row)


def _duplicate_checksums(results: list[DownloadResult]) -> list[dict[str, Any]]:
    by_sha: dict[str, list[str]] = {}
    for result in results:
        if result.sha256_actual and result.status in {"downloaded", "already_present"}:
            by_sha.setdefault(result.sha256_actual, []).append(result.file_id)
    return [
        {"sha256": sha, "file_ids": ids}
        for sha, ids in sorted(by_sha.items())
        if len(ids) > 1
    ]


def download_all(
    manifest: dict[str, Any] | None = None,
    datasets: Iterable[str] | None = None,
    raw_dir: Path = RAW_DIR,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF_SECONDS,
    rate_limit: float = DEFAULT_RATE_LIMIT_SECONDS,
    max_single_file_bytes: int = DEFAULT_MAX_SINGLE_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    max_files: int = DEFAULT_MAX_FILES,
    allow_large: bool = False,
    force: bool = False,
    dry_run: bool = False,
    verify_unavailable: bool = True,
) -> AcquisitionReport:
    """Download the selected manifest entries and write reports."""

    ensure_directories()
    manifest = manifest or read_manifest()
    entries = select_entries(manifest, datasets)
    approval_required = check_limits(
        entries,
        max_single_file_bytes=max_single_file_bytes,
        max_total_bytes=max_total_bytes,
        max_files=max_files,
        allow_large=allow_large,
    )
    approval_ids = {item["file_id"] for item in approval_required}
    disk_free_before = check_disk_space(raw_dir, sum(int(item["expected_bytes"]) for item in entries))

    selected_datasets = sorted({item["accession"] for item in entries})
    report = AcquisitionReport(
        schema_version="1.0.0",
        generated_at=utc_now_iso(),
        manifest="data/registry/download_manifest.json",
        selected_datasets=selected_datasets,
        selected_files=len(entries),
        selected_bytes=sum(int(item["expected_bytes"]) for item in entries),
        limits={
            "max_single_file_bytes": max_single_file_bytes,
            "max_total_bytes": max_total_bytes,
            "max_files": max_files,
            "allow_large": allow_large,
            "min_free_disk_multiplier": MIN_FREE_DISK_MULTIPLIER,
        },
        disk_free_before=disk_free_before,
        disk_free_after=disk_free_before,
    )

    total = len(entries)
    for index, entry in enumerate(entries, start=1):
        if entry["file_id"] in approval_ids:
            result = DownloadResult(
                file_id=entry["file_id"],
                accession=entry["accession"],
                file_name=entry["file_name"],
                status="approval_required",
                bytes_downloaded=0,
                error=(
                    f"expected {entry['expected_bytes']} bytes exceeds "
                    f"max_single_file_bytes={max_single_file_bytes}; rerun with --allow-large "
                    "after reviewing the file"
                ),
            )
            print(
                f"[{index}/{total}] APPROVAL REQUIRED {entry['accession']} {entry['file_name']} "
                f"({entry['expected_bytes']} bytes)",
                flush=True,
            )
            report.results.append(result)
            continue

        print(
            f"[{index}/{total}] {entry['accession']} {entry['file_name']} "
            f"({entry['expected_bytes']} bytes)",
            flush=True,
        )
        if dry_run:
            result = DownloadResult(
                file_id=entry["file_id"],
                accession=entry["accession"],
                file_name=entry["file_name"],
                status="skipped",
                error="dry run",
            )
        else:
            result = download_one(
                entry,
                raw_dir=raw_dir,
                timeout=timeout,
                retries=retries,
                backoff=backoff,
                rate_limit=rate_limit,
                force=force,
            )
        report.results.append(result)
        print(
            f"    -> {result.status}"
            + (f" ({result.bytes_downloaded} bytes)" if result.bytes_downloaded else "")
            + (f" [{result.error}]" if result.error and result.status not in {"listed_404"} else ""),
            flush=True,
        )
        if not dry_run and index < total:
            time.sleep(max(0.0, rate_limit))

    if verify_unavailable and not dry_run:
        report.known_unavailable = verify_known_unavailable(manifest, timeout=timeout)
        for item in report.known_unavailable:
            print(
                f"known-unavailable {item.accession} {item.file_name}: "
                f"{item.status} (observed {item.observed_status})",
                flush=True,
            )

    report.duplicate_checksums = _duplicate_checksums(report.results)
    report.disk_free_after = shutil.disk_usage(raw_dir).free
    report.generated_at = utc_now_iso()

    write_acquisition_manifest(manifest, report.results)
    ACQUISITION_REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    ACQUISITION_REPORT_JSON.write_text(
        json.dumps(report.as_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    return report
