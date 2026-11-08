"""Parser for the legacy SAME test log (PSI-102 ``.xls``).

The workbook has one sheet and no header row. The seven source columns are
preserved in ``raw_row_json``; the first three are promoted to semantic
fields because they form the log's timestamp/event/detail structure. The
remaining cells are not assigned meanings that the source does not state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..config import PARSER_VERSION
from ..provenance import SourceFile, observation_id, raw_row_json
from .base import ParseIssue
from .excel_reader import read_xls_sheet

PARSER_NAME = "test_log"
EXPECTED_ROWS = 119
SHEET_NAME = "Copy of GMT252run1testlog"


@dataclass
class TestLogParseResult:
    source: SourceFile
    table_name: str = "smoke_test_log"
    parser_name: str = PARSER_NAME
    parser_version: str = PARSER_VERSION
    records: list[dict[str, Any]] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)
    physical_rows: int = 0
    data_rows: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_test_log(source: SourceFile) -> TestLogParseResult:
    sheet = read_xls_sheet(
        source.path,
        source,
        sheet_name=SHEET_NAME,
        header_present=False,
    )
    result = TestLogParseResult(
        source=source,
        physical_rows=sheet.physical_rows,
        data_rows=sheet.data_rows,
        issues=list(sheet.issues),
    )
    if sheet.data_rows != EXPECTED_ROWS:
        raise ValueError(
            f"{source.file_name}: expected {EXPECTED_ROWS} non-empty log rows, "
            f"found {sheet.data_rows}"
        )
    for source_row, row in sheet.iter_data_rows():
        cells = list(row)
        cells.extend([None] * (7 - len(cells)))
        timestamp = _text(cells[0])
        event_type = _text(cells[1])
        event_detail = _text(cells[2])
        record = {
            "log_id": observation_id(
                source.accession, source.file_name, sheet.sheet_name, source_row
            ),
            "accession": source.accession,
            "source_file": source.file_name,
            "source_sheet": sheet.sheet_name,
            "source_row": source_row,
            "source_timestamp_string": timestamp,
            "event_type": event_type,
            "event_detail": event_detail,
            "raw_row_json": raw_row_json(sheet.header, cells),
            "source_sha256": source.sha256,
            "retrieved_at": source.retrieved_at,
            "source_url": source.source_url,
            "parser_version": PARSER_VERSION,
        }
        result.records.append(record)
    result.metadata = {
        "sheet": sheet.sheet_name,
        "header_present": False,
        "note": (
            "Legacy SAME test log. The source has no header; column meanings "
            "beyond timestamp/event/detail are not assigned. The year is not "
            "stated in the table."
        ),
    }
    return result
