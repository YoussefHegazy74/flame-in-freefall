"""Dataset and measurement serving-state decisions.

Serving states are deliberately separate from download status and file
availability. A dataset can be downloaded but blocked for quantitative
comparison, or available for exploration but metadata-only for a time series.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.analytics.errors import InvalidQueryError, NotFoundError
from src.analytics.registry import SERVING_STATES, USE_KEYS, RegistryBundle, load_registries

STATE_SEVERITY = {
    "available": 0,
    "available_with_warnings": 1,
    "restricted": 2,
    "metadata_only": 3,
    "blocked": 4,
}


@dataclass(frozen=True)
class ServingDecision:
    resource_type: str
    resource_id: str
    dataset_id: str | None
    use: str
    state: str
    base_state: str
    reasons: list[dict[str, str]]
    restrictions: list[str]
    registry_version: str
    dataset_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "dataset_id": self.dataset_id,
            "use": self.use,
            "state": self.state,
            "base_state": self.base_state,
            "reasons": self.reasons,
            "restrictions": self.restrictions,
            "registry_version": self.registry_version,
            "dataset_version": self.dataset_version,
        }


def _validate_use(use: str) -> None:
    if use not in USE_KEYS:
        raise InvalidQueryError(
            "unknown serving use",
            details={"use": use, "allowed": sorted(USE_KEYS)},
        )


def _use_reason(use: str, state: str) -> dict[str, str]:
    messages = {
        "available": f"The resource is available for {use}.",
        "available_with_warnings": (
            f"The resource is available for {use} only with the documented warnings."
        ),
        "restricted": (
            f"The resource is present but restricted for {use}; do not present it as unrestricted."
        ),
        "blocked": f"The resource is blocked for {use}.",
        "metadata_only": f"Only metadata and provenance can be served for {use}.",
    }
    return {"code": f"use_{state}", "message": messages[state]}


def _dedupe_reasons(reasons: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for reason in reasons:
        key = (reason.get("code", ""), reason.get("message", ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(reason))
    return result


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


class ServingEngine:
    """Evaluate dataset-level and measurement-level serving states."""

    def __init__(self, bundle: RegistryBundle | None = None):
        self.bundle = bundle or load_registries()
        self._datasets = self.bundle.datasets
        self._measurement_states = self.bundle.measurement_states
        self._measurements = self.bundle.measurements

    @property
    def datasets(self) -> dict[str, dict[str, Any]]:
        return self._datasets

    @property
    def measurement_states(self) -> dict[str, dict[str, Any]]:
        return self._measurement_states

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            raise NotFoundError(
                "dataset is not present in the serving registry",
                details={"dataset_id": dataset_id},
            )
        return dataset

    def get_measurement_state(self, measurement_id: str) -> dict[str, Any]:
        state = self._measurement_states.get(measurement_id)
        if state is None:
            raise NotFoundError(
                "measurement is not present in the serving registry",
                details={"measurement_id": measurement_id},
            )
        return state

    def evaluate_dataset(self, dataset_id: str, use: str = "exploration") -> ServingDecision:
        _validate_use(use)
        dataset = self.get_dataset(dataset_id)
        state = dataset["use_states"][use]
        reasons = _dedupe_reasons([_use_reason(use, state)] + dataset["reasons"])
        return ServingDecision(
            resource_type="dataset",
            resource_id=dataset_id,
            dataset_id=dataset_id,
            use=use,
            state=state,
            base_state=dataset["base_state"],
            reasons=reasons,
            restrictions=list(dataset["restrictions"]),
            registry_version=self.bundle.registry_version,
            dataset_version=self.bundle.dataset_version,
        )

    def evaluate_measurement(
        self,
        measurement_id: str,
        use: str = "exploration",
    ) -> ServingDecision:
        _validate_use(use)
        state_entry = self.get_measurement_state(measurement_id)
        dataset = self.get_dataset(state_entry["dataset_id"])
        state = state_entry["use_states"][use]
        reasons = _dedupe_reasons(
            [_use_reason(use, state)] + state_entry["reasons"] + dataset["reasons"]
        )
        restrictions = _dedupe_strings(
            list(state_entry["restrictions"]) + list(dataset["restrictions"])
        )
        return ServingDecision(
            resource_type="measurement",
            resource_id=measurement_id,
            dataset_id=state_entry["dataset_id"],
            use=use,
            state=state,
            base_state=state_entry["serving_state"],
            reasons=reasons,
            restrictions=restrictions,
            registry_version=self.bundle.registry_version,
            dataset_version=self.bundle.dataset_version,
        )

    def list_datasets(
        self,
        *,
        family: str | None = None,
        accession: str | None = None,
        state: str | None = None,
        use: str = "exploration",
    ) -> list[dict[str, Any]]:
        _validate_use(use)
        if state is not None and state not in SERVING_STATES:
            raise InvalidQueryError(
                "unknown serving state",
                details={"state": state, "allowed": sorted(SERVING_STATES)},
            )
        result = []
        for dataset in self._datasets.values():
            if family and dataset["experiment_family"] != family:
                continue
            if accession and dataset["accession"] != accession:
                continue
            if state and dataset["use_states"][use] != state:
                continue
            result.append(dataset)
        return sorted(result, key=lambda item: item["dataset_id"])

    def list_measurements(
        self,
        *,
        accession: str | None = None,
        family: str | None = None,
        dataset_id: str | None = None,
        state: str | None = None,
        use: str = "exploration",
    ) -> list[dict[str, Any]]:
        _validate_use(use)
        if state is not None and state not in SERVING_STATES:
            raise InvalidQueryError(
                "unknown serving state",
                details={"state": state, "allowed": sorted(SERVING_STATES)},
            )
        result = []
        for measurement_id, state_entry in self._measurement_states.items():
            measurement = self._measurements[measurement_id]
            if accession and measurement["accession"] != accession:
                continue
            if family and measurement["experiment_family"] != family:
                continue
            if dataset_id and measurement["dataset_id"] != dataset_id:
                continue
            if state and state_entry["use_states"][use] != state:
                continue
            result.append(
                {
                    "measurement_id": measurement_id,
                    "dataset_id": measurement["dataset_id"],
                    "accession": measurement["accession"],
                    "experiment_family": measurement["experiment_family"],
                    "parameter": measurement["parameter"],
                    "unit": measurement["unit"],
                    "value_kind": measurement["value_kind"],
                    "calibration_status": measurement["calibration_status"],
                    "comparison_status": measurement["comparison_status"],
                    "serving_state": state_entry["serving_state"],
                    "use_states": state_entry["use_states"],
                }
            )
        return sorted(result, key=lambda item: item["measurement_id"])

    def summary(self) -> dict[str, Any]:
        """Return counts by state and use for discovery endpoints."""

        dataset_counts = {state: 0 for state in sorted(SERVING_STATES)}
        measurement_counts = {state: 0 for state in sorted(SERVING_STATES)}
        use_counts: dict[str, dict[str, int]] = {
            use: {state: 0 for state in sorted(SERVING_STATES)} for use in sorted(USE_KEYS)
        }
        for dataset in self._datasets.values():
            dataset_counts[dataset["base_state"]] += 1
            for use, state in dataset["use_states"].items():
                use_counts[use][state] += 1
        for state_entry in self._measurement_states.values():
            measurement_counts[state_entry["serving_state"]] += 1
        return {
            "registry_version": self.bundle.registry_version,
            "dataset_version": self.bundle.dataset_version,
            "state_definitions": self.bundle.serving["state_definitions"],
            "use_definitions": self.bundle.serving["use_definitions"],
            "dataset_base_state_counts": dataset_counts,
            "measurement_base_state_counts": measurement_counts,
            "dataset_use_state_counts": use_counts,
            "dataset_count": len(self._datasets),
            "measurement_count": len(self._measurement_states),
        }
