"""Bounded, non-authoritative conversation context.

Conversation memory exists only to resolve follow-up references such as
"what about PSI-159?" It is never evidence. Every citation and every number
is re-resolved on each request from the canonical registries and tools.
"""

from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from src.assistant.contract import AssistantAnswer

MAX_CONVERSATIONS = 100
MAX_TURNS_PER_CONVERSATION = 8
CONVERSATION_TTL_SECONDS = 30 * 60
MAX_TURN_CHARS = 1200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate(value: str, limit: int = MAX_TURN_CHARS) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


@dataclass(frozen=True)
class ConversationTurn:
    role: Literal["user", "assistant"]
    content: str
    accession: str | None = None
    dataset_id: str | None = None
    answer_type: str | None = None
    evidence_status: str | None = None
    created_at: str = field(default_factory=_now)


@dataclass(frozen=True)
class ConversationContext:
    """A hint for follow-up resolution, explicitly not evidence."""

    conversation_id: str
    turns: list[ConversationTurn]
    last_accession: str | None
    last_dataset_id: str | None
    authoritative: bool = False
    note: str = (
        "Conversation context is non-authoritative. Prior assistant answers "
        "are not evidence and are re-resolved for every request."
    )


@dataclass
class Conversation:
    conversation_id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    updated_at: float = field(default_factory=time.monotonic)

    def add_user(self, question: str, *, accession: str | None = None, dataset_id: str | None = None) -> None:
        self.turns.append(
            ConversationTurn(
                role="user",
                content=_truncate(question),
                accession=accession,
                dataset_id=dataset_id,
            )
        )
        self._trim()

    def add_assistant(self, answer: AssistantAnswer) -> None:
        accession = next(
            (claim.accession for claim in answer.claims if claim.accession),
            None,
        )
        dataset_id = next(
            (claim.dataset_id for claim in answer.claims if claim.dataset_id),
            None,
        )
        self.turns.append(
            ConversationTurn(
                role="assistant",
                content=_truncate(answer.answer),
                accession=accession,
                dataset_id=dataset_id,
                answer_type=answer.answer_type.value,
                evidence_status=answer.evidence_status.value,
            )
        )
        self._trim()

    def _trim(self) -> None:
        if len(self.turns) > MAX_TURNS_PER_CONVERSATION:
            self.turns = self.turns[-MAX_TURNS_PER_CONVERSATION:]
        self.updated_at = time.monotonic()

    def context(self) -> ConversationContext:
        last_accession = None
        last_dataset_id = None
        for turn in reversed(self.turns):
            if last_accession is None and turn.accession:
                last_accession = turn.accession
            if last_dataset_id is None and turn.dataset_id:
                last_dataset_id = turn.dataset_id
            if last_accession and last_dataset_id:
                break
        return ConversationContext(
            conversation_id=self.conversation_id,
            turns=list(self.turns),
            last_accession=last_accession,
            last_dataset_id=last_dataset_id,
        )


class ConversationStore:
    """A process-local, bounded store. It is not durable and not shared."""

    def __init__(
        self,
        *,
        max_conversations: int = MAX_CONVERSATIONS,
        ttl_seconds: int = CONVERSATION_TTL_SECONDS,
    ):
        self.max_conversations = max_conversations
        self.ttl_seconds = ttl_seconds
        self._conversations: dict[str, Conversation] = {}

    def _evict(self) -> None:
        cutoff = time.monotonic() - self.ttl_seconds
        expired = [
            key
            for key, conversation in self._conversations.items()
            if conversation.updated_at < cutoff
        ]
        for key in expired:
            self._conversations.pop(key, None)
        while len(self._conversations) > self.max_conversations:
            oldest = min(
                self._conversations,
                key=lambda key: self._conversations[key].updated_at,
            )
            self._conversations.pop(oldest, None)

    def get(self, conversation_id: str | None) -> Conversation:
        self._evict()
        if conversation_id:
            existing = self._conversations.get(conversation_id)
            if existing is not None:
                return existing
        new_id = conversation_id or "conv_" + secrets.token_hex(12)
        conversation = Conversation(conversation_id=new_id)
        self._conversations[new_id] = conversation
        self._evict()
        return conversation

    def reset(self, conversation_id: str) -> None:
        self._conversations.pop(conversation_id, None)


ACCESSION_PATTERN = re.compile(r"\bPSI-\d{2,4}\b", re.IGNORECASE)
DATASET_PATTERN = re.compile(r"\bpsi-\d{2,4}-[a-z0-9-]+\b", re.IGNORECASE)


def extract_accessions(text: str) -> list[str]:
    return sorted({match.upper() for match in ACCESSION_PATTERN.findall(text)})


def extract_dataset_ids(text: str) -> list[str]:
    return sorted({match.lower() for match in DATASET_PATTERN.findall(text)})


def resolve_followup_accession(
    question: str,
    context: ConversationContext | None,
    explicit_accession: str | None = None,
) -> str | None:
    """Resolve an accession only when the question clearly refers to one."""

    if explicit_accession:
        return explicit_accession.upper()
    mentioned = extract_accessions(question)
    if mentioned:
        return mentioned[0]
    if context is not None and _looks_like_followup(question):
        return context.last_accession
    return None


def resolve_followup_dataset(
    question: str,
    context: ConversationContext | None,
    explicit_dataset_id: str | None = None,
) -> str | None:
    if explicit_dataset_id:
        return explicit_dataset_id.lower()
    mentioned = extract_dataset_ids(question)
    if mentioned:
        return mentioned[0]
    if context is not None and _looks_like_followup(question):
        return context.last_dataset_id
    return None


FOLLOWUP_MARKERS = (
    "it",
    "its",
    "that",
    "those",
    "this",
    "these",
    "the same",
    "what about",
    "and for",
    "how about",
    "there",
    "compare them",
)


def _looks_like_followup(question: str) -> bool:
    lowered = question.lower()
    return any(marker in lowered for marker in FOLLOWUP_MARKERS)
