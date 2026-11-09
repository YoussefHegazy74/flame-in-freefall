#!/usr/bin/env python3
"""Build the committed Phase 2 comparability and serving registries.

Usage::

    .venv/bin/python scripts/build_phase2_registries.py
    .venv/bin/python scripts/build_phase2_registries.py --check

The script is deterministic. ``--check`` fails if the committed JSON differs
from the generated JSON. Source checksums and URLs are copied from the
committed acquisition manifest; no checksum is invented.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analytics import catalog  # noqa: E402
from src.analytics.registry import (  # noqa: E402
    COMPARABILITY_STATES,
    SERVING_STATES,
    USE_KEYS,
)

DEFAULT_OUTPUT_DIR = ROOT / "data" / "metadata"
DEFAULT_DATASET_MANIFEST = ROOT / "data" / "processed" / "dataset_manifest.json"
DEFAULT_DOWNLOAD_MANIFEST = ROOT / "data" / "registry" / "download_manifest.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"required manifest is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _file_index(download_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in download_manifest.get("files", []):
        file_id = record.get("file_id") or f"{record.get('accession')}::{record.get('file_name')}"
        index[file_id] = record
    return index


def _resolve_nasa_file(
    accession: str,
    file_name: str,
    file_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    file_id = f"{accession}::{file_name}"
    record = file_index.get(file_id)
    if record is None:
        raise SystemExit(f"source file is not in the committed acquisition manifest: {file_id}")
    sha256 = record.get("sha256_expected")
    if not sha256:
        raise SystemExit(f"source file has no committed checksum: {file_id}")
    return {
        "kind": "nasa_psi_file",
        "accession": accession,
        "file_name": file_name,
        "sha256": sha256,
        "source_url": record.get("source_url"),
    }


def _resolve_dataset_references(
    references: list[dict[str, Any]],
    file_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for reference in references:
        if reference.get("kind") == "nasa_psi_file":
            resolved.append(
                _resolve_nasa_file(
                    reference["accession"],
                    reference["file_name"],
                    file_index,
                )
            )
        else:
            resolved.append(dict(reference))
    return resolved


def _resolve_measurement_references(
    measurement: dict[str, Any],
    file_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    for key in measurement["source_files"]:
        accession, file_name = catalog.SOURCE_FILES[key]
        references.append(_resolve_nasa_file(accession, file_name, file_index))
    references.extend(dict(document) for document in measurement["source_documents"])
    return references


def _enrich_measurements(
    measurements: list[dict[str, Any]],
    rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {measurement["measurement_id"]: measurement for measurement in measurements}
    precedence = [
        "comparable",
        "conditionally_comparable",
        "blocked",
        "insufficient_metadata",
        "not_comparable",
    ]
    for measurement in measurements:
        measurement_id = measurement["measurement_id"]
        related = [
            rule
            for rule in rules
            if measurement_id in (rule["left_measurement_id"], rule["right_measurement_id"])
        ]
        compatible: set[str] = set()
        incompatible: set[str] = set()
        for rule in related:
            other_id = (
                rule["right_measurement_id"]
                if rule["left_measurement_id"] == measurement_id
                else rule["left_measurement_id"]
            )
            other_dataset = by_id[other_id]["dataset_id"]
            if rule["status"] in {"comparable", "conditionally_comparable"}:
                compatible.add(other_dataset)
            else:
                incompatible.add(other_dataset)
        measurement["compatible_datasets"] = sorted(compatible)
        measurement["incompatible_datasets"] = sorted(incompatible)
        statuses = {rule["status"] for rule in related}
        measurement["comparison_status"] = next(
            (status for status in precedence if status in statuses),
            "not_comparable",
        )
    return measurements


def _dataset_measurement_state(
    measurement: dict[str, Any],
    dataset: dict[str, Any],
) -> dict[str, Any]:
    measurement_id = measurement["measurement_id"]
    override = catalog.SERVING_OVERRIDES.get(measurement_id)
    if override:
        return {
            "measurement_id": measurement_id,
            "dataset_id": dataset["dataset_id"],
            "serving_state": override["serving_state"],
            "use_states": dict(override["use_states"]),
            "reasons": [dict(reason) for reason in override["reasons"]],
            "restrictions": list(override["restrictions"]),
        }

    defaults = dataset["measurement_defaults"]
    base_reasons = [dict(reason) for reason in defaults["reasons"]]
    restrictions = list(measurement["quality_restrictions"])
    restriction_reason = {
        "code": "measurement_restrictions",
        "message": (
            "Measurement-level restrictions: "
            + ", ".join(measurement["quality_restrictions"])
        ),
    }

    if measurement["availability"] == "missing":
        return {
            "measurement_id": measurement_id,
            "dataset_id": dataset["dataset_id"],
            "serving_state": "blocked",
            "use_states": {
                "exploration": "blocked",
                "quantitative_comparison": "blocked",
                "time_series": "blocked",
                "provenance": "available",
            },
            "reasons": [
                {
                    "code": "no_values",
                    "message": "The canonical column exists but has no values in the selected source.",
                }
            ],
            "restrictions": restrictions,
        }

    if measurement["availability"] == "metadata_only":
        return {
            "measurement_id": measurement_id,
            "dataset_id": dataset["dataset_id"],
            "serving_state": "metadata_only",
            "use_states": {
                "exploration": "metadata_only",
                "quantitative_comparison": "blocked",
                "time_series": "metadata_only",
                "provenance": "available",
            },
            "reasons": [
                {
                    "code": "no_canonical_measurements",
                    "message": "No canonical measurement rows exist for this resource.",
                }
            ],
            "restrictions": restrictions,
        }

    if measurement["value_kind"] == "raw" or measurement["calibration_status"] == "uncalibrated":
        reasons = base_reasons + [
            {
                "code": "uncalibrated_raw",
                "message": "The channel is a raw or uncalibrated signal and is not a physical measurement.",
            }
        ]
        return {
            "measurement_id": measurement_id,
            "dataset_id": dataset["dataset_id"],
            "serving_state": "restricted",
            "use_states": {
                "exploration": "available_with_warnings",
                "quantitative_comparison": "blocked",
                "time_series": "available_with_warnings",
                "provenance": "available",
            },
            "reasons": reasons,
            "restrictions": restrictions,
        }

    if measurement["unit_status"] in {"ambiguous", "not_stated"}:
        reasons = base_reasons + [
            {
                "code": "unit_ambiguity",
                "message": "The unit is ambiguous or not stated and must not be silently converted.",
            }
        ]
        return {
            "measurement_id": measurement_id,
            "dataset_id": dataset["dataset_id"],
            "serving_state": "restricted",
            "use_states": {
                "exploration": "available_with_warnings",
                "quantitative_comparison": "blocked",
                "time_series": "restricted",
                "provenance": "available",
            },
            "reasons": reasons,
            "restrictions": restrictions,
        }

    reasons = base_reasons
    if measurement["quality_restrictions"]:
        reasons = reasons + [restriction_reason]
    if measurement["value_kind"] == "computed":
        reasons = reasons + [
            {
                "code": "computed_source_field",
                "message": "The value is computed by the source and must be labeled as computed.",
            }
        ]
    elif measurement["value_kind"] == "categorical":
        reasons = reasons + [
            {
                "code": "categorical_measurement",
                "message": "The value is categorical and must not be aggregated as a number.",
            }
        ]

    return {
        "measurement_id": measurement_id,
        "dataset_id": dataset["dataset_id"],
        "serving_state": defaults["serving_state"],
        "use_states": dict(defaults["use_states"]),
        "reasons": reasons,
        "restrictions": restrictions,
    }


def build_registries(
    dataset_manifest_path: Path = DEFAULT_DATASET_MANIFEST,
    download_manifest_path: Path = DEFAULT_DOWNLOAD_MANIFEST,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the generated comparability and serving registries."""

    dataset_manifest = _load_json(dataset_manifest_path)
    download_manifest = _load_json(download_manifest_path)
    dataset_version = dataset_manifest.get("dataset_version")
    if not dataset_version:
        raise SystemExit("dataset manifest has no dataset_version")
    file_index = _file_index(download_manifest)

    measurements: list[dict[str, Any]] = []
    for definition in catalog.MEASUREMENTS:
        measurement = {
            key: value
            for key, value in definition.items()
            if key not in {"source_files", "source_documents"}
        }
        measurement["source_file_keys"] = list(definition["source_files"])
        measurement["source_references"] = _resolve_measurement_references(
            definition, file_index
        )
        measurements.append(measurement)

    rules: list[dict[str, Any]] = []
    for definition in catalog.RULES:
        rule = {
            key: value
            for key, value in definition.items()
            if key != "source_documents"
        }
        rule["source_references"] = [dict(doc) for doc in definition["source_documents"]]
        rules.append(rule)

    measurements = _enrich_measurements(measurements, rules)

    comparability = {
        "registry_version": catalog.REGISTRY_VERSION,
        "schema_version": catalog.COMPARABILITY_SCHEMA_VERSION,
        "dataset_version": dataset_version,
        "generated_by": "scripts/build_phase2_registries.py",
        "state_definitions": catalog.COMPARABILITY_STATE_DEFINITIONS,
        "default_policy": {
            "status": "not_comparable",
            "justification": (
                "No explicit comparison rule means no approved comparison. "
                "A matching column name, unit, or experiment family is not "
                "sufficient evidence."
            ),
            "engine_behavior": (
                "Return not_comparable with a no_explicit_rule reason and "
                "never infer a comparison."
            ),
        },
        "measurements": measurements,
        "comparison_rules": rules,
    }

    datasets: list[dict[str, Any]] = []
    measurement_states: list[dict[str, Any]] = []
    measurements_by_dataset: dict[str, list[dict[str, Any]]] = {}
    for measurement in measurements:
        measurements_by_dataset.setdefault(measurement["dataset_id"], []).append(measurement)

    for dataset_definition in catalog.DATASETS:
        dataset = dict(dataset_definition)
        dataset["source_references"] = _resolve_dataset_references(
            dataset_definition["source_references"], file_index
        )
        dataset_measurements = measurements_by_dataset.get(dataset["dataset_id"], [])
        dataset["measurement_count"] = len(dataset_measurements)
        states = [
            _dataset_measurement_state(measurement, dataset)
            for measurement in dataset_measurements
        ]
        dataset["measurement_state_ids"] = [state["measurement_id"] for state in states]
        measurement_states.extend(states)
        datasets.append(dataset)

    serving = {
        "registry_version": catalog.REGISTRY_VERSION,
        "schema_version": catalog.SERVING_SCHEMA_VERSION,
        "dataset_version": dataset_version,
        "generated_by": "scripts/build_phase2_registries.py",
        "state_definitions": catalog.SERVING_STATE_DEFINITIONS,
        "use_definitions": catalog.USE_DEFINITIONS,
        "datasets": datasets,
        "measurement_states": measurement_states,
    }
    return comparability, serving


def _serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify committed registries match generated output")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dataset-manifest", type=Path, default=DEFAULT_DATASET_MANIFEST)
    parser.add_argument("--download-manifest", type=Path, default=DEFAULT_DOWNLOAD_MANIFEST)
    args = parser.parse_args(argv)

    comparability, serving = build_registries(
        dataset_manifest_path=args.dataset_manifest,
        download_manifest_path=args.download_manifest,
    )
    outputs = {
        "comparability_registry.json": comparability,
        "serving_registry.json": serving,
    }

    if args.check:
        mismatches: list[str] = []
        for name, payload in outputs.items():
            path = args.output_dir / name
            expected = _serialize(payload)
            if not path.exists():
                mismatches.append(f"{path}: missing")
            elif path.read_text(encoding="utf-8") != expected:
                mismatches.append(f"{path}: content differs")
        if mismatches:
            print("Phase 2 registry check failed:")
            for mismatch in mismatches:
                print(f"  - {mismatch}")
            return 1
        print(
            "Committed Phase 2 registries match the generated output: "
            f"{len(comparability['measurements'])} measurements, "
            f"{len(comparability['comparison_rules'])} rules, "
            f"{len(serving['datasets'])} datasets, "
            f"{len(serving['measurement_states'])} measurement states."
        )
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in outputs.items():
        path = args.output_dir / name
        path.write_text(_serialize(payload), encoding="utf-8")
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
