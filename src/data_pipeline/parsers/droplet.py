"""Parser for the FLEX droplet-combustion experimental table (PSI-69).

The source file is Windows-1252 encoded. The ``0x96`` bytes are en dashes in
the source, not replacement characters. The parser records the encoding
fallback and preserves the exact source text. ``Burning rate; mm`` is stored
as labeled because the unit is ambiguous and must not be relabeled as mm/s
without source confirmation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..config import PARSER_VERSION
from ..provenance import SourceFile, observation_id, raw_row_json
from .base import ParseIssue, add_quality_flag, categorical, iso_date, parse_number
from .csv_reader import read_csv_table

PARSER_NAME = "droplet"
PARSER_VERSION_LOCAL = PARSER_VERSION
EXPECTED_PHYSICAL_ROWS = 274
EXPECTED_DATA_ROWS = 274

HEADER = [
    "FLEX Test #",
    "FLEX Identifier",
    "Test Date",
    "Test GMT",
    "Fuel",
    "Ambient pressure; mmHg",
    "O initial ambient composition; mole fraction",
    "N initial ambient composition; mole fraction",
    "CO initial ambient composition; mole fraction",
    "He initial ambient composition; mole fraction",
    "Droplet initial diameter; mm",
    "Visible flame extinction diameter; mm",
    "Burning rate; mm",
    "Burn time; s",
    "Test end",
]

NUMERIC_FIELDS = {
    "ambient_pressure_mm_hg": "Ambient pressure; mmHg",
    "o2_initial_mole_fraction": "O initial ambient composition; mole fraction",
    "n2_initial_mole_fraction": "N initial ambient composition; mole fraction",
    "co_initial_mole_fraction": "CO initial ambient composition; mole fraction",
    "he_initial_mole_fraction": "He initial ambient composition; mole fraction",
    "droplet_initial_diameter_mm": "Droplet initial diameter; mm",
    "visible_flame_extinction_diameter_mm": "Visible flame extinction diameter; mm",
    "burning_rate_mm_as_labeled": "Burning rate; mm",
    "burn_time_s": "Burn time; s",
}

CATEGORICAL_FIELDS = {
    "flex_identifier": "FLEX Identifier",
    "test_gmt": "Test GMT",
    "fuel": "Fuel",
    "test_end": "Test end",
}


@dataclass
class DropletParseResult:
    source: SourceFile
    table_name: str = "droplet_test"
    parser_name: str = PARSER_NAME
    parser_version: str = PARSER_VERSION_LOCAL
    records: list[dict[str, Any]] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)
    physical_rows: int = 0
    data_rows: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


def parse_droplet(source: SourceFile) -> DropletParseResult:
    table = read_csv_table(source.path, source, expected_header=HEADER)
    result = DropletParseResult(
        source=source,
        physical_rows=table.physical_rows,
        data_rows=table.data_rows,
        issues=list(table.issues),
    )
    if (table.physical_rows, table.data_rows) != (
        EXPECTED_PHYSICAL_ROWS,
        EXPECTED_DATA_ROWS,
    ):
        raise ValueError(
            f"{source.file_name}: expected {EXPECTED_PHYSICAL_ROWS} physical / "
            f"{EXPECTED_DATA_ROWS} data rows, found {table.physical_rows} / {table.data_rows}"
        )
    index = {name: position for position, name in enumerate(table.header)}
    for source_row, row in table.iter_data_rows():
        flags: list[dict[str, Any]] = []
        record: dict[str, Any] = {
            "observation_id": observation_id(
                source.accession, source.file_name, source.sheet, source_row
            ),
            "accession": source.accession,
            "table_id": f"{source.accession}::{source.file_name}",
            "source_file": source.file_name,
            "source_sheet": source.sheet,
            "source_row": source_row,
            "source_url": source.source_url,
            "source_sha256": source.sha256,
            "retrieved_at": source.retrieved_at,
            "parser_version": PARSER_VERSION_LOCAL,
        }
        test_number = parse_number(row[index["FLEX Test #"]])
        record["flex_test_number"] = (
            int(test_number.value) if test_number.value is not None else None
        )
        if test_number.value is None:
            add_quality_flag(
                flags,
                "flex_test_number",
                "FLEX Test #",
                row[index["FLEX Test #"]],
                test_number.flag,
            )
        date_value, date_flag = iso_date(row[index["Test Date"]])
        record["test_date"] = date_value
        if date_flag != "ok":
            add_quality_flag(
                flags, "test_date", "Test Date", row[index["Test Date"]], date_flag
            )
        for canonical, raw_name in CATEGORICAL_FIELDS.items():
            value, flag = categorical(row[index[raw_name]])
            record[canonical] = value
            if flag != "ok":
                add_quality_flag(flags, canonical, raw_name, row[index[raw_name]], flag)
        for canonical, raw_name in NUMERIC_FIELDS.items():
            parsed = parse_number(row[index[raw_name]])
            record[canonical] = parsed.value
            add_quality_flag(flags, canonical, raw_name, row[index[raw_name]], parsed.flag)
            if canonical == "burning_rate_mm_as_labeled" and parsed.value is not None:
                flags.append(
                    {
                        "field": canonical,
                        "raw_field": raw_name,
                        "token": parsed.raw,
                        "flag": "unit_ambiguity",
                    }
                )
        record["quality_flags"] = json.dumps(flags, ensure_ascii=False)
        record["raw_row_json"] = raw_row_json(table.header, row)
        result.records.append(record)

    result.metadata = {
        "encoding": table.encoding,
        "encoding_fallback": table.encoding_fallback,
        "encoding_note": (
            "Source decoded with Windows-1252 fallback; 0x96 bytes are en dashes, "
            "not replacement characters."
            if table.encoding_fallback
            else "Source decoded as UTF-8."
        ),
        "unit_note": (
            "Burning rate; mm is preserved exactly as labeled. The unit is "
            "ambiguous and is not converted to mm/s."
        ),
    }
    return result
