"""Integration tests for the analytics layer over the real canonical dataset.

These tests require the built ``data/processed`` Parquet tables and the
committed quality report. They are marked ``integration`` and skip when the
non-committed canonical data is absent.
"""

from __future__ import annotations

import json
import re

import pytest

from src.analytics.db import AnalyticsDatabase
from src.analytics.errors import InvalidQueryError, LimitExceededError
from src.analytics.registry import load_registries
from src.analytics.service import AnalyticsService
from src.data_pipeline.config import PROCESSED_DIR, REPORTS_DIR

pytestmark = pytest.mark.integration

OXYGEN_LEFT = "psi-10-gas-flame.oxygen_mole_fraction"
OXYGEN_RIGHT = "psi-159-gas-flame.oxygen_mole_fraction"


def require_canonical_data() -> None:
    required = (
        PROCESSED_DIR / "gas_flame_test.parquet",
        PROCESSED_DIR / "telemetry_point.parquet",
        PROCESSED_DIR / "smoke_point.parquet",
        PROCESSED_DIR / "dataset_manifest.json",
        REPORTS_DIR / "dataset_quality_report.json",
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        pytest.skip("canonical data is not present: " + ", ".join(missing))


@pytest.fixture(scope="module")
def db():
    require_canonical_data()
    return AnalyticsDatabase(timeout_seconds=60)


@pytest.fixture(scope="module")
def service(db):
    return AnalyticsService(database=db, bundle=load_registries())


# ----------------------------------------------------------------------
# Dataset identity
# ----------------------------------------------------------------------
def test_canonical_table_counts_and_dataset_version(db):
    health = db.health()
    assert health["database"] == "ok"
    assert health["available_tables"] == 13
    assert health["missing_tables"] == []
    assert re.fullmatch(r"[0-9a-f]{64}", health["dataset_version"])
    assert health["dataset_version"] == db.dataset_manifest()["dataset_version"]

    counts = db.table_counts()
    assert counts["psi_investigation"] == 24
    assert counts["psi_file"] == 16354
    assert counts["experimental_table"] == 22
    assert counts["gas_flame_test"] == 660
    assert counts["material_test"] == 259
    assert counts["droplet_test"] == 274
    assert counts["telemetry_run"] == 5
    assert counts["telemetry_point"] == 1762436
    assert counts["smoke_run"] == 44
    assert counts["smoke_point"] == 6251427
    assert counts["smoke_test_log"] == 119
    assert counts["source_row"] == 2009
    assert counts["experimental_table_cell"] == 24573


# ----------------------------------------------------------------------
# Gas-flame observations
# ----------------------------------------------------------------------
def test_gas_flame_counts_and_pressure_units(db):
    psi10 = db.list_gas_flame_tests(accession="PSI-10")
    assert psi10.total == 256
    assert psi10.page()["excluded_qualified_rows"] == 71
    assert psi10.page()["pressure_field"] == "pressure_initial_atm"
    assert psi10.page()["pressure_unit"] == "atm"

    psi10_all = db.list_gas_flame_tests(accession="PSI-10", include_qualified=True)
    assert psi10_all.total == 327

    psi159 = db.list_gas_flame_tests(accession="PSI-159")
    assert psi159.total == 333
    assert psi159.page()["pressure_field"] == "pressure_approx_bar"
    assert psi159.page()["pressure_unit"] == "bar"

    with pytest.raises(InvalidQueryError):
        db.list_gas_flame_tests(pressure_min=0.5)


def test_gas_flame_fuel_labels_are_not_cross_mapped(db):
    assert db.list_gas_flame_tests(accession="PSI-10", fuel="C2H4").total > 0
    assert db.list_gas_flame_tests(accession="PSI-10", fuel="ethane").total == 0
    assert db.list_gas_flame_tests(accession="PSI-159", fuel="ethane").total > 0
    assert db.list_gas_flame_tests(accession="PSI-159", fuel="C2H4").total == 0


def test_gas_flame_rows_label_computed_fields(db):
    row = db.list_gas_flame_tests(accession="PSI-10", limit=1).items[0]
    assert row["computed_fields"] == ["stoich_mixture_fraction", "adiabatic_flame_temp_k"]
    assert "observation_id" in row
    assert row["source_sha256"]


# ----------------------------------------------------------------------
# Material and droplet observations
# ----------------------------------------------------------------------
def test_material_rows_keep_units_and_missing_values(db):
    psi25 = db.list_material_tests(accession="PSI-25")
    assert psi25.total == 129
    assert psi25.page()["o2_field"] == "initial_o2_pct"
    assert psi25.items[0]["initial_o2_pct"] == pytest.approx(22.2)
    assert all(row["pressure_atm"] is None for row in psi25.items)

    psi26 = db.list_material_tests(accession="PSI-26")
    assert psi26.total == 130
    assert psi26.page()["o2_field"] == "o2_pct"
    assert psi26.items[0]["o2_pct"] == pytest.approx(0.221)
    assert "percent" in psi26.page()["o2_unit_note"]
    assert psi26.page()["spread_rate_available"] is False


def test_droplet_rate_is_preserved_as_labeled(db):
    page = db.list_droplet_tests()
    assert page.total == 274
    assert any(row["burning_rate_mm_as_labeled"] is not None for row in page.items)
    assert all("burning_rate_mm_s" not in row for row in page.items)


# ----------------------------------------------------------------------
# Telemetry
# ----------------------------------------------------------------------
def test_telemetry_runs_are_separate_and_series_are_bounded(db):
    runs = db.list_telemetry_runs()
    assert runs.total == 5
    run_ids = [row["run_id"] for row in runs.items]
    assert len(set(run_ids)) == 5
    assert all("::" in run_id for run_id in run_ids)

    run_id = run_ids[0]
    run = db.get_telemetry_run(run_id)
    assert len(run["channels"]) == 47
    relative = next(
        channel for channel in run["channels"] if channel["channel_name_canonical"] == "relative_time_ms"
    )
    assert relative["unit"] == "ms"
    assert "uncalibrated" in next(
        channel["quality_flags"]
        for channel in run["channels"]
        if channel["channel_name_canonical"] == "radiometer_1_raw"
    )

    series = db.get_telemetry_series(
        run_id, "pcm_air_temp_c", 0, 100000, max_points=100
    )
    assert series["returned_points"] == 54
    assert series["time_unit"] == "ms"
    assert series["points"][0]["time_ms"] == 0.0
    assert isinstance(series["points"][0]["pcm_air_temp_c"], float)
    assert series["source_row_range"][0] <= series["source_row_range"][1]


def test_telemetry_large_range_is_rejected_not_downsampled(db):
    run_id = db.list_telemetry_runs(limit=1).items[0]["run_id"]
    with pytest.raises(LimitExceededError) as excinfo:
        db.get_telemetry_series(run_id, "pcm_air_temp_c", 0, 9573373, max_points=100)
    assert excinfo.value.details["actual_points"] > 100
    assert excinfo.value.details["suggested_max_span_ms"] < 9573373


def test_telemetry_rejects_unknown_channels_and_out_of_range(db):
    run = db.list_telemetry_runs(limit=1).items[0]
    with pytest.raises(InvalidQueryError):
        db.get_telemetry_series(run["run_id"], "not_a_channel", 0, 1000)
    with pytest.raises(InvalidQueryError):
        db.get_telemetry_series(
            run["run_id"], "pcm_air_temp_c", -1, run["time_max_ms"] + 1
        )


# ----------------------------------------------------------------------
# Smoke
# ----------------------------------------------------------------------
def test_smoke_runs_are_separate_and_series_are_bounded(db):
    runs = db.list_smoke_runs()
    assert runs.total == 44
    assert len({row["run_id"] for row in runs.items}) == 44

    run_id = runs.items[0]["run_id"]
    run = db.get_smoke_run(run_id)
    assert len(run["channels"]) == 91
    gas = next(
        channel for channel in run["channels"] if channel["channel_name_canonical"] == "gas_plume_temp_c"
    )
    assert gas["unit"] == "°C"

    series = db.get_smoke_series(run_id, "gas_plume_temp_c", 79, 400, max_points=500)
    assert series["returned_points"] == 318
    assert series["time_unit"] == "s"
    assert series["points"][0]["time_s"] == 79.0
    assert series["source_row_range"][0] <= series["source_row_range"][1]


def test_smoke_large_range_is_rejected(db):
    run_id = db.list_smoke_runs(limit=1).items[0]["run_id"]
    with pytest.raises(LimitExceededError):
        db.get_smoke_series(run_id, "gas_plume_temp_c", 79, 1000, max_points=100)


# ----------------------------------------------------------------------
# Provenance and quality
# ----------------------------------------------------------------------
def test_provenance_matches_the_real_source_file(db):
    record = db.resolve_provenance(
        "PSI-10",
        "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
        row=1,
    )
    assert record["origin"] == "experimental_table"
    assert record["sha256"] == "4a663292bd3f65201943cc71bd661a70383639276a9176f64105b285bf0b6deb"
    assert record["bytes"] == 26933
    assert record["row_verified"] is True
    assert "gas_flame_test" in record["row_tables"]


def test_quality_report_matches_the_canonical_build(db):
    report = db.quality_report()
    assert report["summary"]["tables"] == 13
    assert report["summary"]["total_rows"] == 8058206
    assert report["summary"]["point_rows"] == 8013863
    assert report["summary"]["issues"] == 6
    assert report["summary"]["errors"] == 0
    assert report["flag_tables"]["gas_flame_test"]["ramped_condition"] == 411

    quality = db.dataset_quality(["gas_flame_test"], accession="PSI-10")
    assert quality["tables"][0]["table_name"] == "gas_flame_test"
    assert quality["tables"][0]["rows"] == 660
    assert any(column["name"] == "fuel" for column in quality["tables"][0]["columns_with_missingness"])

    material = db.dataset_quality(["material_test"], accession="PSI-26")
    assert any(issue["code"] == "unit_ambiguity" for issue in material["issues"])


# ----------------------------------------------------------------------
# Service envelopes over real data
# ----------------------------------------------------------------------
def test_service_health_and_metadata(service):
    health = service.health()
    assert health["data"]["status"] == "ok"
    assert health["data"]["database"] == "ok"
    assert health["quality"]["status"] == "verified"

    meta = service.meta()
    assert meta["data"]["investigations_total"] == 24
    assert meta["data"]["canonical_rows"] == 8058206
    assert meta["data"]["measurement_count"] == 93
    assert meta["data"]["comparison_rule_count"] == 60


def test_service_dataset_and_measurement_states(service):
    dataset = service.get_dataset("psi-10-gas-flame")
    assert dataset["data"]["serving"]["exploration"]["state"] == "available_with_warnings"
    assert dataset["data"]["serving"]["quantitative_comparison"]["state"] == "restricted"
    assert dataset["quality"]["status"] == "partial"

    telemetry = service.get_dataset("psi-100-telemetry")
    assert telemetry["data"]["serving"]["quantitative_comparison"]["state"] == "blocked"
    assert telemetry["data"]["serving"]["time_series"]["state"] == "available_with_warnings"

    measurement = service.get_measurement(
        "psi-26-material.o2_pct", use="quantitative_comparison"
    )
    assert measurement["data"]["unit_status"] == "ambiguous"
    assert measurement["data"]["serving"]["state"] == "blocked"

    blocked = service.get_measurement("psi-25-material.pressure_atm")
    assert blocked["data"]["serving"]["state"] == "blocked"


def test_service_comparisons_and_warnings(service):
    comparable = service.compare(
        OXYGEN_LEFT,
        OXYGEN_RIGHT,
        conditions={
            "same_oxygen_basis": True,
            "flame_configuration_documented": True,
        },
    )
    assert comparable["data"]["status"] == "comparable"
    assert comparable["quality"]["status"] == "verified"

    not_comparable = service.compare(OXYGEN_LEFT, "psi-69-droplet.o2_initial_mole_fraction")
    assert not_comparable["data"]["status"] == "not_comparable"
    assert not_comparable["quality"]["status"] == "blocked"

    gas = service.list_gas_flame_tests(accession="PSI-10", limit=2)
    assert gas["meta"]["page"]["total"] == 256
    assert any("computed" in warning for warning in gas["quality"]["warnings"])
    assert gas["provenance"]

    telemetry = service.list_telemetry_runs(limit=2)
    assert telemetry["meta"]["page"]["total"] == 5
    assert telemetry["quality"]["status"] == "partial"
    assert len(telemetry["provenance"]) == 2

    series = service.get_telemetry_series(
        telemetry["data"][0]["run_id"], "pcm_air_temp_c", 0, 100000, max_points=100
    )
    assert series["meta"]["returned_points"] == 54
    assert series["provenance"][0]["row_range"][0] <= series["provenance"][0]["row_range"][1]


def test_service_quality_and_provenance(service):
    listing = service.list_dataset_quality()
    assert len(listing["data"]) == 9
    assert listing["quality"]["status"] == "partial"

    detail = service.get_dataset_quality("psi-26-material")
    assert detail["data"]["quality_status"] == "partial"
    assert detail["data"]["report"]["summary"]["tables"] == 13

    provenance = service.resolve_provenance(
        "PSI-10",
        "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
        row=1,
    )
    assert provenance["data"]["row_verified"] is True
    assert provenance["quality"]["status"] == "verified"
    assert json.dumps(provenance["data"])  # envelope remains JSON-serializable
