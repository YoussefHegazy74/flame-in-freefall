"""Deterministic orchestration for the Phase 5 assistant.

The orchestrator is the application boundary. It owns the order of operations:

1. Resolve bounded conversation context (never evidence).
2. Plan an allowlisted deterministic tool sequence.
3. Compose a grounded draft from tool results.
4. Resolve every citation through the Phase 4 registry.
5. Validate every claim and every number against the tool results.
6. Optionally let a provider rephrase the validated draft.
7. Re-validate the rephrase and fail closed to the deterministic draft.

The model never selects tools, never writes SQL, never sees retrieved source
text as instructions, and never creates citations or numbers.
"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Any, Sequence

from src.analytics.errors import InvalidQueryError
from src.analytics.logging import get_logger
from src.analytics.service import AnalyticsService
from src.assistant.claim_validation import ClaimValidationResult, validate_claims
from src.assistant.citation_validation import (
    CitationValidationResult,
    validate_citations,
)
from src.assistant.composer import Composer, DraftAnswer
from src.assistant.config import (
    DETERMINISTIC_PROVIDER,
    AssistantSettings,
    safe_settings_from_env,
)
from src.assistant.contract import (
    AnswerType,
    AssistantAnswer,
    AssistantQuery,
    AssistantStatus,
    ClarificationRequest,
    Confidence,
    EvidenceStatus,
    Limitation,
    Severity,
    Suggestion,
    ValidationCheck,
    ValidationReport,
)
from src.assistant.conversation import ConversationStore
from src.assistant.planner import Plan, plan_question
from src.assistant.providers import (
    AnswerProvider,
    DeterministicProvider,
    RephraseRequest,
    build_provider,
    extract_numbers,
    validate_rephrase,
)
from src.assistant.retrieval import RetrievalIndex, get_default_index
from src.assistant.suggestions import list_suggestions
from src.assistant.tools import ToolRegistry

LOGGER = get_logger("flame.assistant.orchestrator")

MAX_VALIDATION_ERRORS = 8
MAX_VALIDATION_WARNINGS = 12


class AssistantOrchestrator:
    """Application-owned assistant pipeline."""

    def __init__(
        self,
        *,
        service: AnalyticsService | None = None,
        settings: AssistantSettings | None = None,
        provider: AnswerProvider | None = None,
        fallback_reason: str | None = None,
        retrieval_index: RetrievalIndex | None = None,
        conversation_store: ConversationStore | None = None,
    ) -> None:
        if settings is None:
            settings, config_error = safe_settings_from_env()
        else:
            config_error = settings.config_error
        self.settings = settings
        self.service = service or AnalyticsService()
        self.conversations = conversation_store or ConversationStore()

        if provider is None:
            provider, provider_reason = build_provider(settings)
        else:
            provider_reason = None
        self.provider = provider
        self.fallback_reason = (
            fallback_reason
            or provider_reason
            or config_error
            or settings.config_error
        )
        self._retrieval_index = retrieval_index
        self._retrieval_failures = 0

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------
    def answer(self, query: AssistantQuery, *, request_id: str) -> AssistantAnswer:
        started = time.perf_counter()
        if not self.settings.enabled:
            return self._disabled_answer(query, request_id=request_id)

        question = " ".join(query.question.split())
        if len(question) > self.settings.max_question_chars:
            raise InvalidQueryError(
                "question exceeds the configured assistant length limit",
                details={"max_question_chars": self.settings.max_question_chars},
            )

        conversation = self.conversations.get(query.conversation_id)
        context = conversation.context()
        plan = plan_question(
            question,
            context=context,
            settings=self.settings,
            forced_accession=query.accession,
            forced_dataset_id=query.dataset_id,
        )
        if not query.include_retrieval:
            plan = replace(plan, retrieval_query=None)

        conversation.add_user(
            question,
            accession=plan.accession,
            dataset_id=plan.dataset_id,
        )

        registry = ToolRegistry(
            self.service,
            max_tool_calls=query.max_tool_calls or self.settings.max_tool_calls,
            timeout_seconds=self.settings.timeout_seconds,
            request_id=request_id,
            retrieval_index=self._get_index() if plan.retrieval_query else None,
        )
        composer = Composer(self.service, registry, request_id=request_id)
        draft = composer.compose(plan)
        tools_used = [result.to_tool_call() for result in registry.calls]

        citation_result = validate_citations(
            list(dict.fromkeys(draft.citation_ids)),
            self.service,
            request_id=request_id,
        )
        claim_result = validate_claims(
            draft.claims,
            draft.supporting_data,
            registry.calls,
            answer=draft.answer,
            resolved_citation_ids=citation_result.citation_ids,
        )
        validation = self._validation_report(citation_result, claim_result)

        if plan.topic == "clarification":
            answer = self._clarification_answer(
                plan,
                draft,
                tools_used,
                validation,
                conversation_id=conversation.conversation_id,
                request_id=request_id,
            )
            conversation.add_assistant(answer)
            self._log_answer(plan, answer, started, request_id)
            return answer

        if not validation.passed:
            answer = self._withheld_answer(
                plan,
                tools_used,
                validation,
                conversation_id=conversation.conversation_id,
                request_id=request_id,
            )
            conversation.add_assistant(answer)
            self._log_answer(plan, answer, started, request_id)
            return answer

        answer_text = draft.answer
        provider_name = DETERMINISTIC_PROVIDER
        fallback_mode = bool(self.fallback_reason)
        fallback_reason = self.fallback_reason
        extra_checks: list[ValidationCheck] = []
        extra_warnings: list[str] = []

        if not isinstance(self.provider, DeterministicProvider):
            rephrase_request = RephraseRequest(
                question=question,
                draft_answer=draft.answer,
                allowed_citation_ids=tuple(citation_result.citation_ids),
                allowed_numbers=tuple(sorted(extract_numbers(draft.answer))),
            )
            try:
                rephrase = self.provider.rephrase(rephrase_request)
            except Exception as exc:  # provider boundary: fail closed
                fallback_mode = True
                fallback_reason = (
                    f"configured provider failed safely ({type(exc).__name__}); "
                    "the deterministic answer is shown"
                )
                extra_warnings.append(fallback_reason)
                extra_checks.append(
                    ValidationCheck(
                        name="provider_rephrase_safe_fallback",
                        passed=True,
                        detail=fallback_reason,
                    )
                )
            else:
                boundary_ok, boundary_reason = validate_rephrase(
                    rephrase_request, rephrase.answer
                )
                if not rephrase.accepted or not boundary_ok:
                    fallback_mode = True
                    fallback_reason = (
                        boundary_reason
                        or rephrase.reason
                        or "the provider rephrase was rejected; the deterministic answer is shown"
                    )
                    extra_warnings.append(fallback_reason)
                    extra_checks.append(
                        ValidationCheck(
                            name="provider_rephrase_safe_fallback",
                            passed=True,
                            detail=fallback_reason,
                        )
                    )
                else:
                    rephrased_claims = validate_claims(
                        draft.claims,
                        draft.supporting_data,
                        registry.calls,
                        answer=rephrase.answer,
                        resolved_citation_ids=citation_result.citation_ids,
                    )
                    if rephrased_claims.passed:
                        answer_text = rephrase.answer
                        claim_result = rephrased_claims
                        provider_name = self.provider.name
                        fallback_mode = False
                        fallback_reason = None
                        validation = self._validation_report(
                            citation_result,
                            claim_result,
                            extra_checks=[
                                ValidationCheck(
                                    name="provider_rephrase_preserved_constraints",
                                    passed=True,
                                    detail=(
                                        "numbers and citations preserved; "
                                        "the answer was re-validated"
                                    ),
                                )
                            ],
                        )
                    else:
                        fallback_mode = True
                        fallback_reason = (
                            "the provider rephrase failed claim validation; "
                            "the deterministic answer is shown"
                        )
                        extra_warnings.append(fallback_reason)
                        extra_checks.append(
                            ValidationCheck(
                                name="provider_rephrase_safe_fallback",
                                passed=True,
                                detail=fallback_reason,
                            )
                        )

        if fallback_mode and extra_checks:
            validation = self._validation_report(
                citation_result,
                claim_result,
                extra_checks=extra_checks,
            )
        if extra_warnings:
            validation = validation.model_copy(
                update={
                    "warnings": list(
                        dict.fromkeys(
                            list(validation.warnings) + extra_warnings
                        )
                    )[:MAX_VALIDATION_WARNINGS]
                }
            )

        confidence = draft.confidence
        partial_citations = sum(
            1
            for citation in citation_result.citations
            if citation.verification_status == "partial"
        )
        verified_citations = sum(
            1
            for citation in citation_result.citations
            if citation.verification_status == "verified"
        )
        if (
            confidence == Confidence.high
            and partial_citations
            and verified_citations == 0
        ):
            confidence = Confidence.moderate

        answer = AssistantAnswer(
            request_id=request_id,
            conversation_id=conversation.conversation_id,
            answer=answer_text,
            evidence_status=draft.evidence_status,
            answer_type=draft.answer_type,
            citations=citation_result.citations,
            supporting_data=draft.supporting_data,
            claims=draft.claims,
            limitations=draft.limitations,
            tools_used=tools_used,
            evidence=draft.evidence,
            confidence=confidence,
            confidence_basis=draft.confidence_basis,
            dataset_version=self.service.bundle.dataset_version,
            provider=provider_name,
            fallback_mode=fallback_mode,
            fallback_reason=fallback_reason,
            validation=validation,
        )
        conversation.add_assistant(answer)
        self._log_answer(plan, answer, started, request_id)
        return answer

    def status(self, *, load_index: bool = False) -> AssistantStatus:
        index_version = None
        notes: list[str] = []
        if not self.settings.enabled:
            notes.append(
                "Assistant query handling is disabled by configuration; the "
                "deterministic status remains available."
            )
        if self.fallback_reason:
            notes.append(self.fallback_reason)
        if self.settings.retrieval_enabled:
            if load_index:
                index = self._get_index()
                if index is not None:
                    index_version = index.manifest.index_version
                elif self._retrieval_failures:
                    notes.append(
                        "The verified retrieval index is unavailable; retrieval "
                        "queries fail closed."
                    )
            else:
                notes.append(
                    "The retrieval index version is reported by /assistant/status "
                    "after the index is loaded."
                )
        else:
            notes.append("Verified-document retrieval is disabled by configuration.")

        if not self.settings.enabled:
            mode = "deterministic"
        elif self.fallback_reason or not isinstance(
            self.provider, DeterministicProvider
        ) and not self.settings.llm_configured:
            mode = "fallback"
        elif isinstance(self.provider, DeterministicProvider):
            mode = "deterministic"
        else:
            mode = "provider"

        return AssistantStatus(
            enabled=self.settings.enabled,
            mode=mode,
            provider=self.provider.name,
            model=self.settings.model if mode != "deterministic" else None,
            retrieval_enabled=self.settings.retrieval_enabled,
            index_version=index_version,
            fallback_mode=bool(self.fallback_reason)
            or (mode == "fallback"),
            fallback_reason=self.fallback_reason,
            tools_available=ToolRegistry(self.service).names(),
            notes=list(dict.fromkeys(notes)),
        )

    def suggestions(self, limit: int = 9) -> list[Suggestion]:
        return list_suggestions(limit)

    def tools(self) -> list[dict[str, Any]]:
        return ToolRegistry(self.service).describe()

    # ------------------------------------------------------------------
    # Answer builders
    # ------------------------------------------------------------------
    def _disabled_answer(
        self, query: AssistantQuery, *, request_id: str
    ) -> AssistantAnswer:
        conversation = self.conversations.get(query.conversation_id)
        answer = AssistantAnswer(
            request_id=request_id,
            conversation_id=conversation.conversation_id,
            answer=(
                "The research assistant is disabled on this deployment. No "
                "question was sent to a model, no tool was run, and no answer "
                "was generated."
            ),
            evidence_status=EvidenceStatus.insufficient_evidence,
            answer_type=AnswerType.factual,
            confidence=Confidence.low,
            confidence_basis="The assistant is disabled by configuration.",
            limitations=[
                Limitation(
                    code="assistant_disabled",
                    message=(
                        "Assistant query handling is disabled by configuration."
                    ),
                    severity=Severity.info,
                )
            ],
            dataset_version=self.service.bundle.dataset_version,
            provider=DETERMINISTIC_PROVIDER,
            fallback_mode=True,
            fallback_reason="assistant disabled by configuration",
            validation=ValidationReport(
                passed=True,
                citation_validation_passed=True,
                claim_validation_passed=True,
                checks=[
                    ValidationCheck(
                        name="assistant_disabled",
                        passed=True,
                        detail="No model and no tool were invoked.",
                    )
                ],
            ),
        )
        conversation.add_user(query.question)
        conversation.add_assistant(answer)
        return answer

    def _clarification_answer(
        self,
        plan: Plan,
        draft: DraftAnswer,
        tools_used: Sequence[Any],
        validation: ValidationReport,
        *,
        conversation_id: str,
        request_id: str,
    ) -> AssistantAnswer:
        clarification = draft.clarification or ClarificationRequest(
            question=plan.clarification_question
            or "Please clarify the requested dataset or investigation.",
            options=list(plan.clarification_options),
            missing=list(plan.clarification_missing),
        )
        return AssistantAnswer(
            request_id=request_id,
            conversation_id=conversation_id,
            answer=draft.answer,
            evidence_status=EvidenceStatus.insufficient_evidence,
            answer_type=AnswerType.clarification_required,
            citations=[],
            supporting_data=[],
            claims=[],
            limitations=draft.limitations,
            tools_used=list(tools_used),
            evidence=[],
            confidence=Confidence.low,
            confidence_basis=draft.confidence_basis,
            dataset_version=self.service.bundle.dataset_version,
            provider=DETERMINISTIC_PROVIDER,
            fallback_mode=False,
            clarification=clarification,
            validation=validation,
        )

    def _withheld_answer(
        self,
        plan: Plan,
        tools_used: Sequence[Any],
        validation: ValidationReport,
        *,
        conversation_id: str,
        request_id: str,
    ) -> AssistantAnswer:
        answer_type = plan.answer_type
        if answer_type == AnswerType.clarification_required:
            answer_type = AnswerType.factual
        detail = "; ".join(validation.errors[:3])
        message = (
            "The application withheld the draft because deterministic citation "
            "or claim validation failed."
        )
        if detail:
            message += " " + detail
        return AssistantAnswer(
            request_id=request_id,
            conversation_id=conversation_id,
            answer=(
                "I could not release an answer that passes deterministic "
                "citation and claim validation. The draft was withheld rather "
                "than shown without support. No unsupported number or citation "
                "was substituted."
            ),
            evidence_status=EvidenceStatus.insufficient_evidence,
            answer_type=answer_type,
            citations=[],
            supporting_data=[],
            claims=[],
            limitations=[
                Limitation(
                    code="validation_failed",
                    message=message,
                    severity=Severity.error,
                )
            ],
            tools_used=list(tools_used),
            evidence=[],
            confidence=Confidence.low,
            confidence_basis=(
                "Citation or claim validation failed, so the draft was withheld."
            ),
            dataset_version=self.service.bundle.dataset_version,
            provider=DETERMINISTIC_PROVIDER,
            fallback_mode=bool(self.fallback_reason),
            fallback_reason=self.fallback_reason,
            validation=validation,
        )

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _validation_report(
        self,
        citation_result: CitationValidationResult,
        claim_result: ClaimValidationResult,
        *,
        extra_checks: Sequence[ValidationCheck] = (),
    ) -> ValidationReport:
        errors = list(
            dict.fromkeys(
                list(citation_result.errors) + list(claim_result.errors)
            )
        )
        warnings = list(
            dict.fromkeys(
                list(citation_result.warnings) + list(claim_result.warnings)
            )
        )
        passed = (
            citation_result.passed
            and claim_result.passed
            and not errors
            and all(claim.supported for claim in claim_result.claims)
        )
        return ValidationReport(
            passed=passed,
            citation_validation_passed=citation_result.passed,
            claim_validation_passed=claim_result.passed,
            checks=(
                list(citation_result.checks)
                + list(claim_result.checks)
                + list(extra_checks)
            ),
            errors=errors[:MAX_VALIDATION_ERRORS],
            warnings=warnings[:MAX_VALIDATION_WARNINGS],
        )

    def _get_index(self) -> RetrievalIndex | None:
        if not self.settings.retrieval_enabled:
            return None
        if self._retrieval_index is not None:
            return self._retrieval_index
        try:
            self._retrieval_index = get_default_index(self.service)
        except Exception as exc:  # retrieval must never break non-retrieval tool use
            self._retrieval_failures += 1
            LOGGER.warning(
                "assistant_retrieval_unavailable request_id=%s error=%s",
                "orchestrator",
                type(exc).__name__,
            )
            return None
        return self._retrieval_index

    def _log_answer(
        self,
        plan: Plan,
        answer: AssistantAnswer,
        started: float,
        request_id: str,
    ) -> None:
        LOGGER.info(
            "assistant_answer topic=%s answer_type=%s evidence_status=%s "
            "provider=%s fallback=%s citations=%d claims=%d tools=%d "
            "validation=%s duration_ms=%.2f request_id=%s",
            plan.topic,
            answer.answer_type.value,
            answer.evidence_status.value,
            answer.provider,
            answer.fallback_mode,
            len(answer.citations),
            len(answer.claims),
            len(answer.tools_used),
            answer.validation.passed,
            (time.perf_counter() - started) * 1000,
            request_id,
        )
