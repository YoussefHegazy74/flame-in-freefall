#!/usr/bin/env python3
"""Build authentic small fixtures from the verified raw NASA PSI files.

A fixture is never fabricated. It is an exact header plus a small number of
real source rows, copied without changing field values. The generator records
the source file checksum and the 1-based source data-row numbers in
``data/fixtures/fixtures_manifest.json``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_pipeline.config import FIXTURES_DIR, RAW_DIR
from src.data_pipeline.provenance import load_acquisition_index

MANIFEST_JSON = FIXTURES_DIR / "fixtures_manifest.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_source(path: Path, encoding: str | None = None) -> tuple[list[str], list[list[str]], str]:
    data = path.read_bytes()
    if encoding is None:
        try:
            text = data.decode("utf-8-sig")
            encoding = "utf-8-sig"
        except UnicodeDecodeError:
            text = data.decode("cp1252")
            encoding = "cp1252"
    else:
        text = data.decode(encoding)
    reader = csv.reader(io.StringIO(text, newline=""), strict=False)
    header = next(reader)
    rows = [list(row) for row in reader]
    return header, rows, encoding


def write_fixture(
    *,
    relative_source: str,
    fixture_name: str,
    data_rows: list[int],
    purpose: str,
    encoding: str | None = None,
    write: bool = True,
) -> dict:
    source_path = RAW_DIR / relative_source
    if not source_path.exists():
        raise FileNotFoundError(f"missing source: {source_path}")
    header, rows, used_encoding = read_source(source_path, encoding=encoding)
    selected: list[list[str]] = []
    for row_number in data_rows:
        if row_number < 1 or row_number > len(rows):
            raise IndexError(f"{relative_source}: data row {row_number} is out of range")
        selected.append(rows[row_number - 1])

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(selected)
    payload = buffer.getvalue().encode(used_encoding)
    destination = FIXTURES_DIR / "csv" / fixture_name
    if write:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)

    source_bytes = source_path.read_bytes()
    return {
        "fixture": str(destination.relative_to(ROOT)),
        "source": relative_source,
        "source_sha256": sha256_bytes(source_bytes),
        "source_rows": data_rows,
        "fixture_sha256": sha256_bytes(payload),
        "fixture_bytes": len(payload),
        "encoding": used_encoding,
        "columns": len(header),
        "data_rows": len(selected),
        "purpose": purpose,
    }


def find_row(rows: list[list[str]], column_index: int, token: str) -> int:
    for index, row in enumerate(rows, start=1):
        if len(row) > column_index and row[column_index].strip() == token:
            return index
    raise ValueError(f"token {token!r} not found in column {column_index}")


def build(write: bool = True) -> dict:
    fixtures: list[dict] = []
    fixtures.append(
        write_fixture(
            relative_source="PSI-10/PSI-10_Experimental table_Flame Design_Normal Flame.csv",
            fixture_name="psi10_normal_sentinels.csv",
            data_rows=[1, 2, 188],
            purpose="Normal row, RAMPED condition, and missing final O2/pressure state.",
            write=write,
        )
    )
    fixtures.append(
        write_fixture(
            relative_source="PSI-159/PSI-159_Experimental table_CFI-G_Normal Flames.csv",
            fixture_name="psi159_normal_sample.csv",
            data_rows=[1, 2, 83],
            purpose="Normal CFI-G rows, including a TFP categorical flag and dash sentinels.",
            write=write,
        )
    )
    fixtures.append(
        write_fixture(
            relative_source="PSI-159/PSI-159_Experimental table_CFI-G_Inverse Flames.csv",
            fixture_name="psi159_inverse_errors.csv",
            data_rows=[1, 83, 95, 96],
            purpose="Inverse CFI-G rows with dash sentinels, blank color, and #VALUE! cells.",
            write=write,
        )
    )
    fixtures.append(
        write_fixture(
            relative_source="PSI-69/PSI-69_Experimental table_FLEX.csv",
            fixture_name="psi69_flex_cp1252.csv",
            data_rows=[1, 24, 274],
            purpose=(
                "Windows-1252 FLEX rows; the 0x96 byte in row 24 is an en dash "
                "and must decode without replacement."
            ),
            encoding="cp1252",
            write=write,
        )
    )

    hkp_path = RAW_DIR / "PSI-101/PSI-101_Raw Data_HKPData_gmt250_1.csv"
    hkp_header, hkp_rows, _ = read_source(hkp_path)
    sentinel_row = find_row(hkp_rows, hkp_header.index("PTrakMeasurement(PtPerCC)"), "-999")
    fixtures.append(
        write_fixture(
            relative_source="PSI-101/PSI-101_Raw Data_HKPData_gmt250_1.csv",
            fixture_name="psi101_hkp_sentinel.csv",
            data_rows=[1, sentinel_row],
            purpose="SAME-R rows with a normal P-Trak value and a -999 instrument sentinel.",
            write=write,
        )
    )

    indefinite_path = RAW_DIR / "PSI-101/PSI-101_Raw Data_HKPData_gmt242_6_run89.csv"
    indefinite_header, indefinite_rows, _ = read_source(indefinite_path)
    indefinite_row = find_row(
        indefinite_rows, indefinite_header.index("GasPlumeTemperature(DegC)"), "-1.#IND"
    )
    fixtures.append(
        write_fixture(
            relative_source="PSI-101/PSI-101_Raw Data_HKPData_gmt242_6_run89.csv",
            fixture_name="psi101_hkp_indefinite.csv",
            data_rows=[1, indefinite_row],
            purpose="SAME-R row with the Windows indefinite token -1.#IND.",
            write=write,
        )
    )

    raw_path = RAW_DIR / "PSI-100/PSI-100_Raw Data_Raw telemetry file.csv"
    raw_header, raw_rows, _ = read_source(raw_path)
    negative_row = None
    for index, row in enumerate(raw_rows, start=1):
        try:
            if float(row[0]) < 0:
                negative_row = index
                break
        except (ValueError, IndexError):
            continue
    if negative_row is None:
        raise ValueError("no negative relative-time row found in PSI-100 raw telemetry")
    fixtures.append(
        write_fixture(
            relative_source="PSI-100/PSI-100_Raw Data_Raw telemetry file.csv",
            fixture_name="psi100_raw_sample.csv",
            data_rows=[1, negative_row, 3],
            purpose="Raw SAFFIRE-III rows with a valid time, a negative sentinel time, and scientific notation.",
            write=write,
        )
    )

    acquisition = load_acquisition_index()
    for item in fixtures:
        source_name = Path(item["source"]).name
        accession = Path(item["source"]).parent.name
        record = acquisition.get((accession, source_name))
        if record and record.get("sha256_actual"):
            if item["source_sha256"] != record["sha256_actual"]:
                raise ValueError(
                    f"{item['source']}: source checksum does not match the acquisition manifest"
                )

    manifest = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "note": (
            "Fixtures are exact headers plus selected real rows. Values are not edited. "
            "Source row numbers are 1-based among data rows after the header."
        ),
        "fixtures": fixtures,
    }
    if write:
        MANIFEST_JSON.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_JSON.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="rebuild and compare with committed fixtures")
    args = parser.parse_args(argv)
    manifest = build(write=not args.check)
    if args.check:
        committed = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
        if committed.get("fixtures") != manifest["fixtures"]:
            print("fixture manifest drift detected", file=sys.stderr)
            return 1
        for item in manifest["fixtures"]:
            path = ROOT / item["fixture"]
            if not path.exists():
                print(f"missing fixture: {path}", file=sys.stderr)
                return 1
            if sha256_bytes(path.read_bytes()) != item["fixture_sha256"]:
                print(f"fixture checksum drift: {path}", file=sys.stderr)
                return 1
        print(f"Fixtures match {len(manifest['fixtures'])} authenticated source excerpts.")
        return 0
    print(f"Wrote {len(manifest['fixtures'])} fixtures and {MANIFEST_JSON}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
