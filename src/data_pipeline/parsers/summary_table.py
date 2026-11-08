"""Generic parser for the 22 public experimental summary tables.

Every source cell is preserved in ``experimental_table_cell`` and every
non-empty source row in ``source_row``. This is the canonical representation
for the 18 tables that do not have a dedicated domain parser, and a provenance
backstop for the four that do. No common scientific schema is forced across
tables with incompatible fields.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import ET_CSV, ET_SCHEMAS_JSON, PARSER_VERSION, REGISTRY_JSON
from ..provenance import SourceFile, observation_id, raw_row_json
from .base import ParseIssue, parse_number
from .csv_reader import read_csv_table

PARSER_NAME = "summary_table"


@dataclass
class SummaryParseResult:
    table_metadata: list[dict[str, Any]] = field(default_factory=list)
    cells: list[dict[str, Any]] = field(default_factory=list)
    source_rows: list[dict[str, Any]] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)
    table_issues: dict[str, list[ParseIssue]] = field(default_factory=dict)
    table_count: int = 0
    cell_count: int = 0
    source_row_count: int = 0


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _restricted_map() -> dict[tuple[str, str], bool]:
    registry = _load_json(REGISTRY_JSON)
    result: dict[tuple[str, str], bool] = {}
    for investigation in registry["investigations"]:
        accession = investigation["accession"]
        for item in investigation.get("experimental_tables", []):
            result[(accession, item["file_name"])] = bool(item.get("restricted", False))
    return result


def parse_summary_tables(sources: dict[tuple[str, str], SourceFile]) -> SummaryParseResult:
    """Parse all 22 ETs. ``sources`` is keyed by ``(accession, file_name)``."""

    schemas = _load_json(ET_SCHEMAS_JSON)
    restricted = _restricted_map()
    result = SummaryParseResult()

    with ET_CSV.open("r", encoding="utf-8", newline="") as handle:
        registry_rows = {row["file_name"]: row for row in csv.DictReader(handle)}

    for table_id, schema in schemas["tables"].items():
        accession = schema["accession"]
        file_name = schema["file_name"]
        source = sources.get((accession, file_name))
        if source is None:
            raise KeyError(f"missing source for {table_id}")
        table = read_csv_table(source.path, source, expected_header=schema["header"])
        result.table_issues[table_id] = list(table.issues)
        result.issues.extend(table.issues)
        if table.physical_rows != schema["physical_rows"] or table.data_rows != schema["data_rows"]:
            raise ValueError(
                f"{table_id}: expected {schema['physical_rows']} physical / "
                f"{schema['data_rows']} data rows, found {table.physical_rows} / {table.data_rows}"
            )

        result.table_metadata.append(
            {
                "table_id": table_id,
                "accession": accession,
                "file_name": file_name,
                "file_size_bytes": schema["size_bytes"],
                "in_added": schema["in_added"],
                "restricted": restricted.get((accession, file_name), False),
                "data_rows": table.data_rows,
                "physical_rows": table.physical_rows,
                "columns": len(table.header),
                "sha256": source.sha256,
                "notes": schema.get("notes", ""),
                "encoding": table.encoding,
                "encoding_fallback": table.encoding_fallback,
                "retrieved_at": source.retrieved_at,
                "source_url": source.source_url,
                "parser_version": PARSER_VERSION,
            }
        )

        for source_row, row in table.iter_data_rows():
            nonempty = 0
            numeric = 0
            for column_index, raw_value in enumerate(row):
                text = "" if raw_value is None else str(raw_value)
                if not text.strip():
                    continue
                nonempty += 1
                parsed = parse_number(raw_value)
                if parsed.value is not None:
                    numeric += 1
                column_name = table.header[column_index] if column_index < len(table.header) else ""
                result.cells.append(
                    {
                        "cell_id": observation_id(
                            accession,
                            file_name,
                            None,
                            source_row,
                            suffix=f"col-{column_index:02d}",
                        ),
                        "table_id": table_id,
                        "accession": accession,
                        "source_file": file_name,
                        "source_row": source_row,
                        "source_column_index": column_index,
                        "source_column_name": column_name,
                        "raw_value": text,
                        "numeric_value": parsed.value,
                        "value_flag": parsed.flag,
                        "source_sha256": source.sha256,
                        "retrieved_at": source.retrieved_at,
                        "source_url": source.source_url,
                        "parser_version": PARSER_VERSION,
                    }
                )
            result.source_rows.append(
                {
                    "source_row_id": observation_id(
                        accession, file_name, None, source_row
                    ),
                    "table_id": table_id,
                    "accession": accession,
                    "source_file": file_name,
                    "source_row": source_row,
                    "nonempty_cell_count": nonempty,
                    "numeric_cell_count": numeric,
                    "raw_row_json": raw_row_json(table.header, row),
                    "source_sha256": source.sha256,
                    "retrieved_at": source.retrieved_at,
                    "source_url": source.source_url,
                    "parser_version": PARSER_VERSION,
                }
            )
        result.table_count += 1

    result.cell_count = len(result.cells)
    result.source_row_count = len(result.source_rows)
    return result
