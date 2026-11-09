# API Implementation

**Project:** Flame in Freefall
**Team:** AFAQ
**Application:** `backend/app.py`
**Framework:** FastAPI `0.162.2`, Pydantic `2.14.3`, Uvicorn `0.54.0`
**API version:** `v1`
**Status:** Read-only Phase 2 implementation. Frontend and assistant endpoints are not implemented.

This document describes the running service. `API_DOCUMENTATION.md` remains the broader target contract; this page records what is implemented now and where it intentionally differs.

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

The app reads canonical Parquet from `data/processed` and the quality report from `data/reports`. Override with `FLAME_PROCESSED_DIR` and `FLAME_REPORTS_DIR`.

---

## 2. Implemented routes

All routes are `GET` and live under `/api/v1`.

| Route | Purpose |
|---|---|
| `/health` | Liveness, dataset version, available/missing tables, assistant disabled. |
| `/meta` | API version, registry snapshot, canonical table counts, curated dataset and measurement counts. |
| `/investigations` | NASA PSI catalog with `role`, `q`, `limit`, `offset`. |
| `/investigations/{accession}` | One investigation plus its curated datasets. |
| `/datasets` | Curated dataset registry with `family`, `accession`, `state`, `use`, pagination. |
| `/datasets/quality` | Quality summary for all curated datasets. |
| `/datasets/{dataset_id}` | One curated dataset, all four serving decisions, and its measurements. |
| `/datasets/{dataset_id}/quality` | Quality report slice and serving decisions. |
| `/measurements` | Measurement registry with `accession`, `family`, `dataset_id`, `comparison_status`, `serving_state`, `use`, pagination. |
| `/measurements/{measurement_id}` | One measurement, serving decision, dataset, and rules. |
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
| `/comparability` | Full comparability summary. |
| `/compare` | One comparison decision. |
| `/provenance` | Exact source-file and optional row provenance. |

The target contract also describes `/datasets/{accession}/files`, `/fields`, `/limitations`, `/publications`, `/gas-flame/facets`, `/materials/tests`, `/citations/{id}`, and assistant endpoints. Those are **not implemented** in Phase 2. The implemented material path is `/material/tests`.

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

Pydantic models live in `backend/models.py`:

- `Envelope`
- `ResponseMeta`
- `PageMeta`
- `Quality`
- `ErrorEnvelope`
- `ErrorBody`

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
| 404 | `not_found` | Unknown accession, dataset, run, or observation. |
| 404 | `unknown_measurement` | Unknown measurement identifier. |
| 405 | `method_not_allowed` | Non-GET method. |
| 413 | `range_too_large` | Page or series limit exceeded. |
| 422 | `validation_error` | Pydantic query validation failed. |
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

---

## 6. Request IDs and CORS

Every response includes `X-Request-ID`. If the client sends `X-Request-ID`, it is echoed; otherwise a `req_` identifier is generated. The same value appears in `meta.request_id` or `error.request_id`.

CORS is environment-driven:

| Variable | Default |
|---|---|
| `FLAME_CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` |

Set a comma-separated list to change allowed origins. Credentials are disabled; allowed methods are `GET`, `HEAD`, and `OPTIONS`. `X-Request-ID` is exposed.

`create_app(service=..., cors_origins=...)` allows isolated contract tests with a synthetic dataset.

---

## 7. Response quality mapping

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

## 8. OpenAPI

- Schema: `/api/v1/openapi.json`
- Swagger UI: `/api/v1/docs`
- ReDoc: disabled
- All routes declare the shared error responses: 400, 404, 413, 422, 500, 503.
- The schema contains 23 paths.

`tests/test_api.py` validates the path set, the presence of error responses, the docs endpoint, and every major success and error shape.

---

## 9. Not implemented in Phase 2

- ETag or cache headers.
- Rate limiting.
- Authentication or API keys.
- Citation records endpoint.
- Publication and file-listing endpoints.
- Assistant or LLM endpoints.
- Frontend assets.
- Production deployment configuration.

These remain Phase 3 and later work in `DEVELOPMENT_ROADMAP.md`.

---

## 10. Tests

| Suite | Scope |
|---|---|
| `tests/test_api.py` | Envelopes, all routes, invalid/unknown/repeated parameters, blocked comparisons, pagination, 413 limits, CORS, OpenAPI, unhandled errors. |
| `tests/test_db.py` | Query layer over a synthetic canonical dataset. |
| `tests/test_analytics_integration.py` | API-ready service over the real canonical Parquet tables. |

Run the unit contract tests:

```bash
python -m pytest tests/test_api.py tests/test_db.py -q
```

Run everything, including real-data integration:

```bash
python -m pytest -q
```
