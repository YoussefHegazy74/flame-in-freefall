"""Shared parser contracts, header validation, and sentinel classification."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable, Sequence

from ..provenance import SourceFile


class ParserError(RuntimeError):
    """Base class for parser failures."""


class SourceMissingError(ParserError):
    """Raised when a required source file is absent."""


class HeaderMismatchError(ParserError):
    """Raised when the exact source header does not match the committed schema."""


class RowShapeError(ParserError):
    """Raised when a row cannot be interpreted without guessing."""


class RowCountMismatchError(ParserError):
    """Raised when a validated table's row count differs from the expected count."""


class SchemaValidationError(ParserError):
    """Raised when a canonical table fails a required schema invariant."""


@dataclass(frozen=True)
class ParseIssue:
    severity: str
    code: str
    message: str
    source_row: int | None = None
    field: str | None = None
    token: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "source_row": self.source_row,
            "field": self.field,
            "token": self.token,
        }


@dataclass
class ParseResult:
    source: SourceFile
    parser_name: str
    parser_version: str
    table_name: str
    physical_rows: int
    data_rows: int
    records: list[dict[str, Any]] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_issue(
        self,
        severity: str,
        code: str,
        message: str,
        source_row: int | None = None,
        field_name: str | None = None,
        token: str | None = None,
    ) -> None:
        self.issues.append(
            ParseIssue(
                severity=severity,
                code=code,
                message=message,
                source_row=source_row,
                field=field_name,
                token=token,
            )
        )

    def as_report_dict(self) -> dict[str, Any]:
        return {
            "accession": self.source.accession,
            "file_name": self.source.file_name,
            "sheet": self.source.sheet,
            "parser_name": self.parser_name,
            "parser_version": self.parser_version,
            "table_name": self.table_name,
            "physical_rows": self.physical_rows,
            "data_rows": self.data_rows,
            "records": len(self.records),
            "issue_count": len(self.issues),
            "issues": [issue.as_dict() for issue in self.issues],
            "metadata": self.metadata,
            "source_sha256": self.source.sha256,
            "retrieved_at": self.source.retrieved_at,
            "source_url": self.source.source_url,
        }


@dataclass(frozen=True)
class NumberParse:
    value: float | None
    flag: str
    raw: str | None


SENTINEL_FLAGS: dict[str, str] = {
    "": "missing",
    "-": "sentinel_dash",
    "--": "sentinel_dash",
    "–": "sentinel_dash",
    "—": "sentinel_dash",
    "n/a": "not_applicable",
    "na": "not_applicable",
    "not applicable": "not_applicable",
    "none": "not_measured",
    "null": "missing",
    "nan": "missing",
    "or": "over_range",
    "over range": "over_range",
    "ramp": "ramped_condition",
    "ramped": "ramped_condition",
    "low o2": "low_oxygen_condition",
    "low oxygen": "low_oxygen_condition",
    "unknown": "unknown",
    "tbd": "unknown",
    "insignificant": "non_numeric_qualifier",
    "saturated": "non_numeric_qualifier",
    "see notes": "non_numeric_qualifier",
    "yes": "non_numeric",
    "no": "non_numeric",
    "flash": "non_numeric",
}

SPREADSHEET_ERRORS = {
    "#div/0!",
    "#value!",
    "#n/a",
    "#ref!",
    "#name?",
    "#num!",
    "#null!",
}


def decode_bytes(data: bytes) -> tuple[str, str, bool]:
    """Decode source bytes without losing the original text.

    Returns ``(text, encoding, fallback_used)``. UTF-8 is preferred. A
    Windows-1252 fallback is explicit and reported; it is not treated as
    corrupt text. Replacement decoding is the last resort and is also reported.
    """

    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig"), "utf-8-sig", False
    try:
        return data.decode("utf-8"), "utf-8", False
    except UnicodeDecodeError:
        pass
    for encoding in ("cp1252", "latin-1"):
        try:
            return data.decode(encoding), encoding, True
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8-replace", True


def require_exact_header(
    actual: Sequence[Any],
    expected: Sequence[Any],
    source: SourceFile,
    sheet: str | None = None,
) -> None:
    actual_list = list(actual)
    expected_list = list(expected)
    if actual_list == expected_list:
        return
    differences: list[str] = []
    for index in range(max(len(actual_list), len(expected_list))):
        left = actual_list[index] if index < len(actual_list) else "<missing>"
        right = expected_list[index] if index < len(expected_list) else "<missing>"
        if left != right:
            differences.append(f"column {index}: actual={left!r} expected={right!r}")
        if len(differences) >= 12:
            break
    location = f"{source.file_name}" + (f" sheet {sheet!r}" if sheet else "")
    raise HeaderMismatchError(
        f"header mismatch in {location}: "
        + "; ".join(differences)
        + f" (actual {len(actual_list)} columns, expected {len(expected_list)})"
    )


def row_is_empty(row: Sequence[Any]) -> bool:
    for value in row:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return False
    return True


def pad_row(row: Sequence[Any], width: int) -> tuple[list[Any], str | None]:
    values = list(row)
    if len(values) < width:
        values.extend([None] * (width - len(values)))
        return values, "short_row"
    if len(values) > width:
        return values, "long_row"
    return values, None


def _raw_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def parse_number(value: Any) -> NumberParse:
    """Classify a source value as numeric or as a documented sentinel.

    The raw token is never discarded. A non-numeric qualifier returns
    ``value=None`` with a specific flag; it is never coerced to zero.
    """

    raw = _raw_text(value)
    if value is None:
        return NumberParse(None, "missing", raw)
    if isinstance(value, bool):
        return NumberParse(float(value), "boolean", raw)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return NumberParse(None, "missing", raw)
        if isinstance(value, float) and math.isinf(value):
            return NumberParse(None, "invalid_infinite", raw)
        return NumberParse(float(value), "ok", raw)
    if isinstance(value, (datetime, date)):
        return NumberParse(None, "datetime_value", raw)

    text = str(value).strip()
    if not text:
        return NumberParse(None, "missing", raw)
    key = text.lower()
    if key in SPREADSHEET_ERRORS:
        return NumberParse(None, "spreadsheet_error", raw)
    if key in {"-1.#ind", "1.#ind", "-1.#inf", "1.#inf", "-1.#qnan", "1.#qnan"}:
        return NumberParse(None, "invalid_indefinite", raw)
    if key in SENTINEL_FLAGS:
        return NumberParse(None, SENTINEL_FLAGS[key], raw)

    # Approximate marker: keep the numeric value and label the approximation.
    if text.startswith("~"):
        inner = parse_number(text[1:].strip())
        if inner.value is not None:
            return NumberParse(inner.value, "approximate", raw)
        return NumberParse(None, inner.flag, raw)

    # Percent text: parse the numeric part but label the unit form.
    if text.endswith("%"):
        inner = parse_number(text[:-1].strip())
        if inner.value is not None:
            return NumberParse(inner.value, "percent_text", raw)

    # Inequality or range text is not a point measurement.
    if text.startswith(("<", ">")):
        return NumberParse(None, "inequality_text", raw)
    if ";" in text:
        return NumberParse(None, "range_text", raw)
    if re.fullmatch(r"-?\d+(?:\.\d+)?\s*[-–—]\s*-?\d+(?:\.\d+)?", text):
        return NumberParse(None, "range_text", raw)
    if re.fullmatch(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?", text):
        return NumberParse(float(text.replace(",", "")), "thousands_separator", raw)
    if "," in text:
        return NumberParse(None, "range_text", raw)

    # Plain decimal and scientific notation are numeric. This check must come
    # before the unit-text pattern, otherwise the ``E`` in ``-7.53E-05`` is
    # mistaken for a unit suffix.
    try:
        return NumberParse(float(text), "ok", raw)
    except ValueError:
        pass

    # A numeric value followed by a unit is a unit-bearing text token, not a
    # dimensionless point value. Preserve it and let the field dictionary decide.
    if re.fullmatch(r"-?\d+(?:\.\d+)?\s*[A-Za-z%/][A-Za-z0-9%/^._ -]*", text):
        return NumberParse(None, "unit_text", raw)

    return NumberParse(None, "non_numeric", raw)


def parse_int(value: Any) -> tuple[int | None, str]:
    parsed = parse_number(value)
    if parsed.value is None:
        return None, parsed.flag
    if parsed.flag not in {"ok", "approximate", "thousands_separator"}:
        return None, parsed.flag
    if parsed.value != int(parsed.value):
        return None, "non_integer"
    return int(parsed.value), parsed.flag


def quality_flag(
    field_name: str,
    raw_field: str,
    raw_value: Any,
    flag: str,
) -> dict[str, Any]:
    return {
        "field": field_name,
        "raw_field": raw_field,
        "token": _raw_text(raw_value),
        "flag": flag,
    }


def add_quality_flag(
    flags: list[dict[str, Any]],
    field_name: str,
    raw_field: str,
    raw_value: Any,
    flag: str,
) -> None:
    if flag != "ok":
        flags.append(quality_flag(field_name, raw_field, raw_value, flag))


def categorical(value: Any, missing_tokens: Iterable[str] = ("", "-", "n/a", "none")) -> tuple[str | None, str]:
    """Return a trimmed categorical value and a missing/sentinel flag."""

    if value is None:
        return None, "missing"
    text = str(value).strip()
    if not text:
        return None, "missing"
    if text in {"-", "--", "–", "—"}:
        return None, "sentinel_dash"
    if text.lower() in {token.lower() for token in missing_tokens}:
        return None, "not_available"
    return text, "ok"


def excel_serial_to_date(value: Any, datemode: int = 0) -> str | None:
    """Convert a numeric Excel serial date with an explicit workbook epoch.

    ``datemode=0`` is the 1900 date system (epoch 1899-12-30, accounting for
    Excel's fictitious 1900-02-29). ``datemode=1`` is the 1904 date system.
    """

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    serial = float(value)
    if serial <= 0 or serial > 100_000:
        return None
    from datetime import timedelta

    epoch = datetime(1899, 12, 30) if datemode == 0 else datetime(1904, 1, 1)
    try:
        return (epoch + timedelta(days=serial)).date().isoformat()
    except (OverflowError, ValueError):
        return None


def iso_date(value: Any, datemode: int = 0) -> tuple[str | None, str]:
    """Convert a datetime/date, Excel serial, or common source date string."""

    if value is None or (isinstance(value, str) and not value.strip()):
        return None, "missing"
    if isinstance(value, datetime):
        return value.date().isoformat(), "ok"
    if isinstance(value, date):
        return value.isoformat(), "ok"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        converted = excel_serial_to_date(value, datemode=datemode)
        if converted is not None:
            return converted, "excel_serial"
        return None, "unparsed_date"
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d-%b-%y", "%d-%b-%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat(), "ok"
        except ValueError:
            continue
    return None, "unparsed_date"
