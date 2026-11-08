"""Excel readers for modern ``.xlsx`` and legacy ``.xls`` sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Sequence

from ..provenance import SourceFile
from .base import (
    ParseIssue,
    pad_row,
    require_exact_header,
    row_is_empty,
)


@dataclass
class ExcelSheet:
    path: Path
    sheet_name: str
    header: list[Any]
    rows: list[list[Any]]
    physical_rows: int
    data_rows: int
    issues: list[ParseIssue] = field(default_factory=list)

    def iter_data_rows(self) -> Iterator[tuple[int, list[Any]]]:
        for index, row in enumerate(self.rows, start=1):
            if row_is_empty(row):
                continue
            yield index, row


def _open_xlsx(path: Path):
    import openpyxl

    return openpyxl.load_workbook(path, read_only=True, data_only=True)


def list_xlsx_sheets(path: Path) -> list[str]:
    workbook = _open_xlsx(path)
    try:
        return list(workbook.sheetnames)
    finally:
        workbook.close()


def iter_xlsx_rows(
    path: Path,
    sheet_name: str,
    header_row: int = 1,
    max_rows: int | None = None,
) -> Iterator[tuple[list[Any], list[Any]]]:
    """Yield ``(header, row)`` lazily for a named worksheet.

    ``header_row`` is 1-based. Rows before it are workbook annotations and are
    not data. The caller is responsible for closing the generator.
    """

    workbook = _open_xlsx(path)
    try:
        if sheet_name not in workbook.sheetnames:
            raise KeyError(f"{path} has no sheet {sheet_name!r}; sheets={workbook.sheetnames}")
        worksheet = workbook[sheet_name]
        iterator = worksheet.iter_rows(min_row=header_row, values_only=True)
        try:
            header = list(next(iterator))
        except StopIteration:
            return
        yield header, []
        for index, row in enumerate(iterator, start=1):
            yield header, list(row)
            if max_rows is not None and index >= max_rows:
                break
    finally:
        workbook.close()


def read_xlsx_sheet(
    path: Path,
    source: SourceFile,
    sheet_name: str,
    header_row: int = 1,
    expected_header: Sequence[Any] | None = None,
) -> ExcelSheet:
    workbook = _open_xlsx(path)
    try:
        if sheet_name not in workbook.sheetnames:
            raise KeyError(f"{path} has no sheet {sheet_name!r}; sheets={workbook.sheetnames}")
        worksheet = workbook[sheet_name]
        iterator = worksheet.iter_rows(min_row=header_row, values_only=True)
        try:
            header = list(next(iterator))
        except StopIteration as exc:
            raise ValueError(f"{path} sheet {sheet_name!r} is empty") from exc
        rows = [list(row) for row in iterator]
    finally:
        workbook.close()

    issues: list[ParseIssue] = []
    if expected_header is not None:
        require_exact_header(header, expected_header, source, sheet=sheet_name)
    width = len(header)
    normalized: list[list[Any]] = []
    for index, row in enumerate(rows, start=1):
        padded, issue = pad_row(row, width)
        if issue:
            issues.append(
                ParseIssue(
                    severity="warning",
                    code=issue,
                    message=(
                        f"sheet {sheet_name!r} row has {len(row)} cells but the header has {width}; "
                        "the raw row is preserved."
                    ),
                    source_row=index,
                )
            )
        normalized.append(padded)
    return ExcelSheet(
        path=path,
        sheet_name=sheet_name,
        header=header,
        rows=normalized,
        physical_rows=len(normalized),
        data_rows=sum(1 for row in normalized if not row_is_empty(row)),
        issues=issues,
    )


def _xls_cell_value(book: Any, cell: Any) -> Any:
    import xlrd

    if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
        return None
    if cell.ctype == xlrd.XL_CELL_DATE:
        try:
            return xlrd.xldate_as_datetime(cell.value, book.datemode)
        except (ValueError, OverflowError):
            return None
    if cell.ctype == xlrd.XL_CELL_BOOLEAN:
        return bool(cell.value)
    if cell.ctype == xlrd.XL_CELL_ERROR:
        return xlrd.error_text_from_code.get(cell.value, f"#ERROR({cell.value})")
    if cell.ctype == xlrd.XL_CELL_NUMBER:
        if float(cell.value).is_integer():
            return int(cell.value)
        return float(cell.value)
    return str(cell.value)


def list_xls_sheets(path: Path) -> list[str]:
    import xlrd

    book = xlrd.open_workbook(path)
    return list(book.sheet_names())


def read_xls_sheet(
    path: Path,
    source: SourceFile,
    sheet_name: str | None = None,
    header_row: int = 1,
    header_present: bool = True,
    expected_header: Sequence[Any] | None = None,
) -> ExcelSheet:
    import xlrd

    book = xlrd.open_workbook(path)
    if sheet_name is None:
        sheet = book.sheet_by_index(0)
    else:
        if sheet_name not in book.sheet_names():
            raise KeyError(f"{path} has no sheet {sheet_name!r}; sheets={book.sheet_names()}")
        sheet = book.sheet_by_name(sheet_name)

    raw_rows: list[list[Any]] = []
    for row_index in range(sheet.nrows):
        raw_rows.append(
            [_xls_cell_value(book, sheet.cell(row_index, col)) for col in range(sheet.ncols)]
        )

    if not raw_rows:
        raise ValueError(f"{path} sheet {sheet.name!r} is empty")

    issues: list[ParseIssue] = []
    if header_present:
        header = raw_rows[header_row - 1]
        rows = raw_rows[header_row:]
    else:
        width = max(len(row) for row in raw_rows)
        header = [f"column_{index + 1}" for index in range(width)]
        rows = raw_rows
        issues.append(
            ParseIssue(
                severity="info",
                code="no_header",
                message="source has no header row; generated positional column names",
            )
        )

    if expected_header is not None:
        require_exact_header(header, expected_header, source, sheet=sheet.name)

    width = len(header)
    normalized: list[list[Any]] = []
    for index, row in enumerate(rows, start=1):
        padded, issue = pad_row(row, width)
        if issue:
            issues.append(
                ParseIssue(
                    severity="warning",
                    code=issue,
                    message=(
                        f"sheet {sheet.name!r} row has {len(row)} cells but the header has {width}; "
                        "the raw row is preserved."
                    ),
                    source_row=index,
                )
            )
        normalized.append(padded)

    return ExcelSheet(
        path=path,
        sheet_name=sheet.name,
        header=list(header),
        rows=normalized,
        physical_rows=len(normalized),
        data_rows=sum(1 for row in normalized if not row_is_empty(row)),
        issues=issues,
    )
