"""Paired-comparison contract.

The comparability engine decides whether two measurements may be compared.
This module answers a separate question: is there a verified record-level
alignment method that can produce chart-ready pairs? The answer is no unless a
committed alignment method exists, is marked verified, and the authoritative
decision is ``comparable``.

No method is inferred from matching column names, row numbers, units, or
experiment families. When no method exists the response carries an explicit
explanation and empty observation/series arrays.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.analytics.comparability import ComparisonDecision
from src.analytics.errors import AnalyticsError
from src.analytics.registry import repo_root


def _load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AnalyticsError(
            "paired alignment registry is not available",
            details={"path": path.name},
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AnalyticsError(
            "paired alignment registry could not be read",
            details={"error_type": type(exc).__name__},
        ) from exc
    if not isinstance(payload, dict):
        raise AnalyticsError("paired alignment registry must be a JSON object")
    return payload


class PairedComparisonRegistry:
    """Read-only access to committed alignment methods."""

    def __init__(self, root: Path | str | None = None):
        base = Path(root).expanduser().resolve() if root else repo_root()
        self.path = base / "data" / "metadata" / "paired_alignment_registry.json"
        payload = _load_registry(self.path)
        self.registry_version = payload.get("registry_version")
        self.dataset_version = payload.get("dataset_version")
        self.requirements = payload.get("requirements", {})
        self.methods: dict[str, dict[str, Any]] = {}
        for method in payload.get("methods", []):
            if not isinstance(method, dict) or not method.get("method_id"):
                continue
            self.methods[method["method_id"]] = method

    def for_rule(self, rule_id: str | None) -> dict[str, Any] | None:
        if not rule_id:
            return None
        candidates = [
            method
            for method in self.methods.values()
            if method.get("rule_id") == rule_id
        ]
        if len(candidates) > 1:
            raise AnalyticsError(
                "more than one paired alignment method is registered for a rule",
                details={"rule_id": rule_id},
            )
        return candidates[0] if candidates else None


def evaluate_paired_values(
    decision: ComparisonDecision,
    *,
    registry: PairedComparisonRegistry,
    conditions: Mapping[str, bool | None] | None = None,
) -> dict[str, Any]:
    """Return the paired-values contract for an authoritative decision."""

    base = {
        "available": False,
        "status": "unavailable",
        "alignment": {
            "method_id": None,
            "verified": False,
            "keys": [],
            "value_fields": {},
            "unit_policy": None,
        },
        "conditions": {
            "supplied": dict(conditions or {}),
            "required": [
                {
                    "key": condition.key,
                    "satisfied": condition.satisfied,
                }
                for condition in decision.required_conditions
            ],
        },
        "observations": [],
        "series": [],
        "exclusions": [],
        "dataset_version": decision.dataset_version,
        "provenance": decision.source_references,
    }

    if decision.status not in {"comparable", "conditionally_comparable"}:
        return {
            **base,
            "reason": {
                "code": "comparison_not_approved",
                "message": (
                    "The authoritative comparability decision does not approve a "
                    "record-level comparison, so no paired values are returned."
                ),
                "decision_status": decision.status,
            },
        }

    if decision.status == "conditionally_comparable":
        missing = [
            condition.key
            for condition in decision.required_conditions
            if condition.satisfied is not True
        ]
        return {
            **base,
            "reason": {
                "code": "conditions_not_verified",
                "message": (
                    "Required comparison conditions are not verified, so no paired "
                    "values are returned."
                ),
                "missing_conditions": missing,
            },
        }

    method = registry.for_rule(decision.rule_id)
    if method is None:
        return {
            **base,
            "reason": {
                "code": "no_verified_alignment",
                "message": (
                    "The comparison is approved, but no verified record-level "
                    "alignment method is registered for this rule. The API does "
                    "not pair by row number, interpolate, normalize silently, or "
                    "convert ambiguous units."
                ),
                "rule_id": decision.rule_id,
                "required_alignment": {
                    "keys": [],
                    "note": "A committed method must name exact alignment keys and value fields.",
                },
            },
        }

    if not method.get("verified"):
        return {
            **base,
            "alignment": {
                "method_id": method.get("method_id"),
                "verified": False,
                "keys": method.get("alignment_keys", []),
                "value_fields": {
                    "left": method.get("left_value_field"),
                    "right": method.get("right_value_field"),
                },
                "unit_policy": method.get("unit_policy"),
            },
            "reason": {
                "code": "alignment_not_verified",
                "message": (
                    "An alignment method is registered but is not verified, so no "
                    "paired values are returned."
                ),
                "rule_id": decision.rule_id,
            },
        }

    # A verified method must be executed by an explicit, reviewed executor.
    # No executor is registered in this phase, so fail closed rather than
    # guessing at a join.
    return {
        **base,
        "alignment": {
            "method_id": method.get("method_id"),
            "verified": True,
            "keys": method.get("alignment_keys", []),
            "value_fields": {
                "left": method.get("left_value_field"),
                "right": method.get("right_value_field"),
            },
            "unit_policy": method.get("unit_policy"),
        },
        "reason": {
            "code": "alignment_executor_not_available",
            "message": (
                "The alignment method is verified, but no reviewed executor is "
                "registered. Paired values remain withheld rather than guessed."
            ),
            "rule_id": decision.rule_id,
        },
    }
