# Assistant Answer Contract

**Contract version:** `1.0.0`
**Project:** Flame in Freefall
**Status date:** 2026-11-10

This is the normative contract for every Phase 5 assistant answer. It is
implemented in `src/assistant/contract.py` and tested in
`tests/assistant/test_contract.py`. A response that does not satisfy these
rules is not a valid answer, regardless of how fluent it is.

The contract is independent of the model provider. The deterministic
provider and any optional LLM provider must both produce it.

---

## 1. Top-level shape

Every assistant response uses the existing API envelope:

```json
{
  "data": { "...AssistantAnswer..." },
  "meta": {
    "request_id": "req_...",
    "dataset_version": "2a19f9f2...",
    "generated_at": "2026-11-10T...Z"
  },
  "provenance": [],
  "quality": { "status": "verified", "flags": [] }
}
```

`data` is an `AssistantAnswer`:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `contract_version` | string | yes | `1.0.0` |
| `request_id` | string | yes | Request correlation ID |
| `conversation_id` | string or null | no | Bounded conversation reference |
| `answer` | string | yes | Grounded prose; no HTML |
| `evidence_status` | enum | yes | See §2 |
| `answer_type` | enum | yes | See §2 |
| `citations` | `CitationReference[]` | yes (may be empty) | Resolved Phase 4 citations |
| `supporting_data` | `SupportingData[]` | yes (may be empty) | Deterministic results |
| `claims` | `Claim[]` | yes (may be empty) | Structured claims used by validation |
| `limitations` | `Limitation[]` | yes (may be empty) | Limitations that travel with the answer |
| `tools_used` | `ToolCall[]` | yes (may be empty) | Bounded tool audit records |
| `evidence` | `EvidenceItem[]` | yes (may be empty) | Retrieved or deterministic evidence |
| `confidence` | enum | yes | `high`, `moderate`, `low` |
| `confidence_basis` | string | yes | Why that confidence is justified |
| `dataset_version` | string or null | no | Canonical dataset version |
| `provider` | string | yes | `deterministic` or the configured provider |
| `fallback_mode` | boolean | yes | True when a provider failed or was unavailable |
| `fallback_reason` | string or null | no | Safe, secret-free reason |
| `clarification` | object or null | no | Required only for `clarification_required` |
| `validation` | `ValidationReport` | yes | Application validation result |
| `generated_at` | ISO-8601 string | yes | Generation timestamp |

Unknown fields are rejected (`extra="forbid"`).

`meta` also carries `assistant_contract_version`, `conversation_id`, and
`assistant_provider` for the frontend. `provenance` remains empty because the
resolved citation objects are inside `data.citations`.

The envelope `quality.status` is a coarse transport summary derived from
`data.evidence_status`:

| `evidence_status` | Envelope `quality.status` |
|---|---|
| `fully_supported` | `verified` |
| `partially_supported`, `insufficient_evidence`, `conflicting_evidence` | `partial` |
| `unavailable_data` | `not_available` |

Callers must use `data.evidence_status` for answer semantics; the envelope
quality field is not a second scientific judgment.

### API example

```http
POST /api/v1/assistant/query
Content-Type: application/json

{
  "question": "How many valid PSI-10 gas-flame records are available?",
  "conversation_id": null,
  "include_retrieval": true,
  "max_tool_calls": 6
}
```

The route returns the shared envelope. `POST` responses are
`Cache-Control: no-store`. Invalid bodies, unknown fields, blank questions,
and `max_tool_calls` outside 1–12 return the standard `validation_error`
envelope with HTTP 422. Assistant status, suggestions, and tools are available
without an LLM.

---

## 2. Enumerations

### `evidence_status`

| Value | Meaning |
|---|---|
| `fully_supported` | Every material claim is supported by a deterministic tool or a resolved citation. |
| `partially_supported` | Some claims are supported; at least one limitation or missing condition remains. |
| `insufficient_evidence` | The request cannot be answered from verified artifacts. |
| `unavailable_data` | The requested data are documented as absent or unavailable. |
| `conflicting_evidence` | Verified sources disagree; the conflict is reported, not resolved by guessing. |

### `answer_type`

`factual`, `numerical`, `exploratory`, `comparison`, `methodology`,
`clarification_required`.

### `confidence`

`high`, `moderate`, `low`. This is a coarse label, never a fabricated
numeric probability.

### `value_kind`

`measured`, `computed`, `derived`, `categorical`, `raw`, `not_applicable`.
The value kind must match the registry/tool result. `Tad` and `Zst` are
`computed`. Raw telemetry channels are `raw`. Categorical flags are
`categorical`.

---

## 3. Citation references

Each `CitationReference` preserves:

| Field | Meaning |
|---|---|
| `citation_id` | Phase 4 `cit_f_...` or `cit_r_...` |
| `citation_type` | `file` or `row` |
| `accession` | NASA PSI accession |
| `dataset_ids` | Curated dataset IDs |
| `file_name` | Exact source file name |
| `sheet` | Sheet when available |
| `row` | Row when available |
| `source_url` | Verified source URL when available |
| `sha256` | Verified checksum when available |
| `verification_status` | Phase 4 verification status |
| `availability` | `available` or `unavailable` |
| `downloadable` | False for every unavailable source |
| `resolved` | True only after Phase 4 resolution |

Invariants:

1. A row citation must include `row`.
2. A file citation must not include `row`.
3. An unavailable citation must not be downloadable.
4. Citation IDs must be unique within an answer.
5. A citation ID is never created by a model.

The validator in `src/assistant/citation_validation.py` resolves every ID
through `AnalyticsService.get_citation` and checks the locator, kind,
verification status, availability, accession/dataset scope, and source URL.
Unknown or out-of-scope IDs fail closed. A file record with Phase 4
`verification_status="partial"` is accepted with an explicit warning naming
the missing check; a PSI-101 raw file with `manifest_checksum_missing` is the
canonical example.

---

## 4. Claims

A `Claim` records the atomic factual content used for validation:

| Field | Meaning |
|---|---|
| `claim_id` | Unique within the answer |
| `text` | The claim as expressed in the answer |
| `claim_type` | `numerical`, `factual`, `comparison`, `limitation`, `provenance` |
| `value` | Numeric value for numerical claims |
| `unit` | Unit, preserved from the tool |
| `value_kind` | Measured/computed/derived/categorical/raw |
| `dataset_id` | Dataset scope when applicable |
| `accession` | Investigation scope when applicable |
| `tool_call_id` | Required for numerical claims |
| `citation_ids` | Citations that support the claim |
| `supported` | Set by the application validator, never by a model |
| `validation_notes` | Why the claim passed or failed |

Invariants:

1. A numerical claim requires a `tool_call_id` and a `value_kind`.
2. A numerical claim value must be numeric.
3. If `validation.passed` is true, every claim must be `supported`.
4. If `validation.passed` is true, every claim citation must exist in the
   answer's citation list.

---

## 5. Supporting data and tool calls

`SupportingData` records a bounded deterministic result:

- `data_id`, `tool_call_id`, `label`;
- `value_kind`, `unit`, `dataset_id`, `accession`;
- a human-readable `summary`;
- a bounded `values` object (counts, min/max, mean, field names, reasons);
- `citation_ids`.

`ToolCall` records:

- `call_id`, `tool`, validated `arguments`;
- `status` (`ok`, `empty`, `rejected`, `failed`);
- `duration_ms`;
- a safe `result_summary`;
- a `result_hash` for traceability;
- an optional safe `error`.

The tool audit record never contains secrets, raw filesystem paths, or
unbounded result payloads.

---

## 6. Validation report

`ValidationReport` is the application's own result, not a model self-report:

| Field | Meaning |
|---|---|
| `passed` | True only when all checks pass |
| `citation_validation_passed` | Every citation resolved and matched |
| `claim_validation_passed` | Every claim is grounded and consistent |
| `checks` | Named checks with pass/fail and detail |
| `errors` | Blocking validation errors |
| `warnings` | Non-blocking issues |

Invariants:

1. `passed=true` requires both citation and claim validation.
2. `passed=true` forbids errors.
3. `passed=true` requires every claim to be supported.
4. A failed validation produces a safe answer, not a repaired citation.

---

## 7. Configuration and fallback

Environment variables:

| Variable | Default | Notes |
|---|---|---|
| `FLAME_ASSISTANT_ENABLED` | `true` | If false, assistant routes report disabled. |
| `FLAME_LLM_PROVIDER` | `deterministic` | `deterministic` or `openai_compatible`. |
| `FLAME_LLM_MODEL` | unset | Required for `openai_compatible`. |
| `FLAME_LLM_API_KEY` | unset | Required for `openai_compatible`; never exposed. |
| `FLAME_LLM_BASE_URL` | unset | Absolute http(s) URL; no credentials in the URL. |
| `FLAME_EMBEDDING_PROVIDER` | `deterministic` | `deterministic`, `none`, or `openai_compatible`. |
| `FLAME_EMBEDDING_MODEL` | `tfidf-hash-v1` | Index identity. |
| `FLAME_RETRIEVAL_ENABLED` | `true` | Disable retrieval without disabling tools. |
| `FLAME_ASSISTANT_MAX_TOOL_CALLS` | `6` | 1–12. |
| `FLAME_ASSISTANT_TIMEOUT_SECONDS` | `20` | 1–120. |
| `FLAME_ASSISTANT_MAX_CONTEXT_TURNS` | `4` | 0–10. |
| `FLAME_ASSISTANT_MAX_QUESTION_CHARS` | `1000` | 64–4000. |

Rules:

1. Invalid values are rejected at startup.
2. Invalid optional provider configuration degrades to fallback mode with a
   safe `config_error`; the API still starts and deterministic answers remain
   available.
3. Secrets never appear in status, logs, errors, or the frontend.
4. A provider failure sets `fallback_mode=true` and a safe reason.
5. The deterministic mode is fully functional without an LLM.
6. A provider may only rephrase a validated deterministic draft. It cannot
   plan, choose tools, add numbers or citations, remove limitations, or bypass
   validation. Any violation returns the deterministic draft.

---

## 8. Example: supported numerical answer

```json
{
  "contract_version": "1.0.0",
  "request_id": "req_example",
  "answer": "PSI-10 has 256 included gas-flame rows. 71 qualified rows are excluded by default, leaving 327 canonical rows in total.",
  "evidence_status": "fully_supported",
  "answer_type": "numerical",
  "citations": [
    {
      "citation_id": "cit_f_...",
      "citation_type": "file",
      "accession": "PSI-10",
      "dataset_ids": ["psi-10-gas-flame"],
      "file_name": "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
      "sheet": null,
      "row": null,
      "source_url": "https://psi.nasa.gov/...",
      "sha256": "...",
      "verification_status": "verified",
      "availability": "available",
      "downloadable": true,
      "resolved": true
    }
  ],
  "supporting_data": [
    {
      "data_id": "data_1",
      "tool_call_id": "call_1",
      "label": "PSI-10 gas-flame counts",
      "value_kind": "measured",
      "unit": "rows",
      "dataset_id": "psi-10-gas-flame",
      "accession": "PSI-10",
      "summary": "256 included, 71 excluded qualified, 327 total.",
      "values": {
        "included_rows": 256,
        "excluded_qualified_rows": 71,
        "total_rows": 327
      },
      "citation_ids": ["cit_f_..."]
    }
  ],
  "claims": [
    {
      "claim_id": "claim_1",
      "text": "PSI-10 has 256 included gas-flame rows.",
      "claim_type": "numerical",
      "value": 256,
      "unit": "rows",
      "value_kind": "measured",
      "dataset_id": "psi-10-gas-flame",
      "accession": "PSI-10",
      "tool_call_id": "call_1",
      "citation_ids": ["cit_f_..."],
      "supported": true,
      "validation_notes": []
    }
  ],
  "limitations": [
    {
      "code": "ramped_condition_rows",
      "message": "Qualified ramped/low-oxygen rows are excluded by default.",
      "severity": "warning",
      "citation_ids": []
    }
  ],
  "tools_used": [
    {
      "call_id": "call_1",
      "tool": "gas_flame_statistics",
      "arguments": {"accession": "PSI-10", "include_qualified": false},
      "status": "ok",
      "duration_ms": 4.2,
      "result_summary": "256 included rows",
      "result_hash": "..."
    }
  ],
  "confidence": "high",
  "confidence_basis": "The count comes from a deterministic canonical-table query.",
  "dataset_version": "2a19f9f2...",
  "provider": "deterministic",
  "fallback_mode": false,
  "validation": {
    "passed": true,
    "citation_validation_passed": true,
    "claim_validation_passed": true,
    "checks": [],
    "errors": [],
    "warnings": []
  }
}
```

## 9. Example: safe refusal

```json
{
  "contract_version": "1.0.0",
  "request_id": "req_example",
  "answer": "I cannot treat missing PSI-10 pressure_approx_bar values as zero. The canonical table has no non-null values in that field, so no average can be computed. Missing values are not zero.",
  "evidence_status": "insufficient_evidence",
  "answer_type": "numerical",
  "citations": [],
  "supporting_data": [],
  "claims": [],
  "limitations": [
    {
      "code": "measurement_has_no_canonical_values",
      "message": "pressure_approx_bar has zero canonical values for PSI-10.",
      "severity": "error",
      "citation_ids": []
    }
  ],
  "tools_used": [],
  "confidence": "low",
  "confidence_basis": "The requested imputation is scientifically invalid.",
  "provider": "deterministic",
  "fallback_mode": false,
  "validation": {
    "passed": false,
    "citation_validation_passed": true,
    "claim_validation_passed": true,
    "checks": [],
    "errors": [],
    "warnings": []
  }
}
```

---

## 10. Versioning

- The contract version is independent of the dataset version.
- A breaking field or enum change increments `contract_version`.
- The golden question set records the contract and dataset versions it was
  written against.
- `tests/assistant/test_golden_questions.py` fails when the golden dataset
  version differs from the canonical registry version.
