"""DuckDB query-layer tests over a synthetic canonical dataset.

Every fixture row here is synthetic software test data. These tests verify the
query contract (filtering, bounds, pagination, sentinels, provenance, and the
watchdog) without making scientific claims about any real measurement.
"""

from __future__ import annotations

import threading

import duckdb
import pytest

from src.analytics.db import (
    MAX_PAGE_SIZE,
    MAX_SERIES_POINTS,
    AnalyticsDatabase,
)
from src.analytics.errors import (
    AnalyticsError,
    InvalidQueryError,
    LimitExceededError,
    NotFoundError,
    QueryTimeoutError,
)


@pytest.fixture
def db(synthetic_analytics):
    return synthetic_analytics["db"]


# ----------------------------------------------------------------------
# Health and metadata
# ----------------------------------------------------------------------
def test_health_reports_tables_and_dataset_version(db):
    health = db.health()
    assert health["database"] == "ok"
    assert health["dataset_version"] == "synthetic-version"
    assert health["available_tables"] == 13
    assert health["missing_tables"] == []


def test_table_counts_match_fixture_rows(db):
    counts = db.table_counts()
    assert counts["gas_flame_test"] == 4
    assert counts["telemetry_point"] == 13
    assert counts["smoke_point"] == 8


def test_missing_canonical_table_is_reported(tmp_path):
    from tests.conftest import _write_table

    processed = tmp_path / "processed"
    processed.mkdir()
    _write_table(processed, "psi_investigation", [])
    database = AnalyticsDatabase(
        processed_dir=processed, reports_dir=tmp_path, timeout_seconds=5
    )
    health = database.health()
    assert health["database"] == "degraded"
    assert health["available_tables"] == 1
    assert "gas_flame_test" in health["missing_tables"]


def test_empty_dataset_reports_unavailable(tmp_path):
    processed = tmp_path / "processed"
    processed.mkdir()
    database = AnalyticsDatabase(
        processed_dir=processed, reports_dir=tmp_path, timeout_seconds=5
    )
    health = database.health()
    assert health["database"] == "unavailable"
    assert health["available_tables"] == 0
    with pytest.raises(AnalyticsError) as excinfo:
        database.list_gas_flame_tests()
    assert excinfo.value.code == "service_unavailable"
    assert excinfo.value.http_status == 503


def test_quality_report_is_loaded(db):
    report = db.quality_report()
    assert report["summary"]["tables"] == 13


# ----------------------------------------------------------------------
# Pagination
# ----------------------------------------------------------------------
def test_pagination_reports_total_and_has_more(db):
    first = db.list_gas_flame_tests(include_qualified=True, limit=2, offset=0)
    second = db.list_gas_flame_tests(include_qualified=True, limit=2, offset=2)
    assert first.total == 4
    assert len(first.items) == 2
    assert first.has_more is True
    assert first.page()["has_more"] is True
    assert second.has_more is False
    assert {row["observation_id"] for row in first.items}.isdisjoint(
        {row["observation_id"] for row in second.items}
    )


def test_page_size_and_offset_are_bounded(db):
    with pytest.raises(LimitExceededError):
        db.list_gas_flame_tests(limit=0)
    with pytest.raises(LimitExceededError):
        db.list_gas_flame_tests(limit=MAX_PAGE_SIZE + 1)
    with pytest.raises(InvalidQueryError):
        db.list_gas_flame_tests(offset=-1)


# ----------------------------------------------------------------------
# Gas-flame filtering
# ----------------------------------------------------------------------
def test_gas_flame_qualified_rows_are_excluded_by_default(db):
    default = db.list_gas_flame_tests(accession="PSI-10")
    assert default.total == 1
    assert default.items[0]["observation_id"] == "g1"
    assert default.page()["excluded_qualified_rows"] == 1

    included = db.list_gas_flame_tests(accession="PSI-10", include_qualified=True)
    assert included.total == 2
    assert included.page()["excluded_qualified_rows"] == 0


def test_gas_flame_filters_are_explicit(db):
    assert db.list_gas_flame_tests(flame_type="Normal", include_qualified=True).total == 3
    assert db.list_gas_flame_tests(fuel="c2h4", include_qualified=True).total == 2
    assert db.list_gas_flame_tests(oxygen_min=0.2, include_qualified=True).total == 2
    assert db.list_gas_flame_tests(oxygen_max=0.2, include_qualified=True).total == 2
    assert db.list_gas_flame_tests(hot_ignition="Yes").total == 0


def test_pressure_filter_requires_accession_because_units_differ(db):
    with pytest.raises(InvalidQueryError) as excinfo:
        db.list_gas_flame_tests(pressure_min=0.5)
    assert "atm" in excinfo.value.message and "bar" in excinfo.value.message

    psi10 = db.list_gas_flame_tests(
        accession="PSI-10", pressure_min=1.5, include_qualified=True
    )
    assert psi10.total == 1
    assert psi10.page()["pressure_field"] == "pressure_initial_atm"
    assert psi10.page()["pressure_unit"] == "atm"

    psi159 = db.list_gas_flame_tests(
        accession="PSI-159", pressure_max=2.0, include_qualified=True
    )
    assert psi159.total == 1
    assert psi159.page()["pressure_field"] == "pressure_approx_bar"
    assert psi159.page()["pressure_unit"] == "bar"


def test_gas_flame_rejects_unknown_accession_and_sort(db):
    with pytest.raises(InvalidQueryError):
        db.list_gas_flame_tests(accession="PSI-101")
    with pytest.raises(InvalidQueryError):
        db.list_gas_flame_tests(sort="fuel")
    with pytest.raises(InvalidQueryError):
        db.list_gas_flame_tests(order="sideways")


def test_gas_flame_rows_label_computed_fields(db):
    row = db.get_gas_flame_test("g1")
    assert row["computed_fields"] == ["stoich_mixture_fraction", "adiabatic_flame_temp_k"]
    assert row["quality_flags"] == []


def test_gas_flame_observation_not_found(db):
    with pytest.raises(NotFoundError):
        db.get_gas_flame_test("missing")


# ----------------------------------------------------------------------
# Material and droplet filtering
# ----------------------------------------------------------------------
def test_material_o2_filter_requires_accession(db):
    with pytest.raises(InvalidQueryError):
        db.list_material_tests(o2_min=0.2)

    psi25 = db.list_material_tests(accession="PSI-25", o2_min=20.0)
    assert psi25.total == 1
    assert psi25.page()["o2_field"] == "initial_o2_pct"

    psi26 = db.list_material_tests(accession="PSI-26", o2_max=1.0)
    assert psi26.total == 1
    assert psi26.page()["o2_field"] == "o2_pct"
    assert "percent" in psi26.page()["o2_unit_note"]
    assert psi26.page()["spread_rate_available"] is False


def test_material_rejects_other_accessions(db):
    with pytest.raises(InvalidQueryError):
        db.list_material_tests(accession="PSI-10")


def test_droplet_filters_and_limits(db):
    assert db.list_droplet_tests().total == 2
    assert db.list_droplet_tests(fuel="heptane").total == 1
    assert db.list_droplet_tests(pressure_min=600).total == 1
    with pytest.raises(InvalidQueryError):
        db.list_droplet_tests(accession="PSI-10")


# ----------------------------------------------------------------------
# Telemetry
# ----------------------------------------------------------------------
def test_telemetry_runs_are_separate(db):
    page = db.list_telemetry_runs()
    assert page.total == 2
    assert [row["run_id"] for row in page.items] == ["run-a", "run-b"]
    assert all(row["time_unit"] == "ms" for row in page.items)

    filtered = db.list_telemetry_runs(export_kind="raw_csv")
    assert [row["run_id"] for row in filtered.items] == ["run-a"]


def test_telemetry_run_detail_labels_channel_quality(db):
    run = db.get_telemetry_run("run-a")
    channels = {channel["channel_name_canonical"]: channel for channel in run["channels"]}
    assert channels["pcm_air_temp_c"]["quality_flags"] == ["ok"]
    assert channels["radiometer_1_raw"]["quality_flags"] == ["uncalibrated", "not_stated_unit"]
    assert channels["constant_chan"]["quality_flags"] == ["not_stated_unit", "constant"]
    assert channels["missing_chan"]["quality_flags"] == ["not_stated_unit"]
    assert run["time_unit"] == "ms"
    assert "never concatenated" in run["limitations"][0]


def test_telemetry_series_returns_bounded_points(db):
    series = db.get_telemetry_series(
        "run-a", "pcm_air_temp_c,radiometer_1_raw", 0, 3000, max_points=100
    )
    assert series["returned_points"] == 3
    assert series["points"][0] == {
        "time_ms": 0.0,
        "pcm_air_temp_c": 20.0,
        "radiometer_1_raw": 1.0,
    }
    assert series["excluded_sentinel_rows"] == 1
    assert series["source_row_range"] == [2, 5]
    assert series["time_unit"] == "ms"


def test_telemetry_series_enforces_point_cap(db):
    with pytest.raises(LimitExceededError) as excinfo:
        db.get_telemetry_series("run-a", "pcm_air_temp_c", 0, 3000, max_points=2)
    assert excinfo.value.details["actual_points"] == 3
    assert excinfo.value.details["max_points"] == 2


def test_telemetry_series_rejects_bad_ranges_and_channels(db):
    with pytest.raises(InvalidQueryError):
        db.get_telemetry_series("run-a", "pcm_air_temp_c", 100, 100)
    with pytest.raises(InvalidQueryError):
        db.get_telemetry_series("run-a", "pcm_air_temp_c", -1, 100)
    with pytest.raises(InvalidQueryError):
        db.get_telemetry_series("run-a", "pcm_air_temp_c", 0, 4000)
    with pytest.raises(InvalidQueryError):
        db.get_telemetry_series("run-a", "does_not_exist", 0, 100)
    with pytest.raises(LimitExceededError):
        db.get_telemetry_series("run-a", "pcm_air_temp_c", 0, 100, max_points=MAX_SERIES_POINTS + 1)


def test_telemetry_series_requires_channels_and_range(db):
    with pytest.raises(InvalidQueryError):
        db.get_telemetry_series("run-a", None, 0, 100)
    with pytest.raises(InvalidQueryError):
        db.get_telemetry_series("run-a", "pcm_air_temp_c", None, 100)
    with pytest.raises(InvalidQueryError):
        db.get_telemetry_series("run-a", "pcm_air_temp_c", 0, None)


def test_telemetry_series_channel_cap(db):
    channels = ",".join(f"c{index}" for index in range(9))
    with pytest.raises(LimitExceededError):
        db.get_telemetry_series("run-a", channels, 0, 100)


def test_telemetry_run_not_found(db):
    with pytest.raises(NotFoundError):
        db.get_telemetry_run("missing-run")


# ----------------------------------------------------------------------
# Smoke
# ----------------------------------------------------------------------
def test_smoke_run_detail_labels_uncalibrated_channels(db):
    run = db.get_smoke_run("smoke-a")
    channels = {channel["channel_name_canonical"]: channel for channel in run["channels"]}
    assert channels["detector_1_v"]["quality_flags"] == ["uncalibrated"]
    assert channels["ptrak_count"]["quality_flags"] == ["not_stated_unit", "sentinel"]
    assert run["time_unit"] == "s"


def test_smoke_series_excludes_sentinels_and_invalid_rows(db):
    series = db.get_smoke_series(
        "smoke-a", "gas_plume_temp_c,detector_1_v,ptrak_count", 0, 4, max_points=100
    )
    assert series["returned_points"] == 3
    assert series["excluded_sentinel_rows"] == 1
    assert series["excluded_invalid_rows"] == 1
    assert series["source_row_range"] == [2, 6]
    assert series["points"][0]["gas_plume_temp_c"] == 23.0


def test_smoke_series_enforces_cap_and_range(db):
    with pytest.raises(LimitExceededError):
        db.get_smoke_series("smoke-a", "gas_plume_temp_c", 0, 4, max_points=1)
    with pytest.raises(InvalidQueryError):
        db.get_smoke_series("smoke-a", "gas_plume_temp_c", -1, 4)


# ----------------------------------------------------------------------
# Provenance
# ----------------------------------------------------------------------
def test_provenance_resolves_experimental_table_and_row(db):
    record = db.resolve_provenance("PSI-10", "gas.csv", row=2)
    assert record["origin"] == "experimental_table"
    assert record["sha256"] == "e" * 64
    assert record["row_verified"] is True
    assert set(record["row_tables"]) == {
        "gas_flame_test",
        "experimental_table_cell",
        "source_row",
    }


def test_provenance_falls_back_to_psi_file_and_warns_without_checksum(db):
    record = db.resolve_provenance("PSI-100", "telemetry.csv")
    assert record["origin"] == "psi_file"
    assert record["access_status"] == "available"
    assert record["warnings"] == ["checksum_not_available"]


def test_provenance_rejects_paths_and_missing_files(db):
    with pytest.raises(InvalidQueryError):
        db.resolve_provenance("PSI-10", "../gas.csv")
    with pytest.raises(InvalidQueryError):
        db.resolve_provenance("PSI-10", "/tmp/gas.csv")
    with pytest.raises(InvalidQueryError):
        db.resolve_provenance("PSI-10", "gas.csv", row=0)
    with pytest.raises(NotFoundError):
        db.resolve_provenance("PSI-10", "not-present.csv")


def test_accession_validation_rejects_sql_fragments(db):
    with pytest.raises(InvalidQueryError):
        db.get_investigation("PSI-10'; DROP TABLE gas_flame_test; --")


# ----------------------------------------------------------------------
# Dataset quality
# ----------------------------------------------------------------------
def test_dataset_quality_filters_issues_by_accession(db):
    all_quality = db.dataset_quality(["gas_flame_test"])
    assert [issue["code"] for issue in all_quality["issues"]] == [
        "unit_ambiguity",
        "sentinel_dash",
    ]

    psi10 = db.dataset_quality(["gas_flame_test"], accession="PSI-10")
    assert [issue["code"] for issue in psi10["issues"]] == ["sentinel_dash"]

    table = psi10["tables"][0]
    assert table["table_name"] == "gas_flame_test"
    assert table["columns_with_missingness"][0]["name"] == "fuel"


def test_dataset_quality_ignores_unknown_tables(db):
    quality = db.dataset_quality(["not_a_table"])
    assert quality["tables"] == []


# ----------------------------------------------------------------------
# Watchdog
# ----------------------------------------------------------------------
class _SlowConnection:
    def __init__(self) -> None:
        self.stopped = threading.Event()
        self.closed = False

    def execute(self, sql, params):  # noqa: ARG002
        self.stopped.wait(5)
        raise duckdb.InterruptException("interrupted")

    def interrupt(self) -> None:
        self.stopped.set()

    def close(self) -> None:
        self.closed = True


def test_watchdog_interrupts_a_slow_query(monkeypatch):
    database = AnalyticsDatabase(timeout_seconds=0.05)
    connection = _SlowConnection()
    monkeypatch.setattr(database, "_connect", lambda: connection)

    with pytest.raises(QueryTimeoutError):
        database._scalar("SELECT 1")

    assert connection.closed is True


def test_unknown_database_error_is_wrapped(monkeypatch):
    class _BrokenConnection:
        def execute(self, sql, params):  # noqa: ARG002
            raise duckdb.Error("boom")

        def close(self) -> None:
            pass

    database = AnalyticsDatabase(timeout_seconds=1)
    monkeypatch.setattr(database, "_connect", lambda: _BrokenConnection())

    with pytest.raises(AnalyticsError) as excinfo:
        database._scalar("SELECT 1")
    assert excinfo.value.code == "query_error"
