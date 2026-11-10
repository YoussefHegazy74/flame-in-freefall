# Phase 6 — Real-Model Provider Evaluation

**Project:** Flame in Freefall
**Status date:** 2026-11-10
**Provider contract:** deterministic default, optional OpenAI-compatible rephrase provider
**Live evaluation status:** **PENDING — no provider credentials were available**

This document records the provider integration work and the evaluation that
could not be performed. No real model was called. No real-model result is
claimed.

---

## 1. What is implemented

The optional provider remains a **rephrase-only boundary**. It receives:

- the user question;
- the already validated deterministic draft answer.

It does not receive:

- tool-selection authority;
- retrieved source text as instructions;
- permission to create numbers, citations, accessions, dataset IDs, or URLs.

Implemented provider capabilities:

| Capability | Implementation |
|---|---|
| Configurable provider | `FLAME_LLM_PROVIDER=openai_compatible` |
| Configurable model | `FLAME_LLM_MODEL` |
| Base URL | `FLAME_LLM_BASE_URL`, absolute http(s), no embedded credentials/query/fragment |
| API key | `FLAME_LLM_API_KEY`, server-side only, never serialized or logged |
| Timeout | `FLAME_ASSISTANT_TIMEOUT_SECONDS` / `LLM_TIMEOUT_SECONDS` alias |
| Retries | `FLAME_LLM_MAX_RETRIES` (0–5, default 2) |
| Backoff | `FLAME_LLM_RETRY_BACKOFF_SECONDS` (default 0.5, exponential, capped) |
| Rate-limit handling | Retries HTTP 429 and 5xx; honors numeric `Retry-After` up to 30 seconds |
| Error normalization | Safe `ProviderError` messages with no key or prompt |
| Request IDs | Sends `X-Request-ID` when a request ID is present |
| Token usage | Reads `usage.prompt_tokens`, `usage.completion_tokens`, `usage.total_tokens` |
| Cost estimation | Optional input/output prices per million tokens |
| Safe logging | Provider, status, attempts, token counts, cost, duration, request ID |
| Cancellation/timeout | `httpx` timeouts; failures fall back to deterministic |
| Fallback | Any failure or rejected rephrase returns the validated deterministic draft |

The response contract now includes optional `provider_usage`:

```json
{
  "provider_usage": {
    "prompt_tokens": 120,
    "completion_tokens": 30,
    "total_tokens": 150,
    "estimated_cost_usd": 0.00048,
    "pricing_configured": true
  }
}
```

Values are `null` when the provider does not report them. Cost is estimated only
when both input and output prices are configured.

---

## 2. What was tested

Verified locally without a real model:

- provider configuration parsing and secret redaction;
- bounded retry after HTTP 429 with `Retry-After`;
- bounded retry after a transport error;
- bounded retry stop after HTTP 503;
- request-ID header propagation;
- usage parsing;
- cost estimation;
- unsafe rephrase rejection;
- deterministic fallback;
- output size, control-character, secret, citation, accession, dataset, URL,
  and number checks;
- mock-provider and failing-provider boundary checks in the assistant
  evaluation.

The provider/config tests are in `tests/assistant/test_providers.py` and
`tests/assistant/test_config.py`. The transport tests use `httpx.MockTransport`;
they do not call a hosted model.

---

## 3. Live evaluation command

When credentials are available:

```bash
export FLAME_LLM_PROVIDER=openai_compatible
export FLAME_LLM_BASE_URL=https://provider.example/v1
export FLAME_LLM_MODEL=<verified-model-id>
export FLAME_LLM_API_KEY=<secret>
export FLAME_LLM_MAX_RETRIES=2
export FLAME_LLM_RETRY_BACKOFF_SECONDS=0.5
# Optional pricing, in USD per million tokens:
export FLAME_LLM_INPUT_COST_PER_MILLION=<price>
export FLAME_LLM_OUTPUT_COST_PER_MILLION=<price>

.venv/bin/python scripts/evaluate_assistant.py --use-configured-provider
```

The real-provider run writes
`data/reports/assistant_real_model_evaluation.json`. It does not overwrite the
committed deterministic report. If the provider is not fully configured, the
script exits with status 2 and explains which variables are required. It does
not silently report a deterministic run as a real-model result.

Add `--check` to enforce the same thresholds as the deterministic evaluation.

---

## 4. Metrics to report

A real-model run must report, separately:

| Metric | Meaning |
|---|---|
| Golden questions passed | Contract-level success |
| Citation validity | Every citation independently resolved |
| Supported claims | Every claim linked to a current tool call |
| Numerical exact match | Expected values present |
| Unit consistency | Expected units preserved |
| Tool-selection accuracy | Required tools used, no dangerous tool |
| Correct refusal rate | Missing/unavailable/unit traps refused |
| Prompt-injection resistance | No unsafe answer or secret exposure |
| Latency | Mean, p50, p95, max |
| Token usage | Prompt, completion, total |
| Estimated cost | Only when pricing is configured |

The deterministic, mock-provider, and real-provider results must not be merged
into one score.

---

## 5. Failure policy

A fluent answer is not a pass. A real-model run fails if:

- the provider removes or changes a number or unit;
- the provider adds a citation, accession, dataset ID, URL, or claim;
- a citation does not resolve;
- a numerical claim is not linked to the current tool call;
- the answer weakens a refusal, limitation, or uncertainty statement;
- a prompt-injection question changes tool behavior or exposes a secret;
- unsupported causal, ranking, or fire-risk language appears.

The orchestrator revalidates the rephrased answer. If validation fails, the
deterministic draft is returned with `fallback_mode=true` and a safe reason.

---

## 6. Why live evaluation is pending

No real API key, base URL, or model identifier was available in the environment
used for Phase 6. The integration is complete and tested at the transport and
validation boundaries, but a live-model quality claim would require an actual
call.

This is not a software failure. It is a credential and provider-account
limitation. The correct status is **pending**, not passed.
