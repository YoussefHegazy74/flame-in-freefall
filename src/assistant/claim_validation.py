"""Deterministic claim and answer validation for the Phase 5 assistant.

Validation is fail-closed. It is the last line of defence between a
deterministic draft and a public answer:

* Every structured claim must link to an approved tool call.
* Every numerical claim value must appear in that tool's result.
* Every claim citation must be one of the resolved citations in the answer.
* Claim units and value kinds must match the values the tool returned.
* The prose answer may not introduce a number that no tool returned.
* Dangerous overclaims, secrets, and injection markers are rejected.

The validator never calls a model. A model rephrase is checked separately by
:func:`src.assistant.providers.validate_rephrase` and then this validator is
run again on the rephrased text.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from src.assistant.contract import (
    Claim,
    ClaimType,
    SupportingData,
    ToolStatus,
    ValidationCheck,
    ValueKind,
)

NUMBER_RE = re.compile(
    r"(?<![\w.-])(-?\d+(?:\.\d+)?)(?:[eE]([+-]?\d+))?(?!\w|\.\d)"
)
CITATION_RE = re.compile(r"cit_[fr]_[A-Za-z0-9_-]+")
ACCESSION_RE = re.compile(r"\bPSI-\d{2,4}\b", re.IGNORECASE)
DATASET_RE = re.compile(r"\bpsi-\d{2,4}-[a-z0-9-]+\b", re.IGNORECASE)
PHASE_RE = re.compile(r"\b(?:phase|version|v)\s*\d+(?:\.\d+)*\b", re.IGNORECASE)
IDENTIFIER_RE = re.compile(
    r"\b(?:call|claim|data|ev)_[A-Za-z0-9_]+\b"
    r"|\b[A-Za-z][A-Za-z0-9_]*[A-Za-z][0-9a-f]{6,}\b"
    r"|\b[A-Za-z][A-Za-z0-9_]*_c[0-9a-f]{6,}\b"
)
SECRET_RE = re.compile(
    r"\bsk-[A-Za-z0-9_-]{8,}"
    r"|(?i:api[_ -]?key|secret|password)\s*[:=]\s*\S+"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)

DANGEROUS_ASSERTIONS = (
    re.compile(r"(?i)\b(?:the\s+)?fire[- ]risk\s+score\s+(?:is|was|equals)\b"),
    re.compile(r"(?i)\b(?:the\s+)?materials?\s+(?:is|are)\s+ranked\b"),
    re.compile(r"(?i)\b(?:guarantees?|ensures?)\s+(?:spacecraft\s+)?fire[- ]safety\b"),
    re.compile(r"(?i)\b(?:proves?|confirms?)\s+that\b.{0,80}\bcauses?\b"),
    re.compile(r"(?i)\bcauses?\s+(?:the|a|an|fire|ignition)\b"),
    re.compile(
        r"(?i)\bthe\s+(?:difference|increase|decrease)\s+is\s+(?:caused|due)\s+(?:by|to)\b"
    ),
)
NEGATION_RE = re.compile(
    r"(?i)\b(?:not|no|never|cannot|can't|does not|do not|without|isn't|aren't)\b"
)

COUNT_UNITS = {
    "count",
    "datasets",
    "entries",
    "fields",
    "files",
    "investigations",
    "items",
    "limitations",
    "measurements",
    "publication records",
    "publications",
    "records",
    "rows",
    "runs",
    "values",
}


@dataclass
class ClaimValidationResult:
    passed: bool = True
    claims: list[Claim] = field(default_factory=list)
    checks: list[ValidationCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ungrounded_numbers: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.passed = False
        if message not in self.errors:
            self.errors.append(message)

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def check(self, name: str, passed: bool, detail: str | None = None) -> None:
        self.checks.append(ValidationCheck(name=name, passed=passed, detail=detail))
        if not passed:
            self.fail(detail or name)


def normalize_number(token: str | float | int) -> float | None:
    try:
        value = float(token)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


def _numbers_in_text(text: str) -> list[float]:
    values: list[float] = []
    for match in NUMBER_RE.finditer(text or ""):
        token = match.group(1)
        exponent = match.group(2)
        if exponent is not None:
            token = f"{token}e{int(exponent)}"
        value = normalize_number(token)
        if value is not None:
            values.append(value)
    return values


def strip_identifiers(text: str) -> str:
    """Remove IDs, accessions, dataset IDs, and code-like tokens.

    Those tokens legitimately contain digits but are not numerical claims.
    """

    cleaned = CITATION_RE.sub(" ", text or "")
    cleaned = DATASET_RE.sub(" ", cleaned)
    cleaned = ACCESSION_RE.sub(" ", cleaned)
    cleaned = PHASE_RE.sub(" ", cleaned)
    cleaned = IDENTIFIER_RE.sub(" ", cleaned)
    return cleaned


def answer_numbers(text: str) -> list[float]:
    return _numbers_in_text(strip_identifiers(text))


def _leaves_with_parent(container: Any) -> Iterable[tuple[Any, Mapping[str, Any]]]:
    """Yield leaves plus their immediate parent mapping."""

    def visit(value: Any, parent: Mapping[str, Any], depth: int) -> Iterable[tuple[Any, Mapping[str, Any]]]:
        if depth > 8:
            return
        if isinstance(value, Mapping):
            for key, item in value.items():
                if isinstance(item, (Mapping, list, tuple)):
                    yield from visit(item, value, depth + 1)
                else:
                    yield item, value
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for item in value:
                if isinstance(item, (Mapping, list, tuple)):
                    yield from visit(item, parent, depth + 1)
                else:
                    yield item, parent

    yield from visit(container, {}, 0)


def _numbers_from_strings(value: Any, depth: int = 0) -> list[float]:
    found: list[float] = []
    if depth > 8:
        return found
    if isinstance(value, str):
        found.extend(_numbers_in_text(value))
    elif isinstance(value, Mapping):
        for item in value.values():
            found.extend(_numbers_from_strings(item, depth + 1))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found.extend(_numbers_from_strings(item, depth + 1))
    return found


def _numbers_from_payload(result: Any) -> tuple[list[float], list[float]]:
    numeric: list[float] = []
    textual: list[float] = []
    for attribute in ("data", "values"):
        payload = getattr(result, attribute, None)
        if payload is None:
            continue
        for leaf, _parent in _leaves_with_parent(payload):
            if isinstance(leaf, bool) or leaf is None:
                continue
            if isinstance(leaf, (int, float)):
                value = normalize_number(leaf)
                if value is not None:
                    numeric.append(value)
        textual.extend(_numbers_from_strings(payload))
    return numeric, textual


def _matches(needle: float, haystack: Iterable[float]) -> bool:
    for value in haystack:
        if math.isclose(needle, value, rel_tol=1e-9, abs_tol=1e-12):
            return True
    return False


def _finding_payloads(result: Any, value: float) -> list[Mapping[str, Any]]:
    matches: list[Mapping[str, Any]] = []
    for attribute in ("data", "values"):
        payload = getattr(result, attribute, None)
        if payload is None:
            continue
        for leaf, parent in _leaves_with_parent(payload):
            if isinstance(leaf, bool) or not isinstance(leaf, (int, float)):
                continue
            numeric = normalize_number(leaf)
            if numeric is not None and math.isclose(
                numeric, value, rel_tol=1e-9, abs_tol=1e-12
            ):
                matches.append(parent)
    return matches


def _value_kind(value: Any) -> ValueKind | None:
    if isinstance(value, ValueKind):
        return value
    try:
        return ValueKind(str(value))
    except ValueError:
        return None


def _claim_failure_text(claim: Claim) -> str:
    return f"claim {claim.claim_id} ({claim.claim_type.value}): {claim.text[:140]}"


def _positive_dangerous_patterns(text: str) -> list[str]:
    found: list[str] = []
    for pattern in DANGEROUS_ASSERTIONS:
        for match in pattern.finditer(text or ""):
            prefix = (text or "")[max(0, match.start() - 60) : match.start()]
            if not NEGATION_RE.search(prefix):
                found.append(pattern.pattern)
                break
    return found


def validate_claims(
    claims: Sequence[Claim],
    supporting_data: Sequence[SupportingData],
    tool_results: Sequence[Any],
    *,
    answer: str,
    resolved_citation_ids: Sequence[str],
) -> ClaimValidationResult:
    """Validate every claim and the prose answer against tool results.

    ``tool_results`` must be the registry's ``ToolResult`` objects, not the
    public ``ToolCall`` audit records, because the validator needs the returned
    values. ``tools_used`` in the final answer remains a safe audit projection.
    """

    result = ClaimValidationResult(claims=list(claims))
    calls = {item.call_id: item for item in tool_results}
    resolved = set(resolved_citation_ids)

    for claim in claims:
        notes: list[str] = []
        if not claim.tool_call_id:
            result.fail(f"{_claim_failure_text(claim)} has no tool call")
            claim.validation_notes.append("missing tool call")
            continue

        call = calls.get(claim.tool_call_id)
        if call is None:
            result.fail(f"{_claim_failure_text(claim)} references an unknown tool call")
            claim.validation_notes.append("unknown tool call")
            continue
        if call.status not in {ToolStatus.ok, ToolStatus.empty}:
            result.fail(
                f"{_claim_failure_text(claim)} references a {call.status.value} tool call"
            )
            claim.validation_notes.append(f"tool status {call.status.value}")
            continue

        missing_citations = sorted(set(claim.citation_ids) - resolved)
        if missing_citations:
            result.fail(
                f"{_claim_failure_text(claim)} cites unresolved citations: "
                + ", ".join(missing_citations[:4])
            )
            claim.validation_notes.append("unresolved claim citation")
            continue

        if claim.claim_type == ClaimType.numerical:
            value = normalize_number(claim.value) if claim.value is not None else None
            if value is None:
                result.fail(f"{_claim_failure_text(claim)} has no numeric value")
                claim.validation_notes.append("missing numerical value")
                continue
            numeric, _textual = _numbers_from_payload(call)
            if not _matches(value, numeric):
                result.fail(
                    f"{_claim_failure_text(claim)} value {claim.value} "
                    f"does not appear in tool {call.tool}"
                )
                claim.validation_notes.append("value not present in tool result")
                continue
            payloads = _finding_payloads(call, value)
            compatible = claim.unit in COUNT_UNITS
            for payload in payloads:
                payload_unit = payload.get("unit")
                unit_ok = (
                    not claim.unit
                    or not isinstance(payload_unit, str)
                    or not payload_unit
                    or payload_unit == claim.unit
                )
                payload_kind = _value_kind(payload.get("value_kind"))
                kind_ok = (
                    claim.value_kind is None
                    or payload_kind is None
                    or payload_kind == claim.value_kind
                )
                if unit_ok and kind_ok:
                    compatible = True
                    break
            if not compatible:
                result.fail(
                    f"{_claim_failure_text(claim)} unit {claim.unit} or value "
                    f"kind does not match any tool payload for value {claim.value}"
                )
                claim.validation_notes.append("unit or value kind mismatch")
                continue

        claim.supported = True
        claim.validation_notes.extend(notes)

    for item in supporting_data:
        if item.tool_call_id not in calls:
            result.fail(
                f"supporting data {item.data_id} references an unknown tool call"
            )
        missing_citations = sorted(set(item.citation_ids) - resolved)
        if missing_citations:
            result.fail(
                f"supporting data {item.data_id} cites unresolved citations: "
                + ", ".join(missing_citations[:4])
            )

    # Prose numeric grounding. Numbers that no tool returned are unsupported.
    numeric_pool: list[float] = []
    textual_pool: list[float] = []
    for call in tool_results:
        numeric, textual = _numbers_from_payload(call)
        numeric_pool.extend(numeric)
        textual_pool.extend(textual)
    for claim in claims:
        value = normalize_number(claim.value) if claim.value is not None else None
        if value is not None:
            numeric_pool.append(value)
    for item in supporting_data:
        for leaf, _parent in _leaves_with_parent(item.values):
            if isinstance(leaf, bool) or leaf is None:
                continue
            if isinstance(leaf, (int, float)):
                value = normalize_number(leaf)
                if value is not None:
                    numeric_pool.append(value)
        numeric_pool.extend(_numbers_from_strings(item.summary))
        numeric_pool.extend(_numbers_from_strings(item.values))

    allowed_numbers = numeric_pool + textual_pool
    ungrounded: list[float] = []
    for value in answer_numbers(answer):
        if not _matches(value, allowed_numbers):
            ungrounded.append(value)
    if ungrounded:
        result.ungrounded_numbers = [f"{value:g}" for value in ungrounded]
        result.fail(
            "answer introduced numbers that no deterministic tool returned: "
            + ", ".join(result.ungrounded_numbers[:6])
        )
    result.check(
        "answer_numbers_grounded",
        not ungrounded,
        f"{len(ungrounded)} ungrounded number(s)" if ungrounded else None,
    )

    result.check(
        "claims_link_approved_tools",
        all(claim.supported for claim in claims),
        f"validated {len(claims)} claim(s)",
    )
    result.check(
        "claim_citations_resolved",
        not any(
            set(claim.citation_ids) - resolved for claim in claims
        )
        and not any(
            set(item.citation_ids) - resolved for item in supporting_data
        ),
    )

    assertion_text = "\n".join(claim.text for claim in claims if claim.text)
    overclaims = _positive_dangerous_patterns(assertion_text)
    result.check(
        "no_causal_or_risk_overclaim",
        not overclaims,
        "claim text asserted causation or a fire-risk guarantee"
        if overclaims
        else None,
    )
    prose_overclaims = _positive_dangerous_patterns(answer)
    result.check(
        "answer_no_causal_or_risk_overclaim",
        not prose_overclaims,
        "answer prose asserted causation, a ranking, or a fire-risk guarantee"
        if prose_overclaims
        else None,
    )

    if SECRET_RE.search(answer or ""):
        result.check("no_secret_material", False, "answer contained secret-like text")
    else:
        result.check("no_secret_material", True)

    if "ignore previous instructions" in (answer or "").lower():
        result.check(
            "no_injected_instruction_echo",
            False,
            "answer repeated an injected instruction as content",
        )
    else:
        result.check("no_injected_instruction_echo", True)

    result.passed = not result.errors
    return result
