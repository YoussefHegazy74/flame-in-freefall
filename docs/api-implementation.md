# API Implementation

**Project:** Flame in Freefall
**Team:** AFAQ
**Application:** `backend/app.py`
**Framework:** FastAPI `0.162.2`, Pydantic `2.14.3`, Uvicorn `0.54.0`
**API version:** `v1`
**Status:** Read-only Phase 1–4 exploration API plus the Phase 5 grounded assistant. The assistant is deterministic by default and fails closed to deterministic mode when an optional provider is unavailable.

This document describes the running service. `API_DOCUMENTATION.md` records the broader contract, `docs/phase4-contracts.md` records the Phase 4 response shapes, and `docs/comparison-alignment.md` records the comparison methodology.

---

## 1. Running locally

```bash
. .venv/bin/activate
python -m pip install -r requirements.txt

uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

| URL | Purpose |
|---|---|
| `http://127.0.0.1:8000/api/v1/health` | Liveness and dataset readiness |
| `http://127.0.0.1:8000/api/v1/docs` | Swagger UI |
| `http://127.0.0.1:8000/api/v1/openapi.json` | OpenAPI schema |

The app reads canonical Parquet from `data/processed`, the quality report from `data/reports`, the download manifest from `data/registry`, and the scientific registries from `data/metadata`. Override with `FLAME_PROCESSED_DIR`, `FLAME_REPORTS_DIR`, `FLAME_REGISTRY_DIR`, and `FLAME_METADATA_DIR`.

---

## 2. Implemented routes

All read endpoints are `GET`; the assistant query endpoint is `POST`. They live under `/api/v1`. The OpenAPI schema contains **35 paths**.

| Route | Purpose |
|---|---|
| `/health` | Liveness, dataset version, available/missing tables, assistant mode/provider/fallback. |
| `/meta` | API version, registry snapshot, canonical table counts, curated dataset and measurement counts. |
| `/investigations` | NASA PSI catalog with `role`, `q`, `limit`, `offset`. |
| `/investigations/{accession}` | One investigation plus its curated datasets. |
| `/datasets` | Curated dataset registry with `family`, `accession`, `state`, `use`, pagination. |
| `/datasets/quality` | Quality summary for all curated datasets. |
| `/datasets/{dataset_id}` | One curated dataset, all four serving decisions, and its measurements. |
| `/datasets/{dataset_id}/quality` | Quality report slice and serving decisions. |
| `/datasets/{dataset_id}/files` | Curated file manifest with download and verification status. |
| `/datasets/{dataset_id}/fields` | Field dictionary with units, value kinds, source columns, integrity, and comparability. |
| `/datasets/{dataset_id}/limitations` | Scoped limitations with evidence and affected operations. |
| `/measurements` | Measurement registry with `accession`, `family`, `dataset_id`, `comparison_status`, `serving_state`, `use`, pagination. |
| `/measurements/{measurement_id}` | One measurement, serving decision, dataset, and rules. |
| `/gas-flame/facets` | Facet counts and per-accession distributions from canonical gas-flame rows. |
| `/gas-flame/tests` | PSI-10/PSI-159 rows with filters and pagination. |
| `/gas-flame/tests/{observation_id}` | One gas-flame row. |
| `/material/tests` | PSI-25/PSI-26 rows with filters and pagination. |
| `/droplet/tests` | PSI-69 rows with filters and pagination. |
| `/telemetry/runs` | PSI-100 runs. |
| `/telemetry/runs/{run_id}` | Run metadata and channel profiles. |
| `/telemetry/runs/{run_id}/series` | Bounded telemetry series. |
| `/smoke/runs` | PSI-101 runs. |
| `/smoke/runs/{run_id}` | Run metadata and channel profiles. |
| `/smoke/runs/{run_id}/series` | Bounded smoke series. |
| `/comparability` | Full comparability summary and state definitions. |
| `/compare` | One comparison decision with integrity checks and paired-value eligibility. |
| `/citations` | File-level citation registry with filters. |
| `/citations/{citation_id}` | One file or row citation with row verification. |
| `/publications` | Deduplicated publication registry with filters. |
| `/publications/{publication_id}` | One publication with verification and field status. |
| `/provenance` | Exact source-file and optional row provenance. |
| `/assistant/status` | Safe assistant mode, provider, retrieval status, contract version, and allowlisted tools. |
| `/assistant/suggestions` | Up to nine curated real golden questions. |
| `/assistant/tools` | Closed tool allowlist with strict argument schemas. |
| `/assistant/query` | Grounded answer in the shared envelope; deterministic default, validated citations and claims. |

Assistant endpoints remain unimplemented. The target contract's `/datasets/{accession}/publications` path is replaced by `/publications?dataset_id=...`.

---

## 3. Success envelope

Every success response uses the same shape:

```json
{
  "data": {},
  "meta": {
    "request_id": "req_...",
    "registry_snapshot": "2026-11-08",
    "dataset_version": "2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb",
    "registry_version": "1.0.0",
    "retrieved_at": null,
    "generated_at": "2026-11-09T14:01:47.161561Z",
    "page": {
      "limit": 50,
      "offset": 0,
      "total": 24,
      "has_more": false
    }
  },
  "provenance": [],
  "quality": {
    "status": "verified",
    "flags": [],
    "warnings": []
  }
}
```

Pydantic models live in `backend/models.py`: `Envelope`, `ResponseMeta`, `PageMeta`, `Quality`, `ErrorEnvelope`, and `ErrorBody`.

`quality.status` is one of `verified`, `partial`, `blocked`, `experimental_table_only`, or `not_available`.

---

## 4. Error envelope

Every error uses one shape:

```json
{
  "error": {
    "code": "invalid_query",
    "message": "unknown or repeated query parameters are not allowed",
    "details": {
      "unknown": ["bogus"],
      "repeated": [],
      "allowed": ["limit", "offset"]
    },
    "request_id": "req_..."
  }
}
```

| HTTP | Code | When |
|---:|---|---|
| 400 | `invalid_query` | Unknown/repeated parameter, invalid range, bad channel, bad conditions JSON, path-like file name. |
| 404 | `not_found` | Unknown accession, dataset, run, observation, citation, or publication. |
| 404 | `unknown_measurement` | Unknown measurement identifier. |
| 405 | `method_not_allowed` | Non-GET method. |
| 413 | `range_too_large` | Page or series limit exceeded. |
| 422 | `validation_error` | Pydantic query validation failed. |
| 429 | `rate_limited` | Per-client request limit exceeded. |
| 500 | `internal_error` | Unhandled error; no source details are leaked. |
| 503 | `service_unavailable` | A required canonical table is absent. |
| 503 | `query_timeout` | The bounded query exceeded its time budget. |

`GET /compare` returns `200` for `comparable`, `conditionally_comparable`, `not_comparable`, `blocked`, and `insufficient_metadata`. The scientific result is in `data.status`; the mapped response quality is in `quality.status`.

---

## 5. Query validation

`StrictQueryRoute` rejects:

- undeclared query parameters;
- repeated query parameters.

For example, `/api/v1/health?include_raw=true` returns `400 invalid_query`, and `/api/v1/gas-flame/tests?limit=1&limit=2` returns `400 invalid_query`. Path parameters and request bodies are not accepted for these read-only routes.

Additional validation:

- `limit` is 1–200.
- `offset` is non-negative.
- `max_points` is 1–20,000.
- `row` is 1 or greater.
- `order` is `asc` or `desc`.
- accessions must match `PSI-<number>` and endpoint allowlists.
- sort fields and channels are allowlisted.
- `/compare` conditions must be a JSON object of known keys mapped to `true`, `false`, or `null`.
- `accession` and `dataset_id` must not conflict on `/publications`.

---

## 6. Request IDs, logging, and CORS

Every response includes `X-Request-ID`. If the client sends `X-Request-ID`, it is echoed; otherwise a `req_` identifier is generated. The same value appears in `meta.request_id` or `error.request_id`.

Each request emits one JSON log line with `request_id`, `method`, `path`, `status`, and `duration_ms`. Logs never include raw rows, SQL, secrets, or filesystem paths.

CORS is environment-driven:

| Variable | Default |
|---|---|
| `FLAME_CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` |

Set a comma-separated list to change allowed origins. Credentials are disabled; allowed methods are `GET`, `HEAD`, and `OPTIONS`. `X-Request-ID` is exposed.

`create_app(service=..., assistant=..., cors_origins=..., cache_settings=..., rate_limit_settings=...)` allows isolated contract tests with a synthetic dataset or a stub assistant.

---

## 7. Caching and conditional requests

Caching is enabled by default and process-local. Successful `GET` JSON responses except `/health` receive:

- a strong `ETag` over a stable representation of the body, excluding `meta.request_id` and `meta.generated_at`;
- `Cache-Control: public, max-age=60, must-revalidate` by default;
- `304 Not Modified` when `If-None-Match` matches.

Errors use `Cache-Control: no-store`. Health responses always use `no-store` and do not receive an ETag.

| Variable | Default | Meaning |
|---|---|---|
| `FLAME_CACHE_ENABLED` | `true` | Enable ETag and conditional requests. |
| `FLAME_CACHE_MAX_AGE` | `60` | `max-age` seconds. |
| `FLAME_CACHE_CONTROL` | unset | Full `Cache-Control` override. |

---

## 8. Rate limiting

The limiter is a thread-safe, process-local fixed window keyed by client IP. It is an abuse control, not authentication.

| Variable | Default | Meaning |
|---|---|---|
| `FLAME_RATE_LIMIT_ENABLED` | `true` | Enable the limiter. |
| `FLAME_RATE_LIMIT_REQUESTS` | `600` | Requests per window per client. |
| `FLAME_RATE_LIMIT_WINDOW_SECONDS` | `60` | Window length. |
| `FLAME_TRUST_PROXY` | `false` | Use the first `X-Forwarded-For` value. |

Responses include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset`. A rejected request returns `429` with `Retry-After` and `Cache-Control: no-store`.

---

## 9. Response quality mapping

| Source state | `quality.status` |
|---|---|
| Serving `available` | `verified` |
| Serving `available_with_warnings` or `restricted` | `partial` |
| Serving `blocked` | `blocked` |
| Serving `metadata_only` with an experimental table | `experimental_table_only` |
| Serving `metadata_only` without an experimental table | `not_available` |
| Comparability `comparable` | `verified` |
| Comparability `conditionally_comparable` | `partial` |
| Comparability `not_comparable`, `blocked`, or `insufficient_metadata` | `blocked` |

Warnings are deduplicated. Flags are stable reason codes, not prose.

---

## 10. OpenAPI

- Schema: `/api/v1/openapi.json`
- Swagger UI: `/api/v1/docs`
- ReDoc: disabled
- All routes declare the shared error responses: 400, 404, 413, 422, 500, 503.
- The schema contains **31 paths**.

`tests/test_api.py` validates the path set, the presence of error responses, the docs endpoint, and major success and error shapes. `tests/test_phase4_api.py` validates the Phase 4 contracts over the real canonical dataset. `tests/test_assistant_api.py` validates the assistant HTTP contract, and `tests/assistant` covers the planner, composer, tools, retrieval, providers, orchestration, golden evaluation, and adversarial behavior.

---

## 11. Not implemented

- Authentication or API keys. The public read-only MVP does not need them; rate limiting is not authentication.
- Assistant or LLM endpoints.
- A paired-comparison executor. `/compare` returns `paired_values.available=false` until a verified alignment method is committed.
- Production deployment configuration.

These remain later work in `DEVELOPMENT_ROADMAP.md`.

---

## 12. Tests

| Suite | Scope |
|---|---|
| `tests/test_api.py` | Envelopes, all routes, invalid/unknown/repeated parameters, blocked comparisons, pagination, 413 limits, CORS, OpenAPI, unhandled errors. |
| `tests/test_db.py` | Query layer over a synthetic canonical dataset. |
| `tests/test_analytics_integration.py` | API-ready service over the real canonical Parquet tables. |
| `tests/test_phase4_api.py` | Citations, dataset files/fields/limitations, publications, facets, comparison integrity, paired-value withholding, cache/rate limiting, response contracts, and one real grounded assistant query. |
| `tests/test_assistant_api.py` | Assistant status/suggestions/tools/query, disabled mode, invalid bodies, tool-call bounds, CORS, and fail-closed validation quality. |
| `tests/assistant/` | Contract, configuration, conversation, tools, retrieval, providers, orchestrator, golden evaluation, and adversarial tests. |
| `tests/test_operations.py` | ETag stability, conditional requests, rate-limit windows, settings validation. |

Run the unit contract tests:

```bash
python -m pytest tests/test_api.py tests/test_db.py tests/test_phase4_api.py tests/test_operations.py -q
```

Run everything, including real-data integration:

```bash
python -m pytest -q
```

Current result: **478 passed**.
