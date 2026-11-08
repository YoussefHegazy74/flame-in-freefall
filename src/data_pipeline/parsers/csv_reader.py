"""Strict CSV reading with encoding and row-shape provenance."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Sequence

from ..provenance import SourceFile
from .base import (
    ParseIssue,
    decode_bytes,
    pad_row,
    require_exact_header,
    row_is_empty,
)


@dataclass
class CsvTable:
    path: Path
    header: list[str]
    rows: list[list[str]]
    physical_rows: int
    data_rows: int
    encoding: str
    encoding_fallback: bool
    issues: list[ParseIssue] = field(default_factory=list)

    def iter_data_rows(self) -> Iterator[tuple[int, list[str]]]:
        """Yield ``(source_row, row)`` for non-empty physical rows.

        ``source_row`` is 1-based among physical rows after the header, so a
        blank row still consumes a source-row number. This makes the
        PSI-159 inverse 1,015 physical / 154 valid distinction auditable.
        """

        for index, row in enumerate(self.rows, start=1):
            if row_is_empty(row):
                continue
            yield index, row


def read_csv_table(
    path: Path,
    source: SourceFile,
    expected_header: Sequence[str] | None = None,
) -> CsvTable:
    if not path.exists():
        raise FileNotFoundError(path)
    data = path.read_bytes()
    text, encoding, fallback = decode_bytes(data)
    reader = csv.reader(io.StringIO(text, newline=""), strict=False)
    try:
        header = next(reader)
    except StopIteration as exc:
        raise ValueError(f"{path} is empty") from exc
    rows = [list(row) for row in reader]
    issues: list[ParseIssue] = []
    if fallback:
        issues.append(
            ParseIssue(
                severity="warning",
                code="encoding_fallback",
                message=(
                    f"source was not valid UTF-8; decoded as {encoding}. "
                    "The original bytes and checksum are preserved."
                ),
            )
        )
    if expected_header is not None:
        require_exact_header(header, expected_header, source)
    width = len(header)
    normalized: list[list[str]] = []
    for index, row in enumerate(rows, start=1):
        padded, issue = pad_row(row, width)
        if issue:
            issues.append(
                ParseIssue(
                    severity="warning",
                    code=issue,
                    message=(
                        f"row has {len(row)} fields but the header has {width}; "
                        "the raw row is preserved and canonical mapping uses the header width."
                    ),
                    source_row=index,
                )
            )
        normalized.append(["" if value is None else str(value) for value in padded])
    return CsvTable(
        path=path,
        header=header,
        rows=normalized,
        physical_rows=len(normalized),
        data_rows=sum(1 for row in normalized if not row_is_empty(row)),
        encoding=encoding,
        encoding_fallback=fallback,
        issues=issues,
    )
