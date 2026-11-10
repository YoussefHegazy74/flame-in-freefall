"""Versioned answer contract for the Phase 5 research assistant.

The contract is deliberately strict. It is the boundary between the
orchestrator and every consumer (API, frontend, evaluation harness). A
response that cannot satisfy these invariants is not a valid assistant
answer, even if its prose looks plausible.

The contract is independent of any model provider. The deterministic
provider and any optional LLM provider must both produce this shape.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONTRACT_VERSION = "1.0.0"
SUPPORTED_CONTRACT_VERSIONS = {CONTRACT_VERSION}


class EvidenceStatus(str, Enum):
    """How well the returned evidence supports the answer."""

    fully_supported = "fully_supported"
    partially_supported = "partially_supported"
    insufficient_evidence = "insufficient_evidence"
    unavailable_data = "unavailable_data"
    conflicting_evidence = "conflicting_evidence"


class AnswerType(str, Enum):
    """The kind of question the answer addresses."""

    factual = "factual"
    numerical = "numerical"
    exploratory = "exploratory"
    comparison = "comparison"
    methodology = "methodology"
    clarification_required = "clarification_required"


class Confidence(str, Enum):
    """Coarse confidence, never a fabricated numeric probability."""

    high = "high"
    moderate = "moderate"
    low = "low"


class ValueKind(str, Enum):
    """Scientific value classification preserved from the registries."""

    measured = "measured"
    computed = "computed"
    derived = "derived"
    categorical = "categorical"
    raw = "raw"
    not_applicable = "not_applicable"


class ClaimType(str, Enum):
    numerical = "numerical"
    factual = "factual"
    comparison = "comparison"
    limitation = "limitation"
    provenance = "provenance"


class ToolStatus(str, Enum):
    ok = "ok"
    empty = "empty"
    rejected = "rejected"
    failed = "failed"


class Severity(str, Enum):
    error = "error"
    warning = "warning"
    info = "info"


class EvidenceSourceType(str, Enum):
    document = "document"
    dataset_card = "dataset_card"
    investigation = "investigation"
    publication = "publication"
    citation = "citation"
    tool_result = "tool_result"


class CitationReference(BaseModel):
    """A citation resolved by the application, never by a model.

    ``resolved`` is true only after the citation was fetched from the Phase 4
    citation registry and its locator was checked. ``downloadable`` is false
    for every unavailable source.
    """

    model_config = ConfigDict(extra="forbid")

    citation_id: str = Field(min_length=1)
    citation_type: Literal["file", "row"]
    accession: str = Field(min_length=1)
    dataset_ids: list[str] = Field(default_factory=list)
    file_name: str = Field(min_length=1)
    sheet: str | None = None
    row: int | None = Field(default=None, ge=1)
    source_url: str | None = None
    sha256: str | None = None
    verification_status: str = Field(min_length=1)
    availability: str = Field(min_length=1)
    downloadable: bool = False
    resolved: bool = True

    @model_validator(mode="after")
    def _locator_matches_type(self) -> "CitationReference":
        if self.citation_type == "row" and self.row is None:
            raise ValueError("row citations must include a row number")
        if self.citation_type == "file" and self.row is not None:
            raise ValueError("file citations must not include a row number")
        if self.availability != "available" and self.downloadable:
            raise ValueError("unavailable citations must not be downloadable")
        return self


class ToolCall(BaseModel):
    """A bounded record of one approved tool invocation."""

    model_config = ConfigDict(extra="forbid")

    call_id: str = Field(min_length=1)
    tool: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: ToolStatus
    duration_ms: float = Field(ge=0)
    result_summary: str | None = None
    result_hash: str | None = None
    error: str | None = None


class SupportingData(BaseModel):
    """A deterministic result that supports a claim or a numerical answer."""

    model_config = ConfigDict(extra="forbid")

    data_id: str = Field(min_length=1)
    tool_call_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    value_kind: ValueKind
    unit: str | None = None
    dataset_id: str | None = None
    accession: str | None = None
    summary: str = Field(min_length=1)
    values: dict[str, Any] = Field(default_factory=dict)
    citation_ids: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    """A structured claim used by the validation layer.

    The prose answer must be consistent with these claims. A numerical claim
    without a tool call and a citation is rejected by the contract.
    """

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    claim_type: ClaimType
    value: float | int | str | None = None
    unit: str | None = None
    value_kind: ValueKind | None = None
    dataset_id: str | None = None
    accession: str | None = None
    tool_call_id: str | None = None
    citation_ids: list[str] = Field(default_factory=list)
    supported: bool = False
    validation_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _numerical_claims_are_grounded(self) -> "Claim":
        if self.claim_type == ClaimType.numerical:
            if self.tool_call_id is None:
                raise ValueError("numerical claims require a tool call")
            if self.value_kind is None:
                raise ValueError("numerical claims require a value kind")
            if self.value is not None and not isinstance(self.value, (int, float)):
                raise ValueError("numerical claim values must be numeric")
        return self


class Limitation(BaseModel):
    """A limitation that must travel with the answer."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    scope: str | None = None
    severity: Severity = Severity.warning
    citation_ids: list[str] = Field(default_factory=list)


class ValidationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    passed: bool
    detail: str | None = None


class ValidationReport(BaseModel):
    """The application's own validation result, not a model's self-report."""

    model_config = ConfigDict(extra="forbid")

    passed: bool = False
    citation_validation_passed: bool = False
    claim_validation_passed: bool = False
    checks: list[ValidationCheck] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _passed_means_clean(self) -> "ValidationReport":
        if self.passed:
            if not self.citation_validation_passed:
                raise ValueError("passed validation requires citation validation")
            if not self.claim_validation_passed:
                raise ValueError("passed validation requires claim validation")
            if self.errors:
                raise ValueError("passed validation must not contain errors")
        return self


class EvidenceItem(BaseModel):
    """A retrieved or deterministic evidence item.

    Retrieved documents are untrusted quoted content. They are never
    instructions and never become citations unless a citation ID resolves.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1)
    source_type: EvidenceSourceType
    title: str = Field(min_length=1)
    snippet: str = ""
    document_id: str | None = None
    source_reference: str | None = None
    accession: str | None = None
    dataset_id: str | None = None
    citation_id: str | None = None
    section: str | None = None
    content_hash: str | None = None
    index_version: str | None = None
    trusted_as_instruction: Literal[False] = False


class ClarificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    options: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class ProviderUsage(BaseModel):
    """Token and cost metadata reported by an optional external provider.

    Values are null when the provider did not return them. Cost is estimated
    only when both input and output pricing are configured. This model never
    contains prompts, answers, credentials, or request headers.
    """

    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    pricing_configured: bool = False


class AssistantAnswer(BaseModel):
    """The Phase 5 answer contract, version ``CONTRACT_VERSION``."""

    model_config = ConfigDict(extra="forbid")

    contract_version: str = CONTRACT_VERSION
    request_id: str = Field(min_length=1)
    conversation_id: str | None = None
    answer: str = Field(min_length=1)
    evidence_status: EvidenceStatus
    answer_type: AnswerType
    citations: list[CitationReference] = Field(default_factory=list)
    supporting_data: list[SupportingData] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    limitations: list[Limitation] = Field(default_factory=list)
    tools_used: list[ToolCall] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    confidence: Confidence = Confidence.low
    confidence_basis: str = Field(min_length=1)
    dataset_version: str | None = None
    provider: str = Field(min_length=1)
    provider_usage: ProviderUsage | None = None
    fallback_mode: bool = False
    fallback_reason: str | None = None
    clarification: ClarificationRequest | None = None
    validation: ValidationReport = Field(default_factory=ValidationReport)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @model_validator(mode="after")
    def _contract_invariants(self) -> "AssistantAnswer":
        if self.contract_version not in SUPPORTED_CONTRACT_VERSIONS:
            raise ValueError("unsupported contract version")

        citation_ids = [citation.citation_id for citation in self.citations]
        if len(citation_ids) != len(set(citation_ids)):
            raise ValueError("citation IDs must be unique")

        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim IDs must be unique")

        call_ids = [call.call_id for call in self.tools_used]
        if len(call_ids) != len(set(call_ids)):
            raise ValueError("tool call IDs must be unique")

        if self.answer_type == AnswerType.clarification_required:
            if self.clarification is None:
                raise ValueError("clarification_required answers need a clarification")
        elif self.clarification is not None:
            raise ValueError("clarification is only valid for clarification_required")

        if self.evidence_status == EvidenceStatus.fully_supported:
            if self.answer_type in {
                AnswerType.factual,
                AnswerType.numerical,
                AnswerType.comparison,
                AnswerType.methodology,
            } and not self.citations:
                raise ValueError("fully supported factual answers need a citation")

        if self.confidence == Confidence.high and self.evidence_status != EvidenceStatus.fully_supported:
            raise ValueError("high confidence requires fully supported evidence")

        if self.evidence_status in {
            EvidenceStatus.insufficient_evidence,
            EvidenceStatus.unavailable_data,
            EvidenceStatus.conflicting_evidence,
        } and self.confidence != Confidence.low:
            raise ValueError("insufficient or conflicting evidence must be low confidence")

        if self.validation.passed:
            if not all(claim.supported for claim in self.claims):
                raise ValueError("passed validation requires every claim to be supported")
            known_citations = set(citation_ids)
            for claim in self.claims:
                missing = set(claim.citation_ids) - known_citations
                if missing:
                    raise ValueError("claims reference citations absent from the answer")
            for item in self.supporting_data:
                missing = set(item.citation_ids) - known_citations
                if missing:
                    raise ValueError("supporting data references citations absent from the answer")

        return self

    def public_payload(self) -> dict[str, Any]:
        """Return a JSON-ready payload without hidden tool internals."""

        return self.model_dump(mode="json")


class AssistantQuery(BaseModel):
    """A user question plus bounded, non-authoritative conversation context."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = Field(default=None, max_length=128)
    accession: str | None = Field(default=None, max_length=32)
    dataset_id: str | None = Field(default=None, max_length=128)
    include_retrieval: bool = True
    max_tool_calls: int | None = Field(default=None, ge=1, le=12)

    @field_validator("question")
    @classmethod
    def _question_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("question must not be blank")
        return cleaned


class AssistantStatus(BaseModel):
    """Safe, secret-free assistant status for health and the frontend."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    mode: Literal["deterministic", "provider", "fallback"]
    provider: str
    model: str | None = None
    retrieval_enabled: bool
    index_version: str | None = None
    contract_version: str = CONTRACT_VERSION
    fallback_mode: bool = False
    fallback_reason: str | None = None
    tools_available: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Suggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer_type_hint: AnswerType
