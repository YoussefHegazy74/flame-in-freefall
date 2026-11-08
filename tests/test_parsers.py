"""Parser behavior tests on authentic small fixtures."""

from __future__ import annotations

import json

import pytest

from src.data_pipeline.parsers.base import (
    HeaderMismatchError,
    RowCountMismatchError,
)
from src.data_pipeline.parsers.droplet import HEADER as DROPLET_HEADER
from src.data_pipeline.parsers.droplet import parse_droplet
from src.data_pipeline.parsers.gas_flame import (
    GasFlameSpec,
    parse_gas_flame,
    spec_for,
)
from src.data_pipeline.parsers.material import (
    PSI25_SHEETS,
    PSI26_EXPECTED_ROWS,
    PSI26_HEADER,
    PSI26_HEADER_ROW,
    parse_psi25,
    parse_psi26,
)
from src.data_pipeline.parsers.smoke import (
    iter_smoke_points,
    scan_smoke,
)
from src.data_pipeline.parsers.summary_table import parse_summary_tables
from src.data_pipeline.parsers.telemetry import (
    TelemetrySpec,
    iter_telemetry_points,
    scan_telemetry,
    spec_for as telemetry_spec_for,
)
from src.data_pipeline.parsers.test_log import (
    EXPECTED_ROWS as TEST_LOG_EXPECTED_ROWS,
    SHEET_NAME as TEST_LOG_SHEET,
    parse_test_log,
)
from src.data_pipeline.provenance import SourceFile


def flags_of(record: dict) -> list[dict]:
    return json.loads(record["quality_flags"])


def flag_names(record: dict) -> list[str]:
    return [flag["flag"] for flag in flags_of(record)]


def gas_spec(key: str, accession: str, file_name: str, rows: int) -> GasFlameSpec:
    return GasFlameSpec(
        key=key,
        accession=accession,
        file_name=file_name,
        flame_type="Normal" if key.endswith("normal") else "Inverse",
        expected_physical_rows=rows,
        expected_data_rows=rows,
    )


def test_gas_flame_psi10_fixture_rows_and_sentinels(source_factory, fixtures_dir):
    path = fixtures_dir / "psi10_normal_sentinels.csv"
    source = source_factory(path, accession="PSI-10", file_name=path.name)
    result = parse_gas_flame(
        source,
        gas_spec(
            "PSI-10_normal",
            "PSI-10",
            "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
            3,
        ),
    )
    assert (result.physical_rows, result.data_rows) == (3, 3)
    assert len(result.records) == 3

    normal = result.records[0]
    assert normal["test_code"] == "19115A1"
    assert normal["fuel"] == "C2H4"
    assert normal["oxygen_mole_fraction_initial"] == pytest.approx(0.207128374)
    assert normal["adiabatic_flame_temp_k"] == pytest.approx(2352.144414)
    assert flags_of(normal) == []

    ramped = result.records[1]
    assert ramped["test_code"] == "19115D2"
    assert ramped["fuel_mole_fraction"] is None
    assert "ramped_condition" in flag_names(ramped)
    assert "has_ramped_condition" in flag_names(ramped)

    missing_final = result.records[2]
    assert missing_final["test_code"] == "21301A1"
    assert missing_final["oxygen_mole_fraction_final"] is None
    assert missing_final["pressure_final_atm"] is None
    assert missing_final["pressure_mean_atm"] is None
    assert "has_missing_final_state" in flag_names(missing_final)


def test_gas_flame_psi159_inverse_fixture_errors(source_factory, fixtures_dir):
    path = fixtures_dir / "psi159_inverse_errors.csv"
    source = source_factory(path, accession="PSI-159", file_name=path.name)
    result = parse_gas_flame(
        source,
        gas_spec(
            "PSI-159_inverse",
            "PSI-159",
            "PSI-159_Experimental table_CFI-G_Inverse Flames.csv",
            4,
        ),
    )
    assert len(result.records) == 4

    first = result.records[0]
    assert first["test_code"] == "21196 A1"
    assert first["extinction_mode"] is None
    assert first["color"] is None
    assert first["tfp_flag"] == "No"
    assert first["comments"] == "Failed to ignite"
    assert "sentinel_dash" in flag_names(first)

    error_row = result.records[2]
    assert error_row["peak_burner_temp_k"] is None
    assert "spreadsheet_error" in flag_names(error_row)
    assert "has_spreadsheet_error" in flag_names(error_row)


def test_gas_flame_psi159_normal_fixture_categorical_tfp(source_factory, fixtures_dir):
    path = fixtures_dir / "psi159_normal_sample.csv"
    source = source_factory(path, accession="PSI-159", file_name=path.name)
    result = parse_gas_flame(
        source,
        gas_spec(
            "PSI-159_normal",
            "PSI-159",
            "PSI-159_Experimental table_CFI-G_Normal Flames.csv",
            3,
        ),
    )
    assert result.records[0]["cool_flame_flag"] is None
    assert result.records[1]["tfp_flag"] == "Yes"
    assert result.records[2]["peak_burner_temp_c"] == pytest.approx(34.0)
    assert result.metadata["tfp_semantics"].startswith("categorical")


def test_gas_flame_fails_closed_on_header_and_row_count(source_factory, fixtures_dir):
    path = fixtures_dir / "psi10_normal_sentinels.csv"
    source = source_factory(path, accession="PSI-10", file_name=path.name)
    with pytest.raises(HeaderMismatchError):
        parse_gas_flame(
            source,
            gas_spec(
                "PSI-159_normal",
                "PSI-159",
                "PSI-159_Experimental table_CFI-G_Normal Flames.csv",
                3,
            ),
        )
    with pytest.raises(RowCountMismatchError):
        parse_gas_flame(
            source,
            gas_spec(
                "PSI-10_normal",
                "PSI-10",
                "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
                99,
            ),
        )
    with pytest.raises(KeyError):
        spec_for("PSI-999", "missing.csv")


def test_droplet_fixture_cp1252_and_unit_ambiguity(
    source_factory, fixtures_dir, monkeypatch
):
    import src.data_pipeline.parsers.droplet as droplet

    monkeypatch.setattr(droplet, "EXPECTED_PHYSICAL_ROWS", 3)
    monkeypatch.setattr(droplet, "EXPECTED_DATA_ROWS", 3)
    path = fixtures_dir / "psi69_flex_cp1252.csv"
    source = source_factory(path, accession="PSI-69", file_name=path.name)
    result = parse_droplet(source)

    assert (result.physical_rows, result.data_rows) == (3, 3)
    assert result.metadata["encoding_fallback"] is True
    assert "Windows-1252" in result.metadata["encoding_note"]
    assert any(issue.code == "encoding_fallback" for issue in result.issues)

    first = result.records[0]
    assert first["flex_test_number"] == 1
    assert first["test_date"] == "2009-03-05"
    assert first["ambient_pressure_mm_hg"] == pytest.approx(757.7)
    assert first["burning_rate_mm_as_labeled"] == pytest.approx(0.52)
    assert "unit_ambiguity" in flag_names(first)

    en_dash_row = result.records[1]
    assert en_dash_row["visible_flame_extinction_diameter_mm"] is None
    assert "sentinel_dash" in flag_names(en_dash_row)
    assert en_dash_row["burning_rate_mm_as_labeled"] is None

    last = result.records[2]
    assert last["flex_test_number"] == 274
    assert last["fuel"] == "Heptane"


def test_smoke_fixture_preserves_minus_999_and_indefinite(source_factory, fixtures_dir):
    path = fixtures_dir / "psi101_hkp_sentinel.csv"
    source = source_factory(path, accession="PSI-101", file_name=path.name)
    scan = scan_smoke(source)
    assert (scan.physical_rows, scan.valid_rows) == (2, 2)
    assert scan.malformed_rows == 0
    assert scan.time_min_unix_s == 1283862804
    assert scan.time_max_unix_s == 1283863240

    ptrak = next(stats for stats in scan.stats if stats.raw_name == "PTrakMeasurement(PtPerCC)")
    assert ptrak.sentinel == 1
    assert ptrak.unit == "pt/cc"

    indefinite_source = source_factory(
        fixtures_dir / "psi101_hkp_indefinite.csv",
        accession="PSI-101",
        file_name="PSI-101_Raw Data_HKPData_gmt242_6_run89.csv",
    )
    indefinite_scan = scan_smoke(indefinite_source)
    plume = next(
        stats
        for stats in indefinite_scan.stats
        if stats.raw_name == "GasPlumeTemperature(DegC)"
    )
    assert plume.nonnumeric == 1
    points = list(iter_smoke_points(indefinite_scan))
    invalid = [point for point in points if point["quality_flag"] == "invalid_indefinite"]
    assert len(invalid) == 1
    assert invalid[0]["value"] is None
    assert invalid[0]["raw_value"] == "-1.#IND"


def test_smoke_points_emit_sentinel_with_null_value(source_factory, fixtures_dir):
    path = fixtures_dir / "psi101_hkp_sentinel.csv"
    source = source_factory(path, accession="PSI-101", file_name=path.name)
    scan = scan_smoke(source)
    points = list(iter_smoke_points(scan))
    assert len(points) == 2 * len(scan.stats)
    sentinel = [
        point
        for point in points
        if point["channel_name_raw"] == "PTrakMeasurement(PtPerCC)"
        and point["quality_flag"] == "sentinel"
    ]
    assert len(sentinel) == 1
    assert sentinel[0]["value"] is None
    assert sentinel[0]["raw_value"] == "-999"


def test_smoke_fails_closed_on_wrong_header(source_factory, fixtures_dir):
    path = fixtures_dir / "psi10_normal_sentinels.csv"
    source = source_factory(path, accession="PSI-101", file_name=path.name)
    with pytest.raises(HeaderMismatchError):
        scan_smoke(source)


def test_telemetry_fixture_time_and_scientific_notation(source_factory, fixtures_dir):
    path = fixtures_dir / "psi100_raw_sample.csv"
    source = source_factory(path, accession="PSI-100", file_name=path.name)
    spec = TelemetrySpec(
        accession="PSI-100",
        file_name=path.name,
        sheet=None,
        export_kind="raw_csv",
        time_column="RelativeSeconds",
        expected_physical_rows=3,
        expected_valid_rows=2,
        expected_columns=47,
        exclude_channels=frozenset({"RelativeSeconds"}),
        notes="fixture",
    )
    scan = scan_telemetry(spec, source)
    assert (scan.physical_rows, scan.valid_rows) == (3, 2)
    assert scan.sentinel_rows == 1
    assert scan.time_min_ms == 0
    assert scan.time_max_ms == 1236
    assert len(scan.channel_indices) == 46

    points = list(iter_telemetry_points(scan))
    assert len(points) == 2 * 46
    relative = next(point for point in points if point["source_row"] == 3)
    assert relative["relative_time_s"] == pytest.approx(1.236)
    cygnus = next(
        point
        for point in points
        if point["channel_name_raw"] == "CygnusTimestamp" and point["source_row"] == 3
    )
    assert cygnus["value"] == pytest.approx(1.4966e12)
    assert cygnus["raw_value"] == "1.4966E+12"


def test_telemetry_spec_lookup_and_column_count_failure(source_factory, fixtures_dir):
    real = telemetry_spec_for(
        "PSI-100", "PSI-100_Raw Data_Raw telemetry file.csv", None
    )
    assert real.export_kind == "raw_csv"
    assert real.expected_columns == 47
    with pytest.raises(KeyError):
        telemetry_spec_for("PSI-999", "missing.csv", None)

    path = fixtures_dir / "psi100_raw_sample.csv"
    source = source_factory(path, accession="PSI-100", file_name=path.name)
    wrong = TelemetrySpec(
        accession="PSI-100",
        file_name=path.name,
        sheet=None,
        export_kind="raw_csv",
        time_column="RelativeSeconds",
        expected_physical_rows=3,
        expected_valid_rows=2,
        expected_columns=46,
        exclude_channels=frozenset(),
        notes="fixture",
    )
    with pytest.raises(ValueError, match="expected 46 columns"):
        scan_telemetry(wrong, source)


def test_material_constants_and_missing_workbook_behavior(repo_root):
    assert len(PSI25_SHEETS) == 6
    assert sum(expected_rows for _, expected_rows in PSI25_SHEETS.values()) == 129
    assert PSI26_EXPECTED_ROWS == 130
    assert PSI26_HEADER_ROW == 3
    assert len(PSI26_HEADER) == 30
    assert "O2 % by volume" in PSI26_HEADER

    missing = SourceFile(
        accession="PSI-25",
        file_name="missing.xlsx",
        path=repo_root / "data" / "raw" / "PSI-25" / "missing.xlsx",
        sha256="0" * 64,
        retrieved_at="2026-11-09T00:00:00Z",
        source_url="https://psi.nasa.gov/example",
    )
    with pytest.raises(FileNotFoundError):
        parse_psi25(missing)
    with pytest.raises(FileNotFoundError):
        parse_psi26(missing)


def test_test_log_constants_and_missing_workbook_behavior(repo_root):
    assert TEST_LOG_EXPECTED_ROWS == 119
    assert TEST_LOG_SHEET == "Copy of GMT252run1testlog"
    missing = SourceFile(
        accession="PSI-102",
        file_name="missing.xls",
        path=repo_root / "data" / "raw" / "PSI-102" / "missing.xls",
        sha256="0" * 64,
        retrieved_at="2026-11-09T00:00:00Z",
        source_url="https://psi.nasa.gov/example",
    )
    with pytest.raises(FileNotFoundError):
        parse_test_log(missing)


def test_summary_table_schema_registry_and_missing_source_behavior(repo_root):
    import json

    from src.data_pipeline.config import ET_SCHEMAS_JSON

    schemas = json.loads(ET_SCHEMAS_JSON.read_text(encoding="utf-8"))
    assert schemas["table_count"] == 22
    assert len(schemas["tables"]) == 22
    assert sum(table["data_rows"] for table in schemas["tables"].values()) == 2_009
    for table_id, table in schemas["tables"].items():
        assert table_id == f"{table['accession']}::{table['file_name']}"
        assert len(table["header"]) == table["columns"]
        assert table["physical_rows"] >= table["data_rows"]

    with pytest.raises(KeyError, match="missing source"):
        parse_summary_tables({})


def test_droplet_header_constant_matches_fixture(fixtures_dir):
    import csv
    import io

    text = (fixtures_dir / "psi69_flex_cp1252.csv").read_bytes().decode("cp1252")
    header = next(csv.reader(io.StringIO(text, newline="")))
    assert header == DROPLET_HEADER
