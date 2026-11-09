"""Load and validate the committed Phase 2 JSON registries.

The registries are the runtime source of truth. Validation is intentionally
strict: an unknown state, a duplicate identifier, a rule that references an
unknown measurement, or a measurement that references an unknown canonical
field fails closed rather than producing a permissive decision.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from src.analytics.errors import RegistryError
from src.data_pipeline.schemas import TABLE_SCHEMAS

COMPARABILITY_STATES = {
    "comparable",
    "conditionally_comparable",
    "not_comparable",
    "blocked",
    "insufficient_metadata",
}
SERVING_STATES = {
    "available",
    "available_with_warnings",
    "restricted",
    "blocked",
    "metadata_only",
}
USE_KEYS = {"exploration", "quantitative_comparison", "time_series", "provenance"}
VALUE_KINDS = {"measured", "computed", "derived", "categorical", "raw"}
CALIBRATION_STATUSES = {"calibrated", "not_documented", "uncalibrated", "not_applicable"}
AVAILABILITY_STATUSES = {"available", "missing", "metadata_only"}
UNIT_STATUSES = {"stated", "ambiguous", "not_stated", "not_applicable"}
POLICY_VALUES = {
    "unit": {"identical", "explicit_conversion"},
    "value_kind": {"same", "explicitly_distinguished", "different"},
    "physical_quantity": {"same", "explicitly_related", "different"},
    "calibration": {"not_required", "documented", "same_instrument_or_source"},
}


def repo_root() -> Path:
    """Return the repository root without relying on the current directory."""

    return Path(__file__).resolve().parents[2]


def default_registry_dir() -> Path:
    """Return the registry directory, honoring an environment override."""

    override = os.environ.get("FLAME_REGISTRY_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return repo_root() / "data" / "metadata"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RegistryError(
            "registry file is missing",
            details={"path": str(path)},
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RegistryError(
            "registry file is not valid JSON",
            details={"path": str(path), "error": str(exc)},
        ) from exc
    if not isinstance(payload, dict):
        raise RegistryError(
            "registry root must be a JSON object",
            details={"path": str(path)},
        )
    return payload


def _require(condition: bool, message: str, *, details: dict[str, Any] | None = None) -> None:
    if not condition:
        raise RegistryError(message, details=details)


def _require_keys(mapping: dict[str, Any], keys: Iterable[str], context: str) -> None:
    missing = [key for key in keys if key not in mapping]
    _require(not missing, f"{context} is missing required keys", details={"missing": missing})


def _validate_state_definitions(registry: dict[str, Any], states: set[str], label: str) -> None:
    definitions = registry.get("state_definitions")
    _require(isinstance(definitions, dict), f"{label} state_definitions must be an object")
    missing = sorted(states - set(definitions))
    extra = sorted(set(definitions) - states)
    _require(not missing, f"{label} state_definitions are incomplete", details={"missing": missing})
    _require(not extra, f"{label} state_definitions contain unknown states", details={"extra": extra})
    for state, definition in definitions.items():
        _require(isinstance(definition, dict), f"{label} definition for {state} must be an object")
        _require_keys(definition, ("definition", "engine_behavior" if label == "comparability" else "display_rule"), f"{label} definition {state}")


def _validate_source_references(references: Any, context: str) -> None:
    _require(isinstance(references, list) and references, f"{context} must have source references")
    for reference in references:
        _require(isinstance(reference, dict), f"{context} source reference must be an object")
        _require("kind" in reference, f"{context} source reference must have a kind")


def validate_comparability_registry(registry: dict[str, Any]) -> None:
    """Validate the comparability registry and its cross-references."""

    _require_keys(
        registry,
        (
            "registry_version",
            "schema_version",
            "dataset_version",
            "state_definitions",
            "default_policy",
            "measurements",
            "comparison_rules",
        ),
        "comparability registry",
    )
    _validate_state_definitions(registry, COMPARABILITY_STATES, "comparability")
    default = registry["default_policy"]
    _require(isinstance(default, dict), "default_policy must be an object")
    _require(
        default.get("status") == "not_comparable",
        "default_policy.status must be not_comparable",
    )
    _require(bool(default.get("justification")), "default_policy.justification is required")

    measurements = registry["measurements"]
    _require(isinstance(measurements, list) and measurements, "measurements must be a non-empty list")
    measurement_ids: set[str] = set()
    dataset_ids: set[str] = set()
    for measurement in measurements:
        _require(isinstance(measurement, dict), "measurement must be an object")
        _require_keys(
            measurement,
            (
                "measurement_id",
                "dataset_id",
                "accession",
                "experiment_family",
                "parameter",
                "physical_quantity",
                "physical_meaning",
                "unit",
                "unit_status",
                "measurement_method",
                "value_kind",
                "calibration_status",
                "availability",
                "scientific_justification",
                "comparison_status",
                "source_references",
            ),
            f"measurement {measurement.get('measurement_id', '<unknown>')}",
        )
        measurement_id = measurement["measurement_id"]
        _require(isinstance(measurement_id, str) and measurement_id, "measurement_id must be a non-empty string")
        _require(measurement_id not in measurement_ids, "duplicate measurement_id", details={"measurement_id": measurement_id})
        measurement_ids.add(measurement_id)
        dataset_ids.add(measurement["dataset_id"])
        _require(
            measurement["value_kind"] in VALUE_KINDS,
            "invalid value_kind",
            details={"measurement_id": measurement_id, "value_kind": measurement["value_kind"]},
        )
        _require(
            measurement["calibration_status"] in CALIBRATION_STATUSES,
            "invalid calibration_status",
            details={"measurement_id": measurement_id, "calibration_status": measurement["calibration_status"]},
        )
        _require(
            measurement["availability"] in AVAILABILITY_STATUSES,
            "invalid availability",
            details={"measurement_id": measurement_id, "availability": measurement["availability"]},
        )
        _require(
            measurement["unit_status"] in UNIT_STATUSES,
            "invalid unit_status",
            details={"measurement_id": measurement_id, "unit_status": measurement["unit_status"]},
        )
        _require(
            measurement["comparison_status"] in COMPARABILITY_STATES,
            "invalid comparison_status",
            details={"measurement_id": measurement_id, "comparison_status": measurement["comparison_status"]},
        )
        _validate_source_references(measurement["source_references"], f"measurement {measurement_id}")
        canonical_field = measurement.get("canonical_field")
        if canonical_field is not None:
            _require(isinstance(canonical_field, str) and canonical_field, "canonical_field must be null or a non-empty string")
        canonical_channel = measurement.get("canonical_channel")
        if canonical_channel is not None:
            _require(isinstance(canonical_channel, str) and canonical_channel, "canonical_channel must be null or a non-empty string")

    rules = registry["comparison_rules"]
    _require(isinstance(rules, list) and rules, "comparison_rules must be a non-empty list")
    rule_ids: set[str] = set()
    for rule in rules:
        _require(isinstance(rule, dict), "rule must be an object")
        _require_keys(
            rule,
            (
                "rule_id",
                "left_measurement_id",
                "right_measurement_id",
                "status",
                "required_conditions",
                "policies",
                "scientific_justification",
                "source_references",
            ),
            f"rule {rule.get('rule_id', '<unknown>')}",
        )
        rule_id = rule["rule_id"]
        _require(rule_id not in rule_ids, "duplicate rule_id", details={"rule_id": rule_id})
        rule_ids.add(rule_id)
        _require(
            rule["status"] in COMPARABILITY_STATES,
            "invalid rule status",
            details={"rule_id": rule_id, "status": rule["status"]},
        )
        for key in ("left_measurement_id", "right_measurement_id"):
            _require(
                rule[key] in measurement_ids,
                "rule references an unknown measurement",
                details={"rule_id": rule_id, "field": key, "measurement_id": rule[key]},
            )
        _require(
            rule["left_measurement_id"] != rule["right_measurement_id"],
            "a comparison rule must reference two different measurements",
            details={"rule_id": rule_id},
        )
        _require(isinstance(rule["required_conditions"], list), "required_conditions must be a list")
        for condition in rule["required_conditions"]:
            _require(isinstance(condition, dict), "condition must be an object")
            _require_keys(condition, ("key", "description"), f"condition in {rule_id}")
        _require(isinstance(rule["policies"], dict), "policies must be an object")
        for policy, allowed in POLICY_VALUES.items():
            value = rule["policies"].get(policy)
            _require(
                value in allowed,
                "invalid rule policy",
                details={"rule_id": rule_id, "policy": policy, "value": value},
            )
        _validate_source_references(rule["source_references"], f"rule {rule_id}")


def validate_serving_registry(registry: dict[str, Any], comparability: dict[str, Any]) -> None:
    """Validate the serving registry against the comparability registry."""

    _require_keys(
        registry,
        (
            "registry_version",
            "schema_version",
            "dataset_version",
            "state_definitions",
            "use_definitions",
            "datasets",
            "measurement_states",
        ),
        "serving registry",
    )
    _validate_state_definitions(registry, SERVING_STATES, "serving")
    use_definitions = registry["use_definitions"]
    _require(isinstance(use_definitions, dict), "use_definitions must be an object")
    _require(set(use_definitions) == USE_KEYS, "use_definitions must define exactly the four approved uses")

    measurement_ids = {m["measurement_id"] for m in comparability["measurements"]}
    dataset_ids: set[str] = set()
    for dataset in registry["datasets"]:
        _require(isinstance(dataset, dict), "dataset must be an object")
        _require_keys(
            dataset,
            (
                "dataset_id",
                "accession",
                "display_name",
                "experiment_family",
                "canonical_tables",
                "download_status",
                "measurement_file_status",
                "base_state",
                "use_states",
                "reasons",
                "restrictions",
                "source_references",
            ),
            f"dataset {dataset.get('dataset_id', '<unknown>')}",
        )
        dataset_id = dataset["dataset_id"]
        _require(dataset_id not in dataset_ids, "duplicate dataset_id", details={"dataset_id": dataset_id})
        dataset_ids.add(dataset_id)
        _require(dataset["base_state"] in SERVING_STATES, "invalid dataset base_state", details={"dataset_id": dataset_id})
        _require(set(dataset["use_states"]) == USE_KEYS, "dataset use_states must define exactly four uses", details={"dataset_id": dataset_id})
        for use, state in dataset["use_states"].items():
            _require(state in SERVING_STATES, "invalid dataset use state", details={"dataset_id": dataset_id, "use": use, "state": state})
        _require(isinstance(dataset["reasons"], list) and dataset["reasons"], "dataset reasons must be non-empty", details={"dataset_id": dataset_id})
        _require(isinstance(dataset["restrictions"], list), "dataset restrictions must be a list", details={"dataset_id": dataset_id})
        _validate_source_references(dataset["source_references"], f"dataset {dataset_id}")
        for table in dataset["canonical_tables"]:
            _require(table in TABLE_SCHEMAS, "dataset references an unknown canonical table", details={"dataset_id": dataset_id, "table": table})

    states = registry["measurement_states"]
    _require(isinstance(states, list) and states, "measurement_states must be a non-empty list")
    seen: set[str] = set()
    for state in states:
        _require(isinstance(state, dict), "measurement state must be an object")
        _require_keys(
            state,
            ("measurement_id", "dataset_id", "serving_state", "use_states", "reasons", "restrictions"),
            "measurement state",
        )
        measurement_id = state["measurement_id"]
        _require(measurement_id in measurement_ids, "measurement state references an unknown measurement", details={"measurement_id": measurement_id})
        _require(measurement_id not in seen, "duplicate measurement state", details={"measurement_id": measurement_id})
        seen.add(measurement_id)
        _require(state["serving_state"] in SERVING_STATES, "invalid measurement serving_state", details={"measurement_id": measurement_id})
        _require(set(state["use_states"]) == USE_KEYS, "measurement use_states must define exactly four uses", details={"measurement_id": measurement_id})
        for use, serving_state in state["use_states"].items():
            _require(serving_state in SERVING_STATES, "invalid measurement use state", details={"measurement_id": measurement_id, "use": use, "state": serving_state})
        _require(isinstance(state["reasons"], list) and state["reasons"], "measurement reasons must be non-empty", details={"measurement_id": measurement_id})
    _require(seen == measurement_ids, "every measurement must have a serving state", details={"missing": sorted(measurement_ids - seen)})


@dataclass(frozen=True)
class RegistryBundle:
    """Validated registries plus convenient indexes."""

    comparability: dict[str, Any]
    serving: dict[str, Any]
    comparability_path: Path
    serving_path: Path

    @property
    def dataset_version(self) -> str:
        return self.comparability["dataset_version"]

    @property
    def registry_version(self) -> str:
        return self.comparability["registry_version"]

    @property
    def measurements(self) -> dict[str, dict[str, Any]]:
        return {m["measurement_id"]: m for m in self.comparability["measurements"]}

    @property
    def rules(self) -> dict[str, dict[str, Any]]:
        return {r["rule_id"]: r for r in self.comparability["comparison_rules"]}

    @property
    def datasets(self) -> dict[str, dict[str, Any]]:
        return {d["dataset_id"]: d for d in self.serving["datasets"]}

    @property
    def measurement_states(self) -> dict[str, dict[str, Any]]:
        return {s["measurement_id"]: s for s in self.serving["measurement_states"]}

    def rules_for_measurement(self, measurement_id: str) -> list[dict[str, Any]]:
        return [
            rule
            for rule in self.comparability["comparison_rules"]
            if measurement_id in (rule["left_measurement_id"], rule["right_measurement_id"])
        ]


def load_registries(registry_dir: Path | str | None = None) -> RegistryBundle:
    """Load and validate both registries from ``registry_dir``."""

    directory = Path(registry_dir).expanduser().resolve() if registry_dir else default_registry_dir()
    comparability_path = directory / "comparability_registry.json"
    serving_path = directory / "serving_registry.json"
    comparability = _read_json(comparability_path)
    serving = _read_json(serving_path)
    validate_comparability_registry(comparability)
    validate_serving_registry(serving, comparability)
    _require(
        comparability["dataset_version"] == serving["dataset_version"],
        "registry dataset versions do not match",
        details={
            "comparability": comparability["dataset_version"],
            "serving": serving["dataset_version"],
        },
    )
    return RegistryBundle(
        comparability=comparability,
        serving=serving,
        comparability_path=comparability_path,
        serving_path=serving_path,
    )
