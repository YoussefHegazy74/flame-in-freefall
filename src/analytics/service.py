"""API-ready shaping over the registries, quality report, and DuckDB layer.

The service is the only place where scientific state and data rows meet. It
keeps the two explicit:

* every data response carries the serving decision for the use it supports;
* every comparison carries the comparability decision and its reasons;
* every row-level response carries source provenance;
* computed fields are labeled, and warnings travel with the response.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from src.analytics.citations import (
    CitationRegistry,
    attach_file_citation_ids,
    decode_row_citation_id,
    load_citation_registry,
    row_citation_id,
)
from src.analytics.comparability import ComparabilityEngine
from src.analytics.dataset_metadata import DatasetMetadata
from src.analytics.db import AGGREGATE_TABLES, AnalyticsDatabase, PageResult
from src.analytics.errors import InvalidQueryError, NotFoundError
from src.analytics.facets import build_gas_flame_facets
from src.analytics.field_metadata import field_metadata
from src.analytics.integrity import MeasurementIntegrity
from src.analytics.paired import PairedComparisonRegistry, evaluate_paired_values
from src.analytics.publications import PublicationRegistry
from src.analytics.registry import RegistryBundle, load_registries
from src.analytics.serving import ServingEngine

SERVING_TO_QUALITY = {
    "available": "verified",
    "available_with_warnings": "partial",
    "restricted": "partial",
    "blocked": "blocked",
    "metadata_only": "not_available",
}

COMPARABILITY_TO_QUALITY = {
    "comparable": "verified",
    "conditionally_comparable": "partial",
    "not_comparable": "blocked",
    "blocked": "blocked",
    "insufficient_metadata": "blocked",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _request_id() -> str:
    return "req_" + secrets.token_hex(12)


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _dedupe_dicts(values: Iterable[dict[str, Any]], key_fields: Sequence[str]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []
    for value in values:
        key = tuple(value.get(field) for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


class AnalyticsService:
    """Compose registries, serving decisions, quality, and bounded queries."""

    def __init__(
        self,
        database: AnalyticsDatabase | None = None,
        bundle: RegistryBundle | None = None,
    ):
        self.db = database or AnalyticsDatabase()
        self.bundle = bundle or load_registries()
        self.comparability = ComparabilityEngine(self.bundle)
        self.serving = ServingEngine(self.bundle)
        self.citations = load_citation_registry(self.bundle)
        self.integrity = MeasurementIntegrity(self.db, self.bundle)
        try:
            quality_report = self.db.quality_report()
        except Exception:
            quality_report = None
        self.metadata = DatasetMetadata(
            self.bundle,
            self.citations,
            quality_report=quality_report,
            integrity=self.integrity,
        )
        self.publications = PublicationRegistry()
        self.paired = PairedComparisonRegistry()

    # ------------------------------------------------------------------
    # Envelope helpers
    # ------------------------------------------------------------------
    def _registry_snapshot(self) -> str | None:
        try:
            report = self.db.quality_report()
        except Exception:
            report = {}
        generated = report.get("generated_at") or self.db.dataset_manifest().get("generated_at")
        if not generated:
            return None
        return str(generated)[:10]

    def _envelope(
        self,
        data: Any,
        *,
        request_id: str | None = None,
        page: dict[str, Any] | None = None,
        provenance: list[dict[str, Any]] | None = None,
        quality_status: str = "verified",
        flags: Iterable[str] = (),
        warnings: Iterable[str] = (),
        retrieved_at: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        meta_payload: dict[str, Any] = {
            "request_id": request_id or _request_id(),
            "registry_snapshot": self._registry_snapshot(),
            "dataset_version": self.bundle.dataset_version,
            "registry_version": self.bundle.registry_version,
            "retrieved_at": retrieved_at,
            "generated_at": _now(),
        }
        if page is not None:
            meta_payload["page"] = page
        if meta:
            meta_payload.update(meta)
        quality_payload: dict[str, Any] = {
            "status": quality_status,
            "flags": _dedupe(flag for flag in flags if flag != "ok"),
        }
        unique_warnings = _dedupe(warnings)
        if unique_warnings:
            quality_payload["warnings"] = unique_warnings
        return {
            "data": data,
            "meta": meta_payload,
            "provenance": provenance or [],
            "quality": quality_payload,
        }

    def _dataset_quality_status(self, dataset: dict[str, Any], use: str) -> str:
        state = dataset["use_states"][use]
        if state == "metadata_only":
            has_table = any(
                reference.get("kind") == "nasa_psi_file"
                and "experimental table" in str(reference.get("file_name", "")).lower()
                for reference in dataset.get("source_references", [])
            )
            return "experimental_table_only" if has_table else "not_available"
        return SERVING_TO_QUALITY[state]

    def _serving_quality(
        self,
        dataset_id: str,
        use: str,
    ) -> tuple[str, list[str], list[str]]:
        decision = self.serving.evaluate_dataset(dataset_id, use)
        status = SERVING_TO_QUALITY[decision.state]
        if decision.state == "metadata_only":
            dataset = self.serving.get_dataset(dataset_id)
            status = self._dataset_quality_status(dataset, use)
        flags = [reason["code"] for reason in decision.reasons]
        warnings = [reason["message"] for reason in decision.reasons]
        warnings.extend(decision.restrictions)
        return status, flags, warnings

    def _measurement_quality(
        self,
        measurement_id: str,
        use: str,
    ) -> tuple[str, list[str], list[str]]:
        decision = self.serving.evaluate_measurement(measurement_id, use)
        status = SERVING_TO_QUALITY[decision.state]
        flags = [reason["code"] for reason in decision.reasons]
        warnings = [reason["message"] for reason in decision.reasons]
        warnings.extend(decision.restrictions)
        return status, flags, warnings

    def _row_provenance(self, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in rows:
            source_file = row.get("source_file")
            if not source_file:
                continue
            key = (
                row.get("accession"),
                source_file,
                row.get("source_sheet"),
                row.get("source_sha256"),
                row.get("retrieved_at"),
                row.get("source_url"),
            )
            entry = groups.setdefault(
                key,
                {
                    "accession": row.get("accession"),
                    "file": source_file,
                    "sheet": row.get("source_sheet"),
                    "rows": [],
                    "sha256": row.get("source_sha256"),
                    "retrieved_at": row.get("retrieved_at"),
                    "source_url": row.get("source_url"),
                },
            )
            source_row = row.get("source_row")
            if source_row is not None and source_row not in entry["rows"]:
                entry["rows"].append(int(source_row))
        result = []
        for entry in groups.values():
            entry["rows"].sort()
            citation = self.citations.for_file(
                str(entry.get("accession")), str(entry.get("file"))
            )
            if citation is not None:
                entry["citation_id"] = citation["citation_id"]
                entry["row_citation_ids"] = [
                    row_citation_id(
                        str(entry.get("accession")),
                        str(entry.get("file")),
                        entry.get("sheet"),
                        int(row),
                    )
                    for row in entry["rows"]
                ]
            result.append(entry)
        return sorted(result, key=lambda item: (str(item.get("accession")), str(item.get("file"))))

    def _attach_row_citations(self, rows: Iterable[dict[str, Any]]) -> None:
        for row in rows:
            accession = row.get("accession")
            source_file = row.get("source_file")
            source_row = row.get("source_row")
            if not accession or not source_file or source_row is None:
                continue
            row["citation_id"] = row_citation_id(
                str(accession),
                str(source_file),
                row.get("source_sheet"),
                int(source_row),
            )

    def _run_provenance(
        self,
        run: dict[str, Any],
        *,
        row_range: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]:
        entry = {
            "accession": run.get("accession"),
            "file": run.get("source_file"),
            "sheet": run.get("source_sheet"),
            "rows": [],
            "sha256": run.get("sha256"),
            "retrieved_at": run.get("retrieved_at"),
            "source_url": run.get("source_url"),
        }
        if row_range and len(row_range) == 2 and all(value is not None for value in row_range):
            entry["row_range"] = [int(row_range[0]), int(row_range[1])]
        citation = self.citations.for_file(
            str(entry.get("accession")), str(entry.get("file"))
        )
        if citation is not None:
            entry["citation_id"] = citation["citation_id"]
        return [entry]

    def _registry_provenance(self, references: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return [dict(reference) for reference in references]

    def _measurement_summary(self, measurement: dict[str, Any]) -> dict[str, Any]:
        state = self.serving.get_measurement_state(measurement["measurement_id"])
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
            "compatible_datasets": measurement.get("compatible_datasets", []),
            "incompatible_datasets": measurement.get("incompatible_datasets", []),
            "quality_restrictions": measurement.get("quality_restrictions", []),
            "serving_state": state["serving_state"],
            "use_states": state["use_states"],
        }

    def _dataset_summary(self, dataset: dict[str, Any]) -> dict[str, Any]:
        return {
            "dataset_id": dataset["dataset_id"],
            "accession": dataset["accession"],
            "display_name": dataset["display_name"],
            "experiment_family": dataset["experiment_family"],
            "canonical_tables": dataset["canonical_tables"],
            "download_status": dataset["download_status"],
            "measurement_file_status": dataset["measurement_file_status"],
            "access_scope": dataset.get("access_scope"),
            "base_state": dataset["base_state"],
            "use_states": dataset["use_states"],
            "measurement_count": dataset.get("measurement_count", 0),
            "reasons": dataset["reasons"],
            "restrictions": dataset["restrictions"],
            "source_references": dataset["source_references"],
        }

    def _page(self, result: PageResult) -> dict[str, Any]:
        return result.page()

    # ------------------------------------------------------------------
    # Health and metadata
    # ------------------------------------------------------------------
    def health(self, request_id: str | None = None) -> dict[str, Any]:
        health = self.db.health()
        status = health["database"]
        degraded = status == "degraded"
        unavailable = status == "unavailable"
        data = {
            "status": status,
            "api_version": "v1",
            "registry_snapshot": self._registry_snapshot(),
            "dataset_version": self.bundle.dataset_version,
            "registry_version": self.bundle.registry_version,
            "database": health["database"],
            "assistant": "disabled",
            "available_tables": health["available_tables"],
            "missing_tables": health["missing_tables"],
        }
        flags: list[str] = []
        if unavailable:
            flags.append("dataset_unavailable")
        elif degraded:
            flags.append("missing_canonical_tables")
        return self._envelope(
            data,
            request_id=request_id,
            quality_status="blocked" if unavailable else ("partial" if degraded else "verified"),
            flags=flags,
        )

    def meta(self, request_id: str | None = None) -> dict[str, Any]:
        counts = self.db.table_counts()
        investigations = self.db.list_investigations(limit=1)
        datasets = []
        for dataset in self.serving.list_datasets():
            datasets.append(
                {
                    "dataset_id": dataset["dataset_id"],
                    "accession": dataset["accession"],
                    "display_name": dataset["display_name"],
                    "base_state": dataset["base_state"],
                    "use_states": dataset["use_states"],
                    "measurement_count": dataset.get("measurement_count", 0),
                }
            )
        data = {
            "api_version": "v1",
            "registry_snapshot": self._registry_snapshot(),
            "dataset_version": self.bundle.dataset_version,
            "registry_version": self.bundle.registry_version,
            "canonical_tables": counts,
            "canonical_rows": sum(counts.values()),
            "investigations_total": investigations.total,
            "curated_dataset_count": len(datasets),
            "measurement_count": len(self.comparability.measurements),
            "comparison_rule_count": len(self.comparability.rules),
            "datasets": datasets,
        }
        return self._envelope(data, request_id=request_id)

    # ------------------------------------------------------------------
    # Investigations
    # ------------------------------------------------------------------
    def list_investigations(
        self,
        *,
        role: str | None = None,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        page = self.db.list_investigations(
            role=role, query=query, limit=limit, offset=offset
        )
        return self._envelope(
            page.items,
            request_id=request_id,
            page=self._page(page),
            quality_status="verified",
        )

    def get_investigation(self, accession: str, request_id: str | None = None) -> dict[str, Any]:
        investigation = self.db.get_investigation(accession)
        curated = [
            self._dataset_summary(dataset)
            for dataset in self.serving.datasets.values()
            if dataset["accession"] == accession
        ]
        data = {**investigation, "curated_datasets": curated}
        return self._envelope(
            data,
            request_id=request_id,
            provenance=[
                {
                    "kind": "nasa_psi_investigation",
                    "accession": accession,
                    "title": investigation.get("title"),
                    "doi": investigation.get("doi"),
                }
            ],
        )

    # ------------------------------------------------------------------
    # Datasets and quality
    # ------------------------------------------------------------------
    def list_datasets(
        self,
        *,
        family: str | None = None,
        accession: str | None = None,
        state: str | None = None,
        use: str = "exploration",
        limit: int = 50,
        offset: int = 0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        datasets = self.serving.list_datasets(
            family=family, accession=accession, state=state, use=use
        )
        total = len(datasets)
        page_items = datasets[offset : offset + limit]
        items = []
        flags: list[str] = []
        warnings: list[str] = []
        for dataset in page_items:
            status, dataset_flags, dataset_warnings = self._serving_quality(
                dataset["dataset_id"], use
            )
            flags.extend(dataset_flags)
            warnings.extend(dataset_warnings)
            item = self._dataset_summary(dataset)
            item["serving"] = self.serving.evaluate_dataset(dataset["dataset_id"], use).to_dict()
            item["quality_status"] = status
            items.append(item)
        return self._envelope(
            items,
            request_id=request_id,
            page={
                "limit": limit,
                "offset": offset,
                "total": total,
                "has_more": offset + len(items) < total,
                "use": use,
            },
            quality_status="partial" if any(flag != "use_available" for flag in flags) else "verified",
            flags=flags,
            warnings=warnings,
        )

    def get_dataset(self, dataset_id: str, request_id: str | None = None) -> dict[str, Any]:
        dataset = self.serving.get_dataset(dataset_id)
        measurements = [
            self._measurement_summary(measurement)
            for measurement in self.comparability.measurements.values()
            if measurement["dataset_id"] == dataset_id
        ]
        data = {
            **self._dataset_summary(dataset),
            "serving": {
                use: self.serving.evaluate_dataset(dataset_id, use).to_dict()
                for use in ("exploration", "quantitative_comparison", "time_series", "provenance")
            },
            "measurements": sorted(measurements, key=lambda item: item["measurement_id"]),
        }
        status, flags, warnings = self._serving_quality(dataset_id, "exploration")
        return self._envelope(
            data,
            request_id=request_id,
            provenance=self._registry_provenance(dataset["source_references"]),
            quality_status=status,
            flags=flags,
            warnings=warnings,
        )

    def list_dataset_quality(self, request_id: str | None = None) -> dict[str, Any]:
        items = []
        flags: list[str] = []
        warnings: list[str] = []
        for dataset in self.serving.list_datasets():
            status, dataset_flags, dataset_warnings = self._serving_quality(
                dataset["dataset_id"], "exploration"
            )
            quality = self.db.dataset_quality(
                dataset["canonical_tables"], accession=dataset["accession"]
            )
            items.append(
                {
                    "dataset_id": dataset["dataset_id"],
                    "accession": dataset["accession"],
                    "display_name": dataset["display_name"],
                    "quality_status": status,
                    "base_state": dataset["base_state"],
                    "use_states": dataset["use_states"],
                    "report_summary": quality["summary"],
                    "issues": quality["issues"],
                }
            )
            flags.extend(dataset_flags)
            warnings.extend(dataset_warnings)
        return self._envelope(
            items,
            request_id=request_id,
            quality_status="partial",
            flags=flags,
            warnings=warnings,
        )

    def get_dataset_quality(self, dataset_id: str, request_id: str | None = None) -> dict[str, Any]:
        dataset = self.serving.get_dataset(dataset_id)
        quality = self.db.dataset_quality(
            dataset["canonical_tables"], accession=dataset["accession"]
        )
        serving = {
            use: self.serving.evaluate_dataset(dataset_id, use).to_dict()
            for use in ("exploration", "quantitative_comparison", "time_series", "provenance")
        }
        status, flags, warnings = self._serving_quality(dataset_id, "exploration")
        data = {
            "dataset_id": dataset_id,
            "accession": dataset["accession"],
            "display_name": dataset["display_name"],
            "quality_status": status,
            "serving": serving,
            "report": quality,
        }
        issue_flags = [issue.get("code") for issue in quality["issues"]]
        return self._envelope(
            data,
            request_id=request_id,
            provenance=self._registry_provenance(dataset["source_references"]),
            quality_status=status,
            flags=[*flags, *issue_flags],
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Measurements
    # ------------------------------------------------------------------
    def list_measurements(
        self,
        *,
        accession: str | None = None,
        family: str | None = None,
        dataset_id: str | None = None,
        comparison_status: str | None = None,
        serving_state: str | None = None,
        use: str = "exploration",
        limit: int = 50,
        offset: int = 0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        measurements = self.comparability.list_measurements(
            accession=accession,
            family=family,
            dataset_id=dataset_id,
            status=comparison_status,
        )
        items = []
        for measurement in measurements:
            summary = self._measurement_summary(measurement)
            if serving_state and summary["use_states"][use] != serving_state:
                continue
            items.append(summary)
        total = len(items)
        page_items = items[offset : offset + limit]
        flags = [
            code
            for item in page_items
            for code in item["quality_restrictions"]
        ]
        return self._envelope(
            page_items,
            request_id=request_id,
            page={
                "limit": limit,
                "offset": offset,
                "total": total,
                "has_more": offset + len(page_items) < total,
                "use": use,
            },
            quality_status="partial" if flags else "verified",
            flags=flags,
        )

    def get_measurement(
        self,
        measurement_id: str,
        *,
        use: str = "exploration",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        measurement = self.comparability.get_measurement(measurement_id)
        decision = self.serving.evaluate_measurement(measurement_id, use)
        dataset = self.serving.get_dataset(measurement["dataset_id"])
        rules = [
            {
                "rule_id": rule["rule_id"],
                "left_measurement_id": rule["left_measurement_id"],
                "right_measurement_id": rule["right_measurement_id"],
                "status": rule["status"],
                "scientific_justification": rule["scientific_justification"],
            }
            for rule in self.comparability.list_rules(measurement_id=measurement_id)
        ]
        data = {
            **measurement,
            "serving": decision.to_dict(),
            "dataset": self._dataset_summary(dataset),
            "rules": rules,
        }
        status = SERVING_TO_QUALITY[decision.state]
        return self._envelope(
            data,
            request_id=request_id,
            provenance=self._registry_provenance(measurement["source_references"]),
            quality_status=status,
            flags=[reason["code"] for reason in decision.reasons],
            warnings=[reason["message"] for reason in decision.reasons],
        )

    # ------------------------------------------------------------------
    # Comparability
    # ------------------------------------------------------------------
    def comparability_summary(self, request_id: str | None = None) -> dict[str, Any]:
        summary = self.comparability.summary()
        measurements = [
            self._measurement_summary(measurement)
            for measurement in self.comparability.measurements.values()
        ]
        rules = sorted(self.comparability.rules.values(), key=lambda item: item["rule_id"])
        concepts: dict[str, dict[str, Any]] = {}
        for measurement in measurements:
            concept = concepts.setdefault(
                measurement["physical_quantity"],
                {
                    "physical_quantity": measurement["physical_quantity"],
                    "units": set(),
                    "dataset_ids": set(),
                    "measurement_ids": [],
                    "comparison_statuses": {},
                },
            )
            concept["units"].add(measurement["unit"])
            concept["dataset_ids"].add(measurement["dataset_id"])
            concept["measurement_ids"].append(measurement["measurement_id"])
            concept["comparison_statuses"][measurement["comparison_status"]] = (
                concept["comparison_statuses"].get(measurement["comparison_status"], 0) + 1
            )
        concept_items = []
        for concept in sorted(concepts.values(), key=lambda item: item["physical_quantity"]):
            concept_items.append(
                {
                    "physical_quantity": concept["physical_quantity"],
                    "units": sorted(concept["units"]),
                    "dataset_ids": sorted(concept["dataset_ids"]),
                    "measurement_ids": sorted(concept["measurement_ids"]),
                    "comparison_statuses": concept["comparison_statuses"],
                }
            )
        data = {
            **summary,
            "concepts": concept_items,
            "measurements": sorted(measurements, key=lambda item: item["measurement_id"]),
            "rules": rules,
        }
        return self._envelope(
            data,
            request_id=request_id,
            provenance=_dedupe_dicts(
                [
                    reference
                    for measurement in self.comparability.measurements.values()
                    for reference in measurement.get("source_references", [])
                ],
                ("kind", "accession", "file_name", "path", "section"),
            ),
        )

    def compare(
        self,
        left: str,
        right: str,
        *,
        conditions: Mapping[str, bool | None] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        decision = self.comparability.evaluate(left, right, conditions)
        status = COMPARABILITY_TO_QUALITY[decision.status]
        flags = [reason["code"] for reason in decision.reasons]
        warnings = list(decision.warnings)
        integrity = self.integrity.check_decision(decision)
        paired_values = evaluate_paired_values(
            decision, registry=self.paired, conditions=conditions
        )
        if integrity["status"] == "failed":
            status = "blocked"
            flags.append("measurement_unavailable")
            warnings.extend(integrity["messages"])
            if decision.status == "comparable":
                paired_values = {
                    **paired_values,
                    "available": False,
                    "status": "unavailable",
                    "reason": {
                        "code": "measurement_unavailable",
                        "message": (
                            "The registry approves this comparison, but at least one "
                            "requested measurement has no values in the canonical "
                            "data. No paired values are returned."
                        ),
                        "decision_status": decision.status,
                        "failures": integrity["failures"],
                    },
                }
        data = {
            **decision.to_dict(),
            "integrity": integrity,
            "paired_values": paired_values,
        }
        return self._envelope(
            data,
            request_id=request_id,
            provenance=decision.source_references,
            quality_status=status,
            flags=_dedupe(flags),
            warnings=_dedupe(warnings),
            meta={
                "left": left,
                "right": right,
                "paired_values_available": paired_values["available"],
                "integrity_status": integrity["status"],
            },
        )

    # ------------------------------------------------------------------
    # Citations
    # ------------------------------------------------------------------
    def list_citations(
        self,
        *,
        accession: str | None = None,
        dataset_id: str | None = None,
        kind: str | None = None,
        verification_status: str | None = None,
        availability: str | None = None,
        limit: int = 50,
        offset: int = 0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if dataset_id:
            self.serving.get_dataset(dataset_id)
        citations = self.citations.list(
            accession=accession,
            dataset_id=dataset_id,
            kind=kind,
            verification_status=verification_status,
            availability=availability,
        )
        total = len(citations)
        page_items = citations[offset : offset + limit]
        flags = []
        warnings = []
        for citation in page_items:
            if citation["verification"]["status"] != "verified":
                flags.append("citation_" + citation["verification"]["status"])
            if citation["availability"]["status"] == "unavailable":
                warnings.append(citation["availability"].get("reason") or "Source unavailable.")
        return self._envelope(
            page_items,
            request_id=request_id,
            page={
                "limit": limit,
                "offset": offset,
                "total": total,
                "has_more": offset + len(page_items) < total,
            },
            provenance=[
                {
                    "kind": "citation_registry",
                    "path": "data/registry/download_manifest.json",
                    "section": "files",
                }
            ],
            quality_status="partial" if flags else "verified",
            flags=flags,
            warnings=warnings,
        )

    def _row_citation(self, citation_id: str) -> dict[str, Any]:
        locator = decode_row_citation_id(citation_id)
        record = self.db.resolve_provenance(
            locator["accession"],
            locator["file"],
            sheet=locator["sheet"],
            row=locator["row"],
        )
        file_citation = self.citations.for_file(locator["accession"], locator["file"])
        verification_status = "verified"
        checks = ["canonical_row_located"]
        if record.get("row_verified") is not True:
            verification_status = "unverified"
            checks.append("row_not_found_in_canonical_tables")
        if file_citation is None:
            verification_status = "partial" if verification_status == "verified" else verification_status
            checks.append("file_not_in_curated_manifest")
        elif file_citation["verification"]["status"] != "verified":
            if verification_status == "verified":
                verification_status = "partial"
            checks.append("file_checksum_not_verified")
        if record.get("warnings"):
            checks.extend(record["warnings"])
            if verification_status == "verified":
                verification_status = "partial"
        source = (
            file_citation["source"]
            if file_citation is not None
            else {
                "kind": "nasa_psi_file",
                "accession": record["accession"],
                "file_name": record["file"],
                "sha256": record.get("sha256"),
                "source_url": record.get("source_url"),
            }
        )
        retrieval = (
            file_citation["retrieval"]
            if file_citation is not None
            else {
                "retrieved_at": record.get("retrieved_at"),
                "http_status": None,
                "download_status": "not_in_manifest",
                "bytes": record.get("bytes"),
                "expected_bytes": None,
                "checksum_expected": None,
                "checksum_actual": record.get("sha256"),
                "checksum_match": None,
            }
        )
        return {
            "citation_id": citation_id,
            "kind": "row",
            "accession": record["accession"],
            "dataset_ids": file_citation.get("dataset_ids", []) if file_citation else [],
            "file": (
                file_citation["file"]
                if file_citation is not None
                else {
                    "name": record["file"],
                    "kind": None,
                    "manifest_dataset": None,
                    "priority": None,
                    "purpose": None,
                    "in_added": None,
                }
            ),
            "locator": {
                "type": "row",
                "sheet": record.get("sheet"),
                "row": record.get("row"),
                "row_range": [record["row"], record["row"]],
            },
            "source": source,
            "retrieval": retrieval,
            "verification": {"status": verification_status, "checks": checks},
            "availability": (
                file_citation["availability"]
                if file_citation is not None
                else {
                    "status": "available",
                    "downloadable": False,
                    "reason": "Row provenance is available, but the file is not in the curated manifest.",
                }
            ),
            "row_verification": {
                "row_verified": record.get("row_verified"),
                "row_tables": record.get("row_tables", []),
                "warnings": record.get("warnings", []),
            },
            "provenance": [
                {
                    "kind": "nasa_psi_file",
                    "accession": record["accession"],
                    "file": record["file"],
                    "sheet": record.get("sheet"),
                    "rows": [record["row"]],
                    "sha256": record.get("sha256"),
                    "retrieved_at": record.get("retrieved_at"),
                    "source_url": record.get("source_url"),
                }
            ],
        }

    def get_citation(
        self, citation_id: str, request_id: str | None = None
    ) -> dict[str, Any]:
        if citation_id.startswith("cit_r_"):
            citation = self._row_citation(citation_id)
        elif citation_id.startswith("cit_f_"):
            citation = self.citations.get(citation_id)
        else:
            raise NotFoundError(
                "citation identifier is not recognized",
                details={"citation_id": citation_id},
            )
        status = citation["verification"]["status"]
        quality_status = "verified" if status == "verified" else "partial"
        if citation["availability"]["status"] == "unavailable":
            quality_status = "blocked"
        return self._envelope(
            citation,
            request_id=request_id,
            provenance=citation.get("provenance", []),
            quality_status=quality_status,
            flags=[] if status == "verified" else ["citation_" + status],
            warnings=(
                [citation["availability"]["reason"]]
                if citation["availability"].get("reason")
                else []
            ),
        )

    # ------------------------------------------------------------------
    # Dataset files, fields, and limitations
    # ------------------------------------------------------------------
    def list_dataset_files(
        self,
        dataset_id: str,
        *,
        kind: str | None = None,
        availability: str | None = None,
        limit: int = 50,
        offset: int = 0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        data = self.metadata.list_files(
            dataset_id,
            kind=kind,
            availability=availability,
            limit=limit,
            offset=offset,
        )
        flags = []
        warnings = []
        if data["summary"]["unavailable_files"]:
            flags.append("source_file_unavailable")
            warnings.append(
                "At least one curated source file is unavailable; it is not downloadable."
            )
        if any(
            item["download"]["status"] == "known_unavailable"
            for item in data["files"]
        ):
            flags.append("known_unavailable_http_404")
        return self._envelope(
            data,
            request_id=request_id,
            provenance=[
                {
                    "kind": "download_manifest",
                    "path": "data/registry/download_manifest.json",
                    "section": "files",
                },
                {
                    "kind": "acquisition_report",
                    "path": "data/reports/acquisition_report.json",
                    "section": "results",
                },
            ],
            quality_status="partial" if flags else "verified",
            flags=flags,
            warnings=warnings,
        )

    def list_dataset_fields(
        self,
        dataset_id: str,
        *,
        value_kind: str | None = None,
        physical_quantity: str | None = None,
        comparison_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        data = self.metadata.list_fields(
            dataset_id,
            value_kind=value_kind,
            physical_quantity=physical_quantity,
            comparison_status=comparison_status,
            limit=limit,
            offset=offset,
        )
        flags = [
            restriction
            for field in data["fields"]
            for restriction in field["flags"]
        ]
        return self._envelope(
            data,
            request_id=request_id,
            provenance=[
                {
                    "kind": "comparability_registry",
                    "path": "data/metadata/comparability_registry.json",
                    "section": "measurements",
                },
                {
                    "kind": "serving_registry",
                    "path": "data/metadata/serving_registry.json",
                    "section": "measurement_states",
                },
            ],
            quality_status="partial" if flags else "verified",
            flags=flags,
        )

    def list_dataset_limitations(
        self,
        dataset_id: str,
        *,
        scope: str | None = None,
        category: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        data = self.metadata.list_limitations(
            dataset_id,
            scope=scope,
            category=category,
            severity=severity,
            status=status,
            limit=limit,
            offset=offset,
        )
        flags = [item["code"] for item in data["limitations"]]
        warnings = [
            item["explanation"]
            for item in data["limitations"]
            if item["severity"] == "error"
        ]
        return self._envelope(
            data,
            request_id=request_id,
            provenance=[
                {
                    "kind": "serving_registry",
                    "path": "data/metadata/serving_registry.json",
                    "section": "datasets, measurement_states",
                },
                {
                    "kind": "quality_report",
                    "path": "data/reports/dataset_quality_report.json",
                    "section": "issues",
                },
            ],
            quality_status="blocked" if warnings else "partial",
            flags=flags,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Publications
    # ------------------------------------------------------------------
    def list_publications(
        self,
        *,
        accession: str | None = None,
        dataset_id: str | None = None,
        query: str | None = None,
        year: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if dataset_id:
            dataset = self.serving.get_dataset(dataset_id)
            dataset_accession = dataset["accession"]
            if accession and accession != dataset_accession:
                raise InvalidQueryError(
                    "accession and dataset_id refer to different investigations",
                    details={
                        "accession": accession,
                        "dataset_id": dataset_id,
                        "dataset_accession": dataset_accession,
                    },
                )
            accession = dataset_accession
        data = self.publications.list(
            accession=accession,
            query=query,
            year=year,
            status=status,
            limit=limit,
            offset=offset,
        )
        return self._envelope(
            data,
            request_id=request_id,
            page=data["page"],
            provenance=[
                {
                    "kind": "psi_investigation_registry",
                    "path": "data/registry/psi_combustion_investigations.json",
                    "section": "investigations[].publications",
                }
            ],
            quality_status="partial",
            flags=["year_not_available", "venue_not_available"],
            warnings=[
                "Publication year and venue are not present in the NASA PSI registry and are returned as unavailable."
            ],
            meta={"accession": accession, "dataset_id": dataset_id},
        )

    def get_publication(
        self, publication_id: str, request_id: str | None = None
    ) -> dict[str, Any]:
        publication = self.publications.get(publication_id)
        return self._envelope(
            publication,
            request_id=request_id,
            provenance=publication["source_references"],
            quality_status="partial",
            flags=["year_not_available", "venue_not_available"],
            warnings=[
                "Publication year and venue are not present in the NASA PSI registry and are returned as unavailable."
            ],
        )

    # ------------------------------------------------------------------
    # Gas-flame facets
    # ------------------------------------------------------------------
    def gas_flame_facets(
        self,
        *,
        accession: str | None = None,
        include_qualified: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        rows = self.db.gas_flame_facet_rows(accession)
        data = build_gas_flame_facets(rows, include_qualified=include_qualified)
        accessions = [item["accession"] for item in data["accessions"]]
        status = "verified"
        flags: list[str] = []
        warnings = list(data["notes"])
        for row_accession in accessions:
            dataset_id = next(
                (
                    dataset["dataset_id"]
                    for dataset in self.serving.datasets.values()
                    if dataset["accession"] == row_accession
                ),
                None,
            )
            if dataset_id is None:
                continue
            dataset_status, dataset_flags, dataset_warnings = self._serving_quality(
                dataset_id, "exploration"
            )
            if dataset_status == "blocked":
                status = "blocked"
            elif dataset_status != "verified" and status == "verified":
                status = "partial"
            flags.extend(dataset_flags)
            warnings.extend(dataset_warnings)
        return self._envelope(
            data,
            request_id=request_id,
            provenance=[
                {
                    "kind": "canonical_table",
                    "table": "gas_flame_test",
                    "dataset_version": self.bundle.dataset_version,
                }
            ],
            quality_status=status,
            flags=flags,
            warnings=warnings,
            meta={"accession": accession, "include_qualified": include_qualified},
        )

    # ------------------------------------------------------------------
    # Deterministic statistics
    # ------------------------------------------------------------------
    def gas_flame_statistics(
        self,
        accession: str,
        *,
        include_qualified: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        stats = self.db.gas_flame_statistics(
            accession, include_qualified=include_qualified
        )
        dataset = next(
            (
                item
                for item in self.serving.datasets.values()
                if item["accession"] == accession
            ),
            None,
        )
        dataset_id = dataset["dataset_id"] if dataset else None
        status, flags, warnings = (
            self._serving_quality(dataset_id, "exploration")
            if dataset_id
            else ("partial", [], [])
        )
        measurements = {
            measurement["canonical_field"]: measurement
            for measurement in self.comparability.measurements.values()
            if measurement["dataset_id"] == dataset_id
        }
        for field, payload in stats["fields"].items():
            measurement = measurements.get(field)
            if measurement is None:
                fallback = field_metadata(accession, field)
                payload["measurement_id"] = None
                payload["unit"] = fallback["unit"] if fallback else None
                payload["value_kind"] = fallback["value_kind"] if fallback else None
                payload["comparison_status"] = None
                payload["serving_state"] = None
                payload["metadata_source"] = fallback["source"] if fallback else None
                continue
            serving = self.serving.evaluate_measurement(
                measurement["measurement_id"], "exploration"
            )
            payload["measurement_id"] = measurement["measurement_id"]
            payload["unit"] = measurement["unit"]
            payload["value_kind"] = measurement["value_kind"]
            payload["comparison_status"] = measurement["comparison_status"]
            payload["serving_state"] = serving.state
            payload["metadata_source"] = {
                "kind": "comparability_registry",
                "path": "data/metadata/comparability_registry.json",
                "section": "measurements",
            }
        citations = (
            self.citations.list(dataset_id=dataset_id, kind="experimental_table")
            if dataset_id
            else []
        )
        stats["dataset_id"] = dataset_id
        stats["citation_ids"] = [
            citation["citation_id"] for citation in citations
        ]
        stats["source_files"] = [
            citation["file"]["name"] for citation in citations
        ]
        stats["quality_status"] = status
        stats["warnings"] = warnings
        return self._envelope(
            stats,
            request_id=request_id,
            provenance=[
                {
                    "kind": "canonical_table",
                    "table": "gas_flame_test",
                    "dataset_version": self.bundle.dataset_version,
                }
            ],
            quality_status=status,
            flags=flags,
            warnings=warnings,
            meta={"accession": accession, "include_qualified": include_qualified},
        )

    def dataset_field_statistics(
        self,
        dataset_id: str,
        *,
        fields: Sequence[str] | None = None,
        include_qualified: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        dataset = self.serving.get_dataset(dataset_id)
        tables = list(dataset.get("canonical_tables") or [])
        aggregate_tables = [
            table for table in tables if table in AGGREGATE_TABLES
        ]
        if not aggregate_tables:
            raise InvalidQueryError(
                "this dataset does not support canonical field statistics",
                details={
                    "dataset_id": dataset_id,
                    "canonical_tables": tables,
                    "allowed_tables": list(AGGREGATE_TABLES),
                    "suggestion": (
                        "Use the telemetry or smoke series tools for time-series "
                        "datasets, or the dataset metadata endpoints for "
                        "metadata-only datasets."
                    ),
                },
            )
        table = aggregate_tables[0]
        accession = dataset["accession"]
        stats = self.db.field_statistics(
            table,
            accession,
            fields,
            include_qualified=include_qualified,
        )
        measurements = {
            measurement["canonical_field"]: measurement
            for measurement in self.comparability.measurements.values()
            if measurement["dataset_id"] == dataset_id
        }
        for field, payload in stats["fields"].items():
            measurement = measurements.get(field)
            if measurement is None:
                fallback = field_metadata(accession, field)
                payload["measurement_id"] = None
                payload["unit"] = fallback["unit"] if fallback else None
                payload["value_kind"] = fallback["value_kind"] if fallback else None
                payload["comparison_status"] = None
                payload["serving_state"] = None
                payload["quality_restrictions"] = []
                payload["metadata_source"] = fallback["source"] if fallback else None
                continue
            serving = self.serving.evaluate_measurement(
                measurement["measurement_id"], "exploration"
            )
            payload["measurement_id"] = measurement["measurement_id"]
            payload["unit"] = measurement["unit"]
            payload["value_kind"] = measurement["value_kind"]
            payload["comparison_status"] = measurement["comparison_status"]
            payload["serving_state"] = serving.state
            payload["quality_restrictions"] = list(
                measurement.get("quality_restrictions") or []
            )
            payload["metadata_source"] = {
                "kind": "comparability_registry",
                "path": "data/metadata/comparability_registry.json",
                "section": "measurements",
            }
        citations = self.citations.list(
            dataset_id=dataset_id, kind="experimental_table"
        )
        status, flags, warnings = self._serving_quality(
            dataset_id, "exploration"
        )
        stats["dataset_id"] = dataset_id
        stats["display_name"] = dataset["display_name"]
        stats["citation_ids"] = [
            citation["citation_id"] for citation in citations
        ]
        stats["source_files"] = [
            citation["file"]["name"] for citation in citations
        ]
        stats["quality_status"] = status
        stats["warnings"] = warnings
        return self._envelope(
            stats,
            request_id=request_id,
            provenance=[
                {
                    "kind": "canonical_table",
                    "table": table,
                    "dataset_version": self.bundle.dataset_version,
                }
            ],
            quality_status=status,
            flags=flags,
            warnings=warnings,
            meta={
                "dataset_id": dataset_id,
                "accession": accession,
                "include_qualified": include_qualified,
            },
        )

    # ------------------------------------------------------------------
    # Gas-flame tests
    # ------------------------------------------------------------------
    def list_gas_flame_tests(
        self,
        *,
        accession: str | None = None,
        flame_type: str | None = None,
        fuel: str | None = None,
        oxygen_min: float | None = None,
        oxygen_max: float | None = None,
        pressure_min: float | None = None,
        pressure_max: float | None = None,
        hot_ignition: str | None = None,
        extinction_mode: str | None = None,
        tfp: str | None = None,
        include_qualified: bool = False,
        sort: str = "source_row",
        order: str = "asc",
        limit: int = 50,
        offset: int = 0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        page = self.db.list_gas_flame_tests(
            accession=accession,
            flame_type=flame_type,
            fuel=fuel,
            oxygen_min=oxygen_min,
            oxygen_max=oxygen_max,
            pressure_min=pressure_min,
            pressure_max=pressure_max,
            hot_ignition=hot_ignition,
            extinction_mode=extinction_mode,
            tfp=tfp,
            include_qualified=include_qualified,
            sort=sort,
            order=order,
            limit=limit,
            offset=offset,
        )
        self._attach_row_citations(page.items)
        flags: list[str] = []
        warnings: list[str] = []
        for row in page.items:
            flags.extend(
                item.get("flag", "") for item in row.get("quality_flags", []) if isinstance(item, dict)
            )
        accessions = {row["accession"] for row in page.items} or (
            {accession} if accession else set()
        )
        quality_status = "verified"
        for row_accession in accessions:
            dataset_id = next(
                (
                    dataset["dataset_id"]
                    for dataset in self.serving.datasets.values()
                    if dataset["accession"] == row_accession
                ),
                None,
            )
            if dataset_id is None:
                continue
            status, dataset_flags, dataset_warnings = self._serving_quality(
                dataset_id, "exploration"
            )
            if status == "blocked":
                quality_status = "blocked"
            elif status != "verified" and quality_status == "verified":
                quality_status = "partial"
            flags.extend(dataset_flags)
            warnings.extend(dataset_warnings)
        warnings.append("Tad and Zst are computed by the source, not measured.")
        return self._envelope(
            page.items,
            request_id=request_id,
            page=self._page(page),
            provenance=self._row_provenance(page.items),
            quality_status=quality_status,
            flags=flags,
            warnings=warnings,
        )

    def get_gas_flame_test(self, observation_id: str, request_id: str | None = None) -> dict[str, Any]:
        row = self.db.get_gas_flame_test(observation_id)
        self._attach_row_citations([row])
        dataset_id = next(
            (
                dataset["dataset_id"]
                for dataset in self.serving.datasets.values()
                if dataset["accession"] == row["accession"]
            ),
            None,
        )
        flags = [
            item.get("flag", "")
            for item in row.get("quality_flags", [])
            if isinstance(item, dict)
        ]
        warnings = ["Tad and Zst are computed by the source, not measured."]
        status = "verified"
        if dataset_id:
            status, dataset_flags, dataset_warnings = self._serving_quality(
                dataset_id, "exploration"
            )
            flags.extend(dataset_flags)
            warnings.extend(dataset_warnings)
        return self._envelope(
            row,
            request_id=request_id,
            provenance=self._row_provenance([row]),
            quality_status=status,
            flags=flags,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Material and droplet tests
    # ------------------------------------------------------------------
    def list_material_tests(
        self,
        *,
        accession: str | None = None,
        material: str | None = None,
        flow_restrictor: str | None = None,
        o2_min: float | None = None,
        o2_max: float | None = None,
        limit: int = 50,
        offset: int = 0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        page = self.db.list_material_tests(
            accession=accession,
            material=material,
            flow_restrictor=flow_restrictor,
            o2_min=o2_min,
            o2_max=o2_max,
            limit=limit,
            offset=offset,
        )
        self._attach_row_citations(page.items)
        flags: list[str] = []
        warnings = [
            "No flame-spread rate is available in these test matrices.",
            "Material labels are free text and have not been normalized.",
        ]
        for row in page.items:
            flags.extend(
                item.get("flag", "") for item in row.get("quality_flags", []) if isinstance(item, dict)
            )
        accessions = {row["accession"] for row in page.items} or (
            {accession} if accession else set()
        )
        quality_status = "verified"
        for row_accession in accessions:
            dataset_id = next(
                (
                    dataset["dataset_id"]
                    for dataset in self.serving.datasets.values()
                    if dataset["accession"] == row_accession
                ),
                None,
            )
            if dataset_id is None:
                continue
            status, dataset_flags, dataset_warnings = self._serving_quality(
                dataset_id, "exploration"
            )
            if status == "blocked":
                quality_status = "blocked"
            elif status != "verified" and quality_status == "verified":
                quality_status = "partial"
            flags.extend(dataset_flags)
            warnings.extend(dataset_warnings)
        if page.extra.get("o2_unit_note"):
            warnings.append(page.extra["o2_unit_note"])
        return self._envelope(
            page.items,
            request_id=request_id,
            page=self._page(page),
            provenance=self._row_provenance(page.items),
            quality_status=quality_status,
            flags=flags,
            warnings=warnings,
        )

    def list_droplet_tests(
        self,
        *,
        accession: str = "PSI-69",
        fuel: str | None = None,
        pressure_min: float | None = None,
        pressure_max: float | None = None,
        limit: int = 50,
        offset: int = 0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        page = self.db.list_droplet_tests(
            accession=accession,
            fuel=fuel,
            pressure_min=pressure_min,
            pressure_max=pressure_max,
            limit=limit,
            offset=offset,
        )
        self._attach_row_citations(page.items)
        flags: list[str] = []
        warnings = [
            "The 'Burning rate; mm' column is labeled mm, not mm/s, and is not a validated rate.",
            "Droplet measurements are not comparable with gas-flame or material-spread measurements.",
        ]
        for row in page.items:
            flags.extend(
                item.get("flag", "") for item in row.get("quality_flags", []) if isinstance(item, dict)
            )
        dataset_id = next(
            (
                dataset["dataset_id"]
                for dataset in self.serving.datasets.values()
                if dataset["accession"] == accession
            ),
            None,
        )
        status = "verified"
        if dataset_id:
            status, dataset_flags, dataset_warnings = self._serving_quality(
                dataset_id, "exploration"
            )
            flags.extend(dataset_flags)
            warnings.extend(dataset_warnings)
        return self._envelope(
            page.items,
            request_id=request_id,
            page=self._page(page),
            provenance=self._row_provenance(page.items),
            quality_status=status,
            flags=flags,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------
    def list_telemetry_runs(
        self,
        *,
        accession: str = "PSI-100",
        export_kind: str | None = None,
        limit: int = 50,
        offset: int = 0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        page = self.db.list_telemetry_runs(
            accession=accession, export_kind=export_kind, limit=limit, offset=offset
        )
        status, flags, warnings = self._serving_quality(
            "psi-100-telemetry", "time_series"
        )
        return self._envelope(
            page.items,
            request_id=request_id,
            page=self._page(page),
            provenance=[self._run_provenance(row)[0] for row in page.items],
            quality_status=status,
            flags=flags,
            warnings=warnings,
        )

    def get_telemetry_run(self, run_id: str, request_id: str | None = None) -> dict[str, Any]:
        run = self.db.get_telemetry_run(run_id)
        status, flags, warnings = self._serving_quality(
            "psi-100-telemetry", "time_series"
        )
        return self._envelope(
            run,
            request_id=request_id,
            provenance=self._run_provenance(run),
            quality_status=status,
            flags=flags,
            warnings=warnings,
        )

    def get_telemetry_series(
        self,
        run_id: str,
        channels: str | Sequence[str] | None,
        start_ms: float | None,
        end_ms: float | None,
        *,
        max_points: int = 5000,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        series = self.db.get_telemetry_series(
            run_id, channels, start_ms, end_ms, max_points=max_points
        )
        run = self.db.get_telemetry_run(run_id)
        status, flags, warnings = self._serving_quality(
            "psi-100-telemetry", "time_series"
        )
        for channel in series["channels"]:
            flags.extend(channel["quality_flags"])
        provenance = self._run_provenance(
            run,
            row_range=series.pop("source_row_range", None),
        )
        return self._envelope(
            series,
            request_id=request_id,
            provenance=provenance,
            quality_status=status,
            flags=flags,
            warnings=warnings,
            retrieved_at=run.get("retrieved_at"),
            meta={
                "returned_points": series["returned_points"],
                "excluded_sentinel_rows": series["excluded_sentinel_rows"],
                "time_unit": series["time_unit"],
            },
        )

    # ------------------------------------------------------------------
    # Smoke
    # ------------------------------------------------------------------
    def list_smoke_runs(
        self,
        *,
        accession: str = "PSI-101",
        limit: int = 50,
        offset: int = 0,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        page = self.db.list_smoke_runs(
            accession=accession, limit=limit, offset=offset
        )
        status, flags, warnings = self._serving_quality(
            "psi-101-smoke", "time_series"
        )
        return self._envelope(
            page.items,
            request_id=request_id,
            page=self._page(page),
            provenance=[self._run_provenance(row)[0] for row in page.items],
            quality_status=status,
            flags=flags,
            warnings=warnings,
        )

    def get_smoke_run(self, run_id: str, request_id: str | None = None) -> dict[str, Any]:
        run = self.db.get_smoke_run(run_id)
        status, flags, warnings = self._serving_quality(
            "psi-101-smoke", "time_series"
        )
        return self._envelope(
            run,
            request_id=request_id,
            provenance=self._run_provenance(run),
            quality_status=status,
            flags=flags,
            warnings=warnings,
        )

    def get_smoke_series(
        self,
        run_id: str,
        channels: str | Sequence[str] | None,
        start_s: float | None,
        end_s: float | None,
        *,
        max_points: int = 5000,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        series = self.db.get_smoke_series(
            run_id, channels, start_s, end_s, max_points=max_points
        )
        run = self.db.get_smoke_run(run_id)
        status, flags, warnings = self._serving_quality(
            "psi-101-smoke", "time_series"
        )
        for channel in series["channels"]:
            flags.extend(channel["quality_flags"])
        provenance = self._run_provenance(
            run,
            row_range=series.pop("source_row_range", None),
        )
        return self._envelope(
            series,
            request_id=request_id,
            provenance=provenance,
            quality_status=status,
            flags=flags,
            warnings=warnings,
            retrieved_at=run.get("retrieved_at"),
            meta={
                "returned_points": series["returned_points"],
                "excluded_sentinel_rows": series["excluded_sentinel_rows"],
                "excluded_invalid_rows": series["excluded_invalid_rows"],
                "time_unit": series["time_unit"],
            },
        )

    # ------------------------------------------------------------------
    # Provenance
    # ------------------------------------------------------------------
    def resolve_provenance(
        self,
        accession: str,
        file_name: str,
        *,
        sheet: str | None = None,
        row: int | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        record = self.db.resolve_provenance(
            accession, file_name, sheet=sheet, row=row
        )
        if row is not None:
            record["citation_id"] = row_citation_id(accession, file_name, sheet, row)
        else:
            citation = self.citations.for_file(accession, file_name)
            if citation is not None:
                record["citation_id"] = citation["citation_id"]
        flags = list(record.get("warnings", []))
        file_citation = self.citations.for_file(accession, file_name)
        provenance_entry = {
            "accession": record["accession"],
            "file": record["file"],
            "sheet": record.get("sheet"),
            "rows": [row] if row is not None else [],
            "sha256": record.get("sha256"),
            "retrieved_at": record.get("retrieved_at"),
            "source_url": record.get("source_url"),
            "citation_id": record.get("citation_id"),
        }
        if file_citation is not None:
            provenance_entry["file_citation_id"] = file_citation["citation_id"]
        if row is not None:
            provenance_entry["row_citation_ids"] = [record["citation_id"]]
        return self._envelope(
            record,
            request_id=request_id,
            provenance=[provenance_entry],
            quality_status="partial" if flags else "verified",
            flags=flags,
            retrieved_at=record.get("retrieved_at"),
        )
