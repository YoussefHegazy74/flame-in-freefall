"""Deterministic answer composition for the Phase 5 assistant.

The composer is the only component that writes prose. It reads structured
deterministic tool results, formats numbers directly from those results, and
attaches every factual or numerical claim to the tool call that produced it.
Retrieved documents are exposed as untrusted evidence items and are never used
as a numerical source.

An optional provider may rephrase the completed draft later, but it cannot add
claims, numbers, citations, or limitations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from src.assistant.contract import (
    AnswerType,
    Claim,
    ClaimType,
    ClarificationRequest,
    Confidence,
    EvidenceItem,
    EvidenceSourceType,
    EvidenceStatus,
    Limitation,
    Severity,
    SupportingData,
    ToolStatus,
    ValueKind,
)
from src.assistant.planner import Plan, PlannedCall
from src.assistant.tools import ToolRegistry, ToolResult

RECORD_COUNT_UNIT = "rows"
MAX_QUOTED_SNIPPET = 500
MAX_CITATIONS_PER_RESULT = 4
MAX_CITATIONS = 16

LIMITATION_MESSAGES: dict[str, str] = {
    "catalog_scope_curated": (
        "The catalog covers registered investigations and the nine curated "
        "datasets; it does not ingest every public archive file."
    ),
    "pressure_unit_mismatch": (
        "Pressure fields use different units across datasets; no silent "
        "conversion or field merging is performed."
    ),
    "fuel_labels_not_cross_mapped": (
        "Fuel labels are not cross-mapped between PSI-10 and PSI-159."
    ),
    "computed_tad_zst": (
        "Tad and Zst are computed by the source and are never relabeled as "
        "measured values."
    ),
    "summary_table_only": (
        "The source is an experimental summary table, not a telemetry series."
    ),
    "telemetry_404": (
        "The PSI-98 raw-data telemetry workbooks return HTTP 404 and are not "
        "available."
    ),
    "runs_are_separate": (
        "Telemetry and smoke runs are separate exports and are never "
        "concatenated."
    ),
    "ramped_condition_rows": (
        "Qualified ramped rows are excluded from default aggregation."
    ),
    "undefined_tfp": "The TFP flag is not defined by the source.",
    "unexpanded_xf": "The Xf field is not expanded by the source.",
    "measurement_has_no_canonical_values": (
        "The measurement has no non-null canonical values; missing is not zero."
    ),
    "blank_means_missing": "Blank source cells are missing values, not zeros.",
    "method_not_documented": (
        "The measurement method or calibration is not documented in the "
        "verified artifacts."
    ),
    "do_not_merge_celsius_kelvin": (
        "Celsius and Kelvin temperature columns are separate and are never "
        "merged."
    ),
    "raw_not_calibrated": (
        "Raw detector channels are uncalibrated and are not physical "
        "measurements."
    ),
    "no_verified_alignment": (
        "No verified paired-alignment method is registered."
    ),
    "comparison_not_approved": (
        "The comparison is not approved for quantitative use."
    ),
    "conditions_not_verified": (
        "Required comparison conditions have not been verified."
    ),
    "measurement_unavailable": (
        "At least one measurement has no canonical values."
    ),
    "missing_not_zero": "Missing values are never treated as zero.",
    "conversion_not_authorized": (
        "No approved unit-conversion rule exists for this comparison."
    ),
    "publication_not_in_registry": (
        "The publication registry is the only source of verified publication "
        "records."
    ),
    "year_not_available": "Publication year is unavailable in the registry.",
    "venue_not_available": "Publication venue is unavailable in the registry.",
    "no_fire_risk_model": (
        "No validated fire-risk model, material ranking, or spacecraft "
        "fire-safety guarantee exists in the verified artifacts."
    ),
    "ambiguous_unit": (
        "The oxygen unit is ambiguous: the header says percent while the "
        "observed values are fraction-like."
    ),
    "filesystem_access_blocked": (
        "The assistant has no filesystem tool and never exposes local files or "
        "environment variables."
    ),
    "prompt_injection_blocked": (
        "Retrieved text is untrusted evidence, never an instruction."
    ),
    "no_flame_spread_rate": (
        "No published flame-spread-rate table or validated method is present "
        "in the verified artifacts."
    ),
    "sentinel_values": (
        "Sentinel values such as -999 are not measurements and are preserved "
        "as missing."
    ),
    "metadata_only": (
        "Only metadata and the experimental summary table are available."
    ),
    "unavailable_not_downloadable": (
        "Unavailable files are never presented as downloadable."
    ),
    "retrieval_context_only": (
        "Retrieved documentation explains context; it is not a numerical "
        "source."
    ),
    "tool_unavailable": (
        "A required deterministic tool did not return usable evidence."
    ),
    "validation_failed": (
        "The application withheld the answer because citation or claim "
        "validation failed."
    ),
    "provider_fallback": (
        "A configured language provider was unavailable or produced a "
        "rejected rephrase, so the validated deterministic answer is shown."
    ),
    "clarification_required": (
        "The question needs one bounded clarification before any tool is run."
    ),
    "assistant_disabled": (
        "The assistant is disabled by configuration on this deployment."
    ),
    "internal_error": (
        "The assistant could not complete the request safely and withheld the "
        "draft."
    ),
}


@dataclass
class DraftAnswer:
    answer: str
    evidence_status: EvidenceStatus
    answer_type: AnswerType
    confidence: Confidence = Confidence.low
    confidence_basis: str = ""
    citation_ids: list[str] = field(default_factory=list)
    supporting_data: list[SupportingData] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    limitations: list[Limitation] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)
    clarification: ClarificationRequest | None = None


def _value_kind(value: Any, fallback: ValueKind = ValueKind.not_applicable) -> ValueKind:
    if isinstance(value, ValueKind):
        return value
    try:
        return ValueKind(str(value))
    except ValueError:
        return fallback


def _fmt(value: Any, unit: str | None = None) -> str:
    text = str(value)
    return f"{text} {unit}" if unit else text


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


class Composer:
    """Execute an approved plan and build a deterministic grounded draft."""

    def __init__(
        self,
        service: Any,
        registry: ToolRegistry,
        *,
        request_id: str,
    ):
        self.service = service
        self.registry = registry
        self.request_id = request_id
        self._extra_results: list[ToolResult] = []
        self._supporting: list[SupportingData] = []
        self._claims: list[Claim] = []
        self._limitations: list[Limitation] = []
        self._claim_index = 0
        self._support_index = 0

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def compose(self, plan: Plan) -> DraftAnswer:
        if plan.topic == "clarification":
            return self._clarification(plan)

        results: list[ToolResult] = []
        for call in plan.calls:
            results.append(self.registry.execute(call.tool, call.arguments))

        if plan.retrieval_query:
            results.append(
                self.registry.execute(
                    "search_scientific_documents",
                    {
                        "query": plan.retrieval_query,
                        **(
                            {"accession": plan.retrieval_accession}
                            if plan.retrieval_accession
                            else {}
                        ),
                        **(
                            {"dataset_id": plan.retrieval_dataset_id}
                            if plan.retrieval_dataset_id
                            else {}
                        ),
                        "limit": 4,
                    },
                )
            )

        handler = getattr(self, f"_compose_{plan.topic}", None)
        if handler is None:
            draft = self._compose_retrieval_overview(plan, results)
        else:
            draft = handler(plan, results)

        return self._finalize(plan, draft, results)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _last(self, results: Sequence[ToolResult], tool: str) -> ToolResult | None:
        for result in reversed(results):
            if result.tool == tool:
                return result
        return None

    def _all(self, results: Sequence[ToolResult], tool: str) -> list[ToolResult]:
        return [result for result in results if result.tool == tool]

    def _call(self, tool: str, **arguments: Any) -> ToolResult:
        result = self.registry.execute(tool, arguments)
        self._extra_results.append(result)
        return result

    def _usable(self, result: ToolResult | None) -> bool:
        return result is not None and result.status in {ToolStatus.ok, ToolStatus.empty}

    def _failure(self, plan: Plan, detail: str | None = None) -> DraftAnswer:
        message = LIMITATION_MESSAGES["tool_unavailable"]
        return DraftAnswer(
            answer=(
                "I could not complete this request from the verified artifacts. "
                + (detail or message)
                + " No numerical estimate or citation was substituted."
            ),
            evidence_status=EvidenceStatus.insufficient_evidence,
            answer_type=plan.answer_type,
            confidence=Confidence.low,
            confidence_basis="A required deterministic tool did not return usable evidence.",
            limitations=[self._limitation("tool_unavailable", message)],
        )

    def _limitation(
        self,
        code: str,
        message: str | None = None,
        *,
        scope: str | None = None,
        severity: Severity = Severity.warning,
        citation_ids: Sequence[str] = (),
    ) -> Limitation:
        return Limitation(
            code=code,
            message=message or LIMITATION_MESSAGES.get(code, code.replace("_", " ")),
            scope=scope,
            severity=severity,
            citation_ids=list(dict.fromkeys(citation_ids)),
        )

    def _add_limitation(self, limitation: Limitation) -> None:
        if not any(
            item.code == limitation.code and item.message == limitation.message
            for item in self._limitations
        ):
            self._limitations.append(limitation)

    def _add_limitations_from_tool(
        self,
        result: ToolResult,
        *,
        codes: Sequence[str] | None = None,
        limit: int = 6,
    ) -> None:
        rows = (result.data or {}).get("limitations") or []
        for row in rows:
            code = row.get("code")
            if not isinstance(code, str):
                continue
            if codes is not None and code not in codes:
                continue
            self._add_limitation(
                self._limitation(
                    code,
                    row.get("explanation") or LIMITATION_MESSAGES.get(code),
                    scope=row.get("scope"),
                    severity=Severity(row.get("severity", "warning"))
                    if row.get("severity") in {"error", "warning", "info"}
                    else Severity.warning,
                    citation_ids=result.citation_ids[:4],
                )
            )
            limit -= 1
            if limit <= 0:
                break

    def _support(
        self,
        result: ToolResult,
        label: str,
        *,
        value_kind: ValueKind,
        unit: str | None,
        values: Mapping[str, Any],
        dataset_id: str | None = None,
        accession: str | None = None,
        citation_ids: Sequence[str] = (),
    ) -> SupportingData:
        self._support_index += 1
        item = SupportingData(
            data_id=f"data_{self._support_index}",
            tool_call_id=result.call_id,
            label=label,
            value_kind=value_kind,
            unit=unit,
            dataset_id=dataset_id or result.dataset_id,
            accession=accession or result.accession,
            summary=result.summary[:500],
            values=dict(values),
            citation_ids=list(dict.fromkeys(citation_ids or result.citation_ids)),
        )
        self._supporting.append(item)
        return item

    def _field(self, result: ToolResult, name: str) -> dict[str, Any] | None:
        data = result.data or {}
        fields = data.get("fields")
        if isinstance(fields, dict) and isinstance(fields.get(name), dict):
            return fields[name]
        values = (result.values or {}).get("fields")
        if isinstance(values, dict) and isinstance(values.get(name), dict):
            return values[name]
        return None

    def _support_field(
        self,
        result: ToolResult,
        name: str,
        *,
        label: str | None = None,
        dataset_id: str | None = None,
        accession: str | None = None,
    ) -> SupportingData | None:
        payload = self._field(result, name)
        if payload is None:
            return None
        values = {
            key: payload.get(key)
            for key in ("status", "non_null_count", "missing_count", "min", "max", "mean", "median")
            if payload.get(key) is not None
        }
        return self._support(
            result,
            label or f"{name} summary",
            value_kind=_value_kind(payload.get("value_kind")),
            unit=payload.get("unit"),
            values=values,
            dataset_id=dataset_id,
            accession=accession,
        )

    def _support_counts(
        self,
        result: ToolResult,
        keys: Sequence[str],
        *,
        label: str,
        unit: str = RECORD_COUNT_UNIT,
        dataset_id: str | None = None,
        accession: str | None = None,
    ) -> SupportingData:
        data = result.data or {}
        values = {key: data.get(key) for key in keys if data.get(key) is not None}
        return self._support(
            result,
            label,
            value_kind=ValueKind.derived,
            unit=unit,
            values=values,
            dataset_id=dataset_id,
            accession=accession,
        )

    def _claim(
        self,
        text: str,
        claim_type: ClaimType,
        *,
        result: ToolResult | None = None,
        value: float | int | str | None = None,
        unit: str | None = None,
        value_kind: ValueKind | None = None,
        dataset_id: str | None = None,
        accession: str | None = None,
        citation_ids: Sequence[str] = (),
    ) -> Claim:
        self._claim_index += 1
        claim = Claim(
            claim_id=f"claim_{self._claim_index}",
            text=text,
            claim_type=claim_type,
            value=value,
            unit=unit,
            value_kind=value_kind,
            dataset_id=dataset_id or (result.dataset_id if result else None),
            accession=accession or (result.accession if result else None),
            tool_call_id=result.call_id if result else None,
            citation_ids=list(
                dict.fromkeys(
                    citation_ids
                    or (result.citation_ids[:3] if result is not None else ())
                )
            ),
            supported=False,
        )
        self._claims.append(claim)
        return claim

    def _numeric_claim(
        self,
        text: str,
        value: Any,
        unit: str | None,
        value_kind: ValueKind,
        result: ToolResult,
        *,
        dataset_id: str | None = None,
        accession: str | None = None,
    ) -> Claim | None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        return self._claim(
            text,
            ClaimType.numerical,
            result=result,
            value=value,
            unit=unit,
            value_kind=value_kind,
            dataset_id=dataset_id,
            accession=accession,
        )

    def _claim_field_stat(
        self,
        text: str,
        result: ToolResult,
        field: str,
        key: str,
        *,
        unit_override: str | None = None,
        value_kind_override: ValueKind | None = None,
    ) -> Claim | None:
        payload = self._field(result, field)
        if payload is None:
            return None
        value = payload.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        return self._numeric_claim(
            text,
            value,
            unit_override if unit_override is not None else payload.get("unit"),
            value_kind_override or _value_kind(payload.get("value_kind")),
            result,
        )

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------
    def _finalize(
        self,
        plan: Plan,
        draft: DraftAnswer,
        results: list[ToolResult],
    ) -> DraftAnswer:
        all_results = list(results) + list(self._extra_results)

        citation_ids: list[str] = []
        for result in all_results:
            citation_ids.extend(result.citation_ids[:MAX_CITATIONS_PER_RESULT])
        citation_ids.extend(draft.citation_ids)
        for claim in self._claims:
            citation_ids.extend(claim.citation_ids)
        for item in self._supporting:
            citation_ids.extend(item.citation_ids)
        citation_ids = _unique(citation_ids)[:MAX_CITATIONS]

        for code in plan.expected_limitation_codes:
            if not any(limitation.code == code for limitation in self._limitations):
                relevant_citations: list[str] = []
                for result in all_results:
                    if plan.accession and result.accession == plan.accession:
                        relevant_citations.extend(result.citation_ids[:MAX_CITATIONS_PER_RESULT])
                    elif plan.dataset_id and result.dataset_id == plan.dataset_id:
                        relevant_citations.extend(result.citation_ids[:MAX_CITATIONS_PER_RESULT])
                if not relevant_citations:
                    for result in all_results:
                        relevant_citations.extend(result.citation_ids[:MAX_CITATIONS_PER_RESULT])
                self._add_limitation(
                    self._limitation(
                        code,
                        citation_ids=relevant_citations[:4],
                    )
                )

        # Keep every nested citation reference inside the answer-level set.
        allowed_citations = set(citation_ids)
        for claim in self._claims:
            claim.citation_ids = [
                citation_id
                for citation_id in claim.citation_ids
                if citation_id in allowed_citations
            ]
        for item in self._supporting:
            item.citation_ids = [
                citation_id
                for citation_id in item.citation_ids
                if citation_id in allowed_citations
            ]
        for limitation in self._limitations:
            limitation.citation_ids = [
                citation_id
                for citation_id in limitation.citation_ids
                if citation_id in allowed_citations
            ]

        if draft.evidence_status == EvidenceStatus.fully_supported:
            confidence = Confidence.high
        elif draft.evidence_status == EvidenceStatus.partially_supported:
            confidence = Confidence.moderate
        else:
            confidence = Confidence.low
        if draft.confidence_basis:
            basis = draft.confidence_basis
        elif draft.evidence_status == EvidenceStatus.fully_supported:
            basis = (
                "Every claim is linked to a deterministic tool result and every "
                "citation resolved through the Phase 4 registry."
            )
        elif draft.evidence_status == EvidenceStatus.partially_supported:
            basis = (
                "The answer is limited to deterministic tool output; documented "
                "serving or comparison restrictions prevent a stronger claim."
            )
        else:
            basis = (
                "The verified artifacts do not support the requested claim, so "
                "the answer states the limitation instead of estimating."
            )

        evidence: list[EvidenceItem] = []
        for result in all_results:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{result.call_id}",
                    source_type=EvidenceSourceType.tool_result,
                    title=result.label or result.tool,
                    snippet=result.summary[:MAX_QUOTED_SNIPPET],
                    dataset_id=result.dataset_id,
                    accession=result.accession,
                    content_hash=result.result_hash,
                )
            )
            for chunk in (result.data or {}).get("results") or []:
                source_type = self._evidence_source_type(chunk.get("source_type"))
                citation_id = chunk.get("citation_id")
                if not citation_id:
                    citations = chunk.get("citation_ids") or []
                    citation_id = citations[0] if citations else None
                if citation_id not in allowed_citations:
                    citation_id = None
                evidence.append(
                    EvidenceItem(
                        evidence_id=f"ev_{result.call_id}_{chunk.get('chunk_id', len(evidence))}",
                        source_type=source_type,
                        title=str(
                            chunk.get("source_reference")
                            or chunk.get("section")
                            or chunk.get("document_id")
                            or "verified retrieval chunk"
                        ),
                        snippet=str(chunk.get("content") or "")[:MAX_QUOTED_SNIPPET],
                        document_id=chunk.get("document_id"),
                        source_reference=chunk.get("source_reference"),
                        accession=chunk.get("accession"),
                        dataset_id=chunk.get("dataset_id"),
                        citation_id=citation_id,
                        section=chunk.get("section"),
                        content_hash=chunk.get("content_hash"),
                        index_version=chunk.get("index_version"),
                    )
                )

        return DraftAnswer(
            answer=draft.answer,
            evidence_status=draft.evidence_status,
            answer_type=draft.answer_type,
            confidence=confidence,
            confidence_basis=basis,
            citation_ids=citation_ids,
            supporting_data=self._supporting,
            claims=self._claims,
            limitations=self._limitations,
            evidence=evidence,
            clarification=draft.clarification,
        )

    def _evidence_source_type(self, value: Any) -> EvidenceSourceType:
        return {
            "document": EvidenceSourceType.document,
            "dataset": EvidenceSourceType.dataset_card,
            "investigation": EvidenceSourceType.investigation,
            "publication": EvidenceSourceType.publication,
            "limitation": EvidenceSourceType.document,
            "field": EvidenceSourceType.document,
            "file": EvidenceSourceType.citation,
        }.get(str(value), EvidenceSourceType.document)

    def _clarification(self, plan: Plan) -> DraftAnswer:
        return DraftAnswer(
            answer=plan.clarification_question or "Please clarify the requested scope.",
            evidence_status=EvidenceStatus.insufficient_evidence,
            answer_type=AnswerType.clarification_required,
            confidence=Confidence.low,
            confidence_basis="No verified tool was run because the scope is ambiguous.",
            limitations=[
                self._limitation("clarification_required"),
            ],
            clarification=ClarificationRequest(
                question=plan.clarification_question
                or "Please clarify the requested scope.",
                options=list(plan.clarification_options),
                missing=list(plan.clarification_missing),
            ),
        )

    # ------------------------------------------------------------------
    # Catalog and dataset topics
    # ------------------------------------------------------------------
    def _compose_investigation_catalog(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        investigations = self._last(results, "search_investigations")
        datasets = self._last(results, "search_datasets")
        if not self._usable(investigations) or not self._usable(datasets):
            return self._failure(plan)
        rows = (investigations.data or {}).get("investigations") or []
        total = int((investigations.values or {}).get("total") or len(rows))
        dataset_rows = (datasets.data or {}).get("datasets") or []
        dataset_total = int((datasets.values or {}).get("total") or len(dataset_rows))

        lines = [
            f"The verified catalog contains {total} NASA PSI investigations.",
            "",
            "Registered investigations:",
        ]
        for row in rows:
            accession = row.get("accession")
            acronym = row.get("acronym") or row.get("title") or ""
            lines.append(f"- {accession}: {acronym}")
        lines.extend(
            [
                "",
                (
                    f"The platform has {dataset_total} curated datasets with "
                    "canonical measurement tables or metadata-only records."
                ),
                (
                    "The catalog is a curated evidence layer, not a complete "
                    "ingestion of every public NASA archive file."
                ),
            ]
        )
        self._support_counts(
            investigations,
            ["total"],
            label="investigation catalog count",
            unit="investigations",
        )
        self._numeric_claim(
            f"The verified catalog contains {total} investigations.",
            total,
            "investigations",
            ValueKind.derived,
            investigations,
        )
        self._claim(
            f"The platform exposes {dataset_total} curated datasets.",
            ClaimType.factual,
            result=datasets,
            citation_ids=datasets.citation_ids[:3],
        )
        return DraftAnswer(
            answer="\n".join(lines),
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.factual,
            citation_ids=list(datasets.citation_ids),
        )

    def _compose_psi10_experiments(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        investigation = self._last(results, "get_investigation")
        dataset = self._last(results, "get_dataset")
        fields = self._last(results, "get_dataset_fields")
        limitations = self._last(results, "get_dataset_limitations")
        if not self._usable(investigation) or not self._usable(dataset):
            return self._failure(plan)
        inv = investigation.data or {}
        ds = dataset.data or {}
        field_rows = (fields.data or {}).get("fields") if fields else []
        measured = [row["canonical_name"] for row in field_rows if row.get("value_kind") == "measured"]
        computed = [row["canonical_name"] for row in field_rows if row.get("value_kind") == "computed"]
        categorical = [row["canonical_name"] for row in field_rows if row.get("value_kind") == "categorical"]
        measurement_count = int((dataset.values or {}).get("measurement_count") or 0)

        lines = [
            f"{inv.get('accession')} — {inv.get('title')}.",
            "",
            str(inv.get("rationale") or "").strip(),
            "",
            (
                f"The curated dataset is {ds.get('display_name')} "
                f"({ds.get('dataset_id')}), an experimental summary table with "
                f"{measurement_count} registered measurement definitions."
            ),
        ]
        if field_rows:
            lines.append("")
            if measured:
                lines.append("Measured fields: " + ", ".join(measured) + ".")
            if computed:
                lines.append("Source-computed fields: " + ", ".join(computed) + ".")
            if categorical:
                lines.append("Categorical fields: " + ", ".join(categorical) + ".")
        lines.append(
            "Tad and Zst are computed by the source; they are never relabeled "
            "as measured temperatures or mixture fractions."
        )
        if limitations:
            self._add_limitations_from_tool(
                limitations,
                codes=(
                    "computed_tad_zst",
                    "summary_table_only",
                    "missing_final_state",
                    "ramped_condition_rows",
                ),
            )
        self._numeric_claim(
            f"The dataset has {measurement_count} registered measurement definitions.",
            measurement_count,
            "measurements",
            ValueKind.derived,
            dataset,
        )
        return DraftAnswer(
            answer="\n".join(line for line in lines if line),
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.factual,
            citation_ids=list(
                dict.fromkeys(
                    list(dataset.citation_ids)
                    + (list(fields.citation_ids) if fields else [])
                    + (list(limitations.citation_ids) if limitations else [])
                )
            ),
        )

    def _compose_telemetry_datasets(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        telemetry = self._last(results, "search_datasets")
        smoke = None
        for candidate in self._all(results, "search_datasets"):
            families = {
                row.get("experiment_family")
                for row in (candidate.data or {}).get("datasets") or []
            }
            if "smoke" in families:
                smoke = candidate
            elif "telemetry" in families:
                telemetry = candidate
        files = self._last(results, "get_dataset_files")
        if not self._usable(telemetry):
            return self._failure(plan)
        telemetry_rows = (telemetry.data or {}).get("datasets") or []
        smoke_rows = (smoke.data or {}).get("datasets") or [] if smoke else []
        telemetry_ids = [row.get("dataset_id") for row in telemetry_rows]
        smoke_ids = [row.get("dataset_id") for row in smoke_rows]

        lines = [
            "Curated datasets with time-series telemetry:",
            "- PSI-100 SAFFIRE-III: telemetry exports with radiometer, anemometer, "
            "pressure, smoke-detector, body-rate, and acceleration channels.",
        ]
        if smoke_ids:
            lines.append(
                "- PSI-101 SAME-R: smoke and aerosol telemetry across separate "
                "housekeeping exports."
            )
        if files and self._usable(files):
            summary = (files.data or {}).get("summary") or {}
            unavailable = int(summary.get("unavailable_files") or 0)
            lines.extend(
                [
                    "",
                    (
                        "PSI-98 SAFFIRE-I is metadata-only. Its experimental "
                        "summary table is available, but "
                        f"{unavailable} raw telemetry workbooks return HTTP 404 "
                        "and are not downloadable."
                    ),
                ]
            )
            self._numeric_claim(
                f"PSI-98 has {unavailable} unavailable raw telemetry workbooks.",
                unavailable,
                "files",
                ValueKind.derived,
                files,
            )
        lines.append(
            "Telemetry runs are separate exports and are never concatenated "
            "into one continuous series."
        )
        lines.append(
            "Raw detector channels are uncalibrated unless a verified "
            "calibration record says otherwise."
        )
        if files and self._usable(files):
            self._add_limitations_from_tool(files, codes=("known_unavailable_http_404",))
        return DraftAnswer(
            answer="\n".join(lines),
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.factual,
            citation_ids=list(
                dict.fromkeys(
                    list(telemetry.citation_ids)
                    + (list(smoke.citation_ids) if smoke else [])
                    + (list(files.citation_ids) if files else [])
                )
            ),
        )

    def _compose_gas_flame_difference(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        stats = self._all(results, "gas_flame_statistics")
        s10 = next((item for item in stats if item.accession == "PSI-10"), None)
        s159 = next((item for item in stats if item.accession == "PSI-159"), None)
        limitations = self._last(results, "get_dataset_limitations")
        if not self._usable(s10) or not self._usable(s159):
            return self._failure(plan)
        d10 = s10.data or {}
        d159 = s159.data or {}
        p10 = self._field(s10, "pressure_initial_atm") or {}
        p159 = self._field(s159, "pressure_approx_bar") or {}

        lines = [
            "The two curated gas-flame datasets are not directly poolable.",
            "",
            (
                f"PSI-10 ACME Flame Design has {d10.get('canonical_rows')} canonical "
                f"rows: {d10.get('included_rows')} included and "
                f"{d10.get('excluded_qualified_rows')} qualified rows excluded by "
                "default. Its pressure field is pressure_initial_atm in atm."
            ),
            (
                f"PSI-159 ACME CFI-G has {d159.get('canonical_rows')} canonical "
                f"rows: {d159.get('included_rows')} included and "
                f"{d159.get('excluded_qualified_rows')} qualified rows excluded by "
                "default. Its populated pressure field is pressure_approx_bar in bar."
            ),
            "",
            (
                "The pressure fields are different measurements with different "
                "units and are not converted or merged. Fuel labels are also not "
                "cross-mapped without an explicit chemistry mapping."
            ),
        ]
        for result, accession in ((s10, "PSI-10"), (s159, "PSI-159")):
            self._support_counts(
                result,
                ["canonical_rows", "included_rows", "excluded_qualified_rows"],
                label=f"{accession} gas-flame record counts",
                dataset_id=result.dataset_id,
                accession=accession,
            )
            for key, label in (
                ("canonical_rows", "canonical"),
                ("included_rows", "included"),
                ("excluded_qualified_rows", "excluded qualified"),
            ):
                value = (result.data or {}).get(key)
                if isinstance(value, int):
                    self._numeric_claim(
                        f"{accession} has {value} {label} gas-flame rows.",
                        value,
                        "rows",
                        ValueKind.derived,
                        result,
                        accession=accession,
                    )
        if limitations and self._usable(limitations):
            self._add_limitations_from_tool(
                limitations,
                codes=("serving_restriction_c7602992", "missing_final_state"),
            )
        lines.append(
            f"PSI-10 pressure_initial_atm is recorded in {p10.get('unit')}; "
            f"PSI-159 pressure_approx_bar is recorded in {p159.get('unit')}."
        )
        return DraftAnswer(
            answer="\n".join(lines),
            evidence_status=EvidenceStatus.partially_supported,
            answer_type=AnswerType.exploratory,
            citation_ids=list(
                dict.fromkeys(
                    list(s10.citation_ids)
                    + list(s159.citation_ids)
                    + (list(limitations.citation_ids) if limitations else [])
                )
            ),
        )

    def _compose_psi159_contents(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        dataset = self._last(results, "get_dataset")
        stats = self._last(results, "gas_flame_statistics")
        fields = self._last(results, "get_dataset_fields")
        if not self._usable(dataset) or not self._usable(stats):
            return self._failure(plan)
        ds = dataset.data or {}
        data = stats.data or {}
        summary = ((fields.data or {}).get("summary") if fields else {}) or {}
        field_count = int(summary.get("field_count") or 0)
        without_values = int(summary.get("without_canonical_values") or 0)
        value_kinds = summary.get("value_kinds") or {}

        lines = [
            f"{ds.get('display_name')} ({ds.get('dataset_id')}).",
            "",
            (
                f"The canonical gas-flame table has {data.get('canonical_rows')} "
                f"rows, with {data.get('included_rows')} included and "
                f"{data.get('excluded_qualified_rows')} qualified rows excluded by "
                "default."
            ),
        ]
        if field_count:
            lines.append(
                f"The dataset registers {field_count} fields; {without_values} has "
                "no canonical non-null values."
            )
        if value_kinds:
            lines.append(
                "Value kinds: "
                + ", ".join(
                    f"{count} {kind}" for kind, count in sorted(value_kinds.items())
                )
                + "."
            )
        lines.extend(
            [
                "",
                (
                    "The populated pressure quantity is pressure_approx_bar in bar. "
                    "pressure_initial_atm has zero canonical values and is not "
                    "interchangeable with the bar field."
                ),
                (
                    "The TFP flag is not defined by the source, and Xf is preserved "
                    "only as labeled rather than expanded into a derived quantity."
                ),
            ]
        )
        self._support_counts(
            stats,
            ["canonical_rows", "included_rows", "excluded_qualified_rows"],
            label="PSI-159 gas-flame record counts",
            dataset_id="psi-159-gas-flame",
            accession="PSI-159",
        )
        for key, label in (
            ("canonical_rows", "canonical"),
            ("included_rows", "included"),
            ("excluded_qualified_rows", "excluded qualified"),
        ):
            value = data.get(key)
            if isinstance(value, int):
                self._numeric_claim(
                    f"PSI-159 has {value} {label} gas-flame rows.",
                    value,
                    "rows",
                    ValueKind.derived,
                    stats,
                    dataset_id="psi-159-gas-flame",
                    accession="PSI-159",
                )
        if field_count:
            self._numeric_claim(
                f"The dataset registers {field_count} fields.",
                field_count,
                "fields",
                ValueKind.derived,
                fields,
                dataset_id="psi-159-gas-flame",
                accession="PSI-159",
            )
        return DraftAnswer(
            answer="\n".join(lines),
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.factual,
            citation_ids=list(
                dict.fromkeys(
                    list(dataset.citation_ids)
                    + list(stats.citation_ids)
                    + (list(fields.citation_ids) if fields else [])
                )
            ),
        )

    def _compose_psi10_valid_records(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        stats = self._last(results, "gas_flame_statistics")
        if not self._usable(stats):
            return self._failure(plan)
        data = stats.data or {}
        included = data.get("included_rows")
        excluded = data.get("excluded_qualified_rows")
        canonical = data.get("canonical_rows")
        answer = (
            f"PSI-10 has {included} valid included gas-flame records. "
            f"{excluded} qualified rows are excluded by default, and the canonical "
            f"table contains {canonical} rows in total. Qualified RAMP, RAMPED, or "
            "LOW O2 rows are not fixed set points, so they are not counted as valid "
            "unqualified records."
        )
        self._support_counts(
            stats,
            ["canonical_rows", "included_rows", "excluded_qualified_rows"],
            label="PSI-10 gas-flame record counts",
            dataset_id="psi-10-gas-flame",
            accession="PSI-10",
        )
        for key, text in (
            ("included_rows", f"{included} valid included records"),
            ("excluded_qualified_rows", f"{excluded} excluded qualified rows"),
            ("canonical_rows", f"{canonical} canonical rows"),
        ):
            if isinstance(data.get(key), int):
                self._numeric_claim(
                    f"PSI-10 has {text}.",
                    data[key],
                    "rows",
                    ValueKind.derived,
                    stats,
                    dataset_id="psi-10-gas-flame",
                    accession="PSI-10",
                )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.numerical,
            citation_ids=list(stats.citation_ids),
        )

    def _compose_psi159_valid_records(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        stats = self._last(results, "gas_flame_statistics")
        if not self._usable(stats):
            return self._failure(plan)
        data = stats.data or {}
        included = data.get("included_rows")
        excluded = data.get("excluded_qualified_rows")
        canonical = data.get("canonical_rows")
        answer = (
            f"PSI-159 has {included} valid included gas-flame records. "
            f"{excluded} qualified rows are excluded by default, and the canonical "
            f"table contains {canonical} rows in total. The populated pressure field "
            "is pressure_approx_bar in bar; it is not an atm field."
        )
        self._support_counts(
            stats,
            ["canonical_rows", "included_rows", "excluded_qualified_rows"],
            label="PSI-159 gas-flame record counts",
            dataset_id="psi-159-gas-flame",
            accession="PSI-159",
        )
        for key, text in (
            ("included_rows", f"{included} valid included records"),
            ("excluded_qualified_rows", f"{excluded} excluded qualified rows"),
            ("canonical_rows", f"{canonical} canonical rows"),
        ):
            if isinstance(data.get(key), int):
                self._numeric_claim(
                    f"PSI-159 has {text}.",
                    data[key],
                    "rows",
                    ValueKind.derived,
                    stats,
                    dataset_id="psi-159-gas-flame",
                    accession="PSI-159",
                )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.numerical,
            citation_ids=list(stats.citation_ids),
        )

    # ------------------------------------------------------------------
    # Numerical field topics
    # ------------------------------------------------------------------
    def _compose_psi159_pressure_info(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        stats = self._last(results, "dataset_field_statistics")
        gas = self._last(results, "gas_flame_statistics")
        limitations = self._last(results, "get_dataset_limitations")
        if not self._usable(stats):
            return self._failure(plan)
        bar = self._field(stats, "pressure_approx_bar") or {}
        atm = self._field(stats, "pressure_initial_atm") or {}

        lines = [
            (
                "PSI-159 reports pressure in two separate fields. They are not "
                "merged and no conversion is applied."
            ),
            "",
            (
                f"- pressure_approx_bar: {bar.get('non_null_count')} non-null values "
                f"in {bar.get('unit')}, minimum {bar.get('min')}, maximum "
                f"{bar.get('max')}, mean {bar.get('mean')}."
            ),
            (
                f"- pressure_initial_atm: {atm.get('non_null_count')} non-null "
                f"values in {atm.get('unit')}. The {atm.get('missing_count')} "
                "missing rows are missing, not zero."
            ),
        ]
        self._support_field(stats, "pressure_approx_bar", dataset_id="psi-159-gas-flame", accession="PSI-159")
        self._support_field(stats, "pressure_initial_atm", dataset_id="psi-159-gas-flame", accession="PSI-159")
        for field, key, label in (
            ("pressure_approx_bar", "non_null_count", "non-null bar values"),
            ("pressure_approx_bar", "min", "minimum bar pressure"),
            ("pressure_approx_bar", "max", "maximum bar pressure"),
            ("pressure_approx_bar", "mean", "mean bar pressure"),
            ("pressure_initial_atm", "non_null_count", "non-null atm values"),
        ):
            payload = self._field(stats, field) or {}
            value = payload.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                unit = payload.get("unit")
                self._numeric_claim(
                    f"PSI-159 {field} {label} is {_fmt(value, unit)}.",
                    value,
                    unit,
                    _value_kind(payload.get("value_kind")),
                    stats,
                    dataset_id="psi-159-gas-flame",
                    accession="PSI-159",
                )
        if limitations and self._usable(limitations):
            self._add_limitations_from_tool(
                limitations,
                codes=(
                    "measurement_has_no_canonical_values",
                    "undefined_tfp",
                    "unexpanded_xf",
                ),
            )
        return DraftAnswer(
            answer="\n".join(lines),
            evidence_status=EvidenceStatus.partially_supported,
            answer_type=AnswerType.numerical,
            citation_ids=list(
                dict.fromkeys(
                    list(stats.citation_ids)
                    + (list(gas.citation_ids) if gas else [])
                    + (list(limitations.citation_ids) if limitations else [])
                )
            ),
        )

    def _compose_psi10_oxygen(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        stats = self._last(results, "dataset_field_statistics")
        gas = self._last(results, "gas_flame_statistics")
        limitations = self._last(results, "get_dataset_limitations")
        if not self._usable(stats):
            return self._failure(plan)
        final = self._field(stats, "oxygen_mole_fraction") or {}
        initial = self._field(stats, "oxygen_mole_fraction_initial") or {}
        lines = [
            (
                "PSI-10 registers two separate oxygen fields. They are not merged, "
                "and missing values are not zeros."
            ),
            "",
            (
                f"- oxygen_mole_fraction: {final.get('non_null_count')} non-null "
                f"values in {final.get('unit')}, minimum {final.get('min')}, "
                f"maximum {final.get('max')}."
            ),
            (
                f"- oxygen_mole_fraction_initial: {initial.get('non_null_count')} "
                f"non-null values in {initial.get('unit')}, minimum "
                f"{initial.get('min')}, maximum {initial.get('max')}."
            ),
        ]
        self._support_field(stats, "oxygen_mole_fraction", dataset_id="psi-10-gas-flame", accession="PSI-10")
        self._support_field(stats, "oxygen_mole_fraction_initial", dataset_id="psi-10-gas-flame", accession="PSI-10")
        for field, payload in (
            ("oxygen_mole_fraction", final),
            ("oxygen_mole_fraction_initial", initial),
        ):
            for key, label in (
                ("non_null_count", "non-null values"),
                ("min", "minimum"),
                ("max", "maximum"),
            ):
                value = payload.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    self._numeric_claim(
                        f"PSI-10 {field} {label} is {_fmt(value, payload.get('unit'))}.",
                        value,
                        payload.get("unit"),
                        _value_kind(payload.get("value_kind")),
                        stats,
                        dataset_id="psi-10-gas-flame",
                        accession="PSI-10",
                    )
        if limitations and self._usable(limitations):
            self._add_limitations_from_tool(
                limitations,
                codes=("missing_final_state", "ramped_condition_rows"),
            )
        lines.append(
            "Ramped and LOW O2 qualifiers are preserved and excluded from default "
            "aggregation; they are never treated as fixed set points."
        )
        return DraftAnswer(
            answer="\n".join(lines),
            evidence_status=EvidenceStatus.partially_supported,
            answer_type=AnswerType.numerical,
            citation_ids=list(
                dict.fromkeys(
                    list(stats.citation_ids)
                    + (list(gas.citation_ids) if gas else [])
                    + (list(limitations.citation_ids) if limitations else [])
                )
            ),
        )

    def _compose_psi159_peak_temp(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        stats = self._last(results, "dataset_field_statistics")
        limitations = self._last(results, "get_dataset_limitations")
        if not self._usable(stats):
            return self._failure(plan)
        celsius = self._field(stats, "peak_burner_temp_c") or {}
        kelvin = self._field(stats, "peak_burner_temp_k") or {}
        if celsius.get("status") != "available":
            return self._failure(plan, "The requested temperature field has no values.")
        answer = (
            f"The mean measured peak_burner_temp_c in PSI-159 is "
            f"{celsius.get('mean')} {celsius.get('unit')} over "
            f"{celsius.get('non_null_count')} non-null values. The observed range is "
            f"{celsius.get('min')} to {celsius.get('max')} {celsius.get('unit')}. "
            f"{celsius.get('missing_count')} rows are missing and are not zero. "
            f"peak_burner_temp_k is a separate measured column with "
            f"{kelvin.get('non_null_count')} non-null values; the Celsius and Kelvin "
            "columns are never merged. The calibration method is not documented."
        )
        self._support_field(stats, "peak_burner_temp_c")
        self._support_field(stats, "peak_burner_temp_k")
        for key, label in (
            ("non_null_count", "non-null values"),
            ("mean", "mean"),
            ("min", "minimum"),
            ("max", "maximum"),
            ("missing_count", "missing values"),
        ):
            value = celsius.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                self._numeric_claim(
                    f"peak_burner_temp_c {label} is {_fmt(value, celsius.get('unit') if key != 'non_null_count' and key != 'missing_count' else None)}.",
                    value,
                    celsius.get("unit") if key not in {"non_null_count", "missing_count"} else "values",
                    _value_kind(celsius.get("value_kind")) if key not in {"non_null_count", "missing_count"} else ValueKind.derived,
                    stats,
                    dataset_id="psi-159-gas-flame",
                    accession="PSI-159",
                )
        if limitations and self._usable(limitations):
            self._add_limitations_from_tool(
                limitations,
                codes=("serving_restriction_9985f7a7", "method_not_documented"),
            )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.partially_supported,
            answer_type=AnswerType.numerical,
            citation_ids=list(
                dict.fromkeys(
                    list(stats.citation_ids)
                    + (list(limitations.citation_ids) if limitations else [])
                )
            ),
        )

    def _compose_psi159_pressure_initial(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        stats = self._last(results, "dataset_field_statistics")
        limitations = self._last(results, "get_dataset_limitations")
        if not self._usable(stats):
            return self._failure(plan)
        atm = self._field(stats, "pressure_initial_atm") or {}
        bar = self._field(stats, "pressure_approx_bar") or {}
        answer = (
            f"No PSI-159 pressure_initial_atm values are available: "
            f"{atm.get('non_null_count')} non-null canonical values across "
            f"{atm.get('missing_count')} missing rows. Missing is not zero. "
            f"The source instead reports pressure_approx_bar, which has "
            f"{bar.get('non_null_count')} non-null values in {bar.get('unit')} from "
            f"{bar.get('min')} to {bar.get('max')} {bar.get('unit')}. "
            "pressure_approx_bar is not pressure_initial_atm and is not converted."
        )
        self._support_field(stats, "pressure_initial_atm")
        self._support_field(stats, "pressure_approx_bar")
        for field, payload, label in (
            ("pressure_initial_atm", atm, "non-null atm values"),
            ("pressure_approx_bar", bar, "non-null bar values"),
        ):
            value = payload.get("non_null_count")
            if isinstance(value, int):
                self._numeric_claim(
                    f"{field} has {value} {label}.",
                    value,
                    "values",
                    ValueKind.derived,
                    stats,
                    dataset_id="psi-159-gas-flame",
                    accession="PSI-159",
                )
        if limitations and self._usable(limitations):
            self._add_limitations_from_tool(
                limitations, codes=("measurement_has_no_canonical_values",)
            )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.unavailable_data,
            answer_type=AnswerType.numerical,
            citation_ids=list(
                dict.fromkeys(
                    list(stats.citation_ids)
                    + (list(limitations.citation_ids) if limitations else [])
                )
            ),
        )

    def _compose_telemetry_run_count(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        runs = self._last(results, "get_telemetry_runs")
        limitations = self._last(results, "get_dataset_limitations")
        if not self._usable(runs):
            return self._failure(plan)
        total = int((runs.values or {}).get("total") or 0)
        answer = (
            f"PSI-100 has {total} separate telemetry runs. The exports are separate "
            "runs and are never concatenated into one continuous series. Raw "
            "detector and sensor channels are not calibrated physical measurements "
            "unless a verified calibration record says otherwise."
        )
        self._support_counts(
            runs,
            ["total"],
            label="PSI-100 telemetry run count",
            unit="runs",
            dataset_id="psi-100-telemetry",
            accession="PSI-100",
        )
        self._numeric_claim(
            f"PSI-100 has {total} separate telemetry runs.",
            total,
            "runs",
            ValueKind.derived,
            runs,
            dataset_id="psi-100-telemetry",
            accession="PSI-100",
        )
        if limitations and self._usable(limitations):
            self._add_limitations_from_tool(
                limitations, codes=("separate_runs", "uncalibrated_channels")
            )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.numerical,
            citation_ids=list(
                dict.fromkeys(
                    list(runs.citation_ids)
                    + (list(limitations.citation_ids) if limitations else [])
                )
            ),
        )

    # ------------------------------------------------------------------
    # Comparisons
    # ------------------------------------------------------------------
    def _compose_pressure_comparison(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        evaluations = self._all(results, "evaluate_comparison")
        stats = self._last(results, "dataset_field_statistics")
        if len(evaluations) < 2 or not self._usable(stats):
            return self._failure(plan)
        without_conditions, with_conditions = evaluations[0], evaluations[1]
        d0 = without_conditions.data or {}
        d1 = with_conditions.data or {}
        integrity = d1.get("integrity") or {}
        paired = d1.get("paired_values") or {}
        atm = self._field(stats, "pressure_initial_atm") or {}
        bar = self._field(stats, "pressure_approx_bar") or {}
        answer = (
            "The registered PSI-10 / PSI-159 pressure comparison uses "
            "pressure_initial_atm in atm. Without verified conditions the decision "
            "is conditionally_comparable and states conditions_not_verified for "
            "same_pressure_basis and flame_configuration_documented. "
            f"Even when both conditions are supplied, the comparison cannot "
            f"produce a result: integrity status is {integrity.get('status')} and "
            f"measurement_unavailable is reported because PSI-159 "
            f"pressure_initial_atm has {atm.get('non_null_count')} canonical values. "
            f"The populated PSI-159 field is pressure_approx_bar with "
            f"{bar.get('non_null_count')} values in {bar.get('unit')}; it is a "
            "different measurement, is not registered for this comparison, and is "
            "not converted to atm. "
            f"Paired values available: {str(paired.get('available')).lower()} "
            "(no verified alignment method is registered)."
        )
        self._support_field(stats, "pressure_initial_atm")
        self._support_field(stats, "pressure_approx_bar")
        for field, payload in (("pressure_initial_atm", atm), ("pressure_approx_bar", bar)):
            value = payload.get("non_null_count")
            if isinstance(value, int):
                self._numeric_claim(
                    f"{field} has {value} canonical non-null values in PSI-159.",
                    value,
                    "values",
                    ValueKind.derived,
                    stats,
                    dataset_id="psi-159-gas-flame",
                    accession="PSI-159",
                )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.unavailable_data,
            answer_type=AnswerType.comparison,
            citation_ids=list(
                dict.fromkeys(
                    list(without_conditions.citation_ids)
                    + list(with_conditions.citation_ids)
                    + list(stats.citation_ids)
                )
            ),
        )

    def _compose_oxygen_comparison(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        evaluations = self._all(results, "evaluate_comparison")
        if len(evaluations) < 2:
            return self._failure(plan)
        without_conditions, with_conditions = evaluations[0], evaluations[1]
        d0 = without_conditions.data or {}
        d1 = with_conditions.data or {}
        paired = d1.get("paired_values") or {}
        integrity = d1.get("integrity") or {}
        required = [
            condition.get("key")
            for condition in (d0.get("required_conditions") or [])
            if condition.get("key")
        ]
        answer = (
            "PSI-10 and PSI-159 oxygen_mole_fraction measurements are registered as "
            f"conditionally comparable with rule {d0.get('rule_id')}. The required "
            "conditions are " + ", ".join(required) + ". Without verified conditions "
            "the decision is withheld with conditions_not_verified. When both "
            "conditions are explicitly supplied, the decision status becomes "
            f"{d1.get('status')} and measurement integrity is "
            f"{integrity.get('status')}, but paired observations remain unavailable: "
            f"paired_values.available is {str(paired.get('available')).lower()} because "
            "no verified alignment method is registered. No mean difference, "
            "statistical test, or causal claim is produced."
        )
        if "without_conditions" in plan.flags:
            answer += (
                " The conditions cannot be assumed on the user's behalf; they must "
                "be explicitly verified for the comparison."
            )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.partially_supported,
            answer_type=AnswerType.comparison,
            citation_ids=list(
                dict.fromkeys(
                    list(without_conditions.citation_ids)
                    + list(with_conditions.citation_ids)
                )
            ),
        )

    def _compose_paired_observations(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        evaluation = self._last(results, "evaluate_comparison")
        if not self._usable(evaluation):
            return self._failure(plan)
        paired = (evaluation.data or {}).get("paired_values") or {}
        alignment = paired.get("alignment") or {}
        answer = (
            "No verified paired observations are available. The paired-alignment "
            "registry has no registered method for this comparison "
            f"(alignment verified: {str(alignment.get('verified')).lower()}; "
            f"method_id: {alignment.get('method_id')}). The comparison response "
            f"returns paired_values.available = {str(paired.get('available')).lower()} "
            "and withholds paired values rather than inferring them from separate "
            "summaries. No statistical test was run."
        )
        self._claim(
            "No verified paired-alignment method is registered, so paired observations are unavailable.",
            ClaimType.comparison,
            result=evaluation,
            citation_ids=evaluation.citation_ids,
        )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.factual,
            citation_ids=list(evaluation.citation_ids),
        )

    def _compose_comparison_withheld(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        oxygen = self._all(results, "evaluate_comparison")[0] if self._all(results, "evaluate_comparison") else None
        pressure_results = self._all(results, "evaluate_comparison")
        pressure = pressure_results[1] if len(pressure_results) > 1 else None
        if oxygen is None:
            return self._failure(plan)
        oxygen_reasons = [
            reason.get("code") for reason in (oxygen.data or {}).get("reasons") or []
        ]
        pressure_reasons = (
            [reason.get("code") for reason in (pressure.data or {}).get("reasons") or []]
            if pressure
            else []
        )
        answer = (
            "Comparisons are withheld by the Phase 4 comparability rules, not by "
            "an assistant preference. The evaluator can withhold a comparison when "
            "required conditions are not verified, when no verified paired "
            "alignment exists, when the pair is not approved for quantitative use, "
            "or when one measurement has no canonical values.\n\n"
            "For PSI-10 / PSI-159 oxygen_mole_fraction, the unverified decision "
            f"reports: {', '.join(oxygen_reasons) or 'none'}. The paired-values "
            f"contract still reports paired_values.available = "
            f"{str(((oxygen.data or {}).get('paired_values') or {}).get('available')).lower()} "
            "because no verified alignment method is registered.\n\n"
            "For PSI-10 / PSI-159 pressure_initial_atm, the unverified decision "
            f"reports: {', '.join(pressure_reasons) or 'none'}. PSI-159 also has no "
            "canonical pressure_initial_atm values, so the integrity check reports "
            "measurement_unavailable. Withheld values are never estimated or "
            "imputed."
        )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.methodology,
            citation_ids=list(
                dict.fromkeys(
                    list(oxygen.citation_ids)
                    + (list(pressure.citation_ids) if pressure else [])
                )
            ),
        )

    def _compose_unit_conversion_refusal(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        stats159 = self._last(results, "dataset_field_statistics")
        all_stats = self._all(results, "dataset_field_statistics")
        stats10 = next(
            (item for item in all_stats if item.dataset_id == "psi-10-gas-flame"), None
        )
        if stats159 is None or stats10 is None:
            return self._failure(plan)
        bar = self._field(stats159, "pressure_approx_bar") or {}
        atm = self._field(stats10, "pressure_initial_atm") or {}
        answer = (
            "I cannot convert PSI-159 bar values into PSI-10 atm values. "
            f"PSI-159 pressure_approx_bar is expressed in {bar.get('unit')} and has "
            f"{bar.get('non_null_count')} non-null values. PSI-10 "
            f"pressure_initial_atm is expressed in {atm.get('unit')} and has "
            f"{atm.get('non_null_count')} non-null values. They are different "
            "pressure measurements, and no approved conversion rule exists for this "
            "comparison. No converted values are produced, and missing values are "
            "never treated as zero."
        )
        self._support_field(stats159, "pressure_approx_bar")
        self._support_field(stats10, "pressure_initial_atm")
        for field, payload, result in (
            ("pressure_approx_bar", bar, stats159),
            ("pressure_initial_atm", atm, stats10),
        ):
            value = payload.get("non_null_count")
            if isinstance(value, int):
                self._numeric_claim(
                    f"{field} has {value} non-null values.",
                    value,
                    "values",
                    ValueKind.derived,
                    result,
                )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.insufficient_evidence,
            answer_type=AnswerType.numerical,
            citation_ids=list(
                dict.fromkeys(list(stats159.citation_ids) + list(stats10.citation_ids))
            ),
        )

    def _compose_missing_as_zero(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        stats = self._last(results, "dataset_field_statistics")
        limitations = self._last(results, "get_dataset_limitations")
        if not self._usable(stats):
            return self._failure(plan)
        bar = self._field(stats, "pressure_approx_bar") or {}
        answer = (
            "I cannot treat missing values as zero or compute an average from them. "
            f"pressure_approx_bar has {bar.get('non_null_count')} non-null canonical "
            f"values and {bar.get('missing_count')} missing values. Missing is not "
            "zero, so the requested imputed average is not a valid scientific "
            "result and is not calculated."
        )
        self._support_field(stats, "pressure_approx_bar")
        for key, label in (
            ("non_null_count", "non-null values"),
            ("missing_count", "missing values"),
        ):
            value = bar.get(key)
            if isinstance(value, int):
                self._numeric_claim(
                    f"pressure_approx_bar has {value} {label}.",
                    value,
                    "values",
                    ValueKind.derived,
                    stats,
                    dataset_id="psi-10-gas-flame",
                    accession="PSI-10",
                )
        if limitations and self._usable(limitations):
            self._add_limitations_from_tool(
                limitations, codes=("measurement_has_no_canonical_values",)
            )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.insufficient_evidence,
            answer_type=AnswerType.numerical,
            citation_ids=list(
                dict.fromkeys(
                    list(stats.citation_ids)
                    + (list(limitations.citation_ids) if limitations else [])
                )
            ),
        )

    # ------------------------------------------------------------------
    # Temperature and value-kind topics
    # ------------------------------------------------------------------
    def _compose_psi10_measured_temperature(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        stats = self._last(results, "dataset_field_statistics")
        limitations = self._last(results, "get_dataset_limitations")
        if not self._usable(stats):
            return self._failure(plan)
        tad = self._field(stats, "adiabatic_flame_temp_k") or {}
        peak_c = self._field(stats, "peak_burner_temp_c") or {}
        peak_k = self._field(stats, "peak_burner_temp_k") or {}
        measured_temperature = (
            peak_c.get("status") == "available" or peak_k.get("status") == "available"
        )
        answer = (
            "PSI-10 has no measured flame-temperature field. "
        )
        if not measured_temperature:
            answer += (
                "The only available temperature field is adiabatic_flame_temp_k, "
                f"which the source computes: {tad.get('non_null_count')} non-null "
                f"values from {tad.get('min')} to {tad.get('max')} "
                f"{tad.get('unit')}. It is labeled computed and must not be "
                "relabeled as a measurement."
            )
        else:  # pragma: no cover - guarded by the canonical registry
            answer += "A measured temperature field is present in the registry."
        self._support_field(stats, "adiabatic_flame_temp_k")
        for key, label in (
            ("non_null_count", "non-null values"),
            ("min", "minimum"),
            ("max", "maximum"),
        ):
            value = tad.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                self._numeric_claim(
                    f"adiabatic_flame_temp_k {label} is {_fmt(value, tad.get('unit'))}.",
                    value,
                    tad.get("unit"),
                    ValueKind.computed,
                    stats,
                    dataset_id="psi-10-gas-flame",
                    accession="PSI-10",
                )
        if limitations and self._usable(limitations):
            self._add_limitations_from_tool(
                limitations, codes=("computed_source_field",)
            )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.unavailable_data,
            answer_type=AnswerType.numerical,
            citation_ids=list(
                dict.fromkeys(
                    list(stats.citation_ids)
                    + (list(limitations.citation_ids) if limitations else [])
                )
            ),
        )

    def _compose_measured_vs_computed(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        fields = self._last(results, "get_dataset_fields")
        stats = self._last(results, "dataset_field_statistics")
        if not self._usable(fields):
            return self._failure(plan)
        rows = (fields.data or {}).get("fields") or []
        measured = [row["canonical_name"] for row in rows if row.get("value_kind") == "measured"]
        computed = [row["canonical_name"] for row in rows if row.get("value_kind") == "computed"]
        categorical = [row["canonical_name"] for row in rows if row.get("value_kind") == "categorical"]
        answer = (
            "PSI-10 separates value kinds explicitly. Measured fields include "
            + ", ".join(measured)
            + ". Source-computed fields include "
            + ", ".join(computed)
            + (
                ". Categorical fields include " + ", ".join(categorical) + "."
                if categorical
                else "."
            )
            + "\n\nTad (adiabatic_flame_temp_k) and Zst (stoich_mixture_fraction) are "
            "computed by the source. They are never relabeled as measured values, "
            "and the platform does not recompute them."
        )
        self._claim(
            "Tad and Zst are source-computed fields, not measurements.",
            ClaimType.factual,
            result=fields,
            citation_ids=fields.citation_ids,
        )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.methodology,
            citation_ids=list(
                dict.fromkeys(
                    list(fields.citation_ids)
                    + (list(stats.citation_ids) if stats else [])
                )
            ),
        )

    # ------------------------------------------------------------------
    # Provenance and citations
    # ------------------------------------------------------------------
    def _compose_row_provenance(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        rows_result = self._last(results, "query_gas_flame_tests")
        if not self._usable(rows_result):
            return self._failure(plan)
        rows = (rows_result.data or {}).get("rows") or []
        if not rows:
            return self._failure(plan, "No canonical row matched the request.")
        row = rows[0]
        row_citations = [
            citation_id
            for citation_id in rows_result.citation_ids
            if citation_id.startswith("cit_r_")
        ]
        citation_result = (
            self._call("resolve_citation", citation_id=row_citations[0])
            if row_citations
            else None
        )
        if citation_result is None or not self._usable(citation_result):
            return self._failure(plan, "The row citation could not be resolved.")
        payload = citation_result.data or {}
        source = payload.get("source") or {}
        locator = payload.get("locator") or {}
        availability = payload.get("availability") or {}
        verification = payload.get("verification") or {}
        retrieval = payload.get("retrieval") or {}
        answer = (
            f"The observation originated from {source.get('file_name')}, sheet "
            f"{locator.get('sheet') or 'not recorded'}, row {locator.get('row')}. "
            f"The row citation is {payload.get('citation_id')}. The source file has "
            f"SHA-256 {source.get('sha256') or 'not recorded'} and verification status "
            f"{verification.get('status') or 'unknown'}. Availability is "
            f"{availability.get('status') or 'unknown'}; downloadable is "
            f"{str(availability.get('downloadable')).lower()}. The source URL is "
            f"{source.get('source_url') or 'not recorded'}."
        )
        self._claim(
            "The row resolves to a canonical source file, sheet, and row citation.",
            ClaimType.provenance,
            result=citation_result,
            citation_ids=citation_result.citation_ids,
        )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.factual,
            citation_ids=list(citation_result.citation_ids),
        )

    def _compose_pressure_source(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        fields = self._last(results, "get_dataset_fields")
        if not self._usable(fields):
            return self._failure(plan)
        rows = (fields.data or {}).get("fields") or []
        pressure_rows = [
            row
            for row in rows
            if "pressure" in (row.get("canonical_name") or "")
        ]
        citations = list(fields.citation_ids)
        citation_result = (
            self._call("resolve_citation", citation_id=citations[0])
            if citations
            else None
        )
        if citation_result is None or not self._usable(citation_result):
            return self._failure(plan, "The pressure source citation could not be resolved.")
        payload = citation_result.data or {}
        source = payload.get("source") or {}
        availability = payload.get("availability") or {}
        verification = payload.get("verification") or {}
        names = ", ".join(
            f"{row.get('canonical_name')} ({row.get('unit')})" for row in pressure_rows
        )
        answer = (
            f"The PSI-159 pressure fields are {names}. The resolved source file is "
            f"{source.get('file_name')}, with SHA-256 {source.get('sha256') or 'not recorded'}, "
            f"verification status {verification.get('status') or 'unknown'}, and "
            f"availability {availability.get('status') or 'unknown'}. PSI-159 reports "
            "pressure_approx_bar in bar; it is not an atm field and is not converted."
        )
        self._claim(
            "The PSI-159 pressure fields resolve to an experimental summary table with a recorded checksum.",
            ClaimType.provenance,
            result=citation_result,
            citation_ids=citation_result.citation_ids,
        )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.factual,
            citation_ids=list(
                dict.fromkeys(list(citation_result.citation_ids) + citations)
            ),
        )

    def _compose_file_source_lookup(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        files = self._last(results, "get_dataset_files")
        fields = self._last(results, "get_dataset_fields")
        if not self._usable(files):
            return self._failure(plan)
        rows = (files.data or {}).get("files") or []
        if not rows:
            return self._failure(plan, "No curated source file matched the request.")
        lines = ["Curated source files for this dataset:"]
        for row in rows:
            lines.append(
                f"- {row.get('file_name')} ({row.get('citation_id')}), "
                f"kind {row.get('kind')}, availability {row.get('availability')}, "
                f"downloadable {str(row.get('downloadable')).lower()}."
            )
        return DraftAnswer(
            answer="\n".join(lines),
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.factual,
            citation_ids=list(
                dict.fromkeys(
                    list(files.citation_ids)
                    + (list(fields.citation_ids) if fields else [])
                )
            ),
        )

    def _compose_citation_resolution(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        citation = self._last(results, "resolve_citation")
        if not self._usable(citation):
            return self._failure(plan)
        payload = citation.data or {}
        source = payload.get("source") or {}
        availability = payload.get("availability") or {}
        verification = payload.get("verification") or {}
        locator = payload.get("locator") or {}
        answer = (
            f"Citation {payload.get('citation_id')} resolves to "
            f"{source.get('file_name')} for {payload.get('accession')}. "
            f"Kind: {payload.get('kind')}; sheet: {locator.get('sheet') or 'not applicable'}; "
            f"row: {locator.get('row') or 'not applicable'}. "
            f"Verification status: {verification.get('status') or 'unknown'}; "
            f"availability: {availability.get('status') or 'unknown'}; "
            f"downloadable: {str(availability.get('downloadable')).lower()}. "
            f"SHA-256: {source.get('sha256') or 'not recorded'}. "
            f"Source URL: {source.get('source_url') or 'not recorded'}."
        )
        self._claim(
            "The citation resolves to a verified Phase 4 source record.",
            ClaimType.provenance,
            result=citation,
            citation_ids=citation.citation_ids,
        )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.factual,
            citation_ids=list(citation.citation_ids),
        )

    def _compose_psi98_unavailable(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        files = self._last(results, "get_dataset_files")
        if not self._usable(files):
            return self._failure(plan)
        rows = (files.data or {}).get("files") or []
        unavailable = [
            row for row in rows if row.get("availability") == "unavailable"
        ]
        for row in unavailable[:2]:
            citation_id = row.get("citation_id")
            if citation_id:
                self._call("resolve_citation", citation_id=citation_id)
        lines = [
            (
                "The two PSI-98 raw-data workbooks are not downloadable. Both are "
                "listed by the public inventory, but their download endpoints return "
                "HTTP 404, and they are marked unavailable and non-downloadable."
            ),
            "",
        ]
        for row in unavailable:
            lines.append(
                f"- {row.get('file_name')} ({row.get('citation_id')}): "
                f"{row.get('availability')}, downloadable "
                f"{str(row.get('downloadable')).lower()}."
            )
        lines.extend(
            [
                "",
                (
                    "The PSI-98 experimental summary table is a separate available "
                    "file. Availability of that table does not make the unavailable "
                    "telemetry workbooks downloadable."
                ),
            ]
        )
        return DraftAnswer(
            answer="\n".join(lines),
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.factual,
            citation_ids=list(files.citation_ids),
        )

    def _compose_datasets_without_measurement_files(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        files = self._last(results, "get_dataset_files")
        if not self._usable(files):
            return self._failure(plan)
        summary = (files.data or {}).get("summary") or {}
        unavailable = int(summary.get("unavailable_files") or 0)
        curated = int(summary.get("curated_files") or 0)
        available = int(summary.get("available_files") or 0)
        answer = (
            "PSI-98 SAFFIRE-I is the metadata-only curated dataset. "
            f"It has {curated} curated files: {available} available experimental "
            f"summary table and {unavailable} raw telemetry workbooks that return "
            "HTTP 404 and are not downloadable. Only the summary table and "
            "investigation metadata are available; the telemetry data are not."
        )
        self._numeric_claim(
            f"PSI-98 has {unavailable} unavailable raw telemetry workbooks.",
            unavailable,
            "files",
            ValueKind.derived,
            files,
        )
        self._numeric_claim(
            f"PSI-98 has {curated} curated files, of which {available} is an available summary table.",
            curated,
            "files",
            ValueKind.derived,
            files,
        )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.factual,
            citation_ids=list(files.citation_ids),
        )

    # ------------------------------------------------------------------
    # Limitations and methodology refusals
    # ------------------------------------------------------------------
    def _compose_dataset_limitations(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        limitations = self._last(results, "get_dataset_limitations")
        if not self._usable(limitations):
            return self._failure(plan)
        rows = (limitations.data or {}).get("limitations") or []
        summary = (limitations.data or {}).get("summary") or {}
        total = int(summary.get("total") or len(rows))
        lines = [
            f"{plan.accession or plan.dataset_id} has {total} recorded limitations. "
            "The dataset-scope limitations below are the ones that constrain "
            "scientific use:"
        ]
        dataset_rows = [row for row in rows if row.get("scope") == "dataset"]
        for row in dataset_rows[:8]:
            lines.append(
                f"- {row.get('code')}: {row.get('explanation')}"
            )
        if total > len(dataset_rows[:8]):
            lines.append(
                "Measurement-scope restrictions and the full list are available in "
                "the evidence panel."
            )
        for row in dataset_rows[:8]:
            self._add_limitation(
                self._limitation(
                    str(row.get("code")),
                    str(row.get("explanation")),
                    scope=row.get("scope"),
                    severity=Severity.warning,
                    citation_ids=limitations.citation_ids[:3],
                )
            )
        self._numeric_claim(
            f"{plan.accession or plan.dataset_id} has {total} recorded limitations.",
            total,
            "limitations",
            ValueKind.derived,
            limitations,
        )
        return DraftAnswer(
            answer="\n".join(lines),
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.methodology,
            citation_ids=list(limitations.citation_ids),
        )

    def _compose_psi100_raw_voltage(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        fields = self._last(results, "get_dataset_fields")
        limitations = self._last(results, "get_dataset_limitations")
        raw_fields = []
        if fields:
            raw_fields = [
                row
                for row in (fields.data or {}).get("fields") or []
                if row.get("value_kind") == "raw"
            ]
        names = ", ".join(
            row.get("canonical_name")
            for row in raw_fields[:6]
            if row.get("canonical_name")
        )
        answer = (
            "No. PSI-100 raw voltage channels are uncalibrated signals, not smoke "
            "concentration. "
            + (f"Raw fields include {names}. " if names else "")
            + "The platform does not provide a calibration factor or a validated "
            "conversion from detector volts to smoke concentration, obscuration, or "
            "scatter. Presenting a voltage as concentration would be unsupported."
        )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.insufficient_evidence,
            answer_type=AnswerType.methodology,
            citation_ids=list(
                dict.fromkeys(
                    list(fields.citation_ids) if fields else []
                    + (list(limitations.citation_ids) if limitations else [])
                )
            ),
        )

    def _compose_bass_flame_spread(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        limitations = self._last(results, "get_dataset_limitations")
        answer = (
            "No. The verified BASS/BASS-II artifacts do not contain a published "
            "flame-spread-rate table or a validated method for computing one. The "
            "material test matrix is context, not a rate measurement. The platform "
            "will not calculate a rate from raw images or infer one from material "
            "rows."
        )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.insufficient_evidence,
            answer_type=AnswerType.methodology,
            citation_ids=list(
                limitations.citation_ids if limitations else []
            ),
        )

    def _compose_fire_risk_refusal(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        limitations = self._last(results, "get_dataset_limitations")
        answer = (
            "I cannot calculate a fire-risk score, rank materials, or claim a "
            "spacecraft fire-safety guarantee. No validated risk model exists in "
            "the verified artifacts. The material test matrices provide measured "
            "test conditions and observations, but they do not support a predictive "
            "fire-risk score or a material ranking."
        )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.insufficient_evidence,
            answer_type=AnswerType.methodology,
            citation_ids=list(
                limitations.citation_ids if limitations else []
            ),
        )

    def _compose_psi26_oxygen_unit(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        limitations = self._last(results, "get_dataset_limitations")
        answer = (
            "I cannot relabel PSI-26 oxygen as a confirmed percentage or convert it. "
            "The source header says percent, but the observed values are "
            "fraction-like and the unit status is ambiguous. The values are "
            "preserved as o2_pct exactly as labeled; no conversion to percent or "
            "mole fraction is performed, and the limitation is not ignored."
        )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.insufficient_evidence,
            answer_type=AnswerType.factual,
            citation_ids=list(
                limitations.citation_ids if limitations else []
            ),
        )

    def _compose_publication_invention(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        publications = self._last(results, "get_publications")
        if not self._usable(publications):
            return self._failure(plan)
        values = publications.values or {}
        summary = (publications.data or {}).get("summary") or {}
        total = int(summary.get("publication_count") or values.get("publication_count") or 0)
        with_doi = summary.get("with_doi")
        without_doi = summary.get("without_doi")
        answer = (
            "I cannot invent a publication, author, DOI, title, or finding. "
            f"The verified publication registry contains {total} matching records"
            + (
                f", of which {with_doi} have a DOI and {without_doi} do not"
                if with_doi is not None and without_doi is not None
                else ""
            )
            + ". Year and venue are unavailable in the registry. The registry is the "
            "only source of verified publication records; no fabricated DOI was "
            "produced."
        )
        self._numeric_claim(
            f"The verified publication registry contains {total} matching records.",
            total,
            "publication records",
            ValueKind.derived,
            publications,
        )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.insufficient_evidence,
            answer_type=AnswerType.factual,
            citation_ids=[],
        )

    # ------------------------------------------------------------------
    # Investigation, dataset, and retrieval overviews
    # ------------------------------------------------------------------
    def _compose_acme_flame_design(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        investigation = self._last(results, "get_investigation")
        limitations = self._last(results, "get_dataset_limitations")
        if not self._usable(investigation):
            return self._failure(plan)
        inv = investigation.data or {}
        answer = (
            f"{inv.get('accession')} — {inv.get('title')} ({inv.get('acronym')}). "
            f"{str(inv.get('rationale') or '').strip()}\n\n"
            "The investigation studies gas-flame behavior in microgravity through "
            "normal and inverse flame summary tables. The platform uses the curated "
            "summary tables, not the full raw archive. Tad and Zst are computed by "
            "the source and are not measured quantities."
        )
        if limitations and self._usable(limitations):
            self._add_limitations_from_tool(
                limitations,
                codes=("computed_tad_zst", "summary_table_only"),
            )
        self._claim(
            "ACME Flame Design is a microgravity gas-flame investigation with normal and inverse summary tables.",
            ClaimType.factual,
            result=investigation,
            citation_ids=investigation.citation_ids,
        )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.methodology,
            citation_ids=list(
                dict.fromkeys(
                    list(investigation.citation_ids)
                    + (list(limitations.citation_ids) if limitations else [])
                )
            ),
        )

    def _compose_saffire_iii(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        investigation = self._last(results, "get_investigation")
        dataset = self._last(results, "get_dataset")
        limitations = self._last(results, "get_dataset_limitations")
        if not self._usable(investigation) or not self._usable(dataset):
            return self._failure(plan)
        inv = investigation.data or {}
        ds = dataset.data or {}
        answer = (
            f"{inv.get('accession')} — {inv.get('title')} ({inv.get('acronym')}). "
            f"{str(inv.get('rationale') or '').strip()}\n\n"
            f"The curated dataset is {ds.get('display_name')}. It groups separate "
            "telemetry exports into distinct runs and never concatenates them into "
            "one continuous series. Raw radiometer, anemometer, and smoke-detector "
            "channels are uncalibrated unless a verified calibration record says "
            "otherwise. The platform does not predict or guarantee spacecraft fire "
            "safety."
        )
        if limitations and self._usable(limitations):
            self._add_limitations_from_tool(
                limitations,
                codes=("separate_runs", "uncalibrated_channels"),
            )
        self._claim(
            "SAFFIRE-III telemetry is organized as separate uncalibrated runs.",
            ClaimType.factual,
            result=dataset,
            citation_ids=dataset.citation_ids,
        )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.methodology,
            citation_ids=list(
                dict.fromkeys(
                    list(investigation.citation_ids)
                    + list(dataset.citation_ids)
                    + (list(limitations.citation_ids) if limitations else [])
                )
            ),
        )

    def _compose_same_r(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        dataset = self._last(results, "get_dataset")
        fields = self._last(results, "get_dataset_fields")
        limitations = self._last(results, "get_dataset_limitations")
        runs = self._last(results, "get_smoke_runs")
        if not self._usable(dataset):
            return self._failure(plan)
        ds = dataset.data or {}
        total_runs = int((runs.values or {}).get("total") or 0) if runs else 0
        answer = (
            f"{ds.get('display_name')} ({ds.get('dataset_id')}) contains smoke and "
            "aerosol housekeeping telemetry. "
            + (f"It exposes {total_runs} separate smoke runs. " if total_runs else "")
            + "The -999 P-Trak values are sentinels, not concentrations, and are "
            "preserved as missing. Optical and ion detector voltages are "
            "uncalibrated. Material names and aging conditions require a validated "
            "join to the test logs, and no verified flame-spread rate is available."
        )
        if total_runs:
            self._support_counts(
                runs,
                ["total"],
                label="PSI-101 smoke run count",
                unit="runs",
                dataset_id="psi-101-smoke",
                accession="PSI-101",
            )
            self._numeric_claim(
                f"PSI-101 exposes {total_runs} separate smoke runs.",
                total_runs,
                "runs",
                ValueKind.derived,
                runs,
                dataset_id="psi-101-smoke",
                accession="PSI-101",
            )
        if limitations and self._usable(limitations):
            self._add_limitations_from_tool(
                limitations,
                codes=(
                    "sentinel_ptrak",
                    "material_join_unresolved",
                    "uncalibrated_detectors",
                    "separate_runs",
                ),
            )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.factual,
            citation_ids=list(
                dict.fromkeys(
                    list(dataset.citation_ids)
                    + (list(fields.citation_ids) if fields else [])
                    + (list(limitations.citation_ids) if limitations else [])
                    + (list(runs.citation_ids) if runs else [])
                )
            ),
        )

    def _compose_investigation_overview(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        investigation = self._last(results, "get_investigation")
        dataset = self._last(results, "get_dataset")
        if not self._usable(investigation):
            return self._failure(plan)
        inv = investigation.data or {}
        lines = [
            f"{inv.get('accession')} — {inv.get('title')} ({inv.get('acronym')}).",
            "",
            str(inv.get("rationale") or "").strip(),
        ]
        if dataset and self._usable(dataset):
            ds = dataset.data or {}
            lines.append(
                f"The curated dataset is {ds.get('display_name')} with "
                f"{(dataset.values or {}).get('measurement_count', 0)} registered "
                "measurement definitions."
            )
        limitations = (
            "Limitations recorded for this investigation: "
            + "; ".join(str(item) for item in (inv.get("limitations") or [])[:3])
            + "."
        )
        lines.append(limitations)
        return DraftAnswer(
            answer="\n".join(lines),
            evidence_status=EvidenceStatus.fully_supported,
            answer_type=AnswerType.methodology,
            citation_ids=list(
                dict.fromkeys(
                    list(investigation.citation_ids)
                    + (list(dataset.citation_ids) if dataset else [])
                )
            ),
        )

    def _compose_dataset_overview(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        dataset = self._last(results, "get_dataset")
        if not self._usable(dataset):
            return self._failure(plan)
        ds = dataset.data or {}
        reasons = ds.get("reasons") or []
        lines = [
            f"{ds.get('display_name')} ({ds.get('dataset_id')}) is a "
            f"{ds.get('experiment_family')} dataset with "
            f"{(dataset.values or {}).get('measurement_count', 0)} registered "
            "measurement definitions.",
            "",
            (
                "Serving states: "
                + ", ".join(
                    f"{use}={state}" for use, state in (ds.get("use_states") or {}).items()
                )
                + "."
            ),
        ]
        if reasons:
            lines.append("")
            lines.append("Documented reasons:")
            for reason in reasons[:6]:
                lines.append(f"- {reason.get('code')}: {reason.get('message')}")
        return DraftAnswer(
            answer="\n".join(lines),
            evidence_status=EvidenceStatus.partially_supported,
            answer_type=AnswerType.factual,
            citation_ids=list(dataset.citation_ids),
        )

    def _compose_pressure_fields(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        fields = self._last(results, "get_dataset_fields")
        limitations = self._last(results, "get_dataset_limitations")
        if not self._usable(fields):
            return self._failure(plan)
        rows = (fields.data or {}).get("fields") or []
        lines = ["Available pressure fields:"]
        for row in rows:
            presence = (row.get("missingness") or {}).get("canonical_presence") or {}
            lines.append(
                f"- {row.get('canonical_name')}: unit {row.get('unit')}, "
                f"value kind {row.get('value_kind')}, non-null "
                f"{presence.get('non_null_count')}, status {presence.get('status')}."
            )
        return DraftAnswer(
            answer="\n".join(lines),
            evidence_status=EvidenceStatus.partially_supported,
            answer_type=AnswerType.factual,
            citation_ids=list(
                dict.fromkeys(
                    list(fields.citation_ids)
                    + (list(limitations.citation_ids) if limitations else [])
                )
            ),
        )

    def _compose_retrieval_overview(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        retrieval = self._last(results, "search_scientific_documents")
        if retrieval is None or not self._usable(retrieval):
            return self._failure(plan)
        chunks = (retrieval.data or {}).get("results") or []
        if not chunks:
            return DraftAnswer(
                answer=(
                    "No verified documentation chunk matched this question. I "
                    "cannot produce a factual or numerical answer from unverified "
                    "text."
                ),
                evidence_status=EvidenceStatus.insufficient_evidence,
                answer_type=AnswerType.factual,
                confidence=Confidence.low,
                confidence_basis="Retrieval returned no verified evidence.",
                limitations=[self._limitation("retrieval_context_only")],
            )
        answer = (
            f"I found {len(chunks)} verified documentation or metadata chunks that "
            "match the question. They are shown in the evidence panel and are "
            "labeled as untrusted evidence. Retrieval is lexical (BM25 plus a "
            "hashed TF-IDF baseline), not neural semantic search, and retrieved "
            "numbers are not treated as verified measurements. Ask about a specific "
            "curated dataset, field, comparison, or citation for a deterministic "
            "answer."
        )
        return DraftAnswer(
            answer=answer,
            evidence_status=EvidenceStatus.partially_supported,
            answer_type=AnswerType.exploratory,
            confidence=Confidence.moderate,
            confidence_basis="Verified retrieval found relevant documentation, but no deterministic numerical tool was selected.",
            citation_ids=list(retrieval.citation_ids),
        )

    # ------------------------------------------------------------------
    # Security refusals
    # ------------------------------------------------------------------
    def _compose_security_refusal(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        return DraftAnswer(
            answer=(
                "I cannot show local file contents, environment variables, "
                "credentials, or secrets. The assistant has no filesystem tool and "
                "no unrestricted URL, SQL, or code execution. I can answer "
                "questions about the verified NASA PSI investigations, datasets, "
                "measurements, comparisons, and citations."
            ),
            evidence_status=EvidenceStatus.insufficient_evidence,
            answer_type=AnswerType.factual,
            confidence=Confidence.low,
            confidence_basis="The request is outside the verified scientific tool boundary.",
            limitations=[self._limitation("filesystem_access_blocked")],
        )

    def _compose_prompt_injection(
        self, plan: Plan, results: list[ToolResult]
    ) -> DraftAnswer:
        return DraftAnswer(
            answer=(
                "The quoted text is source content, not an instruction. I will not "
                "execute it, reveal environment variables or secrets, or treat "
                "retrieved text as a system message. Retrieved documents are "
                "untrusted evidence, and only approved deterministic tools can "
                "produce numerical or factual data."
            ),
            evidence_status=EvidenceStatus.insufficient_evidence,
            answer_type=AnswerType.factual,
            confidence=Confidence.low,
            confidence_basis="The request attempts to override the evidence and tool boundary.",
            limitations=[self._limitation("prompt_injection_blocked")],
        )
