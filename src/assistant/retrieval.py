"""Verified-document retrieval for the Phase 5 assistant.

The index is built only from committed documentation and verified metadata:
curated dataset cards, investigation records, publication registry records,
limitation records, field definitions, and curated source-file records. Raw
experimental files are never indexed.

Ranking is deterministic and dependency-free:

* BM25 over normalized scientific tokens.
* A hashed TF-IDF vector cosine score.
* A weighted hybrid score.

The vector component is a lexical hashing baseline, not a neural semantic
embedding. It is labeled as such in the manifest and in every result.

Every chunk preserves its document ID, source type, source reference,
accession, dataset ID, resolvable citation IDs, section, content hash, and
index version. Document chunks and publication cards do not have Phase 4
citations; they are returned as evidence items with ``citation_id=null``.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Sequence

from src.analytics.logging import get_logger
from src.analytics.registry import repo_root

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from src.analytics.service import AnalyticsService

LOGGER = get_logger("flame.assistant.retrieval")

INDEX_SCHEMA_VERSION = "1.0.0"
INDEX_VERSION_PREFIX = "assistant-index-v1"
CARD_BUILDER_VERSION = "2"
DEFAULT_INDEX_PATH = Path("data") / "assistant" / "index.json"

CHUNKING_CONFIG = {
    "strategy": "markdown_heading_paragraph",
    "max_chars": 1600,
    "overlap_chars": 200,
    "min_chars": 40,
}
EMBEDDING_CONFIG = {
    "provider": "deterministic",
    "model": "tfidf-hash-v1",
    "dimensions": 256,
    "note": "Lexical hashed TF-IDF; not a neural semantic embedding.",
}
RETRIEVAL_CONFIG = {
    "method": "bm25+tfidf-hash-v1+source-intent",
    "bm25_k1": 1.5,
    "bm25_b": 0.75,
    "bm25_weight": 0.65,
    "vector_weight": 0.35,
    "exact_match_boost": 0.05,
    "source_intent_boost": 0.08,
    "identifier_match_boost": 0.14,
    "metadata_scope_boost": 0.03,
    "max_per_document": 2,
}

# Source-aware intent terms. These are lexical cues only; they do not claim
# semantic understanding. A boost changes ranking, never eligibility or
# provenance.
SOURCE_INTENT_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "publication",
        (
            "publication",
            "publications",
            "doi",
            "author",
            "authors",
            "venue",
            "paper",
            "papers",
        ),
    ),
    (
        "limitation",
        (
            "limitation",
            "limitations",
            "unavailable",
            "404",
            "missing",
            "blank",
            "withhold",
            "withheld",
            "restriction",
            "separate",
        ),
    ),
    (
        "field",
        (
            "field",
            "fields",
            "column",
            "columns",
            "unit",
            "units",
            "missingness",
            "canonical",
            "voltage",
            "calibration",
        ),
    ),
    (
        "dataset",
        (
            "dataset",
            "datasets",
            "run",
            "runs",
            "catalog",
            "metadata",
            "files",
        ),
    ),
    (
        "file",
        (
            "file",
            "checksum",
            "sha256",
            "provenance",
            "row",
            "rows",
        ),
    ),
    (
        "investigation",
        ("investigation", "investigations", "accession"),
    ),
)

IDENTIFIER_RE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
ACCESSION_QUERY_RE = re.compile(r"\bPSI-\d{2,4}\b", re.IGNORECASE)
DATASET_QUERY_RE = re.compile(
    r"\bpsi-\d{2,4}-[a-z0-9][a-z0-9-]*\b", re.IGNORECASE
)
MAX_CHUNK_CHARS = CHUNKING_CONFIG["max_chars"]
BUILD_COMMAND = ".venv/bin/python scripts/build_assistant_index.py"
VALIDATION_COMMAND = ".venv/bin/python scripts/build_assistant_index.py --check"

SOURCE_TYPES = {
    "document",
    "dataset",
    "investigation",
    "publication",
    "limitation",
    "field",
    "file",
}

DOCUMENT_SOURCES: tuple[dict[str, str], ...] = (
    {
        "source_id": "doc://DATA_DICTIONARY.md",
        "path": "DATA_DICTIONARY.md",
        "title": "Data Dictionary",
    },
    {
        "source_id": "doc://DATA_SOURCES.md",
        "path": "DATA_SOURCES.md",
        "title": "Data Sources",
    },
    {
        "source_id": "doc://PROJECT_ARCHITECTURE.md",
        "path": "PROJECT_ARCHITECTURE.md",
        "title": "Project Architecture",
    },
    {
        "source_id": "doc://API_DOCUMENTATION.md",
        "path": "API_DOCUMENTATION.md",
        "title": "API Documentation",
    },
    {
        "source_id": "doc://docs/known-limitations.md",
        "path": "docs/known-limitations.md",
        "title": "Known Scientific Limitations",
    },
    {
        "source_id": "doc://docs/phase4-contracts.md",
        "path": "docs/phase4-contracts.md",
        "title": "Phase 4 Contracts",
    },
    {
        "source_id": "doc://docs/comparison-alignment.md",
        "path": "docs/comparison-alignment.md",
        "title": "Comparison Alignment Methodology",
    },
    {
        "source_id": "doc://docs/comparability.md",
        "path": "docs/comparability.md",
        "title": "Comparability",
    },
    {
        "source_id": "doc://docs/serving-states.md",
        "path": "docs/serving-states.md",
        "title": "Serving States",
    },
    {
        "source_id": "doc://docs/query-contract.md",
        "path": "docs/query-contract.md",
        "title": "Query Contract",
    },
)

METADATA_SOURCES: tuple[dict[str, str], ...] = (
    {
        "source_id": "registry://comparability",
        "path": "data/metadata/comparability_registry.json",
        "kind": "registry",
    },
    {
        "source_id": "registry://serving",
        "path": "data/metadata/serving_registry.json",
        "kind": "registry",
    },
    {
        "source_id": "registry://paired-alignment",
        "path": "data/metadata/paired_alignment_registry.json",
        "kind": "registry",
    },
    {
        "source_id": "registry://psi-investigations",
        "path": "data/registry/psi_combustion_investigations.json",
        "kind": "registry",
    },
    {
        "source_id": "registry://mvp-dataset-catalog",
        "path": "data/registry/mvp_dataset_catalog.json",
        "kind": "registry",
    },
    {
        "source_id": "registry://download-manifest",
        "path": "data/registry/download_manifest.json",
        "kind": "registry",
    },
    {
        "source_id": "report://acquisition",
        "path": "data/reports/acquisition_report.json",
        "kind": "report",
    },
    {
        "source_id": "report://dataset-quality",
        "path": "data/reports/dataset_quality_report.json",
        "kind": "report",
    },
)

MANIFEST_NOTES = (
    "Hybrid retrieval uses BM25 plus a deterministic hashed TF-IDF vector; it is not a neural semantic embedding.",
    "Document chunks are verified repository documentation, not Phase 4 citations.",
    "Publication cards contain registry metadata only; no abstracts, findings, year, or venue are available.",
    "Cards are generated from committed registries and canonical metadata; raw experimental files are not indexed.",
    "Metadata cards intentionally omit row counts and computed statistics; numerical claims must come from deterministic tools.",
)

ACCESSION_RE = re.compile(r"\bPSI-\d{1,4}\b", re.IGNORECASE)
DATASET_ID_RE = re.compile(r"\bpsi-\d{1,4}-[a-z0-9][a-z0-9-]*\b", re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*")
HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
COUNT_CLAIM_RE = re.compile(
    r"(?<![A-Za-z0-9_-])\d[\d,.]*\s+"
    r"(?:(?:PSI-\d+|physical|raw|canonical|curated|distinct|unique|total|"
    r"normal|inverse|smoke|telemetry|material|droplet|[a-z]+-flame)\s+){0,2}"
    r"(?:rows?|columns?|datasets?|files?|investigations?|publications?|"
    r"measurements?|records?|runs?|tests?|observations?|tables?|percent|"
    r"bytes?|kb|mb|gb|tb)\b",
    re.IGNORECASE,
)
STOPWORDS = frozenset(
    {
        "a",
        "about",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "explain",
        "for",
        "from",
        "had",
        "has",
        "have",
        "here",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "may",
        "me",
        "might",
        "must",
        "no",
        "not",
        "of",
        "on",
        "or",
        "please",
        "should",
        "show",
        "tell",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "to",
        "under",
        "use",
        "used",
        "using",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "why",
        "will",
        "with",
        "would",
    }
)


class RetrievalError(ValueError):
    """Raised when a retrieval index is missing, stale, or invalid."""

    def __init__(
        self, message: str, *, details: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.details = dict(details or {})


class StaleIndexError(RetrievalError):
    """Raised when an index no longer matches its verified sources."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _clean_text(value: Any, *, limit: int | None = None) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\x00", " ")
    text = "".join(
        character if character in "\n\t" or ord(character) >= 32 else " "
        for character in text
    )
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if limit is not None and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def _json_safe(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return "..."
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item, depth + 1) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(dict.fromkeys(value for value in values if value)))


def tokenize(text: str) -> list[str]:
    """Tokenize scientific text deterministically.

    Compound identifiers such as ``pressure_initial_atm`` and ``PSI-10`` are
    kept whole and also split into their parts so exact identifiers and
    ordinary words both retrieve.
    """

    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    normalized = (
        normalized.replace("°", " deg ")
        .replace("²", "2")
        .replace("³", "3")
        .replace("×", "x")
    )
    tokens: list[str] = []
    for match in TOKEN_RE.finditer(normalized):
        raw = match.group(0).strip("._/-")
        if not raw:
            continue
        parts = [part for part in re.split(r"[._/-]+", raw) if part]
        for token in (raw, *parts):
            if token in STOPWORDS:
                continue
            if len(token) == 1 and not token.isdigit():
                continue
            if len(token) > 64:
                continue
            tokens.append(token)
    return tokens


def _source_intent_types(query: str) -> set[str]:
    normalized = query.lower()
    intents: set[str] = set()
    for source_type, terms in SOURCE_INTENT_TERMS:
        if any(re.search(rf"\b{re.escape(term)}\b", normalized) for term in terms):
            intents.add(source_type)
    return intents


def _identifier_tokens(query: str) -> set[str]:
    return {match.group(0).lower() for match in IDENTIFIER_RE.finditer(query)}


class _BM25:
    def __init__(self, documents: Sequence[Sequence[str]]) -> None:
        self.documents = documents
        self.doc_count = len(documents)
        self.doc_freqs: Counter[str] = Counter()
        self.term_freqs: list[Counter[str]] = []
        self.doc_lengths: list[int] = []
        for document in documents:
            counts = Counter(document)
            self.term_freqs.append(counts)
            self.doc_lengths.append(len(document))
            self.doc_freqs.update(counts.keys())
        self.average_length = (
            sum(self.doc_lengths) / self.doc_count if self.doc_count else 0.0
        )

    def scores(self, query_tokens: Sequence[str]) -> list[float]:
        scores = [0.0] * self.doc_count
        if not self.doc_count:
            return scores
        k1 = RETRIEVAL_CONFIG["bm25_k1"]
        b = RETRIEVAL_CONFIG["bm25_b"]
        for term in dict.fromkeys(query_tokens):
            document_frequency = self.doc_freqs.get(term, 0)
            if not document_frequency:
                continue
            idf = math.log(
                1.0
                + (self.doc_count - document_frequency + 0.5)
                / (document_frequency + 0.5)
            )
            for index, counts in enumerate(self.term_freqs):
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                length = self.doc_lengths[index]
                denominator = frequency + k1 * (
                    1.0 - b + b * (length / self.average_length)
                )
                scores[index] += idf * (
                    frequency * (k1 + 1.0) / denominator
                )
        return scores


class _HashingTfidf:
    def __init__(self, documents: Sequence[Sequence[str]]) -> None:
        self.doc_count = len(documents)
        document_frequency: Counter[str] = Counter()
        for document in documents:
            document_frequency.update(set(document))
        self.idf = {
            term: math.log((1.0 + self.doc_count) / (1.0 + frequency)) + 1.0
            for term, frequency in document_frequency.items()
        }
        self.dimensions = EMBEDDING_CONFIG["dimensions"]
        self.vectors = [self._vector(document) for document in documents]

    def _vector(self, tokens: Sequence[str]) -> list[float]:
        vector = [0.0] * self.dimensions
        counts = Counter(tokens)
        for term, frequency in counts.items():
            idf = self.idf.get(term)
            if idf is None:
                continue
            index = int.from_bytes(
                hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest(),
                "big",
            ) % self.dimensions
            vector[index] += (1.0 + math.log(frequency)) * idf
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector

    def query_vector(self, tokens: Sequence[str]) -> list[float]:
        return self._vector(tokens)

    def score(self, query_vector: Sequence[float], index: int) -> float:
        return sum(
            left * right for left, right in zip(query_vector, self.vectors[index])
        )


@dataclass(frozen=True)
class IndexChunk:
    chunk_id: str
    document_id: str
    source_type: str
    source_reference: str
    accession: str | None
    dataset_id: str | None
    citation_id: str | None
    citation_ids: tuple[str, ...]
    section: str | None
    content: str
    content_hash: str
    index_version: str
    accessions: tuple[str, ...] = ()
    dataset_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_type": self.source_type,
            "source_reference": self.source_reference,
            "accession": self.accession,
            "dataset_id": self.dataset_id,
            "citation_id": self.citation_id,
            "citation_ids": list(self.citation_ids),
            "section": self.section,
            "content": self.content,
            "content_hash": self.content_hash,
            "index_version": self.index_version,
            "accessions": list(self.accessions),
            "dataset_ids": list(self.dataset_ids),
            "metadata": _json_safe(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "IndexChunk":
        try:
            return cls(
                chunk_id=str(payload["chunk_id"]),
                document_id=str(payload["document_id"]),
                source_type=str(payload["source_type"]),
                source_reference=str(payload["source_reference"]),
                accession=payload.get("accession"),
                dataset_id=payload.get("dataset_id"),
                citation_id=payload.get("citation_id"),
                citation_ids=tuple(payload.get("citation_ids") or ()),
                section=payload.get("section"),
                content=str(payload["content"]),
                content_hash=str(payload["content_hash"]),
                index_version=str(payload["index_version"]),
                accessions=tuple(payload.get("accessions") or ()),
                dataset_ids=tuple(payload.get("dataset_ids") or ()),
                metadata=dict(payload.get("metadata") or {}),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RetrievalError("index chunk is malformed") from exc


@dataclass(frozen=True)
class IndexManifest:
    index_version: str
    schema_version: str
    dataset_version: str
    registry_version: str
    generated_at: str
    build_command: str
    validation_command: str
    chunking: dict[str, Any]
    embedding: dict[str, Any]
    retrieval: dict[str, Any]
    sources: tuple[dict[str, Any], ...]
    chunk_count: int
    document_count: int
    chunk_digest: str
    source_digest: str
    config_digest: str
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "index_version": self.index_version,
            "schema_version": self.schema_version,
            "dataset_version": self.dataset_version,
            "registry_version": self.registry_version,
            "generated_at": self.generated_at,
            "build_command": self.build_command,
            "validation_command": self.validation_command,
            "chunking": _json_safe(self.chunking),
            "embedding": _json_safe(self.embedding),
            "retrieval": _json_safe(self.retrieval),
            "sources": _json_safe(self.sources),
            "chunk_count": self.chunk_count,
            "document_count": self.document_count,
            "chunk_digest": self.chunk_digest,
            "source_digest": self.source_digest,
            "config_digest": self.config_digest,
            "notes": list(self.notes),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "IndexManifest":
        required = (
            "index_version",
            "schema_version",
            "dataset_version",
            "registry_version",
            "generated_at",
            "build_command",
            "validation_command",
            "chunking",
            "embedding",
            "retrieval",
            "sources",
            "chunk_count",
            "document_count",
            "chunk_digest",
            "source_digest",
            "config_digest",
        )
        missing = [key for key in required if key not in payload]
        if missing:
            raise RetrievalError(
                "index manifest is missing required fields",
                details={"missing": missing},
            )
        try:
            return cls(
                index_version=str(payload["index_version"]),
                schema_version=str(payload["schema_version"]),
                dataset_version=str(payload["dataset_version"]),
                registry_version=str(payload["registry_version"]),
                generated_at=str(payload["generated_at"]),
                build_command=str(payload["build_command"]),
                validation_command=str(payload["validation_command"]),
                chunking=dict(payload["chunking"]),
                embedding=dict(payload["embedding"]),
                retrieval=dict(payload["retrieval"]),
                sources=tuple(dict(item) for item in payload["sources"]),
                chunk_count=int(payload["chunk_count"]),
                document_count=int(payload["document_count"]),
                chunk_digest=str(payload["chunk_digest"]),
                source_digest=str(payload["source_digest"]),
                config_digest=str(payload["config_digest"]),
                notes=tuple(str(item) for item in payload.get("notes") or ()),
                warnings=tuple(str(item) for item in payload.get("warnings") or ()),
            )
        except (TypeError, ValueError) as exc:
            raise RetrievalError("index manifest is malformed") from exc


def _compose(lines: Iterable[str | None], *, limit: int = MAX_CHUNK_CHARS) -> str:
    return _clean_text(
        "\n".join(line for line in lines if line and line.strip()),
        limit=limit,
    )


def _format_value(value: Any) -> str | None:
    if value is None or value == "" or value == [] or value == {}:
        return None
    if isinstance(value, Mapping):
        return json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True)
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value)
    return str(value)


def _line(label: str, value: Any) -> str | None:
    text = _format_value(value)
    return f"{label}: {text}" if text is not None else None


def _qualitative_text(value: Any, *, limit: int = 600) -> str:
    """Remove sentences that state counts, so cards stay non-numerical.

    Registry prose sometimes repeats row, file, or record counts. Those counts
    belong to deterministic tools; a retrieval card must not become a second
    numerical source.
    """

    text = _clean_text(value)
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept = [sentence for sentence in sentences if not COUNT_CLAIM_RE.search(sentence)]
    return _clean_text(" ".join(kept), limit=limit)


def _qualitative_line(
    label: str, value: Any, *, limit: int = 600
) -> str | None:
    text = _qualitative_text(value, limit=limit)
    return f"{label}: {text}" if text else None


def _extract_accessions(text: str) -> tuple[str, ...]:
    return _unique(match.group(0).upper() for match in ACCESSION_RE.finditer(text))


def _extract_dataset_ids(text: str) -> tuple[str, ...]:
    return _unique(
        match.group(0).lower() for match in DATASET_ID_RE.finditer(text)
    )


def _expected_chunk_id(
    document_id: str, section: str | None, content_hash: str
) -> str:
    return "chk_" + _sha256_text(
        f"{document_id}\x00{section or ''}\x00{content_hash}"
    )[:24]


def make_chunk(
    *,
    document_id: str,
    source_type: str,
    source_reference: str,
    content: str,
    section: str | None = None,
    index_version: str = "test-index",
    accession: str | None = None,
    dataset_id: str | None = None,
    citation_ids: Sequence[str] = (),
    accessions: Sequence[str] = (),
    dataset_ids: Sequence[str] = (),
    metadata: Mapping[str, Any] | None = None,
) -> IndexChunk:
    if source_type not in SOURCE_TYPES:
        raise RetrievalError("unknown retrieval source type")
    cleaned = _clean_text(content, limit=MAX_CHUNK_CHARS)
    if not cleaned:
        raise RetrievalError("retrieval chunk content is empty")
    content_hash = _sha256_text(cleaned)
    citations = _unique(citation_ids)
    accession_values = _unique(
        ([accession] if accession else []) + list(accessions)
    )
    dataset_values = _unique(
        ([dataset_id] if dataset_id else []) + list(dataset_ids)
    )
    return IndexChunk(
        chunk_id=_expected_chunk_id(document_id, section, content_hash),
        document_id=document_id,
        source_type=source_type,
        source_reference=source_reference,
        accession=accession,
        dataset_id=dataset_id,
        citation_id=citations[0] if citations else None,
        citation_ids=citations,
        section=section,
        content=cleaned,
        content_hash=content_hash,
        index_version=index_version,
        accessions=accession_values,
        dataset_ids=dataset_values,
        metadata=_json_safe(dict(metadata or {})),
    )


def _parse_markdown_sections(
    text: str, document_title: str
) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    stack: list[tuple[int, str]] = []
    current_lines: list[str] = []
    in_fence = False

    def flush() -> None:
        content = "\n".join(current_lines).strip()
        if not content:
            return
        titles = [title for level, title in stack if level > 1]
        section = " > ".join(titles) if titles else document_title
        sections.append((section, content))

    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            current_lines.append(line)
            continue
        match = None if in_fence else HEADING_RE.match(line)
        if match:
            flush()
            level = len(match.group(1))
            title = match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            current_lines = []
            continue
        current_lines.append(line)
    flush()
    return sections


def _split_text(
    text: str,
    *,
    max_chars: int = CHUNKING_CONFIG["max_chars"],
    overlap_chars: int = CHUNKING_CONFIG["overlap_chars"],
    min_chars: int = CHUNKING_CONFIG["min_chars"],
) -> list[str]:
    text = _clean_text(text)
    if len(text) <= max_chars:
        return [text] if len(text) >= min_chars else []
    body_limit = max(80, max_chars - overlap_chars)
    blocks = re.split(r"\n\s*\n", text)
    pieces: list[str] = []
    current = ""

    def push_current() -> None:
        nonlocal current
        if current.strip():
            pieces.append(current.strip())
        current = ""

    for block in blocks:
        block = block.strip("\n")
        if not block:
            continue
        if len(block) > body_limit:
            push_current()
            for line in block.splitlines():
                if len(line) > body_limit:
                    for start in range(0, len(line), body_limit):
                        piece = line[start : start + body_limit].strip()
                        if piece:
                            pieces.append(piece)
                    continue
                if len(current) + len(line) + 1 > body_limit:
                    push_current()
                current = (current + "\n" + line).strip("\n")
            push_current()
            continue
        if len(current) + len(block) + 2 > body_limit:
            push_current()
            current = block
        else:
            current = (current + "\n\n" + block).strip("\n")
    push_current()

    if overlap_chars and len(pieces) > 1:
        overlapped: list[str] = []
        for index, piece in enumerate(pieces):
            if index == 0:
                overlapped.append(piece)
                continue
            previous = pieces[index - 1]
            tail = previous[-overlap_chars:]
            if " " in tail:
                tail = tail.split(" ", 1)[1]
            combined = (tail + "\n" + piece).strip()
            overlapped.append(combined[:max_chars].rstrip())
        pieces = overlapped
    return [piece for piece in pieces if len(piece) >= min_chars]


def _document_chunks(
    source: Mapping[str, str], text: str, index_version: str
) -> list[IndexChunk]:
    chunks: list[IndexChunk] = []
    title = source["title"]
    path = source["path"]
    for section, content in _parse_markdown_sections(text, title):
        if section.strip().lower() in {"contents", "table of contents"}:
            continue
        prefix = f"{title} — {section}" if section != title else title
        for part, piece in enumerate(
            _split_text(content), start=1
        ):
            body = _compose([prefix, "", piece])
            accessions = _extract_accessions(prefix + "\n" + piece)
            dataset_ids = _extract_dataset_ids(prefix + "\n" + piece)
            chunks.append(
                make_chunk(
                    document_id=f"doc:{path}",
                    source_type="document",
                    source_reference=f"doc://{path}",
                    section=section,
                    content=body,
                    index_version=index_version,
                    accessions=accessions,
                    dataset_ids=dataset_ids,
                    metadata={
                        "document_title": title,
                        "path": path,
                        "part": part,
                    },
                )
            )
    return chunks


def _validate_citation_ids(
    service: "AnalyticsService",
    candidates: Iterable[str | None],
    *,
    limit: int = 6,
) -> list[str]:
    found: list[str] = []
    for citation_id in dict.fromkeys(
        candidate for candidate in candidates if isinstance(candidate, str)
    ):
        try:
            service.citations.get(citation_id)
        except Exception:
            continue
        found.append(citation_id)
        if len(found) >= limit:
            break
    return found


def _citation_ids_for_dataset(
    service: "AnalyticsService", dataset_id: str, *, limit: int = 4
) -> list[str]:
    try:
        citations = service.citations.list(dataset_id=dataset_id)
    except Exception:
        return []
    return _validate_citation_ids(
        service,
        (citation.get("citation_id") for citation in citations),
        limit=limit,
    )


def _citation_ids_from_references(
    service: "AnalyticsService",
    references: Iterable[Mapping[str, Any]],
    *,
    default: Sequence[str] = (),
    limit: int = 6,
) -> list[str]:
    candidates: list[str] = []
    for reference in references:
        if not isinstance(reference, Mapping):
            continue
        citation_id = reference.get("citation_id")
        if isinstance(citation_id, str):
            candidates.append(citation_id)
        if reference.get("kind") == "nasa_psi_file":
            accession = reference.get("accession")
            file_name = reference.get("file_name") or reference.get("file")
            if isinstance(accession, str) and isinstance(file_name, str):
                citation = service.citations.for_file(accession, file_name)
                if citation:
                    candidates.append(citation["citation_id"])
    candidates.extend(default)
    return _validate_citation_ids(service, candidates, limit=limit)


def _dataset_card(dataset: Mapping[str, Any]) -> str:
    serving = dataset.get("serving") or {}
    use_states = serving.get("use_states") or {}
    reasons = dataset.get("reasons") or []
    restrictions = dataset.get("restrictions") or []
    lines = [
        f"Dataset: {dataset.get('display_name')}",
        _line("Dataset ID", dataset.get("dataset_id")),
        _line("Accession", dataset.get("accession")),
        _line("Experiment family", dataset.get("experiment_family")),
        _line("Canonical tables", dataset.get("canonical_tables")),
        _line("Access scope", dataset.get("access_scope")),
        _line("Base serving state", dataset.get("base_state")),
        _line("Download status", dataset.get("download_status")),
        _line("Measurement file status", dataset.get("measurement_file_status")),
        _line("Quality status", dataset.get("quality_status")),
    ]
    for use, state in sorted(use_states.items()):
        lines.append(f"Serving state ({use}): {state}")
    for reason in reasons:
        if not isinstance(reason, Mapping):
            continue
        code = reason.get("code")
        message = _qualitative_text(reason.get("message"))
        if message:
            lines.append(f"Serving reason ({code}): {message}")
        elif code:
            lines.append(
                f"Serving reason code: {code} "
                "(quantitative detail omitted; use deterministic tools)"
            )
    if restrictions:
        lines.append("Restrictions: " + "; ".join(str(item) for item in restrictions))
    return _compose(lines)


def _investigation_card(
    investigation: Mapping[str, Any], curated_dataset_ids: Sequence[str]
) -> str:
    lines = [
        f"Investigation: {investigation.get('accession')}",
        _line("Acronym", investigation.get("acronym")),
        _line("Title", investigation.get("title")),
        _line("DOI", investigation.get("doi")),
        _line("Research area", investigation.get("research_area")),
        _line("Sub research area", investigation.get("sub_research_area")),
        _line("Project type", investigation.get("project_type")),
        _line("Start date", investigation.get("start_date")),
        _line("End date", investigation.get("end_date")),
        _line("MVP role", investigation.get("mvp_role")),
        _qualitative_line("Rationale", investigation.get("rationale")),
        _qualitative_line("Limitations", investigation.get("limitations")),
        _line("Curated datasets", curated_dataset_ids),
    ]
    return _compose(lines)


def _publication_card(publication: Mapping[str, Any]) -> str:
    related = publication.get("related_investigations") or []
    related_text = "; ".join(
        f"{item.get('accession')} ({item.get('acronym')})"
        if item.get("acronym")
        else str(item.get("accession"))
        for item in related
        if isinstance(item, Mapping) and item.get("accession")
    )
    verification = publication.get("verification") or {}
    lines = [
        "Publication registry record",
        _line("Title", publication.get("title")),
        _line("Authors", publication.get("authors")),
        _line("DOI", publication.get("doi")),
        _line("Status", publication.get("status")),
        _line("Related investigations", related_text),
        _line("Verification", verification.get("status")),
        _line("Unavailable fields", verification.get("unavailable_fields")),
        "The verified registry record contains no abstract, findings, year, or venue. Do not infer findings from the title.",
    ]
    return _compose(lines)


def _limitation_card(limitation: Mapping[str, Any]) -> str:
    lines = [
        f"Dataset limitation: {limitation.get('code')}",
        _line("Limitation ID", limitation.get("limitation_id")),
        _line("Dataset ID", limitation.get("dataset_id")),
        _line("Accession", limitation.get("accession")),
        _line("Scope", limitation.get("scope")),
        _line("Severity", limitation.get("severity")),
        _line("Category", limitation.get("category")),
        _qualitative_line("Explanation", limitation.get("explanation")),
        _line("Affected operations", limitation.get("affected_operations")),
        _line("Resolution status", limitation.get("resolution_status")),
        _qualitative_line("Resolution note", limitation.get("resolution_note")),
    ]
    return _compose(lines)


def _field_card(field: Mapping[str, Any]) -> str:
    calibration = field.get("calibration") or {}
    missingness = field.get("missingness") or {}
    presence = missingness.get("canonical_presence") or {}
    comparability = field.get("comparability") or {}
    rules = comparability.get("rules") or []
    source_columns = field.get("source_columns") or []
    lines = [
        f"Field: {field.get('canonical_name')}",
        _line("Field ID", field.get("field_id")),
        _line("Dataset ID", field.get("dataset_id")),
        _line("Accession", field.get("accession")),
        _qualitative_line("Description", field.get("description")),
        _line("Physical quantity", field.get("physical_quantity")),
        _line("Unit", field.get("unit")),
        _line("Unit status", field.get("unit_status")),
        _line("Value kind", field.get("value_kind")),
        _line("Measurement method", field.get("measurement_method")),
        _line("Calibration status", calibration.get("status")),
        _qualitative_line("Calibration note", calibration.get("note")),
        _line("Availability", missingness.get("availability")),
        _line(
            "Canonical presence",
            (
                f"{presence.get('status')} in {presence.get('table')}."
                f"{presence.get('field')}"
                if presence.get("table") and presence.get("field")
                else presence.get("status")
            ),
        ),
        _line("Missingness restrictions", missingness.get("restrictions")),
        _line("Comparison status", comparability.get("status")),
    ]
    for rule in rules[:3]:
        if isinstance(rule, Mapping) and rule.get("scientific_justification"):
            lines.append(
                f"Comparison note ({rule.get('rule_id')}): "
                f"{rule.get('scientific_justification')}"
            )
    for column in source_columns[:4]:
        if not isinstance(column, Mapping):
            continue
        lines.append(
            "Source column: "
            + "; ".join(
                str(part)
                for part in (
                    column.get("raw_column"),
                    column.get("source_file"),
                    column.get("applies_to"),
                )
                if part
            )
        )
    return _compose(lines)


def _file_card(file: Mapping[str, Any]) -> str:
    availability = file.get("availability")
    verification = file.get("verification") or {}
    lines = [
        f"Curated source file: {file.get('file_name')}",
        _line("Citation ID", file.get("citation_id")),
        _line("Dataset IDs", file.get("dataset_ids")),
        _line("Accession", file.get("accession")),
        _line("Kind", file.get("kind")),
        _line("Priority", file.get("priority")),
        _qualitative_line("Purpose", file.get("purpose")),
        _line("Availability", availability),
        _line("Downloadable", file.get("downloadable")),
        _line("Availability reason", file.get("availability_reason")),
        _line("Verification", verification.get("status")),
        _line("Source URL", file.get("source_url")),
    ]
    return _compose(lines)


def _list_publications_all(service: "AnalyticsService") -> list[dict[str, Any]]:
    publications: list[dict[str, Any]] = []
    offset = 0
    while True:
        envelope = service.list_publications(limit=200, offset=offset)
        page_items = envelope.get("data", {}).get("publications") or []
        publications.extend(page_items)
        page = (envelope.get("meta") or {}).get("page") or {}
        total = int(page.get("total") or len(publications))
        if not page_items or len(publications) >= total:
            break
        offset += len(page_items)
    return publications


def _card_chunks(service: "AnalyticsService", index_version: str) -> list[IndexChunk]:
    chunks: list[IndexChunk] = []
    citation_cache: dict[str, list[str]] = {}

    def dataset_citations(dataset_id: str) -> list[str]:
        if dataset_id not in citation_cache:
            citation_cache[dataset_id] = _citation_ids_for_dataset(
                service, dataset_id
            )
        return citation_cache[dataset_id]

    datasets = service.list_datasets(limit=50).get("data") or []
    for dataset in datasets:
        dataset_id = dataset.get("dataset_id")
        accession = dataset.get("accession")
        if not dataset_id or not accession:
            continue
        citations = dataset_citations(dataset_id)
        chunks.append(
            make_chunk(
                document_id=f"dataset:{dataset_id}",
                source_type="dataset",
                source_reference=f"dataset://{dataset_id}",
                accession=accession,
                dataset_id=dataset_id,
                citation_ids=citations,
                accessions=[accession],
                dataset_ids=[dataset_id],
                content=_dataset_card(dataset),
                section="dataset card",
                index_version=index_version,
                metadata={
                    "dataset_id": dataset_id,
                    "accession": accession,
                    "experiment_family": dataset.get("experiment_family"),
                },
            )
        )

        try:
            fields = (
                service.list_dataset_fields(dataset_id, limit=100)
                .get("data", {})
                .get("fields")
                or []
            )
        except Exception:
            fields = []
        for field in fields:
            field_id = field.get("field_id")
            if not field_id:
                continue
            field_citations = _citation_ids_from_references(
                service,
                field.get("source_references") or [],
                default=citations,
            )
            chunks.append(
                make_chunk(
                    document_id=f"field:{field_id}",
                    source_type="field",
                    source_reference=f"field://{dataset_id}/{field_id}",
                    accession=accession,
                    dataset_id=dataset_id,
                    citation_ids=field_citations,
                    accessions=[accession],
                    dataset_ids=[dataset_id],
                    content=_field_card(field),
                    section="field definition",
                    index_version=index_version,
                    metadata={
                        "field_id": field_id,
                        "dataset_id": dataset_id,
                        "accession": accession,
                        "canonical_name": field.get("canonical_name"),
                        "unit": field.get("unit"),
                        "value_kind": field.get("value_kind"),
                    },
                )
            )

        try:
            files = (
                service.list_dataset_files(dataset_id, limit=50)
                .get("data", {})
                .get("files")
                or []
            )
        except Exception:
            files = []
        for file in files:
            citation_id = file.get("citation_id")
            if not citation_id:
                continue
            valid = _validate_citation_ids(service, [citation_id], limit=1)
            if not valid:
                continue
            chunks.append(
                make_chunk(
                    document_id=f"file:{citation_id}",
                    source_type="file",
                    source_reference=f"citation://{citation_id}",
                    accession=accession,
                    dataset_id=dataset_id,
                    citation_ids=valid,
                    accessions=[accession],
                    dataset_ids=[dataset_id],
                    content=_file_card(file),
                    section="source file",
                    index_version=index_version,
                    metadata={
                        "citation_id": citation_id,
                        "dataset_id": dataset_id,
                        "accession": accession,
                        "file_name": file.get("file_name"),
                        "availability": file.get("availability"),
                        "downloadable": file.get("downloadable"),
                    },
                )
            )

        try:
            limitations = (
                service.list_dataset_limitations(dataset_id, limit=100)
                .get("data", {})
                .get("limitations")
                or []
            )
        except Exception:
            limitations = []
        for limitation in limitations:
            limitation_id = limitation.get("limitation_id")
            if not limitation_id:
                continue
            limitation_citations = _citation_ids_from_references(
                service,
                limitation.get("evidence") or [],
                default=citations,
            )
            chunks.append(
                make_chunk(
                    document_id=f"limitation:{limitation_id}",
                    source_type="limitation",
                    source_reference=(
                        f"limitation://{dataset_id}/{limitation_id}"
                    ),
                    accession=accession,
                    dataset_id=dataset_id,
                    citation_ids=limitation_citations,
                    accessions=[accession],
                    dataset_ids=[dataset_id],
                    content=_limitation_card(limitation),
                    section="limitation",
                    index_version=index_version,
                    metadata={
                        "limitation_id": limitation_id,
                        "dataset_id": dataset_id,
                        "accession": accession,
                        "code": limitation.get("code"),
                        "severity": limitation.get("severity"),
                        "category": limitation.get("category"),
                        "scope": limitation.get("scope"),
                    },
                )
            )

    investigations = service.list_investigations(limit=50).get("data") or []
    for investigation in investigations:
        accession = investigation.get("accession")
        if not accession:
            continue
        try:
            curated = service.list_datasets(accession=accession, limit=50).get(
                "data"
            ) or []
        except Exception:
            curated = []
        curated_ids = [
            dataset["dataset_id"]
            for dataset in curated
            if dataset.get("dataset_id")
        ]
        citations: list[str] = []
        for dataset_id in curated_ids:
            citations.extend(dataset_citations(dataset_id))
        citations = _validate_citation_ids(service, citations, limit=6)
        chunks.append(
            make_chunk(
                document_id=f"investigation:{accession}",
                source_type="investigation",
                source_reference=f"investigation://{accession}",
                accession=accession,
                citation_ids=citations,
                accessions=[accession],
                dataset_ids=curated_ids,
                content=_investigation_card(investigation, curated_ids),
                section="investigation card",
                index_version=index_version,
                metadata={
                    "accession": accession,
                    "acronym": investigation.get("acronym"),
                    "title": investigation.get("title"),
                    "doi": investigation.get("doi"),
                    "research_area": investigation.get("research_area"),
                    "curated_dataset_ids": curated_ids,
                },
            )
        )

    for publication in _list_publications_all(service):
        publication_id = publication.get("publication_id")
        if not publication_id:
            continue
        related = publication.get("related_investigations") or []
        related_accessions = [
            item["accession"]
            for item in related
            if isinstance(item, Mapping) and item.get("accession")
        ]
        chunks.append(
            make_chunk(
                document_id=f"publication:{publication_id}",
                source_type="publication",
                source_reference=f"publication://{publication_id}",
                accession=related_accessions[0] if len(related_accessions) == 1 else None,
                accessions=related_accessions,
                content=_publication_card(publication),
                section="publication registry record",
                index_version=index_version,
                metadata={
                    "publication_id": publication_id,
                    "title": publication.get("title"),
                    "doi": publication.get("doi"),
                    "authors": publication.get("authors"),
                    "related_accessions": related_accessions,
                    "verification_status": (publication.get("verification") or {}).get(
                        "status"
                    ),
                },
            )
        )
    return chunks


def _dedupe_chunks(chunks: Iterable[IndexChunk]) -> list[IndexChunk]:
    deduped: list[IndexChunk] = []
    seen: dict[tuple[str, str | None, str], IndexChunk] = {}
    for chunk in chunks:
        key = (chunk.document_id, chunk.section, chunk.content_hash)
        existing = seen.get(key)
        if existing is None:
            seen[key] = chunk
            deduped.append(chunk)
            continue
        merged = IndexChunk(
            **{
                **existing.to_dict(),
                "citation_ids": _unique(
                    list(existing.citation_ids) + list(chunk.citation_ids)
                ),
                "citation_id": (
                    existing.citation_id or chunk.citation_id
                ),
                "accessions": _unique(
                    list(existing.accessions) + list(chunk.accessions)
                ),
                "dataset_ids": _unique(
                    list(existing.dataset_ids) + list(chunk.dataset_ids)
                ),
                "metadata": _json_safe(
                    {**existing.metadata, **chunk.metadata}
                ),
            }
        )
        deduped[deduped.index(existing)] = merged
        seen[key] = merged
    return deduped


def _chunk_digest(chunks: Sequence[IndexChunk]) -> str:
    payload = [chunk.to_dict() for chunk in chunks]
    return _sha256_text(
        json.dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )
    )


def _source_digest(sources: Sequence[Mapping[str, Any]]) -> str:
    payload = {
        source["path"]: source["sha256"]
        for source in sorted(sources, key=lambda item: item["path"])
    }
    return _sha256_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
    )


def _config_payload() -> dict[str, Any]:
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "card_builder_version": CARD_BUILDER_VERSION,
        "chunking": CHUNKING_CONFIG,
        "embedding": EMBEDDING_CONFIG,
        "retrieval": RETRIEVAL_CONFIG,
    }


def _config_digest() -> str:
    return _sha256_text(
        json.dumps(_config_payload(), sort_keys=True, separators=(",", ":"))
    )


def _index_version(
    config_digest: str,
    source_digest: str,
    dataset_version: str = "",
    registry_version: str = "",
) -> str:
    return (
        f"{INDEX_VERSION_PREFIX}-"
        + _sha256_text(
            f"{config_digest}:{source_digest}:{dataset_version}:{registry_version}"
        )[:12]
    )


def compute_source_hashes(root: Path | str | None = None) -> list[dict[str, Any]]:
    base = Path(root).expanduser().resolve() if root else repo_root()
    sources: list[dict[str, Any]] = []
    for source in (*DOCUMENT_SOURCES, *METADATA_SOURCES):
        relative = source["path"]
        path = (base / relative).resolve()
        if base not in path.parents:
            raise RetrievalError("retrieval source escapes the repository root")
        if not path.is_file():
            raise RetrievalError(
                "required retrieval source is missing",
                details={"path": relative},
            )
        data = path.read_bytes()
        sources.append(
            {
                "source_id": source["source_id"],
                "kind": source.get("kind", "document"),
                "path": relative,
                "sha256": _sha256_bytes(data),
                "bytes": len(data),
            }
        )
    return sorted(sources, key=lambda item: item["path"])


def build_index(
    service: "AnalyticsService | None" = None,
    *,
    root: Path | str | None = None,
    include_cards: bool = True,
) -> "RetrievalIndex":
    base = Path(root).expanduser().resolve() if root else repo_root()
    sources = compute_source_hashes(base)
    source_digest = _source_digest(sources)
    config_digest = _config_digest()
    dataset_version = (
        service.bundle.dataset_version if service is not None else "unknown"
    )
    registry_version = (
        service.bundle.registry_version if service is not None else "unknown"
    )
    index_version = _index_version(
        config_digest,
        source_digest,
        dataset_version,
        registry_version,
    )

    chunks: list[IndexChunk] = []
    for source in DOCUMENT_SOURCES:
        text = (base / source["path"]).read_text(encoding="utf-8")
        chunks.extend(_document_chunks(source, text, index_version))
    if include_cards:
        if service is None:
            raise RetrievalError(
                "an analytics service is required to build verified metadata cards"
            )
        chunks.extend(_card_chunks(service, index_version))
    chunks = _dedupe_chunks(chunks)
    if not chunks:
        raise RetrievalError("retrieval index has no chunks")

    document_count = len({chunk.document_id for chunk in chunks})
    manifest = IndexManifest(
        index_version=index_version,
        schema_version=INDEX_SCHEMA_VERSION,
        dataset_version=dataset_version,
        registry_version=registry_version,
        generated_at=datetime.now(timezone.utc).isoformat(),
        build_command=BUILD_COMMAND,
        validation_command=VALIDATION_COMMAND,
        chunking=dict(CHUNKING_CONFIG),
        embedding=dict(EMBEDDING_CONFIG),
        retrieval=dict(RETRIEVAL_CONFIG),
        sources=tuple(sources),
        chunk_count=len(chunks),
        document_count=document_count,
        chunk_digest=_chunk_digest(chunks),
        source_digest=source_digest,
        config_digest=config_digest,
        notes=MANIFEST_NOTES,
    )
    return RetrievalIndex(chunks, manifest)


class RetrievalIndex:
    """A deterministic hybrid index over verified chunks."""

    def __init__(
        self, chunks: Sequence[IndexChunk], manifest: IndexManifest
    ) -> None:
        self.chunks = tuple(chunks)
        self.manifest = manifest
        self._dataset_accession: dict[str, str] = {}
        for chunk in self.chunks:
            if chunk.dataset_id and chunk.accession:
                self._dataset_accession[chunk.dataset_id] = chunk.accession
        self._tokens = [tokenize(chunk.content) for chunk in self.chunks]
        self._bm25 = _BM25(self._tokens)
        self._tfidf = _HashingTfidf(self._tokens)

    @classmethod
    def from_chunks(
        cls,
        chunks: Sequence[IndexChunk],
        manifest: IndexManifest | None = None,
    ) -> "RetrievalIndex":
        if manifest is None:
            chunk_list = list(chunks)
            manifest = IndexManifest(
                index_version=(
                    chunk_list[0].index_version if chunk_list else "test-index"
                ),
                schema_version=INDEX_SCHEMA_VERSION,
                dataset_version="test",
                registry_version="test",
                generated_at=datetime.now(timezone.utc).isoformat(),
                build_command=BUILD_COMMAND,
                validation_command=VALIDATION_COMMAND,
                chunking=dict(CHUNKING_CONFIG),
                embedding=dict(EMBEDDING_CONFIG),
                retrieval=dict(RETRIEVAL_CONFIG),
                sources=(),
                chunk_count=len(chunk_list),
                document_count=len({chunk.document_id for chunk in chunk_list}),
                chunk_digest=_chunk_digest(chunk_list),
                source_digest="test",
                config_digest="test",
                notes=MANIFEST_NOTES,
            )
        return cls(chunks, manifest)

    def _matches_scope(
        self,
        chunk: IndexChunk,
        accession: str | None,
        dataset_id: str | None,
        source_types: Sequence[str],
    ) -> bool:
        if source_types and chunk.source_type not in source_types:
            return False
        if accession:
            if chunk.accession != accession and accession not in chunk.accessions:
                return False
        if dataset_id:
            if dataset_id in chunk.dataset_ids:
                return True
            expected_accession = self._dataset_accession.get(dataset_id)
            if chunk.source_type in {"dataset", "field", "limitation", "file"}:
                return False
            if expected_accession and (
                chunk.accession == expected_accession
                or expected_accession in chunk.accessions
            ):
                return True
            return False
        return True

    def search(
        self,
        query: str,
        *,
        accession: str | None = None,
        dataset_id: str | None = None,
        source_types: Sequence[str] | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        cleaned_query = _clean_text(query, limit=300)
        if not cleaned_query:
            raise RetrievalError("retrieval query is empty")
        if not 1 <= limit <= 20:
            raise RetrievalError("retrieval limit must be between 1 and 20")
        requested_types = tuple(dict.fromkeys(source_types or ()))
        invalid_types = set(requested_types) - SOURCE_TYPES
        if invalid_types:
            raise RetrievalError(
                "retrieval source type is not approved",
                details={"invalid": sorted(invalid_types)},
            )
        if accession:
            accession = accession.upper()
        if dataset_id:
            dataset_id = dataset_id.lower()

        tokens = tokenize(cleaned_query)
        candidates = [
            index
            for index, chunk in enumerate(self.chunks)
            if self._matches_scope(
                chunk, accession, dataset_id, requested_types
            )
        ]
        base_payload = {
            "query": cleaned_query,
            "filters": {
                "accession": accession,
                "dataset_id": dataset_id,
                "source_types": list(requested_types),
            },
            "index_version": self.manifest.index_version,
            "dataset_version": self.manifest.dataset_version,
            "retrieval_method": RETRIEVAL_CONFIG["method"],
            "embedding_model": EMBEDDING_CONFIG["model"],
            "chunk_count": len(self.chunks),
            "candidate_count": len(candidates),
        }
        if not tokens:
            return {
                **base_payload,
                "returned": 0,
                "total_candidates": 0,
                "results": [],
                "warnings": ["The query contains no searchable scientific terms."],
            }
        if not candidates:
            return {
                **base_payload,
                "returned": 0,
                "total_candidates": 0,
                "results": [],
                "warnings": ["No verified chunks match the requested metadata scope."],
            }

        bm25_scores = self._bm25.scores(tokens)
        query_vector = self._tfidf.query_vector(tokens)
        vector_scores = [
            self._tfidf.score(query_vector, index)
            for index in range(len(self.chunks))
        ]
        maximum_bm25 = max(bm25_scores[index] for index in candidates) or 0.0
        scored: list[tuple[float, float, float, bool, int]] = []
        query_lower = cleaned_query.lower()
        intent_types = _source_intent_types(cleaned_query)
        identifiers = _identifier_tokens(cleaned_query)
        query_accessions = {
            match.group(0).upper()
            for match in ACCESSION_QUERY_RE.finditer(cleaned_query)
        }
        query_datasets = {
            match.group(0).lower()
            for match in DATASET_QUERY_RE.finditer(cleaned_query)
        }
        for index in candidates:
            chunk = self.chunks[index]
            bm25 = bm25_scores[index]
            vector = vector_scores[index]
            if bm25 <= 0.0 and vector <= 0.0:
                continue
            bm25_normalized = bm25 / maximum_bm25 if maximum_bm25 else 0.0
            content_lower = chunk.content.lower()
            exact = query_lower in content_lower
            hybrid = (
                RETRIEVAL_CONFIG["bm25_weight"] * bm25_normalized
                + RETRIEVAL_CONFIG["vector_weight"] * vector
            )
            if exact:
                hybrid += RETRIEVAL_CONFIG["exact_match_boost"]
            if chunk.source_type in intent_types:
                hybrid += RETRIEVAL_CONFIG["source_intent_boost"]
            if (
                chunk.source_type == "field"
                and identifiers
                and any(identifier in content_lower for identifier in identifiers)
            ):
                hybrid += RETRIEVAL_CONFIG["identifier_match_boost"]
            if (
                chunk.source_type in {"dataset", "field", "limitation", "file"}
                and (
                    (
                        query_accessions
                        and chunk.accession
                        and chunk.accession.upper() in query_accessions
                    )
                    or (
                        query_datasets
                        and chunk.dataset_id
                        and chunk.dataset_id.lower() in query_datasets
                    )
                )
            ):
                hybrid += RETRIEVAL_CONFIG["metadata_scope_boost"]
            scored.append(
                (min(1.0, hybrid), bm25, vector, exact, index)
            )
        scored.sort(
            key=lambda item: (
                -item[0],
                self.chunks[item[4]].document_id,
                self.chunks[item[4]].chunk_id,
            )
        )

        results: list[dict[str, Any]] = []
        seen_hashes: set[str] = set()
        per_document: Counter[str] = Counter()
        for item in scored:
            chunk = self.chunks[item[4]]
            if chunk.content_hash in seen_hashes:
                continue
            if per_document[chunk.document_id] >= RETRIEVAL_CONFIG["max_per_document"]:
                continue
            seen_hashes.add(chunk.content_hash)
            per_document[chunk.document_id] += 1
            results.append(self._result(item, len(results) + 1))
            if len(results) >= limit:
                break

        warnings: list[str] = []
        if any(result["source_type"] == "document" for result in results):
            warnings.append(
                "Document chunks are repository documentation, not Phase 4 citations."
            )
        if any(result["source_type"] == "publication" for result in results):
            warnings.append(
                "Publication cards contain registry metadata only; no abstract, findings, year, or venue are available."
            )
        if not results:
            warnings.append("No verified chunk matched the query terms.")
        return {
            **base_payload,
            "returned": len(results),
            "total_candidates": len(scored),
            "results": results,
            "warnings": warnings,
        }

    def _result(
        self,
        item: tuple[float, float, float, bool, int],
        rank: int,
    ) -> dict[str, Any]:
        hybrid, bm25, vector, exact, index = item
        chunk = self.chunks[index]
        return {
            "rank": rank,
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "source_type": chunk.source_type,
            "source_reference": chunk.source_reference,
            "accession": chunk.accession,
            "dataset_id": chunk.dataset_id,
            "citation_id": chunk.citation_id,
            "citation_ids": list(chunk.citation_ids),
            "section": chunk.section,
            "content": chunk.content,
            "content_hash": chunk.content_hash,
            "index_version": chunk.index_version,
            "scores": {
                "bm25": round(bm25, 6),
                "vector": round(vector, 6),
                "hybrid": round(hybrid, 6),
            },
            "exact_match": exact,
            "metadata": _json_safe(chunk.metadata),
        }

    def validate(
        self,
        *,
        root: Path | str | None = None,
        verify_sources: bool = False,
    ) -> dict[str, Any]:
        errors: list[str] = []
        if self.manifest.schema_version != INDEX_SCHEMA_VERSION:
            errors.append("index schema version does not match this application")
        expected_version = _index_version(
            self.manifest.config_digest,
            self.manifest.source_digest,
            self.manifest.dataset_version,
            self.manifest.registry_version,
        )
        if self.manifest.index_version != expected_version:
            errors.append("index version does not match its manifest digests")
        if self.manifest.chunk_count != len(self.chunks):
            errors.append("manifest chunk count does not match the index")
        if self.manifest.document_count != len(
            {chunk.document_id for chunk in self.chunks}
        ):
            errors.append("manifest document count does not match the index")
        if self.manifest.chunk_digest != _chunk_digest(self.chunks):
            errors.append("manifest chunk digest does not match the index")

        seen_ids: set[str] = set()
        seen_documents: set[str] = set()
        for chunk in self.chunks:
            seen_documents.add(chunk.document_id)
            if chunk.chunk_id in seen_ids:
                errors.append(f"duplicate chunk ID: {chunk.chunk_id}")
            seen_ids.add(chunk.chunk_id)
            if chunk.source_type not in SOURCE_TYPES:
                errors.append(f"unknown source type: {chunk.source_type}")
            if chunk.content_hash != _sha256_text(chunk.content):
                errors.append(f"content hash mismatch: {chunk.chunk_id}")
            if chunk.chunk_id != _expected_chunk_id(
                chunk.document_id, chunk.section, chunk.content_hash
            ):
                errors.append(f"chunk ID mismatch: {chunk.chunk_id}")
            if chunk.index_version != self.manifest.index_version:
                errors.append(f"chunk index version mismatch: {chunk.chunk_id}")
            if len(chunk.content) > MAX_CHUNK_CHARS:
                errors.append(f"chunk exceeds the configured size: {chunk.chunk_id}")

        if verify_sources:
            try:
                current_sources = compute_source_hashes(root)
            except RetrievalError as exc:
                errors.append(str(exc))
            else:
                if _source_digest(current_sources) != self.manifest.source_digest:
                    errors.append(
                        "retrieval sources changed since the index was built"
                    )
                if self.manifest.sources != tuple(current_sources):
                    errors.append(
                        "retrieval source manifest does not match current sources"
                    )
        return {
            "valid": not errors,
            "errors": errors[:20],
            "index_version": self.manifest.index_version,
            "chunk_count": len(self.chunks),
            "document_count": len(seen_documents),
        }

    def to_payload(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "chunks": [chunk.to_dict() for chunk in self.chunks],
        }

    def write(self, path: Path | str) -> Path:
        destination = Path(path).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(
                self.to_payload(),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            ),
            encoding="utf-8",
        )
        return destination

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "RetrievalIndex":
        if not isinstance(payload, Mapping):
            raise RetrievalError("index payload must be an object")
        manifest_payload = payload.get("manifest")
        chunk_payloads = payload.get("chunks")
        if not isinstance(manifest_payload, Mapping) or not isinstance(
            chunk_payloads, list
        ):
            raise RetrievalError("index payload is malformed")
        manifest = IndexManifest.from_dict(manifest_payload)
        chunks = [IndexChunk.from_dict(item) for item in chunk_payloads]
        return cls(chunks, manifest)

    @classmethod
    def load(
        cls,
        path: Path | str,
        *,
        root: Path | str | None = None,
        verify_sources: bool = True,
    ) -> "RetrievalIndex":
        source_path = Path(path).expanduser()
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RetrievalError("retrieval index is not readable") from exc
        index = cls.from_payload(payload)
        report = index.validate(root=root, verify_sources=verify_sources)
        if not report["valid"]:
            raise RetrievalError(
                "retrieval index validation failed",
                details={"errors": report["errors"]},
            )
        return index

    def status(self) -> dict[str, Any]:
        return {
            "index_version": self.manifest.index_version,
            "schema_version": self.manifest.schema_version,
            "dataset_version": self.manifest.dataset_version,
            "registry_version": self.manifest.registry_version,
            "generated_at": self.manifest.generated_at,
            "chunk_count": self.manifest.chunk_count,
            "document_count": self.manifest.document_count,
            "retrieval_method": RETRIEVAL_CONFIG["method"],
            "embedding_model": EMBEDDING_CONFIG["model"],
            "embedding_note": EMBEDDING_CONFIG["note"],
            "source_count": len(self.manifest.sources),
            "build_command": self.manifest.build_command,
            "validation_command": self.manifest.validation_command,
            "notes": list(self.manifest.notes),
        }


_INDEX_LOCK = threading.Lock()
_INDEX_CACHE: RetrievalIndex | None = None
_INDEX_CACHE_KEY: tuple[str, str] | None = None


def get_default_index(
    service: "AnalyticsService",
    *,
    path: Path | str | None = None,
    force_rebuild: bool = False,
) -> RetrievalIndex:
    """Load the committed build artifact or rebuild it deterministically.

    A stale, missing, or invalid index never blocks the assistant: the index is
    rebuilt in memory from the same verified sources. The build script is the
    supported way to write a reusable index artifact.
    """

    global _INDEX_CACHE, _INDEX_CACHE_KEY
    cache_key = (service.bundle.dataset_version, service.bundle.registry_version)
    with _INDEX_LOCK:
        if (
            not force_rebuild
            and _INDEX_CACHE is not None
            and _INDEX_CACHE_KEY == cache_key
        ):
            return _INDEX_CACHE
        index_path = (
            Path(path).expanduser()
            if path is not None
            else repo_root() / DEFAULT_INDEX_PATH
        )
        try:
            index = RetrievalIndex.load(
                index_path, root=repo_root(), verify_sources=True
            )
            if (
                index.manifest.dataset_version != service.bundle.dataset_version
                or index.manifest.registry_version
                != service.bundle.registry_version
            ):
                raise RetrievalError(
                    "retrieval index dataset or registry version does not match "
                    "the loaded analytics service"
                )
            LOGGER.info(
                "assistant_retrieval_index_loaded index_version=%s chunks=%d",
                index.manifest.index_version,
                index.manifest.chunk_count,
            )
        except Exception as exc:
            LOGGER.info(
                "assistant_retrieval_index_rebuilt reason=%s",
                type(exc).__name__,
            )
            index = build_index(service)
        _INDEX_CACHE = index
        _INDEX_CACHE_KEY = cache_key
        return index


def reset_default_index() -> None:
    """Clear the process-local index cache (used by tests)."""

    global _INDEX_CACHE, _INDEX_CACHE_KEY
    with _INDEX_LOCK:
        _INDEX_CACHE = None
        _INDEX_CACHE_KEY = None
