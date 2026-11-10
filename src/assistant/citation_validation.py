"""Citation validation for assistant answers.

Every citation returned by the assistant is resolved through the Phase 4
citation implementation before the answer is released. The validator never
creates, repairs, or guesses a citation ID. Unknown or mismatched citations
fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse

from src.analytics.errors import AnalyticsError
from src.assistant.contract import CitationReference, ValidationCheck


class CitationResolver(Protocol):
    def get_citation(self, citation_id: str, request_id: str | None = None) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class CitationIssue:
    code: str
    message: str
    citation_id: str | None = None


@dataclass
class CitationValidationResult:
    passed: bool
    citations: list[CitationReference] = field(default_factory=list)
    issues: list[CitationIssue] = field(default_factory=list)
    checks: list[ValidationCheck] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[str]:
        return [f"{issue.code}: {issue.message}" for issue in self.issues]

    @property
    def citation_ids(self) -> list[str]:
        return [citation.citation_id for citation in self.citations]

    def check(self, name: str, passed: bool, detail: str | None = None) -> None:
        self.checks.append(ValidationCheck(name=name, passed=passed, detail=detail))


def _safe_url(value: str | None) -> bool:
    if value is None:
        return True
    parsed = urlparse(value)
    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
        and not parsed.username
        and not parsed.password
    )


def citation_reference_from_payload(payload: dict[str, Any]) -> CitationReference:
    """Build the contract reference from a resolved Phase 4 citation record."""

    citation_id = str(payload["citation_id"])
    kind = payload.get("kind") or payload.get("locator", {}).get("type")
    if kind not in {"file", "row"}:
        raise ValueError("citation kind is not file or row")
    locator = payload.get("locator") or {}
    source = payload.get("source") or {}
    availability = payload.get("availability") or {}
    verification = payload.get("verification") or {}
    file_payload = payload.get("file") or {}
    file_name = source.get("file_name") or file_payload.get("name")
    if not file_name:
        raise ValueError("citation has no source file name")
    return CitationReference(
        citation_id=citation_id,
        citation_type=kind,
        accession=str(payload["accession"]),
        dataset_ids=list(payload.get("dataset_ids") or []),
        file_name=str(file_name),
        sheet=locator.get("sheet"),
        row=locator.get("row"),
        source_url=source.get("source_url"),
        sha256=source.get("sha256"),
        verification_status=str(verification.get("status") or "unknown"),
        availability=str(availability.get("status") or "unknown"),
        downloadable=bool(availability.get("downloadable")),
        resolved=True,
    )


def validate_citations(
    citation_ids: list[str],
    resolver: CitationResolver,
    *,
    expected_accession: str | None = None,
    expected_dataset_id: str | None = None,
    require_available: bool = False,
    request_id: str | None = None,
) -> CitationValidationResult:
    """Resolve and validate every citation ID.

    The result is fail-closed: any unknown, malformed, mismatched, or
    unverifiable citation makes ``passed`` false. Unavailable files are valid
    citations only when they remain marked unavailable and non-downloadable.
    """

    result = CitationValidationResult(passed=True)
    seen: set[str] = set()
    duplicates: list[str] = []

    for citation_id in citation_ids:
        if not isinstance(citation_id, str) or not citation_id:
            result.issues.append(
                CitationIssue(
                    code="citation_id_invalid",
                    message="citation IDs must be non-empty strings",
                )
            )
            continue
        if citation_id in seen:
            duplicates.append(citation_id)
            continue
        seen.add(citation_id)

        if not citation_id.startswith(("cit_f_", "cit_r_")):
            result.issues.append(
                CitationIssue(
                    code="citation_id_invalid",
                    message="citation ID is not a recognized Phase 4 identifier",
                    citation_id=citation_id,
                )
            )
            continue

        try:
            envelope = resolver.get_citation(citation_id, request_id=request_id)
        except AnalyticsError as exc:
            result.issues.append(
                CitationIssue(
                    code="citation_not_found",
                    message=str(exc),
                    citation_id=citation_id,
                )
            )
            continue
        except Exception as exc:  # pragma: no cover - defensive boundary
            result.issues.append(
                CitationIssue(
                    code="citation_resolution_failed",
                    message=f"citation resolution failed ({type(exc).__name__})",
                    citation_id=citation_id,
                )
            )
            continue

        payload = envelope.get("data") if isinstance(envelope, dict) else None
        if not isinstance(payload, dict):
            result.issues.append(
                CitationIssue(
                    code="citation_payload_invalid",
                    message="citation endpoint returned no citation record",
                    citation_id=citation_id,
                )
            )
            continue

        availability_payload = payload.get("availability") or {}
        if (
            availability_payload.get("status") == "unavailable"
            and availability_payload.get("downloadable") is True
        ):
            result.issues.append(
                CitationIssue(
                    code="unavailable_marked_downloadable",
                    message="an unavailable source must never be presented as downloadable",
                    citation_id=citation_id,
                )
            )
            continue

        try:
            reference = citation_reference_from_payload(payload)
        except (KeyError, TypeError, ValueError) as exc:
            result.issues.append(
                CitationIssue(
                    code="citation_payload_invalid",
                    message=str(exc),
                    citation_id=citation_id,
                )
            )
            continue

        prefix = "cit_f_" if reference.citation_type == "file" else "cit_r_"
        if not citation_id.startswith(prefix):
            result.issues.append(
                CitationIssue(
                    code="citation_kind_mismatch",
                    message="citation ID prefix does not match its record kind",
                    citation_id=citation_id,
                )
            )

        if reference.citation_type == "row":
            row_verification = payload.get("row_verification") or {}
            if row_verification.get("row_verified") is not True:
                result.issues.append(
                    CitationIssue(
                        code="row_not_verified",
                        message="row citation does not resolve to a canonical row",
                        citation_id=citation_id,
                    )
                )
            if reference.row is None:
                result.issues.append(
                    CitationIssue(
                        code="row_locator_missing",
                        message="row citation has no row number",
                        citation_id=citation_id,
                    )
                )
        else:
            if reference.verification_status not in {"verified", "unavailable"}:
                result.issues.append(
                    CitationIssue(
                        code="citation_unverified",
                        message="file citation is not verified or documented unavailable",
                        citation_id=citation_id,
                    )
                )

        if reference.availability not in {"available", "unavailable"}:
            result.issues.append(
                CitationIssue(
                    code="citation_availability_unknown",
                    message="citation availability is not available or unavailable",
                    citation_id=citation_id,
                )
            )

        if reference.availability == "unavailable" and reference.downloadable:
            result.issues.append(
                CitationIssue(
                    code="unavailable_marked_downloadable",
                    message="an unavailable source must never be presented as downloadable",
                    citation_id=citation_id,
                )
            )

        if require_available and reference.availability != "available":
            result.issues.append(
                CitationIssue(
                    code="citation_unavailable",
                    message="this answer requires an available source",
                    citation_id=citation_id,
                )
            )

        if expected_accession and reference.accession != expected_accession.upper():
            result.issues.append(
                CitationIssue(
                    code="citation_accession_mismatch",
                    message=(
                        f"citation belongs to {reference.accession}, not "
                        f"{expected_accession.upper()}"
                    ),
                    citation_id=citation_id,
                )
            )

        if expected_dataset_id and expected_dataset_id not in reference.dataset_ids:
            result.issues.append(
                CitationIssue(
                    code="citation_dataset_mismatch",
                    message=(
                        f"citation does not belong to dataset {expected_dataset_id}"
                    ),
                    citation_id=citation_id,
                )
            )

        if not _safe_url(reference.source_url):
            result.issues.append(
                CitationIssue(
                    code="citation_source_url_unsafe",
                    message="citation source URL is not a safe absolute http(s) URL",
                    citation_id=citation_id,
                )
            )

        result.citations.append(reference)

    if duplicates:
        result.warnings.append(
            "Duplicate citation IDs were removed: " + ", ".join(sorted(set(duplicates)))
        )

    result.check(
        "citation_ids_resolved",
        all(
            issue.code != "citation_not_found"
            for issue in result.issues
        ),
        f"resolved {len(result.citations)} of {len(seen)} unique citations",
    )
    result.check(
        "citation_records_verified",
        not any(
            issue.code
            in {
                "row_not_verified",
                "citation_unverified",
                "citation_payload_invalid",
                "citation_kind_mismatch",
            }
            for issue in result.issues
        ),
    )
    result.check(
        "citation_scope_matches",
        not any(
            issue.code in {"citation_accession_mismatch", "citation_dataset_mismatch"}
            for issue in result.issues
        ),
    )
    result.check(
        "unavailable_sources_not_downloadable",
        not any(
            issue.code == "unavailable_marked_downloadable"
            for issue in result.issues
        ),
    )
    result.check("citation_source_urls_safe", not any(
        issue.code == "citation_source_url_unsafe" for issue in result.issues
    ))
    result.passed = not result.issues
    return result
