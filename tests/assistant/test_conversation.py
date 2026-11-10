"""Conversation memory is bounded, non-authoritative, and not evidence."""

from __future__ import annotations

from src.assistant.conversation import (
    ConversationStore,
    extract_accessions,
    extract_dataset_ids,
    resolve_followup_accession,
    resolve_followup_dataset,
)
from src.assistant.contract import (
    AnswerType,
    AssistantAnswer,
    Claim,
    ClaimType,
    Confidence,
    EvidenceStatus,
    ValidationReport,
)


def answer(
    text: str,
    accession: str | None = "PSI-159",
    dataset_id: str | None = None,
) -> AssistantAnswer:
    return AssistantAnswer(
        request_id="req_test",
        answer=text,
        evidence_status=EvidenceStatus.insufficient_evidence,
        answer_type=AnswerType.factual,
        confidence=Confidence.low,
        confidence_basis="Test fixture.",
        provider="deterministic",
        validation=ValidationReport(),
        claims=[
            Claim(
                claim_id="claim_1",
                text=text,
                claim_type=ClaimType.factual,
                accession=accession,
                dataset_id=dataset_id,
                supported=False,
            )
        ],
    )


def test_store_creates_and_reuses_conversations():
    store = ConversationStore()
    first = store.get(None)
    second = store.get(first.conversation_id)
    assert first is second
    assert first.conversation_id.startswith("conv_")


def test_context_is_explicitly_non_authoritative():
    store = ConversationStore()
    conversation = store.get(None)
    conversation.add_user("Tell me about PSI-159.")
    conversation.add_assistant(answer("PSI-159 is a gas-flame dataset."))
    context = conversation.context()
    assert context.authoritative is False
    assert "not evidence" in context.note.lower()
    assert context.last_accession == "PSI-159"


def test_turns_are_bounded():
    store = ConversationStore()
    conversation = store.get(None)
    for index in range(20):
        conversation.add_user(f"question {index}")
    assert len(conversation.turns) <= 8


def test_followup_uses_context_only_for_clear_followups():
    store = ConversationStore()
    conversation = store.get(None)
    conversation.add_user("Tell me about PSI-159.")
    conversation.add_assistant(answer("PSI-159 is a gas-flame dataset."))
    context = conversation.context()
    assert resolve_followup_accession("What about its pressure?", context) == "PSI-159"
    assert resolve_followup_accession("Which datasets contain telemetry?", context) is None
    assert resolve_followup_accession("Compare PSI-10 and PSI-159", context) == "PSI-10"


def test_explicit_context_wins_over_memory():
    store = ConversationStore()
    conversation = store.get(None)
    conversation.add_user("Tell me about PSI-159.")
    conversation.add_assistant(answer("PSI-159 is a gas-flame dataset."))
    context = conversation.context()
    assert (
        resolve_followup_accession(
            "What about it?", context, explicit_accession="PSI-10"
        )
        == "PSI-10"
    )


def test_dataset_followup_resolution():
    store = ConversationStore()
    conversation = store.get(None)
    conversation.add_user("Show psi-159-gas-flame.")
    conversation.add_assistant(
        answer("The dataset has 333 rows.", dataset_id="psi-159-gas-flame")
    )
    context = conversation.context()
    assert (
        resolve_followup_dataset("What about its fields?", context)
        == "psi-159-gas-flame"
    )


def test_extractors_are_case_insensitive_and_deduplicated():
    assert extract_accessions("PSI-10 and psi-10 and PSI-159") == ["PSI-10", "PSI-159"]
    assert extract_dataset_ids("psi-10-gas-flame and PSI-10-GAS-FLAME") == [
        "psi-10-gas-flame"
    ]


def test_reset_removes_a_conversation():
    store = ConversationStore()
    conversation = store.get(None)
    store.reset(conversation.conversation_id)
    replacement = store.get(conversation.conversation_id)
    assert replacement is not conversation
