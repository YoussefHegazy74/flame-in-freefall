"""Phase 5 grounded research assistant.

The assistant is a controlled layer over the verified Phase 1-4 artifacts.
It does not replace the analytics service and it does not become a source of
truth.
"""

from src.assistant.contract import (
    CONTRACT_VERSION,
    AnswerType,
    AssistantAnswer,
    AssistantQuery,
    AssistantStatus,
    CitationReference,
    Claim,
    ClaimType,
    Confidence,
    EvidenceStatus,
    Limitation,
    SupportingData,
    ToolCall,
    ValidationReport,
    ValueKind,
)

__all__ = [
    "CONTRACT_VERSION",
    "AnswerType",
    "AssistantAnswer",
    "AssistantQuery",
    "AssistantStatus",
    "CitationReference",
    "Claim",
    "ClaimType",
    "Confidence",
    "EvidenceStatus",
    "Limitation",
    "SupportingData",
    "ToolCall",
    "ValidationReport",
    "ValueKind",
]
