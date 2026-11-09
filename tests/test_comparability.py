"""Comparability registry and decision-engine tests.

These tests use the committed registries and the real canonical metadata
contracts. They do not require the non-committed Parquet data.
"""

from __future__ import annotations

import copy

import pytest

from src.analytics import catalog
from src.analytics.comparability import ComparabilityEngine
from src.analytics.errors import InvalidQueryError, RegistryError, UnknownMeasurementError
from src.analytics.registry import (
    COMPARABILITY_STATES,
    load_registries,
    validate_comparability_registry,
)

OXYGEN_LEFT = "psi-10-gas-flame.oxygen_mole_fraction"
OXYGEN_RIGHT = "psi-159-gas-flame.oxygen_mole_fraction"
OXYGEN_CONDITIONS = {
    "same_oxygen_basis": True,
    "flame_configuration_documented": True,
}


@pytest.fixture(scope="module")
def bundle():
    return load_registries()


@pytest.fixture(scope="module")
def engine(bundle):
    return ComparabilityEngine(bundle)


def test_comparable_when_every_condition_is_verified(engine):
    decision = engine.evaluate(OXYGEN_LEFT, OXYGEN_RIGHT, OXYGEN_CONDITIONS)
    assert decision.status == "comparable"
    assert decision.rule_id == "psi10-psi159-oxygen"
    assert decision.reasons[0]["code"] == "conditions_verified"
    assert all(condition.satisfied is True for condition in decision.required_conditions)


def test_conditionally_comparable_when_conditions_are_missing(engine):
    decision = engine.evaluate(OXYGEN_LEFT, OXYGEN_RIGHT)
    assert decision.status == "conditionally_comparable"
    assert decision.reasons[0]["code"] == "conditions_not_verified"
    assert {condition.key for condition in decision.required_conditions} == {
        "same_oxygen_basis",
        "flame_configuration_documented",
    }
    assert all(condition.satisfied is None for condition in decision.required_conditions)


def test_failed_condition_returns_not_comparable(engine):
    decision = engine.evaluate(
        OXYGEN_LEFT,
        OXYGEN_RIGHT,
        {"same_oxygen_basis": False, "flame_configuration_documented": True},
    )
    assert decision.status == "not_comparable"
    assert decision.reasons[0]["code"] == "condition_failed"
    failed = [condition.key for condition in decision.required_conditions if condition.satisfied is False]
    assert failed == ["same_oxygen_basis"]


def test_explicit_not_comparable_for_cross_family_oxygen(engine):
    decision = engine.evaluate(
        OXYGEN_LEFT,
        "psi-69-droplet.o2_initial_mole_fraction",
    )
    assert decision.status == "not_comparable"
    assert decision.rule_id == "psi10-psi69-oxygen"
    assert decision.reasons[0]["code"] == "rule_not_comparable"


def test_blocked_for_ambiguous_percent_unit(engine):
    decision = engine.evaluate(
        "psi-25-material.initial_o2_pct",
        "psi-26-material.o2_pct",
    )
    assert decision.status == "blocked"
    assert decision.rule_id == "bass25-26-o2"
    assert "unit_ambiguity" in " ".join(
        restriction for side in (decision.left, decision.right) for restriction in side["quality_restrictions"]
    )


def test_blocked_for_measured_versus_computed(engine):
    decision = engine.evaluate(
        "psi-159-gas-flame.peak_burner_temp_c",
        "psi-10-gas-flame.adiabatic_flame_temp_k",
    )
    assert decision.status == "blocked"
    assert decision.rule_id == "psi159-peakc-tad"
    assert decision.left["value_kind"] == "measured"
    assert decision.right["value_kind"] == "computed"
    assert any("computed" in warning for warning in decision.warnings)


def test_blocked_for_uncalibrated_raw_channels(engine):
    decision = engine.evaluate(
        "psi-100-telemetry.radiometer_1_raw",
        "psi-100-telemetry.radiometer_2_raw",
    )
    assert decision.status == "blocked"
    assert decision.left["calibration_status"] == "uncalibrated"
    assert decision.right["calibration_status"] == "uncalibrated"


def test_blocked_for_missing_measurement(engine):
    decision = engine.evaluate(
        "psi-25-material.pressure_atm",
        "psi-26-material.pressure_atm",
    )
    assert decision.status == "blocked"
    assert decision.left["availability"] == "missing"


def test_insufficient_metadata_for_undefined_acronym(engine):
    decision = engine.evaluate(
        "psi-159-gas-flame.tfp_flag",
        "psi-159-gas-flame.hot_ignition",
    )
    assert decision.status == "insufficient_metadata"
    assert decision.rule_id == "psi159-tfp-hot"


def test_insufficient_metadata_for_undocumented_computed_method(engine):
    decision = engine.evaluate(
        "psi-10-gas-flame.adiabatic_flame_temp_k",
        "psi-159-gas-flame.adiabatic_flame_temp_k",
    )
    assert decision.status == "insufficient_metadata"
    assert "column name" in decision.scientific_justification


def test_default_policy_is_not_comparable(engine):
    decision = engine.evaluate(
        OXYGEN_LEFT,
        "psi-100-telemetry.pcm_air_temp_c",
    )
    assert decision.status == "not_comparable"
    assert decision.rule_id is None
    assert decision.reasons[0]["code"] == "no_explicit_rule"


def test_unknown_measurement_raises(engine):
    with pytest.raises(UnknownMeasurementError) as excinfo:
        engine.evaluate("psi-999.does_not_exist", OXYGEN_LEFT)
    assert excinfo.value.code == "unknown_measurement"


def test_same_measurement_is_rejected(engine):
    with pytest.raises(InvalidQueryError):
        engine.evaluate(OXYGEN_LEFT, OXYGEN_LEFT)


def test_rule_evaluation_is_symmetric(engine):
    forward = engine.evaluate(OXYGEN_LEFT, OXYGEN_RIGHT, OXYGEN_CONDITIONS)
    reverse = engine.evaluate(OXYGEN_RIGHT, OXYGEN_LEFT, OXYGEN_CONDITIONS)
    assert forward.status == reverse.status == "comparable"
    assert forward.rule_id == reverse.rule_id
    assert forward.scientific_justification == reverse.scientific_justification


def test_decision_preserves_version_and_provenance(engine, bundle):
    decision = engine.evaluate(OXYGEN_LEFT, OXYGEN_RIGHT, OXYGEN_CONDITIONS)
    assert decision.dataset_version == bundle.dataset_version
    assert decision.registry_version == bundle.registry_version
    assert decision.source_references
    assert any(reference["kind"] == "nasa_psi_file" for reference in decision.source_references)
    assert all(
        reference.get("sha256")
        for reference in decision.source_references
        if reference["kind"] == "nasa_psi_file"
    )


def test_every_measurement_has_a_documented_comparison_status(bundle):
    for measurement in bundle.comparability["measurements"]:
        assert measurement["comparison_status"] in COMPARABILITY_STATES
        assert measurement["scientific_justification"]


def test_all_required_investigations_are_represented(bundle):
    accessions = {measurement["accession"] for measurement in bundle.comparability["measurements"]}
    assert {"PSI-10", "PSI-159", "PSI-100", "PSI-101", "PSI-25", "PSI-26", "PSI-69"}.issubset(accessions)


def test_catalog_and_registry_ids_match(bundle):
    catalog_ids = {measurement["measurement_id"] for measurement in catalog.MEASUREMENTS}
    registry_ids = {measurement["measurement_id"] for measurement in bundle.comparability["measurements"]}
    assert catalog_ids == registry_ids
    catalog_rules = {rule["rule_id"] for rule in catalog.RULES}
    registry_rules = {rule["rule_id"] for rule in bundle.comparability["comparison_rules"]}
    assert catalog_rules == registry_rules


def test_no_duplicate_rule_pairs(bundle):
    pairs = [
        frozenset((rule["left_measurement_id"], rule["right_measurement_id"]))
        for rule in bundle.comparability["comparison_rules"]
    ]
    assert len(pairs) == len(set(pairs))


def test_registry_validation_rejects_unknown_rule_measurement(bundle):
    broken = copy.deepcopy(bundle.comparability)
    broken["comparison_rules"][0]["left_measurement_id"] = "psi-999.unknown"
    with pytest.raises(RegistryError) as excinfo:
        validate_comparability_registry(broken)
    assert "unknown measurement" in str(excinfo.value)


def test_registry_validation_rejects_duplicate_measurement(bundle):
    broken = copy.deepcopy(bundle.comparability)
    broken["measurements"].append(copy.deepcopy(broken["measurements"][0]))
    with pytest.raises(RegistryError):
        validate_comparability_registry(broken)


def test_registry_validation_rejects_unknown_state(bundle):
    broken = copy.deepcopy(bundle.comparability)
    broken["comparison_rules"][0]["status"] = "probably_fine"
    with pytest.raises(RegistryError):
        validate_comparability_registry(broken)
