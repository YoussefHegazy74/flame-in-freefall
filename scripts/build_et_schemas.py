#!/usr/bin/env python3
"""Build or check ``data/registry/experimental_table_schemas.json``.

The schema registry is generated from the authenticated experimental-table
files, not from a hand-written guess. It records the exact header, row counts,
checksum, encoding, and blank-row behavior for every one of the 22 tables.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_pipeline.config import ET_CSV, ET_SCHEMAS_JSON, RAW_DIR
from src.data_pipeline.parsers.base import decode_bytes
from src.data_pipeline.parsers.csv_reader import read_csv_table
from src.data_pipeline.provenance import source_from_path

SCHEMA_VERSION = "1.0.0"
GENERATED_DATE = "2026-11-09"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_schemas() -> dict:
    with ET_CSV.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    tables = {}
    for row in rows:
        accession = row["accession"]
        file_name = row["file_name"]
        path = RAW_DIR / accession / file_name
        if not path.exists():
            raise FileNotFoundError(
                f"missing raw experimental table {path}; run the downloader first"
            )
        actual_sha = sha256_file(path)
        if actual_sha != row["sha256"]:
            raise ValueError(
                f"{accession} / {file_name}: checksum {actual_sha} does not match "
                f"the registry {row['sha256']}"
            )
        source = source_from_path(accession, file_name, path, sha256=actual_sha)
        table = read_csv_table(path, source)
        expected_physical = int(row["physical_rows"])
        expected_data = int(row["data_rows"])
        if table.physical_rows != expected_physical or table.data_rows != expected_data:
            raise ValueError(
                f"{accession} / {file_name}: expected {expected_physical} physical / "
                f"{expected_data} data rows, found {table.physical_rows} / {table.data_rows}"
            )
        if len(table.header) != int(row["columns"]):
            raise ValueError(
                f"{accession} / {file_name}: expected {row['columns']} columns, "
                f"found {len(table.header)}"
            )
        table_id = f"{accession}::{file_name}"
        tables[table_id] = {
            "accession": accession,
            "file_name": file_name,
            "sha256": actual_sha,
            "size_bytes": path.stat().st_size,
            "physical_rows": table.physical_rows,
            "data_rows": table.data_rows,
            "empty_rows": table.physical_rows - table.data_rows,
            "columns": len(table.header),
            "header": table.header,
            "encoding": table.encoding,
            "encoding_fallback": table.encoding_fallback,
            "in_added": row["in_added"].strip().lower() == "true",
            "notes": row.get("notes", ""),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_date": GENERATED_DATE,
        "source_registry": "data/registry/psi_experimental_tables.csv",
        "table_count": len(tables),
        "tables": dict(sorted(tables.items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare the committed schema with a fresh build; exit 1 on drift.",
    )
    args = parser.parse_args(argv)

    schemas = build_schemas()
    generated = json.dumps(schemas, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if not ET_SCHEMAS_JSON.exists():
            print(f"missing committed schema: {ET_SCHEMAS_JSON}", file=sys.stderr)
            return 1
        if ET_SCHEMAS_JSON.read_text(encoding="utf-8") != generated:
            print("experimental-table schema drift detected", file=sys.stderr)
            return 1
        print(
            f"Committed schema matches {schemas['table_count']} authenticated "
            f"experimental tables."
        )
        return 0
    ET_SCHEMAS_JSON.parent.mkdir(parents=True, exist_ok=True)
    ET_SCHEMAS_JSON.write_text(generated, encoding="utf-8")
    print(
        f"Wrote {ET_SCHEMAS_JSON} with {schemas['table_count']} tables "
        f"and {sum(t['data_rows'] for t in schemas['tables'].values())} data rows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
