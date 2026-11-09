"""Scientific comparability decisions over the committed registry.

The engine has one governing rule: an absent explicit rule means
``not_comparable``. It never infers a comparison from matching column names,
matching units, or membership in the same experiment family.

Even when a rule exists, the engine applies hard integrity checks for
availability, physical quantity, value kind, units, and calibration. Conditions
can only upgrade a ``conditionally_comparable`` rule to ``comparable``; they
cannot override an explicit ``blocked``, ``not_comparable``, or
``insufficient_metadata`` decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from src.analytics.errors import InvalidQueryError, UnknownMeasurementError
from src.analytics.registry import RegistryBundle, load_registries

HARD_STATUSES = {"not_comparable", "blocked", "insufficient_metadata"}
ALLOWED_STATUSES = HARD_STATUSES | {"comparable", "conditionally_comparable"}


@dataclass(frozen=True)
class ConditionStatus:
    key: str
    description: str
    satisfied: bool | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "description": self.description,
            "satisfied": self.satisfied,
        }


@dataclass(frozen=True)
class ComparisonDecision:
    left: dict[str, Any]
    right: dict[str, Any]
    status: str
    rule_id: str | None
    reasons: list[dict[str, str]]
    required_conditions: list[ConditionStatus]
    warnings: list[str]
    scientific_justification: str
    source_references: list[dict[str, Any]]
    registry_version: str
    dataset_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "left": self.left,
            "right": self.right,
            "status": self.status,
            "rule_id": self.rule_id,
            "reasons": self.reasons,
            "required_conditions": [condition.to_dict() for condition in self.required_conditions],
            "warnings": self.warnings,
            "scientific_justification": self.scientific_justification,
            "source_references": self.source_references,
            "registry_version": self.registry_version,
            "dataset_version": self.dataset_version,
        }


def _measurement_summary(measurement: dict[str, Any]) -> dict[str, Any]:
    return {
        "measurement_id": measurement["measurement_id"],
        "dataset_id": measurement["dataset_id"],
        "accession": measurement["accession"],
        "experiment_family": measurement["experiment_family"],
        "parameter": measurement["parameter"],
        "canonical_field": measurement.get("canonical_field"),
        "canonical_channel": measurement.get("canonical_channel"),
        "physical_quantity": measurement["physical_quantity"],
        "unit": measurement["unit"],
        "unit_status": measurement["unit_status"],
        "value_kind": measurement["value_kind"],
        "calibration_status": measurement["calibration_status"],
        "availability": measurement["availability"],
        "comparison_status": measurement["comparison_status"],
        "quality_restrictions": measurement.get("quality_restrictions", []),
    }


def _reason(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _dedupe_references(references: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for reference in references:
        key = repr(sorted(reference.items()))
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(reference))
    return result


def _measurement_warnings(measurement: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if measurement["value_kind"] == "computed":
        warnings.append(
            f"{measurement['measurement_id']} is a computed source value, not a measured quantity."
        )
    if measurement["value_kind"] == "categorical":
        warnings.append(
            f"{measurement['measurement_id']} is categorical and must not be aggregated as a number."
        )
    if measurement["calibration_status"] == "not_documented":
        warnings.append(
            f"{measurement['measurement_id']} has no calibration record in the selected source."
        )
    if measurement["unit_status"] in {"ambiguous", "not_stated"}:
        warnings.append(
            f"{measurement['measurement_id']} has an ambiguous or unstated unit."
        )
    return warnings


class ComparabilityEngine:
    """Evaluate pairwise comparison requests against explicit rules."""

    def __init__(self, bundle: RegistryBundle | None = None):
        self.bundle = bundle or load_registries()
        self._measurements = self.bundle.measurements
        self._rules = self.bundle.rules
        self._pair_index: dict[frozenset[str], dict[str, Any]] = {}
        for rule in self._rules.values():
            key = frozenset((rule["left_measurement_id"], rule["right_measurement_id"]))
            if key in self._pair_index:
                raise InvalidQueryError(
                    "registry contains more than one rule for the same measurement pair",
                    details={"rule_id": rule["rule_id"]},
                )
            self._pair_index[key] = rule

    @property
    def measurements(self) -> dict[str, dict[str, Any]]:
        return self._measurements

    @property
    def rules(self) -> dict[str, dict[str, Any]]:
        return self._rules

    def get_measurement(self, measurement_id: str) -> dict[str, Any]:
        measurement = self._measurements.get(measurement_id)
        if measurement is None:
            raise UnknownMeasurementError(
                "measurement is not present in the comparability registry",
                details={"measurement_id": measurement_id},
            )
        return measurement

    def list_measurements(
        self,
        *,
        accession: str | None = None,
        family: str | None = None,
        dataset_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        if status is not None and status not in ALLOWED_STATUSES:
            raise InvalidQueryError(
                "unknown comparability status",
                details={"status": status, "allowed": sorted(ALLOWED_STATUSES)},
            )
        result = []
        for measurement in self._measurements.values():
            if accession and measurement["accession"] != accession:
                continue
            if family and measurement["experiment_family"] != family:
                continue
            if dataset_id and measurement["dataset_id"] != dataset_id:
                continue
            if status and measurement["comparison_status"] != status:
                continue
            result.append(measurement)
        return sorted(result, key=lambda item: item["measurement_id"])

    def list_rules(
        self,
        *,
        measurement_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        if status is not None and status not in ALLOWED_STATUSES:
            raise InvalidQueryError(
                "unknown comparability status",
                details={"status": status, "allowed": sorted(ALLOWED_STATUSES)},
            )
        result = []
        for rule in self._rules.values():
            if measurement_id and measurement_id not in (
                rule["left_measurement_id"],
                rule["right_measurement_id"],
            ):
                continue
            if status and rule["status"] != status:
                continue
            result.append(rule)
        return sorted(result, key=lambda item: item["rule_id"])

    def _hard_failure(
        self,
        left: dict[str, Any],
        right: dict[str, Any],
        status: str,
        reason: dict[str, str],
        justification: str,
        *,
        rule: dict[str, Any] | None = None,
    ) -> ComparisonDecision:
        return ComparisonDecision(
            left=_measurement_summary(left),
            right=_measurement_summary(right),
            status=status,
            rule_id=rule["rule_id"] if rule else None,
            reasons=[reason],
            required_conditions=[],
            warnings=_measurement_warnings(left) + _measurement_warnings(right),
            scientific_justification=justification,
            source_references=_dedupe_references(
                (rule or {}).get("source_references", [])
                + left.get("source_references", [])
                + right.get("source_references", [])
            ),
            registry_version=self.bundle.registry_version,
            dataset_version=self.bundle.dataset_version,
        )

    def evaluate(
        self,
        left_measurement_id: str,
        right_measurement_id: str,
        conditions: Mapping[str, bool | None] | None = None,
    ) -> ComparisonDecision:
        """Return a traceable comparison decision for two measurement IDs."""

        left = self.get_measurement(left_measurement_id)
        right = self.get_measurement(right_measurement_id)
        if left_measurement_id == right_measurement_id:
            raise InvalidQueryError(
                "a comparison requires two different measurements",
                details={"measurement_id": left_measurement_id},
            )

        rule = self._pair_index.get(frozenset((left_measurement_id, right_measurement_id)))
        if rule is None:
            return self._hard_failure(
                left,
                right,
                "not_comparable",
                _reason(
                    "no_explicit_rule",
                    "No explicit comparison rule exists for this measurement pair.",
                ),
                (
                    "The registry defaults to not comparable when no explicit rule "
                    "exists. Matching names, units, or experiment families are not "
                    "sufficient evidence."
                ),
            )

        if rule["status"] in HARD_STATUSES:
            return self._hard_failure(
                left,
                right,
                rule["status"],
                _reason(
                    f"rule_{rule['status']}",
                    "The explicit comparison rule assigns this hard status.",
                ),
                rule["scientific_justification"],
                rule=rule,
            )

        # Hard integrity checks. Conditions cannot override these.
        for measurement in (left, right):
            if measurement["availability"] == "missing":
                return self._hard_failure(
                    left,
                    right,
                    "blocked",
                    _reason(
                        "measurement_unavailable",
                        f"{measurement['measurement_id']} has no values in the selected source.",
                    ),
                    rule["scientific_justification"],
                    rule=rule,
                )
            if measurement["availability"] == "metadata_only":
                return self._hard_failure(
                    left,
                    right,
                    "blocked",
                    _reason(
                        "metadata_only",
                        f"{measurement['measurement_id']} has no canonical measurement rows.",
                    ),
                    rule["scientific_justification"],
                    rule=rule,
                )

        policies = rule["policies"]
        if (
            left["physical_quantity"] != right["physical_quantity"]
            and policies["physical_quantity"] != "explicitly_related"
        ):
            return self._hard_failure(
                left,
                right,
                "not_comparable",
                _reason(
                    "different_physical_quantity",
                    "The measurements refer to different physical quantities.",
                ),
                rule["scientific_justification"],
                rule=rule,
            )

        if (
            left["value_kind"] != right["value_kind"]
            and policies["value_kind"] != "explicitly_distinguished"
        ):
            return self._hard_failure(
                left,
                right,
                "blocked",
                _reason(
                    "value_kind_mismatch",
                    "Measured, computed, derived, categorical, and raw values cannot be mixed without an explicit distinction.",
                ),
                rule["scientific_justification"],
                rule=rule,
            )

        if left["unit"] != right["unit"] and policies["unit"] != "explicit_conversion":
            return self._hard_failure(
                left,
                right,
                "blocked",
                _reason(
                    "unit_mismatch",
                    "The units differ and the rule does not approve an explicit conversion.",
                ),
                rule["scientific_justification"],
                rule=rule,
            )

        if left["calibration_status"] == "uncalibrated" or right["calibration_status"] == "uncalibrated":
            return self._hard_failure(
                left,
                right,
                "blocked",
                _reason(
                    "uncalibrated_raw",
                    "At least one side is an uncalibrated raw signal, not a physical measurement.",
                ),
                rule["scientific_justification"],
                rule=rule,
            )

        if policies["calibration"] == "documented":
            if (
                left["calibration_status"] != "calibrated"
                or right["calibration_status"] != "calibrated"
            ):
                return self._hard_failure(
                    left,
                    right,
                    "blocked",
                    _reason(
                        "calibration_not_documented",
                        "The rule requires documented calibration on both sides.",
                    ),
                    rule["scientific_justification"],
                    rule=rule,
                )

        required: list[ConditionStatus] = []
        implicit_conditions: list[tuple[str, str]] = []
        if left["unit"] != right["unit"] and policies["unit"] == "explicit_conversion":
            implicit_conditions.append(
                (
                    "explicit_unit_conversion",
                    "A documented conversion between the two units has been applied.",
                )
            )
        if policies["calibration"] == "same_instrument_or_source" and left["dataset_id"] != right["dataset_id"]:
            implicit_conditions.append(
                (
                    "same_measurement_method",
                    "The measurement method and instrument are documented as equivalent.",
                )
            )

        supplied = conditions or {}
        for condition in list(rule["required_conditions"]) + [
            {"key": key, "description": description}
            for key, description in implicit_conditions
        ]:
            key = condition["key"]
            value = supplied.get(key)
            if value is None:
                satisfied: bool | None = None
            else:
                satisfied = bool(value)
            required.append(
                ConditionStatus(
                    key=key,
                    description=condition["description"],
                    satisfied=satisfied,
                )
            )

        failed = [condition for condition in required if condition.satisfied is False]
        missing = [condition for condition in required if condition.satisfied is None]

        warnings = _measurement_warnings(left) + _measurement_warnings(right)
        if left["unit"] != right["unit"]:
            warnings.append("The units differ; an explicit conversion is part of the decision.")
        if left["value_kind"] != right["value_kind"]:
            warnings.append("The value kinds differ and are explicitly distinguished by the rule.")

        if failed:
            status = "not_comparable"
            reasons = [
                _reason(
                    "condition_failed",
                    "Required comparison conditions were supplied but not satisfied: "
                    + ", ".join(condition.key for condition in failed),
                )
            ]
        elif missing:
            status = "conditionally_comparable"
            reasons = [
                _reason(
                    "conditions_not_verified",
                    "Required comparison conditions have not been verified: "
                    + ", ".join(condition.key for condition in missing),
                )
            ]
        else:
            status = "comparable"
            reasons = [
                _reason(
                    "conditions_verified" if required else "rule_comparable",
                    "Every required comparison condition is verified."
                    if required
                    else "The explicit rule approves this comparison without additional conditions.",
                )
            ]

        return ComparisonDecision(
            left=_measurement_summary(left),
            right=_measurement_summary(right),
            status=status,
            rule_id=rule["rule_id"],
            reasons=reasons,
            required_conditions=required,
            warnings=warnings,
            scientific_justification=rule["scientific_justification"],
            source_references=_dedupe_references(
                rule.get("source_references", [])
                + left.get("source_references", [])
                + right.get("source_references", [])
            ),
            registry_version=self.bundle.registry_version,
            dataset_version=self.bundle.dataset_version,
        )

    def summary(self) -> dict[str, Any]:
        """Return registry-level counts and definitions for API discovery."""

        status_counts = {status: 0 for status in sorted(ALLOWED_STATUSES)}
        for measurement in self._measurements.values():
            status_counts[measurement["comparison_status"]] += 1
        rule_counts = {status: 0 for status in sorted(ALLOWED_STATUSES)}
        for rule in self._rules.values():
            rule_counts[rule["status"]] += 1
        return {
            "registry_version": self.bundle.registry_version,
            "dataset_version": self.bundle.dataset_version,
            "default_policy": self.bundle.comparability["default_policy"],
            "state_definitions": self.bundle.comparability["state_definitions"],
            "measurement_status_counts": status_counts,
            "rule_status_counts": rule_counts,
            "measurement_count": len(self._measurements),
            "rule_count": len(self._rules),
        }
