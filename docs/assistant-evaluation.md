# Assistant Evaluation

**Project:** Flame in Freefall
**Status date:** 2026-11-10
**Golden set version:** `1.0.1`
**Answer contract version:** `1.0.0`
**Scope:** `src/assistant/evaluation.py`, `scripts/evaluate_assistant.py`, `tests/assistant/`

The evaluation harness measures separate properties of the grounded assistant.
It does not collapse them into one "accuracy" or "trust" score. It also does
not pretend that a deterministic software run is a real language-model
evaluation.

The committed report is `data/reports/assistant_evaluation.json`. It records
the golden-set version, dataset version, index version, provider mode, every
per-question result, retrieval metrics, provider-boundary checks, latency, and
failure categories.

---

## 1. What is evaluated

| Layer | What is checked |
|---|---|
| Contract | Status, answer type, validation, limitations, metadata, and non-empty prose. |
| Citations | Every cited ID resolves independently through the Phase 4 citation service and matches its kind, accession, dataset scope, file, checksum, URL, verification, availability, and row locator. |
| Claims | Every claim links to a current tool call, cites only resolved answer citations, and is marked supported. |
| Numbers | Expected values and units appear in structured tool output or claims, within the declared tolerance. |
| Refusal | Questions that require refusal return the expected `insufficient_evidence` or `unavailable_data` status without an unsupported claim. |
| Tool selection | The required tools were used, no dangerous tool was used, and no tool failed or was rejected. |
| Scope | At least one citation matches the expected accession and dataset ID. |
| Safety | No secret, local path, SQL statement, or unauthorized URL appears in the serialized answer; no evidence item is marked as a trusted instruction. |
| Retrieval | Precision@k, recall@k, MRR, unknown labels, and per-case results on the labelled retrieval set. |
| Provider boundary | A failing provider must fall back perfectly; a deterministic mock provider must rephrase without changing numbers or citations. |
| Latency | Mean, p50, p95, and maximum elapsed time for the evaluated run. |

---

## 2. Golden set

`tests/assistant/golden_questions.json` version `1.0.1` contains 36 questions
bound to canonical dataset version
`2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb`.

| Category | Count |
|---|---:|
| Adversarial | 7 |
| Numerical | 6 |
| Dataset discovery | 5 |
| Limitations | 5 |
| Experimental understanding | 4 |
| Comparison | 4 |
| Provenance | 3 |
| Prompt injection | 1 |
| Methodology | 1 |
| **Total** | **36** |

Each question declares:

- expected `evidence_status` and `answer_type`;
- the required tools and citation types;
- expected limitation codes and evidence sources;
- expected accession/dataset scope;
- expected numeric values, fields, units, and tolerances;
- forbidden claims;
- a human-readable expected behavior.

Expected numbers were read from the canonical Phase 2–4 artifacts or from a
deterministic service call on 2026-11-10. No expected value comes from a
publication title, an abstract, or a model output.

Version `1.0.1` added explicit `dq-029` count expectations after the
unit-conversion composer was corrected to select PSI-159 statistics by
`dataset_id` rather than by call order.

---

## 3. How to run

```bash
# Full evaluation, writes data/reports/assistant_evaluation.json.
.venv/bin/python scripts/evaluate_assistant.py

# Same, plus a non-zero exit when a threshold fails.
.venv/bin/python scripts/evaluate_assistant.py --check

# Evaluation tests only.
.venv/bin/python -m pytest tests/assistant/test_evaluation.py -q
```

Optional flags:

| Flag | Effect |
|---|---|
| `--output PATH` | Write the report somewhere other than the default. |
| `--questions PATH` | Use a different golden set. |
| `--retrieval-cases PATH` | Use a different labelled retrieval set. |
| `--no-retrieval` | Skip retrieval cases and the index. |
| `--no-provider-checks` | Skip failing-provider and mock-provider checks. |
| `--use-configured-provider` | Evaluate the environment-configured provider; may call a real model and is not reproducible. |

The default run uses `AssistantSettings()` with the deterministic provider. It
does not read provider credentials from the environment and does not call a
hosted model. `FLAME_LOG_LEVEL` defaults to `WARNING` in this script so the
metric summary is readable; set it explicitly to `INFO` for tool-level logs.

---

## 4. Current verified results

The committed deterministic run reports:

| Metric | Result |
|---|---:|
| Golden questions passed | 36 / 36 |
| Contract pass rate | 1.0 |
| Citation references | 117 |
| Citations valid | 117 |
| Citation validity rate | 1.0 |
| Claims | 59 |
| Supported claims | 59 |
| Supported claim rate | 1.0 |
| Claims linked to a current tool call | 59 |
| Claim–tool link rate | 1.0 |
| Numeric checks | 30 |
| Numeric matches | 30 |
| Numerical exact-match rate | 1.0 |
| Unit checks | 30 |
| Unit matches | 30 |
| Unit consistency rate | 1.0 |
| Tool-selection questions | 35 |
| Tool-selection passes | 35 |
| Tool-selection accuracy | 1.0 |
| Refusal questions | 12 |
| Correct refusals | 12 |
| Correct refusal rate | 1.0 |
| Required evidence sources | 4 |
| Sources covered | 4 |
| Source coverage rate | 1.0 |
| Scope checks | 28 |
| Scope checks covered | 28 |
| Scope coverage rate | 1.0 |
| Failure categories | none |

Latency in that run: mean `115.024 ms`, p50 `89.145 ms`, p95 `335.201 ms`,
maximum `773.147 ms`. Latency depends on the machine, warm caches, and the
first index build, so treat it as an indicative measurement rather than a
service-level guarantee.

### Retrieval

| Metric | Result |
|---|---:|
| Labelled cases | 7 |
| Usable cases | 7 |
| Label errors | 0 |
| Mean precision@5 | 0.602381 |
| Mean recall@5 | 1.0 |
| Mean reciprocal rank | 0.761905 |

The relevance labels are minimal. Precision is a lower bound because
unlabelled results may be relevant. The set is too small to support a general
retrieval claim.

### Provider boundary

| Check | Result |
|---|---|
| Failing-provider fallback | Passed |
| Deterministic mock-provider rephrase | Passed |
| Real model evaluated | **No** |

The failing provider is a stub that raises `ProviderError`. The mock provider
returns a deterministic prefix plus the validated draft. These checks prove
that the boundary and fallback work; they do not measure model quality.

---

## 5. `--check` thresholds

`--check` exits non-zero when any of the following fails:

- contract pass rate below 1.0;
- citation validity below 1.0;
- numerical exact match below 1.0;
- unit consistency below 1.0;
- tool-selection accuracy below 1.0;
- correct-refusal rate below 1.0;
- any golden question fails;
- failing-provider fallback checks fail;
- mock-provider rephrase checks fail;
- retrieval labels contain unknown document IDs;
- mean recall@5 is below 0.8.

The thresholds are strict because the golden set is small and each expectation
is tied to a verified artifact. A failure is a release blocker, not a warning
to waive.

---

## 6. What the evaluation does not establish

1. **No real language-model quality.** No hosted model was called. The
   optional provider is exercised only through deterministic stubs. A
   real-model run must be reported separately with its model name, provider,
   date, cost, and configuration.
2. **No scientific validation.** Passing software tests does not prove a
   scientific conclusion. The evaluation checks grounding and contract
   compliance, not the truth of a hypothesis.
3. **Small, version-bound golden set.** The 36 questions cover known risks and
   common question shapes. They are not a representative sample of all
   possible user questions. The set is bound to one canonical dataset version
   and must be reviewed when that version changes.
4. **Minimal retrieval labels.** Seven cases cannot establish general
   retrieval quality. The lexical method is expected to miss paraphrase and
   synonym variants that a semantic model might find.
5. **Latency is not a service-level objective.** The measured values are from
   a local deterministic run, not a load test or a production deployment.
6. **No paired-comparison execution.** The evaluation confirms that paired
   values are withheld when no verified alignment exists. It does not evaluate
   a paired executor, because none is implemented.
7. **No causal or risk claims.** Refusal tests confirm that the assistant does
   not produce fire-risk scores, material rankings, or causal conclusions from
   correlation.

---

## 7. Report schema

`data/reports/assistant_evaluation.json` contains:

| Field | Meaning |
|---|---|
| `evaluation_version` | Harness version. |
| `generated_at` | UTC generation timestamp. |
| `golden_version` | Golden-set version used. |
| `contract_version` | Answer contract version. |
| `dataset_version` | Canonical dataset version. |
| `mode` | `deterministic` or `provider`. |
| `real_model_evaluated` | Boolean; false unless a real provider run is recorded. |
| `provider` | Safe provider metadata (name, model, mode, fallback). |
| `index` | Retrieval enabled flag and index version. |
| `summary` | Aggregate metrics and failure categories. |
| `questions` | Per-question result, failures, counts, and latency. |
| `retrieval` | Retrieval metrics, per-case results, index and dataset versions. |
| `provider_checks` | Failing-provider and mock-provider checks. |
| `limitations` | Explicit scope limits for the report. |
| `command` | Command used to generate the report. |

The report intentionally keeps per-metric values rather than an overall score.
A single number would hide the difference between citation validity, numerical
grounding, refusal behavior, and retrieval quality.

---

## 8. Updating the golden set

1. Add or change a question only with a verified source or a deterministic
   service call.
2. Record the expected status, type, tools, citations, limitations, scope, and
   numeric values.
3. Add a forbidden claim where a plausible wrong answer exists.
4. Bump `golden_version` when expectations change.
5. Regenerate the report and commit it with the code and test change.
6. Rebuild the retrieval index after documentation changes.
7. Review the dataset version; a new canonical dataset requires a new golden
   review.

Do not weaken an expectation to make a failing answer pass. Fix the composer,
tool, or contract instead, or record why the correct behavior is a refusal.

---

## 9. Related documents

- `docs/assistant-answer-contract.md` — answer schema and validation.
- `docs/assistant-tools.md` — deterministic tool catalog.
- `docs/assistant-retrieval.md` — index, ranking, and retrieval evaluation.
- `docs/assistant-security.md` — adversarial coverage and trust boundaries.
- `tests/assistant/golden_questions.json` — versioned questions.
- `tests/assistant/retrieval_golden.json` — labelled retrieval cases.
- `data/reports/assistant_evaluation.json` — generated report.
