"""Dataset file, field, and limitation metadata for the read-only API.

Everything here is assembled from committed metadata: the download manifest,
the acquisition report, the serving and comparability registries, the source
field maps in the parsers, and the dataset-quality report. No filesystem path
is exposed, no unselected archive file is listed, and no description is
invented when the source does not provide one.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from src.analytics.citations import CitationRegistry, file_citation_id
from src.analytics.errors import InvalidQueryError, NotFoundError
from src.analytics.integrity import MeasurementIntegrity, PresenceCheck
from src.analytics.registry import RegistryBundle, repo_root
from src.data_pipeline.channels import CHANNEL_MAP
from src.data_pipeline.parsers.droplet import (
    CATEGORICAL_FIELDS as DROPLET_CATEGORICAL_FIELDS,
    NUMERIC_FIELDS as DROPLET_NUMERIC_FIELDS,
)
from src.data_pipeline.parsers.gas_flame import FIELD_MAP as GAS_FLAME_FIELD_MAP
from src.data_pipeline.parsers.smoke import SMOKE_CHANNELS

GAS_FLAME_SOURCES = {
    ("PSI-10", "normal"): (
        "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
        "PSI-10_normal",
    ),
    ("PSI-10", "inverse"): (
        "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
        "PSI-10_inverse",
    ),
    ("PSI-159", "normal"): (
        "PSI-159_Experimental table_CFI-G_Normal Flames.csv",
        "PSI-159_normal",
    ),
    ("PSI-159", "inverse"): (
        "PSI-159_Experimental table_CFI-G_Inverse Flames.csv",
        "PSI-159_inverse",
    ),
}

MATERIAL_SOURCES = {
    "PSI-25": {
        "file": "PSI-25_Science Documents_BASS-II_Test.Matrices.xlsx",
        "sheets": ["Bhattacharjee", "Ferkul", "Miller", "Olson", "Fernandez-Pello", "T'ien"],
        "columns": {
            "material": "Material",
            "initial_o2_pct": "calibrated  initial O2 % by vol ",
            "final_o2_pct": "calibrated final O2 % by vol",
            "initial_co2_pct": "Initial CO2 % by vol",
            "final_co2_pct": "Final CO2 % by vol",
            "initial_co_ppm": "Initial CO (ppm)",
            "final_co_ppm": "Final CO (ppm)",
            "flow_restrictor": "Flow restrictor",
            "fan_display": "Fan display",
            "air_display": "Air display",
        },
    },
    "PSI-26": {
        "file": "PSI-26_Science Documents_As Run_Test Matrix.xlsx",
        "sheets": ["as run matrix"],
        "columns": {
            "material": "material",
            "o2_pct": "O2 % by volume",
            "pressure_atm": "pressure, atm",
            "co2_mm_hg": "CO2, mm Hg",
            "flow_restrictor": "Flow restrictor",
            "fan_display": "Fan display",
            "air_display": "Air display",
        },
    },
}

SCOPE_ORDER = {"dataset": 0, "file": 1, "measurement": 2, "comparison": 3}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "item"


def _restriction_sentence(scope: str, code: str) -> str:
    code = code.strip().rstrip(".")
    return f"{scope} restriction recorded in the serving registry: {code}."


def _restriction_code(value: str) -> str:
    text = value.strip()
    if re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", text):
        return text
    return "serving_restriction_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def _restriction_explanation(scope: str, value: str) -> str:
    text = value.strip()
    if " " in text:
        return text
    return _restriction_sentence(scope, text)


def _presence_explanation(presence: PresenceCheck) -> str:
    if presence.status == "missing" and presence.reason == "field_not_in_canonical_table":
        return (
            f"The registry field {presence.field} is not a column in the canonical "
            f"{presence.table} table for {presence.accession}, so it has no values."
        )
    explanation = (
        f"The registry lists {presence.measurement_id} as available, but the "
        f"canonical {presence.table} table has {presence.non_null_count or 0} "
        f"non-null values in {presence.field} for {presence.accession} across "
        f"{presence.total_rows or 0} rows."
    )
    for alternative in presence.alternatives:
        explanation += (
            f" The source reports {alternative['canonical_field']} in "
            f"{alternative['unit']}; that is a different field and is not "
            "substituted for this registry field."
        )
    return explanation


def _presence_evidence(presence: PresenceCheck) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    if presence.table and presence.field:
        evidence.append(
            {
                "kind": "canonical_data",
                "path": f"data/processed/{presence.table}.parquet",
                "field": presence.field,
                "accession": presence.accession,
                "non_null_count": presence.non_null_count,
                "total_rows": presence.total_rows,
            }
        )
    for alternative in presence.alternatives:
        item = alternative.get("evidence")
        if isinstance(item, dict):
            evidence.append(dict(item))
    return evidence


def _category(code: str) -> str:
    code = code.lower()
    if any(token in code for token in ("404", "unavailable", "missing", "no_time", "not_selected")):
        return "availability"
    if any(token in code for token in ("unit", "o2_", "burning_rate", "pressure_basis")):
        return "units"
    if "calibrat" in code:
        return "calibration"
    if any(token in code for token in ("sentinel", "spreadsheet", "blank", "case_variant", "over_range")):
        return "data_quality"
    if "computed" in code:
        return "value_kind"
    if any(token in code for token in ("compar", "pair", "metadata_only", "undefined")):
        return "comparability"
    if any(token in code for token in ("summary", "separate_runs", "time_series", "context", "legacy")):
        return "scope"
    return "data_quality"


def _severity(state: str, fallback: str = "warning") -> str:
    if state == "blocked":
        return "error"
    if state in {"restricted", "available_with_warnings"}:
        return "warning"
    if state == "metadata_only":
        return "info"
    return fallback


def _affected_operations(use_states: dict[str, str]) -> list[str]:
    return [
        use
        for use in ("exploration", "quantitative_comparison", "time_series", "provenance")
        if use_states.get(use) != "available"
    ]


def _source_columns(measurement: dict[str, Any]) -> list[dict[str, Any]]:
    dataset_id = measurement["dataset_id"]
    accession = measurement["accession"]
    field = measurement.get("canonical_field")
    channel = measurement.get("canonical_channel")
    columns: list[dict[str, Any]] = []

    if dataset_id in {"psi-10-gas-flame", "psi-159-gas-flame"} and field:
        for (source_accession, flame_type), (file_name, table_key) in GAS_FLAME_SOURCES.items():
            if source_accession != accession:
                continue
            mapping = GAS_FLAME_FIELD_MAP.get(table_key, {})
            raw = mapping.get(field)
            if raw:
                columns.append(
                    {
                        "raw_column": raw,
                        "source_file": file_name,
                        "applies_to": f"{flame_type.capitalize()} flame rows",
                    }
                )

    if dataset_id in {"psi-25-material", "psi-26-material"} and field:
        source = MATERIAL_SOURCES.get(accession)
        if source and field in source["columns"]:
            columns.append(
                {
                    "raw_column": source["columns"][field],
                    "source_file": source["file"],
                    "source_sheets": source["sheets"],
                }
            )

    if dataset_id == "psi-69-droplet" and field:
        raw = DROPLET_NUMERIC_FIELDS.get(field) or DROPLET_CATEGORICAL_FIELDS.get(field)
        if raw:
            columns.append(
                {
                    "raw_column": raw,
                    "source_file": "PSI-69_Experimental table_FLEX.csv",
                }
            )

    if dataset_id == "psi-100-telemetry" and channel:
        raw_names = sorted(
            raw
            for raw, definition in CHANNEL_MAP.items()
            if definition.canonical == channel
        )
        if raw_names:
            columns.append(
                {
                    "raw_columns": raw_names,
                    "source_file": "PSI-100_Raw Data_Raw telemetry file.csv",
                    "note": "The same canonical channel also appears under workbook header spellings.",
                }
            )
    elif dataset_id == "psi-100-telemetry" and field == "relative_time_ms":
        columns.append(
            {
                "raw_column": "RelativeSeconds",
                "source_file": "PSI-100_Raw Data_Raw telemetry file.csv",
                "note": "Values are milliseconds despite the header name.",
            }
        )

    if dataset_id == "psi-101-smoke" and channel:
        raw_names = sorted(
            raw
            for raw, definition in SMOKE_CHANNELS.items()
            if definition["canonical"] == channel
        )
        if raw_names:
            columns.append(
                {
                    "raw_columns": raw_names,
                    "source_file": "PSI-101_Raw Data_HKPData_gmt250_1.csv",
                    "note": "Representative run; the other 43 HKP exports share the same header.",
                }
            )

    if dataset_id == "psi-102-smoke-log" and field == "event_type":
        columns.append(
            {
                "raw_column": "column B (0-based index 1)",
                "source_file": "PSI-102_Analyzed Data_Run 1 GMT252 testlog.xls",
                "note": "The legacy log has no header row; the parser promotes the second cell.",
            }
        )

    return columns


class DatasetMetadata:
    """Files, fields, and limitations for one curated dataset."""

    def __init__(
        self,
        bundle: RegistryBundle,
        citations: CitationRegistry,
        *,
        root: Path | str | None = None,
        quality_report: dict[str, Any] | None = None,
        integrity: MeasurementIntegrity | None = None,
    ):
        self.bundle = bundle
        self.citations = citations
        self.integrity = integrity
        self.root = Path(root).expanduser().resolve() if root else repo_root()
        self.quality_report = quality_report or _load_json(
            self.root / "data" / "reports" / "dataset_quality_report.json"
        )
        investigations = _load_json(
            self.root / "data" / "registry" / "psi_combustion_investigations.json"
        )
        self.investigations = {
            item.get("accession"): item
            for item in investigations.get("investigations", [])
            if isinstance(item, dict) and item.get("accession")
        }
        acquisition = _load_json(
            self.root / "data" / "reports" / "acquisition_report.json"
        )
        self.known_unavailable = acquisition.get("known_unavailable", [])

    # ------------------------------------------------------------------
    # Files
    # ------------------------------------------------------------------
    def _file_item(self, citation: dict[str, Any]) -> dict[str, Any]:
        return {
            "file_id": citation["citation_id"],
            "citation_id": citation["citation_id"],
            "file_name": citation["file"]["name"],
            "accession": citation["accession"],
            "dataset_ids": citation.get("dataset_ids", []),
            "kind": citation["file"].get("kind"),
            "priority": citation["file"].get("priority"),
            "purpose": citation["file"].get("purpose"),
            "source_url": citation["source"].get("source_url"),
            "availability": citation["availability"]["status"],
            "downloadable": citation["availability"]["downloadable"],
            "availability_reason": citation["availability"].get("reason"),
            "download": {
                "status": citation["retrieval"].get("download_status"),
                "http_status": citation["retrieval"].get("http_status"),
                "bytes": citation["retrieval"].get("bytes"),
                "retrieved_at": citation["retrieval"].get("retrieved_at"),
                "sha256": citation["source"].get("sha256"),
                "checksum_match": citation["retrieval"].get("checksum_match"),
            },
            "verification": citation["verification"],
            "provenance": citation["provenance"],
        }

    def list_files(
        self,
        dataset_id: str,
        *,
        kind: str | None = None,
        availability: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        dataset = self.bundle.datasets.get(dataset_id)
        if dataset is None:
            raise NotFoundError(
                "dataset is not present in the serving registry",
                details={"dataset_id": dataset_id},
            )
        citations = self.citations.list(dataset_id=dataset_id)
        items = [self._file_item(citation) for citation in citations]
        if kind:
            items = [item for item in items if item["kind"] == kind]
        if availability:
            items = [item for item in items if item["availability"] == availability]
        total = len(items)
        page_items = items[offset : offset + limit]
        investigation = self.investigations.get(dataset["accession"], {})
        public_count = int(investigation.get("file_count") or 0)
        experimental_table_count = int(investigation.get("experimental_table_count") or 0)
        curated_count = len(citations)
        return {
            "dataset_id": dataset_id,
            "accession": dataset["accession"],
            "display_name": dataset["display_name"],
            "files": page_items,
            "summary": {
                "curated_files": curated_count,
                "available_files": sum(
                    1 for item in items if item["availability"] == "available"
                ),
                "unavailable_files": sum(
                    1 for item in items if item["availability"] == "unavailable"
                ),
                "downloadable_files": sum(1 for item in items if item["downloadable"]),
                "known_unavailable_files": sum(
                    1
                    for item in items
                    if item["download"]["status"] == "known_unavailable"
                ),
                "experimental_tables": sum(
                    1 for item in items if item["kind"] == "experimental_table"
                ),
            },
            "inventory": {
                "public_inventory_file_count": public_count,
                "curated_file_count": curated_count,
                "not_selected_file_count": max(public_count - curated_count, 0),
                "public_experimental_table_count": experimental_table_count,
                "archive_status": investigation.get("archive_status"),
                "note": (
                    "Only curated files are listed. The public inventory count is "
                    "shown for context; unselected archive files are not exposed."
                ),
            },
            "page": {
                "limit": limit,
                "offset": offset,
                "total": total,
                "has_more": offset + len(page_items) < total,
            },
        }

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    def _field_item(self, measurement: dict[str, Any]) -> dict[str, Any]:
        state = self.bundle.measurement_states.get(measurement["measurement_id"], {})
        rules = self.bundle.rules_for_measurement(measurement["measurement_id"])
        canonical_name = (
            measurement.get("canonical_field")
            or measurement.get("canonical_channel")
            or measurement.get("parameter")
        )
        presence = (
            self.integrity.check(measurement["measurement_id"])
            if self.integrity is not None
            else None
        )
        presence_dict = presence.to_dict() if presence is not None else None
        missing_canonical_values = presence is not None and presence.status == "missing"
        restrictions = list(measurement.get("quality_restrictions", []))
        if state.get("restrictions"):
            for restriction in state["restrictions"]:
                if restriction not in restrictions:
                    restrictions.append(restriction)
        if missing_canonical_values and "measurement_has_no_canonical_values" not in restrictions:
            restrictions.append("measurement_has_no_canonical_values")
        return {
            "field_id": measurement["measurement_id"],
            "measurement_id": measurement["measurement_id"],
            "dataset_id": measurement["dataset_id"],
            "accession": measurement["accession"],
            "canonical_name": canonical_name,
            "parameter": measurement["parameter"],
            "description": measurement.get("physical_meaning"),
            "physical_quantity": measurement["physical_quantity"],
            "unit": measurement["unit"],
            "unit_status": measurement["unit_status"],
            "value_kind": measurement["value_kind"],
            "measurement_method": measurement.get("measurement_method"),
            "calibration": {
                "status": measurement["calibration_status"],
                "note": (
                    "No calibration document is recorded for this field."
                    if measurement["calibration_status"] in {"not_documented", "uncalibrated"}
                    else None
                ),
            },
            "missingness": {
                "availability": measurement["availability"],
                "restrictions": restrictions,
                "canonical_presence": presence_dict,
                "policy": (
                    "Missing values are never zero; qualifiers and sentinels are "
                    "preserved as documented in DATA_DICTIONARY.md."
                ),
            },
            "integrity": presence_dict,
            "alternatives": (
                [dict(item) for item in presence.alternatives] if presence else []
            ),
            "flags": restrictions,
            "comparability": {
                "status": measurement["comparison_status"],
                "compatible_datasets": measurement.get("compatible_datasets", []),
                "incompatible_datasets": measurement.get("incompatible_datasets", []),
                "rules": [
                    {
                        "rule_id": rule["rule_id"],
                        "status": rule["status"],
                        "scientific_justification": rule["scientific_justification"],
                    }
                    for rule in sorted(rules, key=lambda item: item["rule_id"])
                ],
            },
            "source_columns": _source_columns(measurement),
            "source_references": measurement.get("source_references", []),
            "serving_state": state.get("serving_state"),
            "use_states": state.get("use_states", {}),
        }

    def list_fields(
        self,
        dataset_id: str,
        *,
        value_kind: str | None = None,
        physical_quantity: str | None = None,
        comparison_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        dataset = self.bundle.datasets.get(dataset_id)
        if dataset is None:
            raise NotFoundError(
                "dataset is not present in the serving registry",
                details={"dataset_id": dataset_id},
            )
        measurements = [
            measurement
            for measurement in self.bundle.measurements.values()
            if measurement["dataset_id"] == dataset_id
        ]
        items = [self._field_item(measurement) for measurement in measurements]
        if value_kind:
            items = [item for item in items if item["value_kind"] == value_kind]
        if physical_quantity:
            items = [
                item for item in items if item["physical_quantity"] == physical_quantity
            ]
        if comparison_status:
            items = [
                item
                for item in items
                if item["comparability"]["status"] == comparison_status
            ]
        items.sort(key=lambda item: item["field_id"])
        total = len(items)
        page_items = items[offset : offset + limit]
        return {
            "dataset_id": dataset_id,
            "accession": dataset["accession"],
            "display_name": dataset["display_name"],
            "fields": page_items,
            "summary": {
                "field_count": total,
                "with_verified_source_column": sum(
                    1 for item in items if item["source_columns"]
                ),
                "with_canonical_values": sum(
                    1
                    for item in items
                    if (item.get("integrity") or {}).get("status") == "available"
                ),
                "without_canonical_values": sum(
                    1
                    for item in items
                    if (item.get("integrity") or {}).get("status") == "missing"
                ),
                "presence_not_checked": sum(
                    1
                    for item in items
                    if (item.get("integrity") or {}).get("status") == "not_checked"
                ),
                "value_kinds": {
                    kind: sum(1 for item in items if item["value_kind"] == kind)
                    for kind in sorted({item["value_kind"] for item in items})
                },
                "comparison_statuses": {
                    status: sum(
                        1
                        for item in items
                        if item["comparability"]["status"] == status
                    )
                    for status in sorted(
                        {item["comparability"]["status"] for item in items}
                    )
                },
            },
            "page": {
                "limit": limit,
                "offset": offset,
                "total": total,
                "has_more": offset + len(page_items) < total,
            },
        }

    # ------------------------------------------------------------------
    # Limitations
    # ------------------------------------------------------------------
    def _dataset_limitations(self, dataset: dict[str, Any]) -> list[dict[str, Any]]:
        items = []
        use_states = dataset.get("use_states", {})
        state = dataset.get("base_state", "available")
        for reason in dataset.get("reasons", []):
            code = str(reason.get("code") or "dataset_reason")
            items.append(
                {
                    "limitation_id": f"lim_d_{_slug(dataset['dataset_id'])}_{_slug(code)}",
                    "scope": "dataset",
                    "scope_id": dataset["dataset_id"],
                    "dataset_id": dataset["dataset_id"],
                    "accession": dataset["accession"],
                    "category": _category(code),
                    "severity": _severity(state),
                    "code": code,
                    "explanation": reason.get("message"),
                    "affected_operations": _affected_operations(use_states),
                    "evidence": dataset.get("source_references", []),
                    "resolution_status": "documented",
                    "resolution_note": "Recorded as a dataset-level serving limitation.",
                }
            )
        for restriction in dataset.get("restrictions", []):
            code = _restriction_code(str(restriction))
            items.append(
                {
                    "limitation_id": f"lim_d_{_slug(dataset['dataset_id'])}_{code}",
                    "scope": "dataset",
                    "scope_id": dataset["dataset_id"],
                    "dataset_id": dataset["dataset_id"],
                    "accession": dataset["accession"],
                    "category": _category(str(restriction)),
                    "severity": _severity(state),
                    "code": code,
                    "explanation": _restriction_explanation("Dataset", str(restriction)),
                    "affected_operations": _affected_operations(use_states),
                    "evidence": dataset.get("source_references", []),
                    "resolution_status": "documented",
                    "resolution_note": "Recorded as a dataset-level serving restriction.",
                }
            )
        return items

    def _measurement_limitations(self, dataset: dict[str, Any]) -> list[dict[str, Any]]:
        items = []
        for measurement_id, state in sorted(self.bundle.measurement_states.items()):
            measurement = self.bundle.measurements.get(measurement_id)
            if measurement is None or measurement["dataset_id"] != dataset["dataset_id"]:
                continue
            use_states = state.get("use_states", {})
            for reason in state.get("reasons", []):
                code = str(reason.get("code") or "measurement_reason")
                items.append(
                    {
                        "limitation_id": f"lim_m_{_slug(measurement_id)}_{_slug(code)}",
                        "scope": "measurement",
                        "scope_id": measurement_id,
                        "dataset_id": dataset["dataset_id"],
                        "accession": dataset["accession"],
                        "category": _category(code),
                        "severity": _severity(state.get("serving_state", "available")),
                        "code": code,
                        "explanation": reason.get("message"),
                        "affected_operations": _affected_operations(use_states),
                        "evidence": measurement.get("source_references", []),
                        "resolution_status": "documented",
                        "resolution_note": "Recorded as a measurement-level serving limitation.",
                    }
                )
            for restriction in state.get("restrictions", []):
                code = _restriction_code(str(restriction))
                limitation_id = f"lim_m_{_slug(measurement_id)}_{code}"
                if any(item["limitation_id"] == limitation_id for item in items):
                    continue
                items.append(
                    {
                        "limitation_id": limitation_id,
                        "scope": "measurement",
                        "scope_id": measurement_id,
                        "dataset_id": dataset["dataset_id"],
                        "accession": dataset["accession"],
                        "category": _category(str(restriction)),
                        "severity": _severity(state.get("serving_state", "available")),
                        "code": code,
                        "explanation": _restriction_explanation(
                            "Measurement", str(restriction)
                        ),
                        "affected_operations": _affected_operations(use_states),
                        "evidence": measurement.get("source_references", []),
                        "resolution_status": "documented",
                        "resolution_note": "Recorded as a measurement-level serving restriction.",
                    }
                )
            presence = (
                self.integrity.check(measurement_id)
                if self.integrity is not None
                else None
            )
            if (
                presence is not None
                and presence.status == "missing"
                and measurement.get("availability") != "missing"
            ):
                limitation_id = (
                    f"lim_i_{_slug(measurement_id)}_no_canonical_values"
                )
                if not any(item["limitation_id"] == limitation_id for item in items):
                    items.append(
                        {
                            "limitation_id": limitation_id,
                            "scope": "measurement",
                            "scope_id": measurement_id,
                            "dataset_id": dataset["dataset_id"],
                            "accession": dataset["accession"],
                            "category": "availability",
                            "severity": "error",
                            "code": "measurement_has_no_canonical_values",
                            "explanation": _presence_explanation(presence),
                            "affected_operations": [
                                "exploration",
                                "quantitative_comparison",
                                "time_series",
                                "provenance",
                            ],
                            "evidence": _presence_evidence(presence),
                            "resolution_status": "open",
                            "resolution_note": (
                                "The registry is preserved as authoritative and was "
                                "not rewritten. The canonical field is empty for this "
                                "accession; any comparison using it is blocked by the "
                                "measurement-integrity check until the registry or "
                                "canonical data is corrected."
                            ),
                        }
                    )
        return items

    def _issue_datasets(self, issue: dict[str, Any]) -> set[str]:
        details = issue.get("details") or {}
        accession = details.get("accession")
        if accession:
            return {
                dataset["dataset_id"]
                for dataset in self.bundle.datasets.values()
                if dataset["accession"] == accession
            }
        column = str(details.get("column") or "")
        code = str(issue.get("code") or "")
        if code == "missing_final_state":
            return {"psi-10-gas-flame"}
        if code == "spreadsheet_error":
            return {"psi-159-gas-flame"}
        if code == "sentinel_points":
            return {"psi-101-smoke"}
        if column == "burning_rate_mm_as_labeled":
            return {"psi-69-droplet"}
        return set()

    def _quality_limitations(self, dataset: dict[str, Any]) -> list[dict[str, Any]]:
        items = []
        for index, issue in enumerate(self.quality_report.get("issues", [])):
            if dataset["dataset_id"] not in self._issue_datasets(issue):
                continue
            code = str(issue.get("code") or "quality_issue")
            items.append(
                {
                    "limitation_id": (
                        f"lim_q_{_slug(dataset['dataset_id'])}_{_slug(code)}_{index}"
                    ),
                    "scope": "dataset",
                    "scope_id": dataset["dataset_id"],
                    "dataset_id": dataset["dataset_id"],
                    "accession": dataset["accession"],
                    "category": _category(code),
                    "severity": issue.get("severity", "warning"),
                    "code": code,
                    "explanation": issue.get("message"),
                    "affected_operations": [
                        "exploration",
                        "quantitative_comparison",
                    ],
                    "evidence": [
                        {
                            "kind": "quality_report",
                            "path": "data/reports/dataset_quality_report.json",
                            "section": f"issues[{index}]",
                        }
                    ],
                    "resolution_status": "open",
                    "resolution_note": "Preserved in the dataset-quality report.",
                }
            )
        return items

    def _file_limitations(self, dataset: dict[str, Any]) -> list[dict[str, Any]]:
        items = []
        for item in self.known_unavailable:
            if not isinstance(item, dict) or item.get("accession") != dataset["accession"]:
                continue
            file_name = str(item.get("file_name") or "")
            if not file_name:
                continue
            citation_id = file_citation_id(dataset["accession"], file_name)
            items.append(
                {
                    "limitation_id": f"lim_f_{_slug(citation_id)}",
                    "scope": "file",
                    "scope_id": citation_id,
                    "dataset_id": dataset["dataset_id"],
                    "accession": dataset["accession"],
                    "category": "availability",
                    "severity": "error",
                    "code": "known_unavailable_http_404",
                    "explanation": (
                        f"{file_name} is listed by the public PSI inventory but the "
                        "download endpoint returns HTTP 404. It is not available and "
                        "must not be presented as downloadable."
                    ),
                    "affected_operations": [
                        "exploration",
                        "quantitative_comparison",
                        "time_series",
                        "provenance",
                    ],
                    "evidence": [
                        {
                            "kind": "acquisition_report",
                            "path": "data/reports/acquisition_report.json",
                            "section": "known_unavailable",
                        }
                    ],
                    "resolution_status": "accepted",
                    "resolution_note": (
                        "Verified during acquisition; the file is retained only as a "
                        "documented unavailable citation."
                    ),
                }
            )
        return items

    def list_limitations(
        self,
        dataset_id: str,
        *,
        scope: str | None = None,
        category: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        dataset = self.bundle.datasets.get(dataset_id)
        if dataset is None:
            raise NotFoundError(
                "dataset is not present in the serving registry",
                details={"dataset_id": dataset_id},
            )
        if scope and scope not in SCOPE_ORDER:
            raise InvalidQueryError(
                "unknown limitation scope",
                details={"scope": scope, "allowed": sorted(SCOPE_ORDER)},
            )
        if severity and severity not in SEVERITY_ORDER:
            raise InvalidQueryError(
                "unknown limitation severity",
                details={"severity": severity, "allowed": sorted(SEVERITY_ORDER)},
            )
        items = [
            *self._dataset_limitations(dataset),
            *self._measurement_limitations(dataset),
            *self._quality_limitations(dataset),
            *self._file_limitations(dataset),
        ]
        if scope:
            items = [item for item in items if item["scope"] == scope]
        if category:
            items = [item for item in items if item["category"] == category]
        if severity:
            items = [item for item in items if item["severity"] == severity]
        if status:
            items = [item for item in items if item["resolution_status"] == status]
        items.sort(
            key=lambda item: (
                SCOPE_ORDER[item["scope"]],
                SEVERITY_ORDER.get(item["severity"], 9),
                item["limitation_id"],
            )
        )
        total = len(items)
        page_items = items[offset : offset + limit]
        return {
            "dataset_id": dataset_id,
            "accession": dataset["accession"],
            "display_name": dataset["display_name"],
            "limitations": page_items,
            "summary": {
                "total": total,
                "by_scope": {
                    key: sum(1 for item in items if item["scope"] == key)
                    for key in sorted({item["scope"] for item in items})
                },
                "by_severity": {
                    key: sum(1 for item in items if item["severity"] == key)
                    for key in sorted({item["severity"] for item in items})
                },
                "by_status": {
                    key: sum(1 for item in items if item["resolution_status"] == key)
                    for key in sorted({item["resolution_status"] for item in items})
                },
            },
            "page": {
                "limit": limit,
                "offset": offset,
                "total": total,
                "has_more": offset + len(page_items) < total,
            },
        }
