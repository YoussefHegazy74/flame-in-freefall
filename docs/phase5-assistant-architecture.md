# Phase 5 — Grounded Research Assistant Architecture

**Project:** Flame in Freefall
**Team:** AFAQ
**Contract version:** 1.0.0
**Status:** Milestone C (verified retrieval)

This document defines the Phase 5 architecture before any model provider is
selected. The assistant is a controlled layer over the verified Phase 1–4
artifacts. It is not a new source of truth, it does not replace the analytics
service, and it does not become authoritative when a model is configured.

---

## 1. Goals

1. Answer questions about the curated NASA PSI combustion data using verified
   evidence.
2. Route every numerical question through a deterministic backend tool.
3. Attach a resolvable Phase 4 citation to every supported factual claim.
4. Preserve units, value kinds, missingness, and comparison restrictions.
5. Refuse unsupported requests explicitly instead of guessing.
6. Continue to work with no LLM configured.
7. Treat retrieved text as untrusted evidence, never as instructions.

## 2. Non-goals

- No fire-risk score, material ranking, or spacecraft fire-safety guarantee.
- No causal claims from correlation.
- No fabricated publications, authors, DOIs, URLs, measurements, or citations.
- No paired comparison values while the alignment registry is empty.
- No arbitrary SQL, filesystem paths, URLs, or code execution.
- No replacement for the Phase 3/4 exploration pages.

---

## 3. Baseline

Phase 4 is the baseline at commit
`1e35c262a5e9c4ad3041bf26d36392d8793c4df6`. The assistant reuses:

- `AnalyticsService` for catalog, dataset, citation, provenance, comparison,
  gas-flame, material, droplet, telemetry, smoke, publication, and metadata
  responses;
- `AnalyticsDatabase` for bounded canonical-table access;
- `CitationRegistry` and `get_citation` for file and row citation resolution;
- `ComparabilityEngine`, `MeasurementIntegrity`, and
  `PairedComparisonRegistry` for comparison decisions;
- `ServingEngine` for dataset and measurement states;
- `DatasetMetadata` for files, fields, and limitations;
- `PublicationRegistry` for verified publication records.

The assistant calls these methods internally. It does not make HTTP requests
to its own API.

---

## 4. Components

```
User question
    |
    v
AssistantQuery (validated)
    |
    v
Intent classifier / planner  <--- ConversationContext (non-authoritative)
    |
    +--> Deterministic tools ---> AnalyticsService / AnalyticsDatabase
    |         |                        |
    |         |                        +--> canonical Parquet tables
    |         |                        +--> registries and reports
    |         v
    |    ToolResult (bounded, hashed)
    |
    +--> Retrieval (verified documents, dataset cards, investigations,
    |               publications) -> EvidenceItem list
    |
    v
Answer composer (deterministic; optional provider may rephrase)
    |
    v
Claim + citation validation
    |
    v
AssistantAnswer (contract 1.0.0)
    |
    v
API envelope + frontend evidence panel
```

### 4.1 Contract (`src/assistant/contract.py`)

The versioned Pydantic models are the boundary. The deterministic provider
and any optional LLM provider must both produce `AssistantAnswer`. The model
rejects invalid combinations such as a numerical claim without a tool call,
an unavailable citation marked downloadable, or a high-confidence answer
without fully supported evidence.

### 4.2 Configuration (`src/assistant/config.py`)

Environment-driven settings with validation. Secrets are excluded from
`repr`, status payloads, logs, and errors. Invalid optional provider
configuration degrades to the deterministic provider and reports a safe
reason. See `.env.example` and `docs/assistant-answer-contract.md` §7.

### 4.3 Conversation (`src/assistant/conversation.py`)

A bounded, process-local store. It resolves follow-up references such as
"what about its pressure?" but is explicitly non-authoritative. Previous
answers are never evidence; every number and citation is re-resolved.

### 4.4 Tools (`src/assistant/tools.py`, Milestone B)

A strict allowlist of named tools with typed argument schemas. Each tool
wraps an existing service method and returns a bounded result with a hash,
duration, status, and safe summary. There is no arbitrary SQL, path, URL, or
code tool.

### 4.5 Retrieval (`src/assistant/retrieval.py`, Milestone C)

A reproducible index over verified documents and metadata. BM25 is the
required lexical baseline. A deterministic TF-IDF vector score provides a
hybrid ranking without an external embedding dependency. Every chunk keeps
its document ID, source reference, accession, dataset ID, citation ID when
available, section, content hash, and index version.

The index covers committed documentation plus dataset, investigation,
publication, limitation, field, and curated-file cards generated from the
Phase 1-4 registries. Metadata cards omit count-bearing prose so retrieval
cannot become a numerical source; numbers come from deterministic tools.
Retrieved text is labeled untrusted evidence, never instructions.

The manifest records the index schema, chunking and embedding configuration,
retrieval weights, source SHA-256 values, dataset and registry versions,
chunk digest, build timestamp, and build/validation commands. The generated
artifact is gitignored. Build and check it with:

```bash
.venv/bin/python scripts/build_assistant_index.py
.venv/bin/python scripts/build_assistant_index.py --check
```

A missing, stale, or version-mismatched index is rebuilt in memory from the
same verified sources, so retrieval never blocks the assistant.

### 4.6 Orchestration (`src/assistant/orchestrator.py`, Milestone D)

The orchestrator classifies intent, selects tools, executes them, retrieves
context, composes a draft answer, validates claims and citations, and
returns the contract. Provider output cannot bypass these steps.

### 4.7 Provider abstraction (`src/assistant/providers.py`, Milestone D)

`deterministic` is the default and the fallback. `openai_compatible` is
optional. A provider may propose a plan or rephrase a draft, but it never
controls tool implementation, security boundaries, citations, or validation.
Provider failures return a deterministic answer with `fallback_mode=true`
and a safe `fallback_reason`.

### 4.8 Validation (`src/assistant/citation_validation.py` and Milestone D)

Citation validation resolves every ID through the Phase 4 implementation.
Claim validation checks tool linkage, units, value kinds, limitations, and
comparison decisions. A failed validation produces a safe response, not a
repaired or invented citation.

### 4.9 API (`backend/app.py`, Milestone D)

Routes under `/api/v1/assistant`:

- `GET /api/v1/assistant/status`
- `GET /api/v1/assistant/suggestions`
- `GET /api/v1/assistant/tools`
- `POST /api/v1/assistant/query`

The existing read-only endpoints are unchanged. CORS adds `POST` only for the
assistant query route.

### 4.10 Frontend (`frontend/src/app/assistant`, Milestone E)

A conversation area, evidence panel, citation drawer integration, suggested
questions, fallback/provider status, and explicit scientific transparency.
The frontend renders the contract; it does not reimplement validation.

---

## 5. Separation of retrieval and analytics

| Question kind | Source of truth | Allowed in RAG? |
|---|---|---|
| Counts, averages, min/max, distributions | Deterministic tool over canonical tables | No |
| Actual experimental values | Deterministic tool | No |
| Telemetry and smoke series | Deterministic tool | No |
| Quality statistics | Deterministic tool and registries | Explanation only |
| Comparison eligibility | Comparability service | Explanation only |
| Paired observations | Paired-value service only | Never inferred |
| Investigation objectives | Verified metadata and documents | Yes |
| Dataset structure | Verified metadata and data dictionary | Yes |
| Publications | Publication registry | Yes |
| Limitations and methodology | Verified documents and registries | Yes |

If a numerical question has no appropriate tool, the answer is
`insufficient_evidence` or `unavailable_data`. The model must not calculate a
statistic from retrieved prose.

---

## 6. Evidence and citation flow

1. Tools return canonical values and provenance references.
2. The application resolves file and row citations through
   `AnalyticsService.get_citation`.
3. The validator checks existence, kind, locator, verification status,
   availability, accession/dataset scope, and safe source URLs.
4. Only resolved `CitationReference` objects enter the answer.
5. Retrieved documents without a resolvable citation remain `EvidenceItem`
   entries with `citation_id=null`. They are not presented as verified
   citations.
6. Unavailable files remain `availability="unavailable"` and
   `downloadable=false`.

---

## 7. Provider and fallback behavior

| Configuration | Mode | Behavior |
|---|---|---|
| `FLAME_ASSISTANT_ENABLED=false` | disabled | Assistant routes report disabled; exploration pages unchanged. |
| No LLM variables | deterministic | Full deterministic planner, tools, retrieval, validation. |
| `FLAME_LLM_PROVIDER=openai_compatible` and valid config | provider | Provider may plan/rephrase; deterministic validation still runs. |
| Provider timeout/error/invalid output | fallback | Deterministic answer with `fallback_mode=true` and safe reason. |
| Invalid optional provider config | deterministic | Safe `config_error`; the API still starts. |

The rest of the platform never depends on a paid provider.

---

## 8. Security boundaries

- Retrieved text is data, never instructions.
- Tool allowlist and strict argument schemas.
- No arbitrary SQL, filesystem, URL, or code execution.
- No secret or environment access.
- No raw data directory access from the planner.
- Bounded pagination, result caps, tool-call limits, and timeouts.
- Structured logs record tool name, validated arguments, status, duration,
  and request ID. Secrets and unnecessary user content are not logged.
- Prompt injection inside retrieved chunks is quoted or ignored, never
  executed.

See `docs/assistant-security.md` for the threat model and adversarial tests.

---

## 9. Failure and refusal behavior

| Situation | Result |
|---|---|
| Unknown citation | Validation failure; safe `insufficient_evidence` response. |
| Row citation does not resolve | Validation failure; no fabricated replacement. |
| Missing values requested as zero | Refusal; `insufficient_evidence`. |
| Ambiguous unit conversion | Refusal; `insufficient_evidence`. |
| Measurement absent from canonical table | `unavailable_data` with the field and reason. |
| Comparison unregistered | `not_comparable` explanation; no paired values. |
| Comparison registered but conditions unverified | `conditions_not_verified`; no paired values. |
| Paired alignment empty | `no_verified_alignment`; no paired values. |
| Provider unavailable | Deterministic fallback with a visible reason. |
| Prompt injection | Quoted as untrusted content; no tool or secret action. |

---

## 10. Milestones

- **A — Audit and contracts:** answer schema, golden questions, citation
  validator contract, architecture and contract documentation.
- **B — Deterministic tools:** allowlisted wrappers, aggregation, tests.
- **C — Retrieval:** verified-document ingestion, BM25 + TF-IDF hybrid,
  manifest, build script, tests.
- **D — Orchestration:** intent classification, controlled tool calls,
  grounded composition, claim/citation validation, fallback, API.
- **E — Frontend:** `/assistant`, conversation, evidence, citation drawer,
  status, accessibility.
- **F — Evaluation:** golden evaluation, adversarial tests, provider
  failures, full regression.
- **G — Documentation and release:** docs updates, review, commit, push,
  remote SHA verification.

---

## 11. Known limitations at Milestone A

- No real LLM credentials are available. Real-model evaluation will be
  reported separately from deterministic/mock-provider tests.
- The paired-alignment registry is empty. Paired values remain unavailable.
- PSI-159 `pressure_initial_atm` and PSI-10 `pressure_approx_bar` have zero
  canonical values.
- The two PSI-98 telemetry/sensor workbooks return HTTP 404.
- The assistant is not scientifically validated merely because its software
  tests pass. Evaluation is reported per metric, with failure categories and
  known limitations.
