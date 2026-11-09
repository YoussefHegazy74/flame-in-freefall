"""Serving-state registry and evaluation tests.

The tests cover every serving state at dataset and measurement level and
verify that serving state is not confused with download or file status.
"""

from __future__ import annotations

import copy

import pytest

from src.analytics import catalog
from src.analytics.errors import InvalidQueryError, NotFoundError, RegistryError
from src.analytics.registry import (
    SERVING_STATES,
    USE_KEYS,
    load_registries,
    validate_serving_registry,
)
from src.analytics.serving import ServingEngine


@pytest.fixture(scope="module")
def bundle():
    return load_registries()


@pytest.fixture(scope="module")
def engine(bundle):
    return ServingEngine(bundle)


def test_all_five_serving_states_are_reachable(engine):
    assert engine.evaluate_dataset("psi-98-metadata", "exploration").state == "metadata_only"
    assert engine.evaluate_dataset("psi-100-telemetry", "quantitative_comparison").state == "blocked"
    assert engine.evaluate_dataset("psi-10-gas-flame", "quantitative_comparison").state == "restricted"
    assert engine.evaluate_dataset("psi-10-gas-flame", "exploration").state == "available_with_warnings"
    assert engine.evaluate_measurement("psi-100-telemetry.cygnus_timestamp_ms", "exploration").state == "available"
    assert engine.evaluate_measurement("psi-25-material.pressure_atm", "exploration").state == "blocked"
    assert engine.evaluate_measurement("psi-100-telemetry.radiometer_1_raw", "quantitative_comparison").state == "blocked"
    assert engine.evaluate_measurement("psi-10-gas-flame.oxygen_mole_fraction", "exploration").state == "available_with_warnings"
    assert engine.evaluate_measurement("psi-98-metadata.telemetry_sensor_data", "exploration").state == "metadata_only"


def test_dataset_states_are_specific_to_use(engine):
    assert engine.evaluate_dataset("psi-100-telemetry", "time_series").state == "available_with_warnings"
    assert engine.evaluate_dataset("psi-100-telemetry", "quantitative_comparison").state == "blocked"
    assert engine.evaluate_dataset("psi-100-telemetry", "provenance").state == "available"


def test_psi10_quantitative_use_is_restricted(engine):
    decision = engine.evaluate_dataset("psi-10-gas-flame", "quantitative_comparison")
    assert decision.state == "restricted"
    assert decision.base_state == "available_with_warnings"
    assert any(reason["code"] == "use_restricted" for reason in decision.reasons)
    assert decision.restrictions


def test_psi101_quantitative_use_is_blocked(engine):
    decision = engine.evaluate_dataset("psi-101-smoke", "quantitative_comparison")
    assert decision.state == "blocked"
    assert any("uncalibrated" in reason["message"].lower() for reason in decision.reasons)


def test_material_spread_rate_is_not_served_as_measurement(engine):
    for dataset_id in ("psi-25-material", "psi-26-material"):
        decision = engine.evaluate_dataset(dataset_id, "quantitative_comparison")
        assert decision.state == "blocked"
        assert any("flame-spread rate" in restriction.lower() for restriction in decision.restrictions)


def test_psi26_oxygen_unit_is_restricted(engine):
    decision = engine.evaluate_measurement("psi-26-material.o2_pct", "quantitative_comparison")
    assert decision.state == "blocked"
    assert any(reason["code"] == "unit_ambiguity" for reason in decision.reasons)


def test_psi69_burning_rate_is_not_approved_for_quantitative_use(engine):
    decision = engine.evaluate_measurement(
        "psi-69-droplet.burning_rate_mm_as_labeled",
        "quantitative_comparison",
    )
    assert decision.state == "blocked"
    assert any("mm/s" in restriction for restriction in decision.restrictions)


def test_psi25_missing_pressure_is_blocked_everywhere_but_provenance(engine):
    for use in ("exploration", "quantitative_comparison", "time_series"):
        assert engine.evaluate_measurement("psi-25-material.pressure_atm", use).state == "blocked"
    assert engine.evaluate_measurement("psi-25-material.pressure_atm", "provenance").state == "available"


def test_psi98_is_metadata_only_not_download_status(engine):
    dataset = engine.get_dataset("psi-98-metadata")
    assert dataset["download_status"] == "partial"
    assert dataset["measurement_file_status"] == "unavailable"
    assert dataset["base_state"] == "metadata_only"
    assert engine.evaluate_dataset("psi-98-metadata", "quantitative_comparison").state == "blocked"
    assert engine.evaluate_dataset("psi-98-metadata", "provenance").state == "available"


def test_psi100_is_downloaded_but_blocked_for_quantitative_comparison(engine):
    dataset = engine.get_dataset("psi-100-telemetry")
    assert dataset["download_status"] == "available"
    assert dataset["measurement_file_status"] == "available"
    assert engine.evaluate_dataset("psi-100-telemetry", "quantitative_comparison").state == "blocked"


def test_provenance_is_available_for_every_dataset(engine):
    for dataset in engine.datasets.values():
        decision = engine.evaluate_dataset(dataset["dataset_id"], "provenance")
        assert decision.state == "available"


def test_non_available_states_have_human_readable_reasons(engine):
    for dataset in engine.datasets.values():
        for use in USE_KEYS:
            decision = engine.evaluate_dataset(dataset["dataset_id"], use)
            if decision.state != "available":
                assert decision.reasons
                assert all(reason["message"] for reason in decision.reasons)


def test_every_measurement_has_all_four_use_states(engine):
    for measurement_id, state_entry in engine.measurement_states.items():
        assert set(state_entry["use_states"]) == USE_KEYS
        assert state_entry["serving_state"] in SERVING_STATES
        for state in state_entry["use_states"].values():
            assert state in SERVING_STATES


def test_unknown_dataset_raises(engine):
    with pytest.raises(NotFoundError):
        engine.evaluate_dataset("does-not-exist")


def test_unknown_measurement_raises(engine):
    with pytest.raises(NotFoundError):
        engine.evaluate_measurement("does-not-exist")


def test_invalid_use_raises(engine):
    with pytest.raises(InvalidQueryError):
        engine.evaluate_dataset("psi-10-gas-flame", "ranking")


def test_invalid_state_filter_raises(engine):
    with pytest.raises(InvalidQueryError):
        engine.list_datasets(state="probably_fine")


def test_list_datasets_filters_by_state_and_use(engine):
    blocked = engine.list_datasets(state="blocked", use="quantitative_comparison")
    assert {dataset["dataset_id"] for dataset in blocked} >= {
        "psi-100-telemetry",
        "psi-101-smoke",
        "psi-25-material",
        "psi-26-material",
        "psi-98-metadata",
    }
    metadata_only = engine.list_datasets(state="metadata_only", use="exploration")
    assert [dataset["dataset_id"] for dataset in metadata_only] == ["psi-98-metadata"]


def test_list_measurements_filters_by_state(engine):
    blocked = engine.list_measurements(state="blocked", use="quantitative_comparison")
    assert any(item["measurement_id"] == "psi-26-material.o2_pct" for item in blocked)
    assert any(item["measurement_id"] == "psi-69-droplet.burning_rate_mm_as_labeled" for item in blocked)


def test_summary_counts_cover_every_dataset_and_measurement(engine, bundle):
    summary = engine.summary()
    assert summary["dataset_count"] == len(bundle.serving["datasets"])
    assert summary["measurement_count"] == len(bundle.serving["measurement_states"])
    assert sum(summary["dataset_base_state_counts"].values()) == summary["dataset_count"]
    assert sum(summary["measurement_base_state_counts"].values()) == summary["measurement_count"]
    for use in USE_KEYS:
        assert sum(summary["dataset_use_state_counts"][use].values()) == summary["dataset_count"]


def test_catalog_and_serving_registry_datasets_match(bundle):
    catalog_ids = {dataset["dataset_id"] for dataset in catalog.DATASETS}
    registry_ids = {dataset["dataset_id"] for dataset in bundle.serving["datasets"]}
    assert catalog_ids == registry_ids


def test_registry_validation_rejects_unknown_measurement_state(bundle):
    broken = copy.deepcopy(bundle.serving)
    broken["measurement_states"][0]["measurement_id"] = "psi-999.unknown"
    with pytest.raises(RegistryError):
        validate_serving_registry(broken, bundle.comparability)


def test_registry_validation_rejects_missing_use_state(bundle):
    broken = copy.deepcopy(bundle.serving)
    del broken["datasets"][0]["use_states"]["time_series"]
    with pytest.raises(RegistryError):
        validate_serving_registry(broken, bundle.comparability)
