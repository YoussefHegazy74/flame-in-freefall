"""Row-level provenance helpers."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DOWNLOAD_MANIFEST_CSV, RAW_DIR


class ProvenanceError(RuntimeError):
    """Raised when a source file or its provenance record is missing."""


@dataclass(frozen=True)
class SourceFile:
    accession: str
    file_name: str
    path: Path
    sha256: str
    retrieved_at: str
    source_url: str
    sheet: str | None = None
    expected_bytes: int | None = None

    def with_sheet(self, sheet: str | None) -> "SourceFile":
        return SourceFile(
            accession=self.accession,
            file_name=self.file_name,
            path=self.path,
            sha256=self.sha256,
            retrieved_at=self.retrieved_at,
            source_url=self.source_url,
            sheet=sheet,
            expected_bytes=self.expected_bytes,
        )


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_from_mtime(path: Path) -> str:
    return (
        datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_acquisition_index(path: Path = DOWNLOAD_MANIFEST_CSV) -> dict[tuple[str, str], dict[str, str]]:
    index: dict[tuple[str, str], dict[str, str]] = {}
    if not path.exists():
        return index
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            index[(row["accession"], row["file_name"])] = row
    return index


def source_from_entry(
    entry: dict[str, Any],
    raw_dir: Path = RAW_DIR,
    sheet: str | None = None,
    index: dict[tuple[str, str], dict[str, str]] | None = None,
) -> SourceFile:
    path = raw_dir / entry["accession"] / entry["file_name"]
    if not path.exists():
        raise ProvenanceError(
            f"source file is missing: {path}; run the downloader for {entry['accession']}"
        )
    index = index if index is not None else load_acquisition_index()
    record = index.get((entry["accession"], entry["file_name"]), {})
    sha = record.get("sha256_actual") or sha256_file(path)
    retrieved_at = record.get("retrieved_at") or utc_from_mtime(path)
    return SourceFile(
        accession=entry["accession"],
        file_name=entry["file_name"],
        path=path,
        sha256=sha,
        retrieved_at=retrieved_at,
        source_url=entry["source_url"],
        sheet=sheet,
        expected_bytes=entry.get("expected_bytes"),
    )


def source_from_path(
    accession: str,
    file_name: str,
    path: Path,
    sha256: str | None = None,
    retrieved_at: str | None = None,
    source_url: str = "",
    sheet: str | None = None,
) -> SourceFile:
    if not path.exists():
        raise ProvenanceError(f"source file is missing: {path}")
    return SourceFile(
        accession=accession,
        file_name=file_name,
        path=path,
        sha256=sha256 or sha256_file(path),
        retrieved_at=retrieved_at or utc_from_mtime(path),
        source_url=source_url,
        sheet=sheet,
    )


def slugify(value: str, max_length: int = 60) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return (text or "unknown")[:max_length]


def observation_id(
    accession: str,
    file_name: str,
    sheet: str | None,
    source_row: int,
    suffix: str | None = None,
) -> str:
    """Return a deterministic, collision-resistant row/cell identifier.

    The readable prefix is for humans. A short digest over the full,
    untruncated source key prevents two long channel names or long file names
    from collapsing to the same identifier after slug truncation.
    """

    full_key = "\x1f".join(
        [accession, file_name, sheet or "", str(source_row), suffix or ""]
    )
    digest = hashlib.sha1(full_key.encode("utf-8")).hexdigest()[:10]
    parts = [
        accession,
        slugify(file_name, 40),
        slugify(sheet, 24) if sheet else "file",
        f"{source_row:06d}",
    ]
    if suffix:
        parts.append(slugify(suffix, 40))
    parts.append(digest)
    return ":".join(parts)


def raw_row_json(header: list[Any], row: list[Any]) -> str:
    """Preserve a source row exactly, including duplicate/blank headers.

    A list of ``[header, value]`` pairs is used instead of a mapping so that
    duplicate headers and column order are not lost.
    """

    pairs = []
    for index, value in enumerate(row):
        column = header[index] if index < len(header) else None
        pairs.append([column, value])
    return json.dumps(pairs, ensure_ascii=False, default=str)
