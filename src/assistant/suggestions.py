"""Curated suggested questions for the Phase 5 assistant.

These are real questions from the versioned golden set. They are suggestions,
not evidence: every answer is re-resolved through the deterministic tools and
Phase 4 citation registry.
"""

from __future__ import annotations

from src.assistant.contract import AnswerType, Suggestion

SUGGESTIONS: tuple[Suggestion, ...] = (
    Suggestion(
        question_id="dq-001",
        category="dataset_discovery",
        question="Which combustion investigations are available?",
        answer_type_hint=AnswerType.factual,
    ),
    Suggestion(
        question_id="dq-002",
        category="dataset_discovery",
        question="What experiments are included in PSI-10?",
        answer_type_hint=AnswerType.factual,
    ),
    Suggestion(
        question_id="dq-008",
        category="experimental_understanding",
        question="What does the PSI-159 dataset contain?",
        answer_type_hint=AnswerType.factual,
    ),
    Suggestion(
        question_id="dq-009",
        category="numerical",
        question="How many valid PSI-10 gas-flame records are available?",
        answer_type_hint=AnswerType.numerical,
    ),
    Suggestion(
        question_id="dq-011",
        category="numerical",
        question="What is the available pressure information for PSI-159?",
        answer_type_hint=AnswerType.numerical,
    ),
    Suggestion(
        question_id="dq-015",
        category="limitations",
        question=(
            "Can PSI-10 pressure values be directly compared with PSI-159 "
            "pressure values?"
        ),
        answer_type_hint=AnswerType.comparison,
    ),
    Suggestion(
        question_id="dq-020",
        category="comparison",
        question="Can PSI-10 and PSI-159 oxygen measurements be compared?",
        answer_type_hint=AnswerType.comparison,
    ),
    Suggestion(
        question_id="dq-026",
        category="provenance",
        question="Can citation cit_f_2a9f8d907458d052 be resolved?",
        answer_type_hint=AnswerType.factual,
    ),
    Suggestion(
        question_id="dq-036",
        category="methodology",
        question="What is the difference between measured and computed values in PSI-10?",
        answer_type_hint=AnswerType.methodology,
    ),
)


def list_suggestions(limit: int = 9) -> list[Suggestion]:
    return list(SUGGESTIONS[: max(1, min(limit, len(SUGGESTIONS)))])
