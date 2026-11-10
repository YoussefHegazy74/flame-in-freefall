# Phase 6 — Operations and Monitoring

**Project:** Flame in Freefall
**Status date:** 2026-11-10
**Scope:** FastAPI operations, structured logs, metrics, readiness, and runbook

The platform exposes lightweight, process-local operational visibility. It does
not store user questions or answers, and it does not add a third-party
observability dependency. The design is intentionally small enough for the
current single-process deployment.

---

## 1. Liveness, readiness, and metrics

| Endpoint | Cache | Purpose |
|---|---|---|
| `GET /api/v1/health` | `no-store` | Liveness, dataset state, assistant mode/provider/fallback, contract version |
| `GET /api/v1/ready` | `no-store` | Deployment gate; HTTP 200 only when required checks pass |
| `GET /api/v1/metrics` | `no-store` | Aggregate request, latency, rate-limit, assistant, tool, and token counters |

`/health` always returns the shared API envelope. `/ready` returns the same
envelope shape with HTTP 503 when not ready so a container orchestrator can act
on the status code.

### Readiness checks

| Check | Pass condition |
|---|---|
| Dataset | Database state is `ok` when `FLAME_READINESS_REQUIRE_FULL_DATASET=true`; dataset version is present |
| Assistant index | A usable index version is available when retrieval is enabled and `FLAME_READINESS_REQUIRE_ASSISTANT_INDEX=true` |

The response exposes the individual check states. A failed readiness response
does not expose file paths, credentials, or stack traces.

---

## 2. Metrics schema

`GET /api/v1/metrics` returns:

```json
{
  "data": {
    "enabled": true,
    "started_at": "2026-11-10T...Z",
    "requests": {
      "total": 120,
      "by_method": {"GET": 110, "POST": 10},
      "by_status": {"200": 118, "429": 2},
      "by_route": {"/api/v1/health": 40}
    },
    "rate_limited_total": 2,
    "latency_ms": {
      "samples": 120,
      "mean": 42.1,
      "p95": 110.4,
      "max": 560.2
    },
    "assistant": {
      "queries_total": 10,
      "fallback_total": 0,
      "disabled_total": 0,
      "validation_failures_total": 0,
      "evidence_status": {"fully_supported": 10},
      "answer_type": {"numerical": 6, "factual": 4},
      "tool_calls_total": 20,
      "tool_failures_total": 0,
      "provider_calls_total": 0,
      "provider_errors_total": 0,
      "provider_tokens": {"prompt": 0, "completion": 0, "total": 0},
      "provider_estimated_cost_usd": 0.0,
      "mode": "deterministic",
      "provider": "deterministic",
      "retrieval_enabled": true
    },
    "dataset_version": "2a19f9f2...",
    "registry_version": "..."
  }
}
```

Latency uses a bounded sample (4,096 recent requests). Route keys use the
FastAPI route template, so arbitrary 404 paths cannot grow the dictionary
without bound.

The metrics payload does **not** include:

- user questions or assistant answers;
- citation identifiers;
- request headers or provider keys;
- file paths or raw data;
- per-user identifiers.

---

## 3. Structured logs

The API writes one JSON object per request:

```json
{
  "ts": "2026-11-10T...Z",
  "level": "INFO",
  "logger": "flame.api",
  "message": "request",
  "request_id": "req_...",
  "method": "GET",
  "path": "/api/v1/datasets/psi-10-gas-flame",
  "status": 200,
  "duration_ms": 12.3
}
```

Assistant logs add:

- topic, answer type, evidence status;
- provider and fallback flag;
- citation, claim, and tool counts;
- validation result;
- prompt/completion tokens and estimated cost when reported;
- request ID and duration.

The provider transport logs retry attempts, status codes, and wait times. It
never logs the prompt, draft answer, API key, or authorization header.

---

## 4. Operational signals

| Signal | Source | Typical response |
|---|---|---|
| `/ready` 503, `dataset_not_ready` | Canonical tables missing or database unavailable | Restore/mount `data/processed`, rerun validation |
| `/ready` 503, `assistant_index_not_ready` | Index missing or source rebuild failed | Rebuild `data/assistant` or relax the index gate deliberately |
| `429` rate limit spike | Public traffic or abuse | Inspect `rate_limited_total`; raise limit only with capacity evidence |
| Rising p95 latency on telemetry/gas-flame | Parquet/DuckDB work under load | Add workers, narrow ranges, or precompute summary views |
| `provider_errors_total` rises | Provider outage, timeout, rate limit | Check provider status; deterministic fallback remains active |
| `assistant_validation_failures_total` rises | Citation or claim validation regression | Block release; inspect the affected question IDs |
| `tool_failures_total` rises | Data or tool contract problem | Inspect safe tool logs; do not substitute an estimate |
| Dataset/index version change | Data or documentation update | Rebuild, rerun evaluation, update reports |

---

## 5. Startup and restart

1. Start the backend with the canonical data mounted.
2. Check `/api/v1/health` for the dataset state.
3. Check `/api/v1/ready`; index loading may take longer on first request.
4. Start the frontend and open `/`.
5. Run a citation lookup and one deterministic assistant question.
6. Check `/api/v1/metrics` for request counts and assistant counters.

Restarting the backend resets process-local rate limits, latency samples, and
counters. It does not alter canonical data, committed registries, citations, or
the retrieval index.

---

## 6. Scaling constraints

The current deployment is a single backend process:

- rate limiting is in-memory and per-process;
- metrics are in-memory and per-process;
- conversation memory is in-memory and bounded;
- DuckDB opens read-only views per query and does not share a write state.

For multiple replicas, add a shared rate-limit store and a shared metrics/telemetry
backend. Do not claim global rate limiting until that exists.

---

## 7. Runbook: common failures

### Canonical data unavailable

Symptoms: `/health` status `unavailable`; `/ready` 503 with
`dataset_not_ready`.

Action: verify the read-only mount at `/app/data/processed`; run
`python -m src.data_pipeline validate`; confirm the dataset version.

### Retrieval index stale or missing

Symptoms: `/ready` 503 with `assistant_index_not_ready`; assistant retrieval
warnings.

Action: run `python scripts/build_assistant_index.py --check`; rebuild if stale;
confirm the index version; restart the backend if the artifact was replaced.

### Provider outage

Symptoms: assistant answers still return, but `provider_errors_total` rises and
`fallback_mode=true`.

Action: no scientific action is required; the deterministic draft is shown.
Investigate the provider separately. Do not disable validation to force provider
text through.

### Citation or claim validation regression

Symptoms: `assistant_validation_failures_total` rises; answers are withheld.

Action: treat as a release blocker. Run the golden evaluation and inspect the
failed question IDs. Do not relax the validator to make a fluent answer pass.

### Rate-limit pressure

Symptoms: `429` responses and `rate_limited_total` growth.

Action: confirm whether traffic is legitimate. The default is 600 requests per
60 seconds per client. Increasing it requires capacity evidence and, for
multiple replicas, a shared limiter.

---

## 8. Privacy

- No user account or profile exists.
- Conversation state is held in memory, bounded, and non-authoritative.
- Question and answer text are not stored in the metrics registry or request
  logs.
- Provider credentials are never included in status, health, metrics, logs, or
  error messages.
