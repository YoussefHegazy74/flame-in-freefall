"""Parsers for the BASS-II (PSI-25) and BASS as-run (PSI-26) test matrices.

These workbooks are experimental context, not flame-spread measurements. The
canonical table preserves the source row, the exact text for display/gain
fields, and explicit quality flags for ``OR``, ``none``, and the documented
``-1`` CO sentinel. PSI-26's single ``O2 % by volume`` value is stored in
``o2_pct`` and is never relabeled as an initial or final O2 measurement.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import PARSER_VERSION
from ..provenance import SourceFile, observation_id, raw_row_json
from .base import (
    ParseIssue,
    add_quality_flag,
    categorical,
    iso_date,
    parse_number,
)
from .excel_reader import read_xlsx_sheet

PSI25_HEADER_COMMON = [
    "Actual Date  (for Video Display Date, add 1 for Leap Year)",
    "GMT 2014-",
    "Test no.",
    "Sample no.",
    "Material",
    "Flow restrictor",
    "Fan display",
    "Air display",
    "Radiometer gain   (1000, 250, 50, 10)",
    "total frames shot",
    "calibrated  initial O2 % by vol ",
    "calibrated final O2 % by vol",
    "Initial CO2 % by vol",
    "Final CO2 % by vol",
    "Initial CO (ppm)",
    "Final CO (ppm)",
]

PSI25_HEADER_OLSON = [
    "Actual Date  (for Video Display Date, add 1 for Leap Year)",
    "GMT 2014- (except last 3 tests from 2016)",
    "Test no.",
    "Sample no.",
    "Material",
    "Flow restrictor",
    "Fan display",
    "Air display",
    "Radiometer gain   (1000, 250, 50, 10)",
    "total frames shot",
    "calibrated  initial O2 % by vol ",
    "calibrated final O2 % by vol",
    "Initial CO2 % by vol",
    "Final CO2 % by vol",
    "Initial CO (ppm)",
    "Final CO (ppm)",
]

PSI25_SHEETS: dict[str, tuple[list[str], int]] = {
    "Bhattacharjee": (PSI25_HEADER_COMMON, 22),
    "Ferkul": (PSI25_HEADER_COMMON, 4),
    "Miller": (PSI25_HEADER_COMMON, 20),
    "Olson": (PSI25_HEADER_OLSON, 27),
    "Fernandez-Pello": (PSI25_HEADER_COMMON, 27),
    "T'ien": (PSI25_HEADER_COMMON, 29),
}

PSI26_HEADER = [
    "Actual Date  (for SPICE Display Date, add 1 for Leap Year)",
    "Approx Start Time ( with GMT)",
    "As run test no.",
    "Test no.",
    "Sample no.",
    "material",
    "Igniter",
    "Flow restrictor",
    "Sample distance",
    "Fan display",
    "Air display",
    "Radiometer gain ( 1000, 250, 50, 10)",
    "Radiometer display",
    "GN2 Pot",
    "GN2 display",
    "Filter y/n",
    "Release Mode (CH/CL)",
    "Exposure Mode (M/A)",
    "Exposure compensation   (-#EV)",
    "Bracket frames and exposure bracket (#F/ 1.0)",
    "shutter speed (1/s)",
    "F stop",
    "ISO",
    "shutter hold s /cont",
    "SD card S/N",
    "total frames shot",
    "O2 % by volume",
    "pressure, atm",
    "CO2, mm Hg",
    "Test Observations and Anomalies (ignited, spread, extinguished, burn time, color, etc.) ",
]

PSI26_SHEET = "as run matrix"
PSI26_HEADER_ROW = 3
PSI26_EXPECTED_ROWS = 130


@dataclass
class MaterialParseResult:
    source: SourceFile
    table_name: str = "material_test"
    parser_name: str = "material"
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


def _numeric_with_flags(
    raw_value: Any,
    canonical: str,
    raw_name: str,
    flags: list[dict[str, Any]],
    *,
    minus_one_sentinel: bool = False,
) -> float | None:
    raw_text = _text(raw_value)
    if minus_one_sentinel and raw_text in {"-1", "-1.0"}:
        flags.append(
            {
                "field": canonical,
                "raw_field": raw_name,
                "token": raw_text,
                "flag": "sentinel_minus_one",
            }
        )
        return None
    parsed = parse_number(raw_value)
    add_quality_flag(flags, canonical, raw_name, raw_value, parsed.flag)
    return parsed.value


def _material_record(
    *,
    source: SourceFile,
    sheet: str,
    source_row: int,
    table_id: str,
    values: dict[str, Any],
    raw_header: list[Any],
    raw_row: list[Any],
    context: dict[str, Any],
    flags: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "observation_id": observation_id(
            source.accession, source.file_name, sheet, source_row
        ),
        "accession": source.accession,
        "table_id": table_id,
        "source_file": source.file_name,
        "source_sheet": sheet,
        "source_row": source_row,
        "record_type": values.get("record_type", "test"),
        "test_date": values.get("test_date"),
        "gmt_day": values.get("gmt_day"),
        "as_run_test_no": values.get("as_run_test_no"),
        "test_no": values.get("test_no"),
        "sample_no": values.get("sample_no"),
        "material": values.get("material"),
        "flow_restrictor": values.get("flow_restrictor"),
        "fan_display": values.get("fan_display"),
        "air_display": values.get("air_display"),
        "radiometer_gain": values.get("radiometer_gain"),
        "total_frames": values.get("total_frames"),
        "initial_o2_pct": values.get("initial_o2_pct"),
        "final_o2_pct": values.get("final_o2_pct"),
        "o2_pct": values.get("o2_pct"),
        "initial_co2_pct": values.get("initial_co2_pct"),
        "final_co2_pct": values.get("final_co2_pct"),
        "initial_co_ppm": values.get("initial_co_ppm"),
        "final_co_ppm": values.get("final_co_ppm"),
        "pressure_atm": values.get("pressure_atm"),
        "co2_mm_hg": values.get("co2_mm_hg"),
        "observations": values.get("observations"),
        "context_json": json.dumps(context, ensure_ascii=False, default=str),
        "quality_flags": json.dumps(flags, ensure_ascii=False),
        "raw_row_json": raw_row_json(raw_header, raw_row),
        "source_sha256": source.sha256,
        "retrieved_at": source.retrieved_at,
        "source_url": source.source_url,
        "parser_version": PARSER_VERSION,
    }


def parse_psi25(source: SourceFile) -> MaterialParseResult:
    result = MaterialParseResult(source=source)
    total = 0
    for sheet_name, (expected_header, expected_rows) in PSI25_SHEETS.items():
        sheet = read_xlsx_sheet(
            source.path,
            source,
            sheet_name=sheet_name,
            header_row=1,
            expected_header=expected_header,
        )
        result.issues.extend(sheet.issues)
        result.physical_rows += sheet.physical_rows
        result.data_rows += sheet.data_rows
        if sheet.data_rows != expected_rows:
            raise ValueError(
                f"{source.file_name} sheet {sheet_name!r}: expected {expected_rows} "
                f"non-empty data rows, found {sheet.data_rows}"
            )
        index = {str(name): position for position, name in enumerate(sheet.header)}
        for source_row, row in sheet.iter_data_rows():
            flags: list[dict[str, Any]] = []
            values: dict[str, Any] = {}
            date_value, date_flag = iso_date(row[index[expected_header[0]]])
            values["test_date"] = date_value
            if date_flag not in {"ok", "missing"}:
                flags.append(
                    {
                        "field": "test_date",
                        "raw_field": expected_header[0],
                        "token": _text(row[index[expected_header[0]]]),
                        "flag": date_flag,
                    }
                )
            values["gmt_day"] = _text(row[index[expected_header[1]]])
            values["test_no"] = _text(row[index["Test no."]])
            values["sample_no"] = _text(row[index["Sample no."]])
            values["material"] = _text(row[index["Material"]])
            values["flow_restrictor"] = _text(row[index["Flow restrictor"]])
            values["fan_display"] = _text(row[index["Fan display"]])
            values["air_display"] = _text(row[index["Air display"]])
            values["radiometer_gain"] = _text(
                row[index["Radiometer gain   (1000, 250, 50, 10)"]]
            )
            values["total_frames"] = _text(row[index["total frames shot"]])
            for canonical, raw_name, minus_one in (
                ("initial_o2_pct", "calibrated  initial O2 % by vol ", False),
                ("final_o2_pct", "calibrated final O2 % by vol", False),
                ("initial_co2_pct", "Initial CO2 % by vol", False),
                ("final_co2_pct", "Final CO2 % by vol", False),
                ("initial_co_ppm", "Initial CO (ppm)", True),
                ("final_co_ppm", "Final CO (ppm)", True),
            ):
                values[canonical] = _numeric_with_flags(
                    row[index[raw_name]],
                    canonical,
                    raw_name,
                    flags,
                    minus_one_sentinel=minus_one,
                )
            values["record_type"] = "test"
            table_id = f"{source.accession}::{source.file_name}::{sheet_name}"
            result.records.append(
                _material_record(
                    source=source,
                    sheet=sheet_name,
                    source_row=source_row,
                    table_id=table_id,
                    values=values,
                    raw_header=sheet.header,
                    raw_row=row,
                    context={},
                    flags=flags,
                )
            )
            total += 1
    if total != 129:
        raise ValueError(f"{source.file_name}: expected 129 total material rows, found {total}")
    result.metadata = {
        "sheets": list(PSI25_SHEETS),
        "total_rows": total,
        "note": "BASS-II test matrix; context only, no flame-spread rate is derived.",
    }
    return result


def parse_psi26(source: SourceFile) -> MaterialParseResult:
    import openpyxl

    result = MaterialParseResult(source=source)
    workbook = openpyxl.load_workbook(source.path, read_only=True, data_only=True)
    try:
        if PSI26_SHEET not in workbook.sheetnames:
            raise KeyError(
                f"{source.path} has no sheet {PSI26_SHEET!r}; sheets={workbook.sheetnames}"
            )
        worksheet = workbook[PSI26_SHEET]
        rows = list(worksheet.iter_rows(values_only=True))
    finally:
        workbook.close()

    if len(rows) < PSI26_HEADER_ROW:
        raise ValueError(f"{source.path} sheet {PSI26_SHEET!r} has no header row")
    header = [str(value) if value is not None else "" for value in rows[PSI26_HEADER_ROW - 1]]
    from .base import require_exact_header

    require_exact_header(header, PSI26_HEADER, source, sheet=PSI26_SHEET)

    data_rows = rows[PSI26_HEADER_ROW:]
    non_empty = [row for row in data_rows if any(value is not None and str(value).strip() for value in row)]
    result.physical_rows = len(data_rows)
    result.data_rows = len(non_empty)
    if len(non_empty) != PSI26_EXPECTED_ROWS:
        raise ValueError(
            f"{source.file_name} sheet {PSI26_SHEET!r}: expected "
            f"{PSI26_EXPECTED_ROWS} non-empty data rows, found {len(non_empty)}"
        )

    index = {name: position for position, name in enumerate(header)}
    mapped_raw = {
        PSI26_HEADER[0],
        PSI26_HEADER[2],
        PSI26_HEADER[3],
        PSI26_HEADER[4],
        PSI26_HEADER[5],
        PSI26_HEADER[7],
        PSI26_HEADER[9],
        PSI26_HEADER[10],
        PSI26_HEADER[11],
        PSI26_HEADER[25],
        PSI26_HEADER[26],
        PSI26_HEADER[27],
        PSI26_HEADER[28],
        PSI26_HEADER[29],
    }

    for source_row, row in enumerate(non_empty, start=1):
        flags: list[dict[str, Any]] = []
        values: dict[str, Any] = {}
        date_value, date_flag = iso_date(row[index[PSI26_HEADER[0]]])
        values["test_date"] = date_value
        if date_flag not in {"ok", "missing"}:
            flags.append(
                {
                    "field": "test_date",
                    "raw_field": PSI26_HEADER[0],
                    "token": _text(row[index[PSI26_HEADER[0]]]),
                    "flag": date_flag,
                }
            )
        values["as_run_test_no"] = _text(row[index[PSI26_HEADER[2]]])
        values["test_no"] = _text(row[index[PSI26_HEADER[3]]])
        values["sample_no"] = _text(row[index[PSI26_HEADER[4]]])
        values["material"] = _text(row[index[PSI26_HEADER[5]]])
        values["flow_restrictor"] = _text(row[index[PSI26_HEADER[7]]])
        values["fan_display"] = _text(row[index[PSI26_HEADER[9]]])
        values["air_display"] = _text(row[index[PSI26_HEADER[10]]])
        values["radiometer_gain"] = _text(row[index[PSI26_HEADER[11]]])
        values["total_frames"] = _text(row[index[PSI26_HEADER[25]]])
        values["o2_pct"] = _numeric_with_flags(
            row[index[PSI26_HEADER[26]]], "o2_pct", PSI26_HEADER[26], flags
        )
        values["pressure_atm"] = _numeric_with_flags(
            row[index[PSI26_HEADER[27]]], "pressure_atm", PSI26_HEADER[27], flags
        )
        values["co2_mm_hg"] = _numeric_with_flags(
            row[index[PSI26_HEADER[28]]], "co2_mm_hg", PSI26_HEADER[28], flags
        )
        values["observations"] = _text(row[index[PSI26_HEADER[29]]])
        record_type = "test" if any(
            values.get(key) for key in ("test_no", "sample_no", "material")
        ) else "note"
        values["record_type"] = record_type
        context = {
            header[position]: row[position]
            for position in range(len(header))
            if header[position] not in mapped_raw and position < len(row)
        }
        table_id = f"{source.accession}::{source.file_name}::{PSI26_SHEET}"
        result.records.append(
            _material_record(
                source=source,
                sheet=PSI26_SHEET,
                source_row=source_row,
                table_id=table_id,
                values=values,
                raw_header=header,
                raw_row=row,
                context=context,
                flags=flags,
            )
        )

    result.metadata = {
        "sheet": PSI26_SHEET,
        "header_row": PSI26_HEADER_ROW,
        "data_rows": len(non_empty),
        "test_rows": sum(1 for record in result.records if record["record_type"] == "test"),
        "note_rows": sum(1 for record in result.records if record["record_type"] == "note"),
        "note": (
            "BASS as-run matrix; the single O2 % by volume value is stored as "
            "o2_pct, never as initial/final O2. Context only."
        ),
    }
    return result
