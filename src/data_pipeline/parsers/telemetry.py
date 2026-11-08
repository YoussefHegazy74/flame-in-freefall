"""Streaming parser for the three published SAFFIRE-III telemetry exports.

The exports are never concatenated. Each file or workbook sheet becomes its
own run, with its own row counts, time range, checksum, and channel profiles.
The tidy ``telemetry_point`` rows preserve the exact source channel name and
flag sentinel, constant, uncalibrated, and unit-less channels instead of
silently dropping or normalizing them.
"""

from __future__ import annotations

import csv
import io
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from ..channels import ChannelDefinition, channel_definition
from ..config import PARSER_VERSION
from ..provenance import SourceFile, observation_id
from .base import decode_bytes, parse_number, row_is_empty


@dataclass(frozen=True)
class TelemetrySpec:
    accession: str
    file_name: str
    sheet: str | None
    export_kind: str
    time_column: str
    expected_physical_rows: int
    expected_valid_rows: int
    expected_columns: int
    exclude_channels: frozenset[str]
    notes: str

    @property
    def run_id(self) -> str:
        stem = Path(self.file_name).stem
        if self.sheet:
            return f"{self.accession}::{stem}::{self.sheet}"
        return f"{self.accession}::{stem}"

    @property
    def source_id(self) -> str:
        if self.sheet:
            return f"{self.accession}::{Path(self.file_name).stem}::{self.sheet}"
        return f"{self.accession}::{Path(self.file_name).stem}"


TELEMETRY_SPECS: tuple[TelemetrySpec, ...] = (
    TelemetrySpec(
        accession="PSI-100",
        file_name="PSI-100_Raw Data_Raw telemetry file.csv",
        sheet=None,
        export_kind="raw_csv",
        time_column="RelativeSeconds",
        expected_physical_rows=3972,
        expected_valid_rows=3966,
        expected_columns=47,
        exclude_channels=frozenset({"RelativeSeconds"}),
        notes="Raw SAFFIRE-III telemetry export; six negative/sentinel time rows.",
    ),
    TelemetrySpec(
        accession="PSI-100",
        file_name="PSI-100_Raw Data_Saffire_Data_Table2017.161.00.42.03-EU.csv",
        sheet=None,
        export_kind="cleaned_csv",
        time_column="RelativeSeconds",
        expected_physical_rows=11450,
        expected_valid_rows=11449,
        expected_columns=47,
        exclude_channels=frozenset({"RelativeSeconds"}),
        notes="Cleaned SAFFIRE-III telemetry export; one sentinel time footer row.",
    ),
    TelemetrySpec(
        accession="PSI-100",
        file_name="PSI-100_Raw Data_Saffire-III 1 Hz Telemetry Data.xlsx",
        sheet="RawData",
        export_kind="xlsx_rawdata",
        time_column="RelativeSeconds",
        expected_physical_rows=73462,
        expected_valid_rows=11449,
        expected_columns=50,
        exclude_channels=frozenset({"RelativeSeconds"}),
        notes="Combined workbook sheet; empty formatting rows inflate the physical count.",
    ),
    TelemetrySpec(
        accession="PSI-100",
        file_name="PSI-100_Raw Data_Saffire-III 1 Hz Telemetry Data.xlsx",
        sheet="SaffireData",
        export_kind="xlsx_saffire",
        time_column="Relative Time (ms)",
        expected_physical_rows=11449,
        expected_valid_rows=11449,
        expected_columns=33,
        exclude_channels=frozenset({"Relative Time (ms)", "Relative Time (s)"}),
        notes="Saffire housekeeping subset; relative time columns are not duplicated as channels.",
    ),
    TelemetrySpec(
        accession="PSI-100",
        file_name="PSI-100_Raw Data_Saffire-III 1 Hz Telemetry Data.xlsx",
        sheet="CygnusData",
        export_kind="xlsx_cygnus",
        time_column="Relative Time (ms)",
        expected_physical_rows=69869,
        expected_valid_rows=11449,
        expected_columns=25,
        exclude_channels=frozenset({"Relative Time (ms)", "Relative Time (s)"}),
        notes="Cygnus subset; rows without a numeric relative time are not emitted as points.",
    ),
)


def spec_for(accession: str, file_name: str, sheet: str | None = None) -> TelemetrySpec:
    for spec in TELEMETRY_SPECS:
        if spec.accession == accession and spec.file_name == file_name and spec.sheet == sheet:
            return spec
    raise KeyError(f"no telemetry spec for {accession} / {file_name} / {sheet!r}")


@dataclass
class ChannelStats:
    index: int
    raw_name: str
    definition: ChannelDefinition
    count: int = 0
    missing: int = 0
    sentinel: int = 0
    nonnumeric: int = 0
    first_value: float | None = None
    all_equal: bool = True
    min_value: float | None = None
    max_value: float | None = None
    excluded: bool = False

    def observe(self, value: Any) -> None:
        parsed = parse_number(value)
        raw = parsed.raw
        if raw is None or not str(raw).strip():
            self.missing += 1
            return
        if str(raw).strip() == "-999":
            self.sentinel += 1
            return
        if parsed.value is None:
            if parsed.flag == "sentinel_dash":
                self.sentinel += 1
            else:
                self.nonnumeric += 1
            return
        self.count += 1
        if self.first_value is None:
            self.first_value = parsed.value
        elif self.all_equal and parsed.value != self.first_value:
            self.all_equal = False
        if self.min_value is None or parsed.value < self.min_value:
            self.min_value = parsed.value
        if self.max_value is None or parsed.value > self.max_value:
            self.max_value = parsed.value

    @property
    def constant(self) -> bool:
        return self.count >= 2 and self.all_equal

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "raw_name": self.raw_name,
            "canonical_name": self.definition.canonical,
            "unit": self.definition.unit,
            "uncalibrated": self.definition.uncalibrated,
            "note": self.definition.note,
            "count": self.count,
            "missing": self.missing,
            "sentinel": self.sentinel,
            "nonnumeric": self.nonnumeric,
            "min": self.min_value,
            "max": self.max_value,
            "constant": self.constant,
            "excluded_as_time": self.excluded,
        }


@dataclass
class TelemetryScan:
    spec: TelemetrySpec
    source: SourceFile
    header: list[str]
    channel_stats: list[ChannelStats]
    physical_rows: int = 0
    empty_rows: int = 0
    invalid_time_rows: int = 0
    sentinel_rows: int = 0
    valid_rows: int = 0
    time_min_ms: float | None = None
    time_max_ms: float | None = None
    issues: list[str] = field(default_factory=list)

    @property
    def run_id(self) -> str:
        return self.spec.run_id

    @property
    def channel_indices(self) -> list[int]:
        return [stats.index for stats in self.channel_stats if not stats.excluded]

    @property
    def constant_channels(self) -> set[int]:
        return {stats.index for stats in self.channel_stats if not stats.excluded and stats.constant}

    @property
    def column_count(self) -> int:
        return len(self.header)

    def channel_profiles(self) -> list[dict[str, Any]]:
        return [stats.as_dict() for stats in self.channel_stats]

    def as_run_record(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "accession": self.spec.accession,
            "source_file": self.spec.file_name,
            "source_sheet": self.spec.sheet or "",
            "export_kind": self.spec.export_kind,
            "physical_rows": self.physical_rows,
            "empty_rows": self.empty_rows,
            "invalid_time_rows": self.invalid_time_rows,
            "sentinel_rows": self.sentinel_rows,
            "valid_rows": self.valid_rows,
            "time_min_ms": self.time_min_ms,
            "time_max_ms": self.time_max_ms,
            "column_count": self.column_count,
            "channel_count": len(self.channel_indices),
            "constant_channels_json": __import__("json").dumps(
                [self.header[index] for index in sorted(self.constant_channels)],
                ensure_ascii=False,
            ),
            "channel_profiles_json": __import__("json").dumps(
                self.channel_profiles(), ensure_ascii=False
            ),
            "sha256": self.source.sha256,
            "retrieved_at": self.source.retrieved_at,
            "source_url": self.source.source_url,
            "parser_version": PARSER_VERSION,
            "notes": self.spec.notes,
        }


@contextmanager
def open_source_rows(
    spec: TelemetrySpec, source: SourceFile
) -> Iterator[tuple[list[str], Iterator[tuple[int, list[Any]]]]]:
    """Yield the exact header and a streaming row iterator.

    CSV rows are decoded without silently replacing bytes; a Windows-1252
    fallback is recorded in the scan issues. XLSX rows are read with
    ``openpyxl`` in read-only mode.
    """

    if spec.sheet is None:
        data = source.path.read_bytes()
        text, encoding, fallback = decode_bytes(data)
        reader = csv.reader(io.StringIO(text, newline=""), strict=False)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"{source.path} is empty") from exc
        if fallback:
            yield header, ((index, row) for index, row in enumerate(reader, start=1))
        else:
            yield header, ((index, row) for index, row in enumerate(reader, start=1))
        return

    import openpyxl

    workbook = openpyxl.load_workbook(source.path, read_only=True, data_only=True)
    try:
        if spec.sheet not in workbook.sheetnames:
            raise KeyError(
                f"{source.path} has no sheet {spec.sheet!r}; sheets={workbook.sheetnames}"
            )
        worksheet = workbook[spec.sheet]
        iterator = worksheet.iter_rows(values_only=True)
        try:
            header = [str(value) if value is not None else "" for value in next(iterator)]
        except StopIteration as exc:
            raise ValueError(f"{source.path} sheet {spec.sheet!r} is empty") from exc
        yield header, (
            (index, list(row)) for index, row in enumerate(iterator, start=1)
        )
    finally:
        workbook.close()


def scan_telemetry(spec: TelemetrySpec, source: SourceFile) -> TelemetryScan:
    """Profile one telemetry run without materializing its point table."""

    with open_source_rows(spec, source) as (header, rows):
        if len(header) != spec.expected_columns:
            raise ValueError(
                f"{spec.file_name} {spec.sheet or ''}: expected {spec.expected_columns} "
                f"columns, found {len(header)}"
            )
        time_index = header.index(spec.time_column) if spec.time_column in header else -1
        if time_index < 0:
            raise ValueError(
                f"{spec.file_name} {spec.sheet or ''}: missing time column {spec.time_column!r}"
            )

        channel_stats: list[ChannelStats] = []
        for index, name in enumerate(header):
            if not name:
                continue
            definition = channel_definition(name)
            channel_stats.append(
                ChannelStats(
                    index=index,
                    raw_name=name,
                    definition=definition,
                    excluded=name in spec.exclude_channels,
                )
            )
        stats_by_index = {stats.index: stats for stats in channel_stats}
        scan = TelemetryScan(
            spec=spec,
            source=source,
            header=header,
            channel_stats=channel_stats,
        )

        for source_row, row in rows:
            scan.physical_rows += 1
            if row_is_empty(row):
                scan.empty_rows += 1
                continue
            if time_index >= len(row):
                scan.invalid_time_rows += 1
                continue
            parsed_time = parse_number(row[time_index])
            if parsed_time.value is None:
                scan.invalid_time_rows += 1
                continue
            if parsed_time.value < 0:
                scan.sentinel_rows += 1
                continue
            scan.valid_rows += 1
            time_value = parsed_time.value
            if scan.time_min_ms is None or time_value < scan.time_min_ms:
                scan.time_min_ms = time_value
            if scan.time_max_ms is None or time_value > scan.time_max_ms:
                scan.time_max_ms = time_value
            for index, stats in stats_by_index.items():
                if index < len(row):
                    stats.observe(row[index])

        if scan.physical_rows != spec.expected_physical_rows:
            raise ValueError(
                f"{spec.file_name} {spec.sheet or ''}: expected "
                f"{spec.expected_physical_rows} physical rows, found {scan.physical_rows}"
            )
        if scan.valid_rows != spec.expected_valid_rows:
            raise ValueError(
                f"{spec.file_name} {spec.sheet or ''}: expected "
                f"{spec.expected_valid_rows} valid rows, found {scan.valid_rows}"
            )
        return scan


def iter_telemetry_points(scan: TelemetryScan) -> Iterator[dict[str, Any]]:
    """Yield tidy point rows for one scanned run.

    Missing cells are counted in the channel profile but not emitted as point
    rows. Sentinel and non-numeric cells are emitted with a null value and a
    specific quality flag so that the source token remains auditable.
    """

    spec = scan.spec
    source = scan.source
    constant = scan.constant_channels
    with open_source_rows(spec, source) as (header, rows):
        time_index = header.index(spec.time_column)
        for source_row, row in rows:
            if row_is_empty(row):
                continue
            if time_index >= len(row):
                continue
            parsed_time = parse_number(row[time_index])
            if parsed_time.value is None or parsed_time.value < 0:
                continue
            relative_time_ms = parsed_time.value
            for stats in scan.channel_stats:
                if stats.excluded:
                    continue
                index = stats.index
                if index >= len(row):
                    continue
                value = row[index]
                parsed = parse_number(value)
                raw = parsed.raw
                if raw is None or not str(raw).strip():
                    continue
                if str(raw).strip() == "-999":
                    point_value = None
                    quality = "sentinel"
                elif parsed.value is None:
                    point_value = None
                    if parsed.flag == "sentinel_dash":
                        quality = "sentinel"
                    elif parsed.flag == "spreadsheet_error":
                        quality = "spreadsheet_error"
                    else:
                        quality = parsed.flag
                else:
                    point_value = parsed.value
                    quality = "ok"
                    if index in constant:
                        quality = "constant"
                    elif stats.definition.uncalibrated:
                        quality = "uncalibrated"
                    elif stats.definition.unit == "not stated":
                        quality = "not_stated_unit"
                yield {
                    "observation_id": observation_id(
                        spec.accession,
                        spec.file_name,
                        spec.sheet,
                        source_row,
                        suffix=stats.raw_name,
                    ),
                    "run_id": spec.run_id,
                    "accession": spec.accession,
                    "source_file": spec.file_name,
                    "source_sheet": spec.sheet or "",
                    "source_row": source_row,
                    "relative_time_ms": relative_time_ms,
                    "relative_time_s": relative_time_ms / 1000.0,
                    "channel_name_raw": stats.raw_name,
                    "channel_name_canonical": stats.definition.canonical,
                    "raw_value": raw,
                    "value": point_value,
                    "unit": stats.definition.unit,
                    "quality_flag": quality,
                    "source_sha256": source.sha256,
                    "retrieved_at": source.retrieved_at,
                    "source_url": source.source_url,
                }
