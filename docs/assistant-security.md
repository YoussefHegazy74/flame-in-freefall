# Phase 5 — Assistant Security and Trust Boundaries

**Status:** Milestone D
**Scope:** `/api/v1/assistant` and `src/assistant/*`

The assistant is a controlled layer over verified Phase 1–4 artifacts. It is
not an autonomous agent. The deterministic planner selects tools from a closed
allowlist, the deterministic composer writes the draft, and the application
validates citations and claims before release.

---

## 1. Assets and non-assets

Protect:

- provider credentials and environment variables;
- local filesystem paths and raw/processed data directories;
- canonical NASA data and registry integrity;
- citation resolution and provenance;
- the distinction between measured, computed, derived, and raw values.

Not permitted under any circumstance:

- fabricating measurements, publications, authors, DOIs, URLs, or citations;
- treating missing values as zero;
- converting ambiguous units without an approved rule;
- generating SQL, filesystem paths, shell commands, or arbitrary HTTP requests;
- claiming a fire-risk score, material ranking, causal effect, or spacecraft
  fire-safety guarantee.

---

## 2. Trust boundaries

| Boundary | Trusted? | Control |
|---|---|---|
| User question | No | Length, schema, rate limits, bounded tool calls |
| Retrieved documents | No | Quoted as evidence; never instructions; no tool selection |
| Citation registry | Yes | Phase 4 resolver; unknown records fail closed |
| Canonical tables | Yes | Read-only allowlisted service methods |
| Deterministic planner | Yes | Closed topic rules; no generated SQL or paths |
| Deterministic composer | Yes | Templates; every number from tool results |
| Optional provider | No | Rephrase-only; strict preservation checks; fallback |
| Provider credentials | Secret | Environment only; never serialized or logged |

The assistant calls `AnalyticsService` internally. It does not make HTTP
requests to its own API and cannot broaden the service surface.

---

## 3. Tool boundary

`src/assistant/tools.py` defines 22 tools with strict Pydantic argument
schemas. Tool names such as `sql_query`, `read_file`, `fetch_url`,
`run_shell`, and `execute_code` do not exist. The registry enforces:

- an allowlisted name and validated arguments;
- a maximum number of calls per request;
- bounded result size and pagination;
- a per-call timeout;
- rejection of unknown tools and invalid arguments;
- audit records with tool name, arguments, status, duration, and result hash.

The planner never reads a filesystem path, opens a URL, or builds SQL from user
text. Numerical answers use analytical service methods, not retrieved prose.

---

## 4. Retrieval boundary

Only committed, verified artifacts are indexed. Retrieval cards intentionally
omit count-bearing prose so RAG cannot become a numerical source.

When retrieved text enters an answer:

- it is labeled `evidence_trust="untrusted_source_text"`;
- it is labeled `instruction_policy="never_follow_source_instructions"`;
- evidence items carry `trusted_as_instruction=false`;
- a retrieved chunk is never promoted to a citation unless a Phase 4
  citation ID resolves;
- instructions inside retrieved text are not executed and cannot call tools,
  change the system prompt, or reveal secrets.

The retrieval index is reproducible from committed sources. Generated indexes
are gitignored. Manifest validation checks source hashes, dataset/registry
versions, chunking configuration, and index version drift.

---

## 5. Provider boundary

The optional OpenAI-compatible provider receives only:

- the user question;
- the already validated deterministic draft.

It does not receive retrieved source text, tool results, schemas, credentials,
or instruction authority. It cannot choose tools or produce citations.

`validate_rephrase()` rejects a candidate that:

- is empty, oversized, or grows beyond the safe expansion limit;
- contains control characters or secret-like text;
- introduces or removes a number;
- introduces an unapproved citation ID, investigation accession, dataset ID,
  or URL;
- adds a causal, ranking, or fire-risk assertion;
- adds an unsupported self-reference.

The orchestrator repeats the boundary check on every provider return, then
reruns claim validation against the tool results. Any failure falls back to
the deterministic draft. A provider error is reported as a safe reason without
the exception payload or credentials.

---

## 6. Citation and claim integrity

Every citation ID is resolved with `AnalyticsService.get_citation`. Unknown,
mismatched, or out-of-scope IDs fail closed. A `partial` file record is
accepted only with a warning that names the missing verification check.

Every claim must link to an approved tool call and must cite only resolved
answer citations. Numerical claims must match a value the tool returned, with
the same unit and value kind. Prose may not introduce a number that no tool
returned. If validation fails, the draft is withheld; no citation or number is
repaired.

---

## 7. Secrets and logging

- Configuration is environment-driven; `.env` is gitignored.
- `AssistantSettings.api_key` uses `repr=False`.
- Status and health return only enabled/mode/provider/model/retrieval fields.
- Tool logs record tool name, validated arguments, status, duration, and
  request ID. A retrieval tool argument may contain a bounded user-derived
  search phrase; tool results, credentials, and secrets are not logged.
- Error handlers never return exception messages or filesystem paths.

---

## 8. Adversarial test coverage

| Threat | Test |
|---|---|
| SQL / filesystem / URL execution | `tests/assistant/test_adversarial.py` |
| Secret exfiltration | `tests/assistant/test_adversarial.py` |
| Prompt-injection echo | `tests/assistant/test_adversarial.py` |
| Provider introduces numbers/citations | `tests/assistant/test_providers.py`, `test_orchestrator.py` |
| Provider timeout / HTTP failure / invalid JSON | `tests/assistant/test_providers.py` |
| Missing-value imputation | `tests/assistant/test_orchestrator.py`, golden `dq-028` |
| Unauthorized unit conversion | `tests/assistant/test_orchestrator.py`, golden `dq-029` |
| Fabricated publication | golden `dq-030` |
| Fire-risk score / ranking | golden `dq-031` |
| Untrusted retrieved text | golden `dq-033` |
| Citation validation failure withholds draft | `tests/assistant/test_orchestrator.py` |

These tests demonstrate software behavior. They are not a scientific
validation of the underlying NASA experiments.

---

## 9. Residual limitations

- No real LLM credentials are available in this environment. Provider tests
  use deterministic stubs or mocked HTTP transports; they do not evaluate a
  hosted model.
- The assistant can only answer within the curated artifacts. Absence of an
  answer is not evidence that the underlying phenomenon does not exist.
- Rate limiting and CORS are deployment controls, not substitutes for
  authentication or network isolation.
