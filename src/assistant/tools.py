"""Strict, allowlisted deterministic tools for the Phase 5 assistant.

Every tool wraps an existing analytics service method. There is no arbitrary
SQL, filesystem path, URL fetch, or code execution. Arguments are validated by
Pydantic models with ``extra="forbid"``. Results are bounded, hashed, and
logged with the request ID.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Annotated, Any, Callable, Literal, Mapping, Sequence

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError

from src.analytics.errors import AnalyticsError, InvalidQueryError, NotFoundError
from src.analytics.logging import get_logger
from src.analytics.service import AnalyticsService
from src.assistant.contract import ToolCall, ToolStatus, ValueKind

LOGGER = get_logger("flame.assistant.tools")

MAX_TOOL_RESULT_BYTES = 512_000
MAX_LOG_ARGUMENT_CHARS = 120
SECRET_KEYS = {"api_key", "apikey", "secret", "token", "password", "authorization"}

ACCESSION_RE = re.compile(r"^PSI-\d{1,4}$")
DATASET_RE = re.compile(r"^psi-\d{1,4}-[a-z0-9-]+$")
FIELD_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
CONDITION_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
CHANNEL_RE = re.compile(r"^[A-Za-z0-9_.@\[\]-]{1,128}$")
CITATION_RE = re.compile(r"^cit_[fr]_[A-Za-z0-9_-]{4,512}$")


class ToolError(ValueError):
    """Base class for safe tool errors."""


class ToolNotFoundError(ToolError):
    pass


class ToolLimitExceededError(ToolError):
    pass


def _accession(value: str) -> str:
    text = value.strip().upper()
    if not ACCESSION_RE.fullmatch(text):
        raise ValueError("accession must look like PSI-10")
    return text


def _dataset_id(value: str) -> str:
    text = value.strip().lower()
    if not DATASET_RE.fullmatch(text):
        raise ValueError("dataset_id must look like psi-10-gas-flame")
    return text


def _field_name(value: str) -> str:
    text = value.strip()
    if not FIELD_RE.fullmatch(text):
        raise ValueError("field names must be lowercase canonical names")
    return text


def _channel_name(value: str) -> str:
    text = value.strip()
    if not CHANNEL_RE.fullmatch(text) or ".." in text or "/" in text or "\\" in text:
        raise ValueError("channel name is not a safe canonical channel")
    return text


def _citation_id(value: str) -> str:
    text = value.strip()
    if not CITATION_RE.fullmatch(text):
        raise ValueError("citation_id must be a Phase 4 cit_f_ or cit_r_ identifier")
    return text


def _file_name(value: str) -> str:
    text = value.strip()
    if (
        not text
        or len(text) > 255
        or "/" in text
        or "\\" in text
        or ".." in text
    ):
        raise ValueError("file_name must be an exact source file name, not a path")
    return text


AccessionStr = Annotated[str, AfterValidator(_accession)]
DatasetStr = Annotated[str, AfterValidator(_dataset_id)]
FieldStr = Annotated[str, AfterValidator(_field_name)]
ChannelStr = Annotated[str, AfterValidator(_channel_name)]
CitationStr = Annotated[str, AfterValidator(_citation_id)]
FileNameStr = Annotated[str, AfterValidator(_file_name)]

Limit = Annotated[int, Field(ge=1, le=50)]
Offset = Annotated[int, Field(ge=0, le=10_000)]
Use = Literal["exploration", "quantitative_comparison", "time_series", "provenance"]
ServingState = Literal[
    "available", "available_with_warnings", "restricted", "blocked", "metadata_only"
]
ComparisonStatus = Literal[
    "comparable",
    "conditionally_comparable",
    "not_comparable",
    "blocked",
    "insufficient_metadata",
]
ValueKindName = Literal["measured", "computed", "derived", "categorical", "raw"]
Family = Literal[
    "gas_flame", "material", "droplet", "telemetry", "smoke", "smoke_log", "metadata"
]


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchInvestigationsArgs(ToolArgs):
    query: str | None = Field(default=None, max_length=200)
    role: str | None = Field(default=None, max_length=32)
    limit: Limit = 10
    offset: Offset = 0


class GetInvestigationArgs(ToolArgs):
    accession: AccessionStr


class SearchDatasetsArgs(ToolArgs):
    family: Family | None = None
    accession: AccessionStr | None = None
    state: ServingState | None = None
    use: Use = "exploration"
    limit: Limit = 10
    offset: Offset = 0


class GetDatasetArgs(ToolArgs):
    dataset_id: DatasetStr


class GetDatasetFieldsArgs(ToolArgs):
    dataset_id: DatasetStr
    value_kind: ValueKindName | None = None
    physical_quantity: str | None = Field(default=None, max_length=64)
    comparison_status: ComparisonStatus | None = None
    limit: Limit = 25
    offset: Offset = 0


class GetDatasetLimitationsArgs(ToolArgs):
    dataset_id: DatasetStr
    scope: Literal["dataset", "file", "measurement", "comparison"] | None = None
    category: str | None = Field(default=None, max_length=64)
    severity: Literal["error", "warning", "info"] | None = None
    status: str | None = Field(default=None, max_length=32)
    limit: Limit = 25
    offset: Offset = 0


class GetDatasetFilesArgs(ToolArgs):
    dataset_id: DatasetStr
    kind: str | None = Field(default=None, max_length=64)
    availability: Literal["available", "unavailable"] | None = None
    limit: Limit = 25
    offset: Offset = 0


class GetPublicationsArgs(ToolArgs):
    accession: AccessionStr | None = None
    dataset_id: DatasetStr | None = None
    query: str | None = Field(default=None, max_length=200)
    year: int | None = Field(default=None, ge=1900, le=2100)
    status: str | None = Field(default=None, max_length=32)
    limit: Limit = 10
    offset: Offset = 0


class GasFlameStatisticsArgs(ToolArgs):
    accession: AccessionStr
    include_qualified: bool = False


class QueryGasFlameTestsArgs(ToolArgs):
    accession: AccessionStr | None = None
    flame_type: str | None = Field(default=None, max_length=64)
    fuel: str | None = Field(default=None, max_length=64)
    oxygen_min: float | None = Field(default=None, ge=0, le=1)
    oxygen_max: float | None = Field(default=None, ge=0, le=1)
    pressure_min: float | None = Field(default=None, ge=0, le=1000)
    pressure_max: float | None = Field(default=None, ge=0, le=1000)
    hot_ignition: str | None = Field(default=None, max_length=32)
    extinction_mode: str | None = Field(default=None, max_length=32)
    tfp: str | None = Field(default=None, max_length=32)
    include_qualified: bool = False
    sort: Literal[
        "source_row",
        "oxygen_mole_fraction",
        "pressure",
        "peak_burner_temp_c",
        "observation_id",
    ] = "source_row"
    order: Literal["asc", "desc"] = "asc"
    limit: Limit = 20
    offset: Offset = 0


class DatasetFieldStatisticsArgs(ToolArgs):
    dataset_id: DatasetStr
    fields: list[FieldStr] | None = Field(default=None, max_length=12)
    include_qualified: bool = False


class QueryMaterialTestsArgs(ToolArgs):
    accession: AccessionStr | None = None
    material: str | None = Field(default=None, max_length=128)
    flow_restrictor: str | None = Field(default=None, max_length=64)
    o2_min: float | None = Field(default=None, ge=0, le=100)
    o2_max: float | None = Field(default=None, ge=0, le=100)
    limit: Limit = 20
    offset: Offset = 0


class QueryDropletTestsArgs(ToolArgs):
    accession: AccessionStr = "PSI-69"
    fuel: str | None = Field(default=None, max_length=64)
    pressure_min: float | None = Field(default=None, ge=0, le=1000)
    pressure_max: float | None = Field(default=None, ge=0, le=1000)
    limit: Limit = 20
    offset: Offset = 0


class GetTelemetryRunsArgs(ToolArgs):
    accession: AccessionStr = "PSI-100"
    export_kind: str | None = Field(default=None, max_length=64)
    limit: Limit = 20
    offset: Offset = 0


class QueryTelemetrySeriesArgs(ToolArgs):
    run_id: str = Field(min_length=1, max_length=256)
    channels: list[ChannelStr] = Field(min_length=1, max_length=8)
    start_ms: float = Field(ge=0)
    end_ms: float = Field(ge=0)
    max_points: int = Field(default=500, ge=1, le=1000)


class GetSmokeRunsArgs(ToolArgs):
    accession: AccessionStr = "PSI-101"
    limit: Limit = 20
    offset: Offset = 0


class QuerySmokeSeriesArgs(ToolArgs):
    run_id: str = Field(min_length=1, max_length=256)
    channels: list[ChannelStr] = Field(min_length=1, max_length=8)
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    max_points: int = Field(default=500, ge=1, le=1000)


class EvaluateComparisonArgs(ToolArgs):
    left: str = Field(min_length=3, max_length=256)
    right: str = Field(min_length=3, max_length=256)
    conditions: dict[str, bool | None] | None = Field(default=None, max_length=10)

    @property
    def validated_conditions(self) -> dict[str, bool | None] | None:
        if self.conditions is None:
            return None
        for key in self.conditions:
            if not CONDITION_RE.fullmatch(key):
                raise ValueError("condition keys must be lowercase snake_case")
        return self.conditions


class ResolveCitationArgs(ToolArgs):
    citation_id: CitationStr


class GetProvenanceArgs(ToolArgs):
    accession: AccessionStr
    file_name: FileNameStr
    sheet: str | None = Field(default=None, max_length=100)
    row: int | None = Field(default=None, ge=1, le=10_000_000)


class GetMeasurementsArgs(ToolArgs):
    accession: AccessionStr | None = None
    dataset_id: DatasetStr | None = None
    family: Family | None = None
    comparison_status: ComparisonStatus | None = None
    serving_state: ServingState | None = None
    use: Use = "exploration"
    limit: Limit = 25
    offset: Offset = 0


@dataclass
class ToolPayload:
    data: dict[str, Any]
    summary: str
    citation_ids: list[str] = field(default_factory=list)
    status: ToolStatus = ToolStatus.ok
    dataset_id: str | None = None
    accession: str | None = None
    value_kind: ValueKind | None = None
    unit: str | None = None
    label: str | None = None
    values: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    call_id: str
    tool: str
    arguments: dict[str, Any]
    status: ToolStatus
    duration_ms: float
    data: dict[str, Any]
    summary: str
    citation_ids: list[str] = field(default_factory=list)
    dataset_id: str | None = None
    accession: str | None = None
    value_kind: ValueKind | None = None
    unit: str | None = None
    label: str | None = None
    values: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    result_hash: str | None = None

    def to_tool_call(self) -> ToolCall:
        return ToolCall(
            call_id=self.call_id,
            tool=self.tool,
            arguments=self.arguments,
            status=self.status,
            duration_ms=self.duration_ms,
            result_summary=self.summary,
            result_hash=self.result_hash,
            error=self.error,
        )


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_model: type[ToolArgs]
    handler: Callable[[AnalyticsService, ToolArgs], ToolPayload]
    category: str

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "arguments_schema": self.args_model.model_json_schema(),
        }


# ----------------------------------------------------------------------
# Safe result shaping
# ----------------------------------------------------------------------
def _collect_citation_ids(value: Any, *, limit: int = 64) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    def walk(node: Any, depth: int = 0) -> None:
        if len(found) >= limit or depth > 6:
            return
        if isinstance(node, dict):
            for key, item in node.items():
                if key in {"citation_id", "file_citation_id"} and isinstance(item, str):
                    if item.startswith(("cit_f_", "cit_r_")) and item not in seen:
                        seen.add(item)
                        found.append(item)
                elif key in {"citation_ids", "row_citation_ids"} and isinstance(item, list):
                    for citation_id in item:
                        if (
                            isinstance(citation_id, str)
                            and citation_id.startswith(("cit_f_", "cit_r_"))
                            and citation_id not in seen
                        ):
                            seen.add(citation_id)
                            found.append(citation_id)
                else:
                    walk(item, depth + 1)
        elif isinstance(node, list):
            for item in node:
                walk(item, depth + 1)

    walk(value)
    return found


def _dataset_citation_ids(
    service: AnalyticsService, dataset_id: str, *, limit: int = 6
) -> list[str]:
    try:
        citations = service.citations.list(dataset_id=dataset_id)
    except Exception:  # pragma: no cover - defensive boundary
        return []
    return [citation["citation_id"] for citation in citations[:limit]]


def _provenance_citation_ids(
    service: AnalyticsService, provenance: Sequence[Mapping[str, Any]]
) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for reference in provenance:
        if not isinstance(reference, Mapping):
            continue
        citation_id = reference.get("citation_id")
        if isinstance(citation_id, str) and citation_id.startswith(("cit_f_", "cit_r_")):
            if citation_id not in seen:
                seen.add(citation_id)
                found.append(citation_id)
        if reference.get("kind") != "nasa_psi_file":
            continue
        accession = reference.get("accession")
        file_name = reference.get("file_name") or reference.get("file")
        if not isinstance(accession, str) or not isinstance(file_name, str):
            continue
        citation = service.citations.for_file(accession, file_name)
        if citation and citation["citation_id"] not in seen:
            seen.add(citation["citation_id"])
            found.append(citation["citation_id"])
    return found


def _compact_investigation(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "accession",
        "acronym",
        "title",
        "doi",
        "research_area",
        "sub_research_area",
        "project_type",
        "start_date",
        "end_date",
        "public",
        "restricted",
        "file_count",
        "experimental_table_count",
        "archive_status",
        "mvp_role",
        "rationale",
        "limitations",
    )
    return {key: row.get(key) for key in keys if key in row}


def _compact_dataset(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "dataset_id",
        "accession",
        "display_name",
        "experiment_family",
        "canonical_tables",
        "access_scope",
        "base_state",
        "use_states",
        "measurement_count",
        "download_status",
        "measurement_file_status",
        "reasons",
        "restrictions",
    )
    return {key: row.get(key) for key in keys if key in row}


def _compact_field(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "field_id",
        "measurement_id",
        "dataset_id",
        "accession",
        "canonical_name",
        "parameter",
        "description",
        "physical_quantity",
        "unit",
        "unit_status",
        "value_kind",
        "measurement_method",
        "calibration",
        "missingness",
        "integrity",
        "serving",
        "comparison",
        "flags",
    )
    return {key: row.get(key) for key in keys if key in row}


def _compact_limitation(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "limitation_id",
        "scope",
        "scope_id",
        "dataset_id",
        "accession",
        "category",
        "severity",
        "code",
        "explanation",
        "affected_operations",
        "status",
        "resolution_note",
    )
    return {key: row.get(key) for key in keys if key in row}


def _compact_file(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "file_id",
        "citation_id",
        "file_name",
        "accession",
        "dataset_ids",
        "kind",
        "priority",
        "purpose",
        "source_url",
        "availability",
        "downloadable",
        "availability_reason",
        "download",
        "verification",
    )
    return {key: row.get(key) for key in keys if key in row}


def _compact_publication(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "publication_id",
        "title",
        "authors",
        "doi",
        "doi_url",
        "year",
        "venue",
        "status",
        "related_investigations",
        "verification",
        "field_status",
    )
    return {key: row.get(key) for key in keys if key in row}


def _compact_row(row: Mapping[str, Any]) -> dict[str, Any]:
    blocked = {"raw_row_json", "context_json"}
    return {key: value for key, value in row.items() if key not in blocked}


def _page(env: Mapping[str, Any]) -> dict[str, Any]:
    return dict(env.get("meta", {}).get("page") or {})


def _safe_summary(value: Any, limit: int = 240) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


# ----------------------------------------------------------------------
# Handlers
# ----------------------------------------------------------------------
def _search_investigations(service: AnalyticsService, args: SearchInvestigationsArgs) -> ToolPayload:
    env = service.list_investigations(
        role=args.role, query=args.query, limit=args.limit, offset=args.offset
    )
    items = [_compact_investigation(row) for row in env["data"]]
    total = int(_page(env).get("total") or len(items))
    return ToolPayload(
        data={"investigations": items, "page": _page(env)},
        summary=f"{total} investigations matched the request.",
        values={"total": total},
    )


def _get_investigation(service: AnalyticsService, args: GetInvestigationArgs) -> ToolPayload:
    env = service.get_investigation(args.accession)
    data = _compact_investigation(env["data"])
    data["curated_datasets"] = [
        _compact_dataset(dataset) for dataset in env["data"].get("curated_datasets", [])
    ]
    citation_ids: list[str] = []
    for dataset in data["curated_datasets"]:
        citation_ids.extend(
            _dataset_citation_ids(service, dataset["dataset_id"], limit=2)
        )
    citation_ids = list(dict.fromkeys(citation_ids))[:8]
    return ToolPayload(
        data=data,
        summary=f"{args.accession}: {_safe_summary(data.get('title'))}",
        citation_ids=citation_ids,
        accession=args.accession,
        label=f"{args.accession} investigation",
        values={"curated_dataset_count": len(data["curated_datasets"])},
    )


def _search_datasets(service: AnalyticsService, args: SearchDatasetsArgs) -> ToolPayload:
    env = service.list_datasets(
        family=args.family,
        accession=args.accession,
        state=args.state,
        use=args.use,
        limit=args.limit,
        offset=args.offset,
    )
    items = [_compact_dataset(row) for row in env["data"]]
    citation_ids: list[str] = []
    for item in items:
        citation_ids.extend(_dataset_citation_ids(service, item["dataset_id"], limit=2))
    citation_ids = list(dict.fromkeys(citation_ids))[:10]
    total = int(_page(env).get("total") or len(items))
    return ToolPayload(
        data={"datasets": items, "page": _page(env)},
        summary=f"{total} curated datasets matched the request.",
        citation_ids=citation_ids,
        values={"total": total},
    )


def _get_dataset(service: AnalyticsService, args: GetDatasetArgs) -> ToolPayload:
    env = service.get_dataset(args.dataset_id)
    data = _compact_dataset(env["data"])
    data["serving"] = env["data"].get("serving")
    data["measurements"] = [
        {
            key: measurement.get(key)
            for key in (
                "measurement_id",
                "parameter",
                "canonical_field",
                "unit",
                "unit_status",
                "value_kind",
                "availability",
                "comparison_status",
                "quality_restrictions",
            )
            if key in measurement
        }
        for measurement in env["data"].get("measurements", [])
    ]
    citation_ids = _dataset_citation_ids(service, args.dataset_id)
    return ToolPayload(
        data=data,
        summary=f"{args.dataset_id}: {_safe_summary(data.get('display_name'))}",
        citation_ids=citation_ids,
        dataset_id=args.dataset_id,
        accession=data.get("accession"),
        label=f"{args.dataset_id} dataset",
        values={"measurement_count": data.get("measurement_count", 0)},
    )


def _get_dataset_fields(service: AnalyticsService, args: GetDatasetFieldsArgs) -> ToolPayload:
    env = service.list_dataset_fields(
        args.dataset_id,
        value_kind=args.value_kind,
        physical_quantity=args.physical_quantity,
        comparison_status=args.comparison_status,
        limit=args.limit,
        offset=args.offset,
    )
    data = dict(env["data"])
    data["fields"] = [_compact_field(row) for row in env["data"].get("fields", [])]
    citation_ids = _dataset_citation_ids(service, args.dataset_id)
    field_count = (data.get("summary") or {}).get("field_count", len(data["fields"]))
    return ToolPayload(
        data=data,
        summary=(
            f"{field_count} fields matched for {args.dataset_id}; "
            f"{len(data['fields'])} returned."
        ),
        citation_ids=citation_ids,
        dataset_id=args.dataset_id,
        accession=data.get("accession"),
        label=f"{args.dataset_id} fields",
        values={"total": data.get("total", len(data["fields"]))},
    )


def _get_dataset_limitations(
    service: AnalyticsService, args: GetDatasetLimitationsArgs
) -> ToolPayload:
    env = service.list_dataset_limitations(
        args.dataset_id,
        scope=args.scope,
        category=args.category,
        severity=args.severity,
        status=args.status,
        limit=args.limit,
        offset=args.offset,
    )
    data = dict(env["data"])
    data["limitations"] = [
        _compact_limitation(row) for row in env["data"].get("limitations", [])
    ]
    citation_ids = _dataset_citation_ids(service, args.dataset_id)
    total = (data.get("summary") or {}).get("total", len(data["limitations"]))
    return ToolPayload(
        data=data,
        summary=f"{total} limitations matched for {args.dataset_id}; {len(data['limitations'])} returned.",
        citation_ids=citation_ids,
        dataset_id=args.dataset_id,
        accession=data.get("accession"),
        label=f"{args.dataset_id} limitations",
        values={"total": total},
    )


def _get_dataset_files(service: AnalyticsService, args: GetDatasetFilesArgs) -> ToolPayload:
    env = service.list_dataset_files(
        args.dataset_id,
        kind=args.kind,
        availability=args.availability,
        limit=args.limit,
        offset=args.offset,
    )
    data = dict(env["data"])
    data["files"] = [_compact_file(row) for row in env["data"].get("files", [])]
    citation_ids = [
        row["citation_id"]
        for row in data["files"]
        if isinstance(row.get("citation_id"), str)
    ]
    return ToolPayload(
        data=data,
        summary=(
            f"{data.get('summary', {}).get('curated_files', len(data['files']))} "
            f"curated files for {args.dataset_id}."
        ),
        citation_ids=list(dict.fromkeys(citation_ids))[:12],
        dataset_id=args.dataset_id,
        accession=data.get("accession"),
        label=f"{args.dataset_id} files",
        values=dict(data.get("summary") or {}),
    )


def _get_publications(service: AnalyticsService, args: GetPublicationsArgs) -> ToolPayload:
    env = service.list_publications(
        accession=args.accession,
        dataset_id=args.dataset_id,
        query=args.query,
        year=args.year,
        status=args.status,
        limit=args.limit,
        offset=args.offset,
    )
    data = dict(env["data"])
    data["publications"] = [
        _compact_publication(row) for row in env["data"].get("publications", [])
    ]
    summary = data.get("summary") or {}
    total = summary.get("publication_count", _page(env).get("total", len(data["publications"])))
    return ToolPayload(
        data=data,
        summary=(
            f"{total} publication records matched; "
            f"{len(data['publications'])} returned."
        ),
        dataset_id=args.dataset_id,
        accession=args.accession,
        label="publication records",
        values={
            "publication_count": summary.get("publication_count", total),
            "with_doi": summary.get("with_doi"),
            "without_doi": summary.get("without_doi"),
            "year_available": summary.get("year_available"),
            "venue_available": summary.get("venue_available"),
        },
    )


def _gas_flame_statistics(
    service: AnalyticsService, args: GasFlameStatisticsArgs
) -> ToolPayload:
    env = service.gas_flame_statistics(
        args.accession, include_qualified=args.include_qualified
    )
    data = env["data"]
    pressure = data.get("pressure") or {}
    pressure_stats = pressure.get("stats") or {}
    values = {
        "canonical_rows": data.get("canonical_rows"),
        "included_rows": data.get("included_rows"),
        "excluded_qualified_rows": data.get("excluded_qualified_rows"),
        "pressure_field": pressure.get("field"),
        "pressure_unit": pressure.get("unit"),
        "pressure_non_null_count": pressure_stats.get("non_null_count"),
        "pressure_min": pressure_stats.get("min"),
        "pressure_max": pressure_stats.get("max"),
        "pressure_mean": pressure_stats.get("mean"),
        "field_metadata": {
            name: {
                "unit": payload.get("unit"),
                "value_kind": payload.get("value_kind"),
                "measurement_id": payload.get("measurement_id"),
                "status": payload.get("status"),
                "non_null_count": payload.get("non_null_count"),
            }
            for name, payload in (data.get("fields") or {}).items()
        },
    }
    summary = (
        f"{args.accession}: {data.get('included_rows')} included rows, "
        f"{data.get('excluded_qualified_rows')} excluded qualified rows, "
        f"{data.get('canonical_rows')} canonical rows; "
        f"pressure field {pressure.get('field')} in {pressure.get('unit')}."
    )
    return ToolPayload(
        data=data,
        summary=summary,
        citation_ids=list(data.get("citation_ids") or []),
        dataset_id=data.get("dataset_id"),
        accession=args.accession,
        value_kind=None,
        unit=None,
        label=f"{args.accession} gas-flame statistics",
        values=values,
    )


def _query_gas_flame_tests(
    service: AnalyticsService, args: QueryGasFlameTestsArgs
) -> ToolPayload:
    env = service.list_gas_flame_tests(
        accession=args.accession,
        flame_type=args.flame_type,
        fuel=args.fuel,
        oxygen_min=args.oxygen_min,
        oxygen_max=args.oxygen_max,
        pressure_min=args.pressure_min,
        pressure_max=args.pressure_max,
        hot_ignition=args.hot_ignition,
        extinction_mode=args.extinction_mode,
        tfp=args.tfp,
        include_qualified=args.include_qualified,
        sort=args.sort,
        order=args.order,
        limit=args.limit,
        offset=args.offset,
    )
    rows = [_compact_row(row) for row in env["data"]]
    total = int(_page(env).get("total") or len(rows))
    citation_ids = _collect_citation_ids(rows)
    return ToolPayload(
        data={
            "rows": rows,
            "page": _page(env),
            "pressure_field": _page(env).get("pressure_field"),
            "pressure_unit": _page(env).get("pressure_unit"),
            "excluded_qualified_rows": _page(env).get("excluded_qualified_rows"),
        },
        summary=f"{total} gas-flame rows matched; {len(rows)} returned in this page.",
        citation_ids=citation_ids,
        accession=args.accession,
        label="gas-flame test rows",
        values={
            "total": total,
            "returned": len(rows),
            "excluded_qualified_rows": _page(env).get("excluded_qualified_rows"),
        },
        status=ToolStatus.ok if rows else ToolStatus.empty,
    )


def _dataset_field_statistics(
    service: AnalyticsService, args: DatasetFieldStatisticsArgs
) -> ToolPayload:
    env = service.dataset_field_statistics(
        args.dataset_id,
        fields=args.fields,
        include_qualified=args.include_qualified,
    )
    data = env["data"]
    field_values: dict[str, Any] = {}
    parts: list[str] = []
    for name, payload in (data.get("fields") or {}).items():
        field_values[name] = {
            "status": payload.get("status"),
            "non_null_count": payload.get("non_null_count"),
            "missing_count": payload.get("missing_count"),
            "min": payload.get("min"),
            "max": payload.get("max"),
            "mean": payload.get("mean"),
            "median": payload.get("median"),
            "unit": payload.get("unit"),
            "value_kind": payload.get("value_kind"),
        }
        if payload.get("status") == "available":
            parts.append(
                f"{name}: {payload.get('non_null_count')} non-null, "
                f"min {payload.get('min')}, max {payload.get('max')} "
                f"{payload.get('unit') or ''}".strip()
            )
        else:
            parts.append(f"{name}: no non-null values")
    return ToolPayload(
        data=data,
        summary="; ".join(parts)[:600] or "No fields returned.",
        citation_ids=list(data.get("citation_ids") or []),
        dataset_id=args.dataset_id,
        accession=data.get("accession"),
        value_kind=None,
        unit=None,
        label=f"{args.dataset_id} field statistics",
        values={"fields": field_values, "included_rows": data.get("included_rows")},
    )


def _query_material_tests(
    service: AnalyticsService, args: QueryMaterialTestsArgs
) -> ToolPayload:
    env = service.list_material_tests(
        accession=args.accession,
        material=args.material,
        flow_restrictor=args.flow_restrictor,
        o2_min=args.o2_min,
        o2_max=args.o2_max,
        limit=args.limit,
        offset=args.offset,
    )
    rows = [_compact_row(row) for row in env["data"]]
    total = int(_page(env).get("total") or len(rows))
    return ToolPayload(
        data={"rows": rows, "page": _page(env)},
        summary=f"{total} material test rows matched; {len(rows)} returned.",
        citation_ids=_collect_citation_ids(rows),
        accession=args.accession,
        label="material test rows",
        values={"total": total, "returned": len(rows)},
        status=ToolStatus.ok if rows else ToolStatus.empty,
    )


def _query_droplet_tests(
    service: AnalyticsService, args: QueryDropletTestsArgs
) -> ToolPayload:
    env = service.list_droplet_tests(
        accession=args.accession,
        fuel=args.fuel,
        pressure_min=args.pressure_min,
        pressure_max=args.pressure_max,
        limit=args.limit,
        offset=args.offset,
    )
    rows = [_compact_row(row) for row in env["data"]]
    total = int(_page(env).get("total") or len(rows))
    return ToolPayload(
        data={"rows": rows, "page": _page(env)},
        summary=f"{total} droplet test rows matched; {len(rows)} returned.",
        citation_ids=_collect_citation_ids(rows),
        accession=args.accession,
        label="droplet test rows",
        values={"total": total, "returned": len(rows)},
        status=ToolStatus.ok if rows else ToolStatus.empty,
    )


def _get_telemetry_runs(
    service: AnalyticsService, args: GetTelemetryRunsArgs
) -> ToolPayload:
    env = service.list_telemetry_runs(
        accession=args.accession,
        export_kind=args.export_kind,
        limit=args.limit,
        offset=args.offset,
    )
    runs = [_compact_row(row) for row in env["data"]]
    total = int(_page(env).get("total") or len(runs))
    return ToolPayload(
        data={"runs": runs, "page": _page(env)},
        summary=f"{total} telemetry runs returned; {len(runs)} in this page.",
        citation_ids=_provenance_citation_ids(service, env.get("provenance", [])),
        accession=args.accession,
        label=f"{args.accession} telemetry runs",
        values={"total": total, "returned": len(runs)},
        status=ToolStatus.ok if runs else ToolStatus.empty,
    )


def _series_summary(points: Sequence[Mapping[str, Any]], channels: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for channel in channels:
        key = channel.get("channel_name_canonical")
        if not key:
            continue
        values = [
            point[key]
            for point in points
            if isinstance(point.get(key), (int, float))
        ]
        summary.append(
            {
                "channel_name_canonical": key,
                "unit": channel.get("unit"),
                "quality_flags": channel.get("quality_flags", []),
                "point_count": len(values),
                "min": min(values) if values else None,
                "max": max(values) if values else None,
                "mean": (sum(values) / len(values)) if values else None,
                "first": values[0] if values else None,
                "last": values[-1] if values else None,
            }
        )
    return summary


def _query_telemetry_series(
    service: AnalyticsService, args: QueryTelemetrySeriesArgs
) -> ToolPayload:
    env = service.get_telemetry_series(
        args.run_id,
        args.channels,
        args.start_ms,
        args.end_ms,
        max_points=args.max_points,
    )
    data = env["data"]
    points = data.get("points") or []
    channel_summary = _series_summary(points, data.get("channels") or [])
    return ToolPayload(
        data={
            "run_id": data.get("run_id"),
            "time_unit": data.get("time_unit"),
            "start_ms": data.get("start_ms"),
            "end_ms": data.get("end_ms"),
            "returned_points": data.get("returned_points"),
            "excluded_sentinel_rows": data.get("excluded_sentinel_rows"),
            "channels": channel_summary,
            "points_sample": list(points[:20]),
        },
        summary=(
            f"{data.get('returned_points')} telemetry points across "
            f"{len(channel_summary)} channels."
        ),
        citation_ids=_provenance_citation_ids(service, env.get("provenance", [])),
        accession="PSI-100",
        label="telemetry series summary",
        values={"returned_points": data.get("returned_points"), "channels": channel_summary},
        status=ToolStatus.ok if points else ToolStatus.empty,
    )


def _get_smoke_runs(service: AnalyticsService, args: GetSmokeRunsArgs) -> ToolPayload:
    env = service.list_smoke_runs(
        accession=args.accession, limit=args.limit, offset=args.offset
    )
    runs = [_compact_row(row) for row in env["data"]]
    total = int(_page(env).get("total") or len(runs))
    return ToolPayload(
        data={"runs": runs, "page": _page(env)},
        summary=f"{total} smoke runs returned; {len(runs)} in this page.",
        citation_ids=_provenance_citation_ids(service, env.get("provenance", [])),
        accession=args.accession,
        label=f"{args.accession} smoke runs",
        values={"total": total, "returned": len(runs)},
        status=ToolStatus.ok if runs else ToolStatus.empty,
    )


def _query_smoke_series(
    service: AnalyticsService, args: QuerySmokeSeriesArgs
) -> ToolPayload:
    env = service.get_smoke_series(
        args.run_id,
        args.channels,
        args.start_s,
        args.end_s,
        max_points=args.max_points,
    )
    data = env["data"]
    points = data.get("points") or []
    channel_summary = _series_summary(points, data.get("channels") or [])
    return ToolPayload(
        data={
            "run_id": data.get("run_id"),
            "time_unit": data.get("time_unit"),
            "start_s": data.get("start_s"),
            "end_s": data.get("end_s"),
            "returned_points": data.get("returned_points"),
            "excluded_sentinel_rows": data.get("excluded_sentinel_rows"),
            "excluded_invalid_rows": data.get("excluded_invalid_rows"),
            "channels": channel_summary,
            "points_sample": list(points[:20]),
        },
        summary=(
            f"{data.get('returned_points')} smoke points across "
            f"{len(channel_summary)} channels."
        ),
        citation_ids=_provenance_citation_ids(service, env.get("provenance", [])),
        accession="PSI-101",
        label="smoke series summary",
        values={"returned_points": data.get("returned_points"), "channels": channel_summary},
        status=ToolStatus.ok if points else ToolStatus.empty,
    )


def _evaluate_comparison(
    service: AnalyticsService, args: EvaluateComparisonArgs
) -> ToolPayload:
    conditions = args.validated_conditions
    env = service.compare(args.left, args.right, conditions=conditions)
    data = env["data"]
    paired = data.get("paired_values") or {}
    integrity = data.get("integrity") or {}
    reasons = [reason.get("code") for reason in data.get("reasons", [])]
    payload = {
        "left": data.get("left"),
        "right": data.get("right"),
        "status": data.get("status"),
        "rule_id": data.get("rule_id"),
        "reasons": data.get("reasons"),
        "required_conditions": data.get("required_conditions"),
        "warnings": data.get("warnings"),
        "scientific_justification": data.get("scientific_justification"),
        "integrity": {
            "status": integrity.get("status"),
            "failures": integrity.get("failures"),
            "messages": integrity.get("messages"),
        },
        "paired_values": {
            "available": paired.get("available"),
            "status": paired.get("status"),
            "alignment": paired.get("alignment"),
            "exclusions": paired.get("exclusions"),
        },
    }
    citation_ids = _provenance_citation_ids(
        service, data.get("source_references", [])
    )
    return ToolPayload(
        data=payload,
        summary=(
            f"Comparison status {data.get('status')}; paired values available: "
            f"{paired.get('available')}. Reasons: {', '.join(str(r) for r in reasons)}."
        ),
        citation_ids=citation_ids,
        accession=(data.get("left") or {}).get("accession"),
        dataset_id=(data.get("left") or {}).get("dataset_id"),
        label="comparison decision",
        values={
            "status": data.get("status"),
            "reason_codes": reasons,
            "paired_values_available": paired.get("available"),
            "integrity_status": integrity.get("status"),
        },
    )


def _resolve_citation(service: AnalyticsService, args: ResolveCitationArgs) -> ToolPayload:
    env = service.get_citation(args.citation_id)
    data = env["data"]
    source = data.get("source") or {}
    availability = data.get("availability") or {}
    return ToolPayload(
        data=data,
        summary=(
            f"{args.citation_id}: {source.get('file_name')} "
            f"({availability.get('status')})."
        ),
        citation_ids=[args.citation_id],
        accession=data.get("accession"),
        dataset_id=(data.get("dataset_ids") or [None])[0],
        label="resolved citation",
        values={
            "citation_id": args.citation_id,
            "availability": availability.get("status"),
            "downloadable": availability.get("downloadable"),
            "verification_status": (data.get("verification") or {}).get("status"),
        },
    )


def _get_provenance(service: AnalyticsService, args: GetProvenanceArgs) -> ToolPayload:
    env = service.resolve_provenance(
        args.accession,
        args.file_name,
        sheet=args.sheet,
        row=args.row,
    )
    data = env["data"]
    citation_ids = _provenance_citation_ids(service, env.get("provenance", []))
    return ToolPayload(
        data=data,
        summary=(
            f"Provenance resolved for {args.accession} / {args.file_name}"
            + (f" row {args.row}" if args.row else "")
            + "."
        ),
        citation_ids=citation_ids,
        accession=args.accession,
        label="source provenance",
        values={
            "citation_id": data.get("citation_id"),
            "sha256": data.get("sha256"),
            "row_verified": data.get("row_verified"),
        },
    )


def _get_measurements(
    service: AnalyticsService, args: GetMeasurementsArgs
) -> ToolPayload:
    env = service.list_measurements(
        accession=args.accession,
        dataset_id=args.dataset_id,
        family=args.family,
        comparison_status=args.comparison_status,
        serving_state=args.serving_state,
        use=args.use,
        limit=args.limit,
        offset=args.offset,
    )
    items = env["data"]
    total = int(_page(env).get("total") or len(items))
    compact = [
        {
            key: item.get(key)
            for key in (
                "measurement_id",
                "dataset_id",
                "accession",
                "experiment_family",
                "parameter",
                "canonical_field",
                "canonical_channel",
                "physical_quantity",
                "unit",
                "unit_status",
                "value_kind",
                "calibration_status",
                "availability",
                "comparison_status",
                "quality_restrictions",
                "serving",
            )
            if key in item
        }
        for item in items
    ]
    return ToolPayload(
        data={"measurements": compact, "page": _page(env)},
        summary=f"{total} measurements matched; {len(compact)} returned.",
        accession=args.accession,
        dataset_id=args.dataset_id,
        label="measurement definitions",
        values={"total": total, "returned": len(compact)},
        status=ToolStatus.ok if compact else ToolStatus.empty,
    )


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "search_investigations",
        "Search the verified NASA PSI investigation catalog by accession, acronym, title, or MVP role.",
        SearchInvestigationsArgs,
        _search_investigations,
        "catalog",
    ),
    ToolSpec(
        "get_investigation",
        "Get one investigation and its curated datasets.",
        GetInvestigationArgs,
        _get_investigation,
        "catalog",
    ),
    ToolSpec(
        "search_datasets",
        "Search the nine curated datasets by family, accession, or serving state.",
        SearchDatasetsArgs,
        _search_datasets,
        "catalog",
    ),
    ToolSpec(
        "get_dataset",
        "Get one curated dataset, its serving states, and its measurements.",
        GetDatasetArgs,
        _get_dataset,
        "catalog",
    ),
    ToolSpec(
        "get_dataset_fields",
        "List verified field definitions, units, value kinds, and missingness.",
        GetDatasetFieldsArgs,
        _get_dataset_fields,
        "metadata",
    ),
    ToolSpec(
        "get_dataset_limitations",
        "List dataset, file, measurement, and comparison limitations.",
        GetDatasetLimitationsArgs,
        _get_dataset_limitations,
        "metadata",
    ),
    ToolSpec(
        "get_dataset_files",
        "List curated source files, citations, checksums, and availability.",
        GetDatasetFilesArgs,
        _get_dataset_files,
        "provenance",
    ),
    ToolSpec(
        "get_publications",
        "Search verified publication registry records. Year and venue are unavailable.",
        GetPublicationsArgs,
        _get_publications,
        "publications",
    ),
    ToolSpec(
        "gas_flame_statistics",
        "Deterministic counts, pressure, oxygen, temperature, and field summaries for PSI-10 or PSI-159.",
        GasFlameStatisticsArgs,
        _gas_flame_statistics,
        "numerical",
    ),
    ToolSpec(
        "query_gas_flame_tests",
        "Query bounded gas-flame test rows with strict filters and row citations.",
        QueryGasFlameTestsArgs,
        _query_gas_flame_tests,
        "rows",
    ),
    ToolSpec(
        "dataset_field_statistics",
        "Deterministic non-null counts, min, max, mean, and median for allowlisted canonical fields.",
        DatasetFieldStatisticsArgs,
        _dataset_field_statistics,
        "numerical",
    ),
    ToolSpec(
        "query_material_tests",
        "Query bounded BASS/BASS-II material test rows with row citations.",
        QueryMaterialTestsArgs,
        _query_material_tests,
        "rows",
    ),
    ToolSpec(
        "query_droplet_tests",
        "Query bounded FLEX droplet test rows with row citations.",
        QueryDropletTestsArgs,
        _query_droplet_tests,
        "rows",
    ),
    ToolSpec(
        "get_telemetry_runs",
        "List separate SAFFIRE-III telemetry runs. Runs are never concatenated.",
        GetTelemetryRunsArgs,
        _get_telemetry_runs,
        "time_series",
    ),
    ToolSpec(
        "query_telemetry_series",
        "Query a bounded telemetry time range and return deterministic channel summaries.",
        QueryTelemetrySeriesArgs,
        _query_telemetry_series,
        "time_series",
    ),
    ToolSpec(
        "get_smoke_runs",
        "List separate SAME-R smoke runs. Runs are never concatenated.",
        GetSmokeRunsArgs,
        _get_smoke_runs,
        "time_series",
    ),
    ToolSpec(
        "query_smoke_series",
        "Query a bounded smoke time range and return deterministic channel summaries.",
        QuerySmokeSeriesArgs,
        _query_smoke_series,
        "time_series",
    ),
    ToolSpec(
        "evaluate_comparison",
        "Evaluate a registered comparison, its conditions, integrity, and paired-value availability.",
        EvaluateComparisonArgs,
        _evaluate_comparison,
        "comparison",
    ),
    ToolSpec(
        "resolve_citation",
        "Resolve one Phase 4 file or row citation and preserve its verification and availability.",
        ResolveCitationArgs,
        _resolve_citation,
        "provenance",
    ),
    ToolSpec(
        "get_provenance",
        "Resolve a canonical source file or row to its provenance and citation.",
        GetProvenanceArgs,
        _get_provenance,
        "provenance",
    ),
    ToolSpec(
        "get_measurements",
        "List registered measurement definitions, units, value kinds, and serving states.",
        GetMeasurementsArgs,
        _get_measurements,
        "metadata",
    ),
)

TOOL_INDEX: dict[str, ToolSpec] = {spec.name: spec for spec in TOOL_SPECS}


def _sanitize_arguments(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return "..."
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key.lower() in SECRET_KEYS:
                result[key] = "[redacted]"
            else:
                result[key] = _sanitize_arguments(item, depth + 1)
        return result
    if isinstance(value, list):
        return [_sanitize_arguments(item, depth + 1) for item in value[:20]]
    if isinstance(value, str) and len(value) > MAX_LOG_ARGUMENT_CHARS:
        return value[: MAX_LOG_ARGUMENT_CHARS - 1] + "…"
    return value


def _result_hash(data: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        data, sort_keys=True, ensure_ascii=False, default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ToolRegistry:
    """Execute allowlisted tools with call limits, validation, and logging."""

    def __init__(
        self,
        service: AnalyticsService,
        *,
        max_tool_calls: int = 6,
        timeout_seconds: float = 20.0,
        request_id: str | None = None,
    ):
        self.service = service
        self.max_tool_calls = max_tool_calls
        self.timeout_seconds = timeout_seconds
        self.request_id = request_id
        self._calls: list[ToolResult] = []
        self._deadline = time.monotonic() + timeout_seconds

    @property
    def calls(self) -> list[ToolResult]:
        return list(self._calls)

    def names(self) -> list[str]:
        return sorted(TOOL_INDEX)

    def describe(self) -> list[dict[str, Any]]:
        return [spec.describe() for spec in TOOL_SPECS]

    def execute(
        self, name: str, arguments: Mapping[str, Any] | None = None
    ) -> ToolResult:
        started = time.perf_counter()
        call_id = f"call_{len(self._calls) + 1}"
        raw_arguments = dict(arguments or {})
        spec = TOOL_INDEX.get(name)

        def rejected(message: str) -> ToolResult:
            duration = (time.perf_counter() - started) * 1000
            result = ToolResult(
                call_id=call_id,
                tool=name,
                arguments=raw_arguments,
                status=ToolStatus.rejected,
                duration_ms=duration,
                data={"error": message},
                summary=message,
                error=message,
            )
            self._calls.append(result)
            self._log(result)
            return result

        if spec is None:
            return rejected("tool is not in the approved allowlist")
        if len(self._calls) >= self.max_tool_calls:
            return rejected("assistant tool-call limit reached")
        if time.monotonic() > self._deadline:
            return rejected("assistant tool timeout reached")
        if not isinstance(raw_arguments, Mapping):
            return rejected("tool arguments must be an object")

        try:
            args = spec.args_model.model_validate(raw_arguments)
        except ValidationError as exc:
            details = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors(include_url=False)[:5]
            )
            return rejected(f"invalid tool arguments: {details}")

        try:
            payload = spec.handler(self.service, args)
        except (InvalidQueryError, NotFoundError) as exc:
            duration = (time.perf_counter() - started) * 1000
            result = ToolResult(
                call_id=call_id,
                tool=name,
                arguments=args.model_dump(mode="json"),
                status=ToolStatus.rejected,
                duration_ms=duration,
                data={"error": str(exc)},
                summary=str(exc),
                error=str(exc),
            )
            self._calls.append(result)
            self._log(result)
            return result
        except AnalyticsError as exc:
            duration = (time.perf_counter() - started) * 1000
            message = f"{type(exc).__name__}: {exc}"
            result = ToolResult(
                call_id=call_id,
                tool=name,
                arguments=args.model_dump(mode="json"),
                status=ToolStatus.failed,
                duration_ms=duration,
                data={"error": message},
                summary=message,
                error=message,
            )
            self._calls.append(result)
            self._log(result)
            return result
        except Exception as exc:  # pragma: no cover - defensive boundary
            duration = (time.perf_counter() - started) * 1000
            message = f"tool execution failed ({type(exc).__name__})"
            result = ToolResult(
                call_id=call_id,
                tool=name,
                arguments=args.model_dump(mode="json"),
                status=ToolStatus.failed,
                duration_ms=duration,
                data={"error": message},
                summary=message,
                error=message,
            )
            self._calls.append(result)
            self._log(result)
            return result

        encoded = json.dumps(
            payload.data, sort_keys=True, ensure_ascii=False, default=str
        ).encode("utf-8")
        duration = (time.perf_counter() - started) * 1000
        if len(encoded) > MAX_TOOL_RESULT_BYTES:
            message = "tool result exceeded the bounded response size"
            result = ToolResult(
                call_id=call_id,
                tool=name,
                arguments=args.model_dump(mode="json"),
                status=ToolStatus.failed,
                duration_ms=duration,
                data={"error": message},
                summary=message,
                error=message,
            )
            self._calls.append(result)
            self._log(result)
            return result

        result = ToolResult(
            call_id=call_id,
            tool=name,
            arguments=args.model_dump(mode="json"),
            status=payload.status,
            duration_ms=duration,
            data=payload.data,
            summary=payload.summary,
            citation_ids=list(dict.fromkeys(payload.citation_ids)),
            dataset_id=payload.dataset_id,
            accession=payload.accession,
            value_kind=payload.value_kind,
            unit=payload.unit,
            label=payload.label,
            values=payload.values,
            result_hash=_result_hash(payload.data),
        )
        self._calls.append(result)
        self._log(result)
        return result

    def _log(self, result: ToolResult) -> None:
        LOGGER.info(
            "assistant_tool tool=%s status=%s duration_ms=%.2f request_id=%s arguments=%s",
            result.tool,
            result.status.value,
            result.duration_ms,
            self.request_id or "unknown",
            json.dumps(_sanitize_arguments(result.arguments), sort_keys=True),
            extra={
                "request_id": self.request_id,
                "status": result.status.value,
                "duration_ms": round(result.duration_ms, 2),
            },
        )
