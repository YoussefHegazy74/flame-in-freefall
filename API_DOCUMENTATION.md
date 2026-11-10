# API Documentation

**Project:** Flame in Freefall
**Team:** AFAQ
**API version:** `v1`
**Status:** Read-only Phase 1–4 implementation plus the Phase 5 grounded assistant under `backend/`. This document describes the implemented surface and the remaining target contract; exact paths, validation, and test coverage are recorded in `docs/api-implementation.md`, and Phase 4 response shapes and methodology are recorded in `docs/phase4-contracts.md` and `docs/comparison-alignment.md`.

The local service is runnable with `uvicorn backend.app:app`. Do not call these endpoints against a production URL until a deployment exists and is listed in the release notes.

---

## 1. Scope

The API is **read-only** for the public MVP. It exposes:

- the NASA PSI investigation catalog and file metadata;
- curated dataset roles, limitations, and access status;
- gas-flame test rows from PSI-10 and PSI-159;
- SAFFIRE-III telemetry runs and channels from PSI-100;
- SAME-R smoke/detector runs and channels from PSI-101;
- BASS/BASS-II material test matrices from PSI-25 and PSI-26;
- curated comparisons and the comparability matrix;
- provenance and citation records;
- grounded assistant answers, if the optional insight layer is enabled.

It does not expose:

- arbitrary SQL, table names, file paths, or filesystem access;
- raw NASA files through the API (the provenance endpoint links to the NASA download endpoint);
- write operations, user accounts, or saved views in the MVP;
- computed risk scores, material rankings, or predictions;
- any value that is not backed by a source row and a citation.

### 1.1 Implementation status (Phase 4)

Implemented and tested:

| Implemented path | Purpose |
|---|---|
| `GET /api/v1/health` | Liveness, dataset version, table readiness. |
| `GET /api/v1/meta` | Registry snapshot, canonical counts, dataset and measurement counts. |
| `GET /api/v1/investigations` | NASA PSI catalog. |
| `GET /api/v1/investigations/{accession}` | One investigation and curated datasets. |
| `GET /api/v1/datasets` | Curated dataset registry with use-specific serving states. |
| `GET /api/v1/datasets/quality` | Quality summary for all curated datasets. |
| `GET /api/v1/datasets/{dataset_id}` | One dataset, all four serving decisions, measurements. |
| `GET /api/v1/datasets/{dataset_id}/quality` | Quality report slice. |
| `GET /api/v1/datasets/{dataset_id}/files` | Curated file manifest with availability and download status. |
| `GET /api/v1/datasets/{dataset_id}/fields` | Field dictionary derived from the comparability registry and verified source columns. |
| `GET /api/v1/datasets/{dataset_id}/limitations` | Scoped limitations with evidence and affected operations. |
| `GET /api/v1/measurements` | Measurement registry with serving states. |
| `GET /api/v1/measurements/{measurement_id}` | One measurement, serving decision, rules. |
| `GET /api/v1/gas-flame/facets` | Facet counts and per-accession distributions from canonical rows. |
| `GET /api/v1/gas-flame/tests` | PSI-10/PSI-159 rows with filters. |
| `GET /api/v1/gas-flame/tests/{observation_id}` | One gas-flame row. |
| `GET /api/v1/material/tests` | PSI-25/PSI-26 rows with filters. |
| `GET /api/v1/droplet/tests` | PSI-69 rows with filters. |
| `GET /api/v1/telemetry/runs` | PSI-100 runs. |
| `GET /api/v1/telemetry/runs/{run_id}` | Run metadata and channels. |
| `GET /api/v1/telemetry/runs/{run_id}/series` | Bounded telemetry series. |
| `GET /api/v1/smoke/runs` | PSI-101 runs. |
| `GET /api/v1/smoke/runs/{run_id}` | Run metadata and channels. |
| `GET /api/v1/smoke/runs/{run_id}/series` | Bounded smoke series. |
| `GET /api/v1/comparability` | Comparability summary. |
| `GET /api/v1/compare` | One comparison decision with integrity checks and paired-value eligibility. |
| `GET /api/v1/citations` | File-level citation registry with filters. |
| `GET /api/v1/citations/{citation_id}` | One file or row citation, including row verification. |
| `GET /api/v1/publications` | Deduplicated publication registry with filters. |
| `GET /api/v1/publications/{publication_id}` | One publication record with verification and field status. |
| `GET /api/v1/provenance` | Source-file and optional row provenance. |
| `GET /api/v1/assistant/status` | Safe assistant mode, provider, retrieval status, contract version, and tools. |
| `GET /api/v1/assistant/suggestions` | Curated real golden questions; suggestions are not evidence. |
| `GET /api/v1/assistant/tools` | Allowlisted tool descriptions and argument schemas. |
| `POST /api/v1/assistant/query` | Grounded answer in the shared envelope; deterministic by default. |

Known differences from the target contract below:

- The investigation catalog is `/investigations`, not `/datasets`; `/datasets` means curated datasets.
- Dataset metadata paths use the curated `dataset_id` (for example `psi-10-gas-flame`), not the accession.
- The material path is `/material/tests`, not `/materials/tests`.
- Publication records are served from `/publications` and `/publications/{publication_id}`; there is no `/datasets/{dataset_id}/publications` path. Filter `/publications?dataset_id=...` or `?accession=...` instead.
- Assistant endpoints are **not implemented**.
- A blocked or not-comparable decision is returned as HTTP `200` from `/compare`, with the decision in `data.status`.
- The implemented success envelope always includes `data`, `meta`, `provenance`, and `quality`; `quality.status` uses the five values listed in §3.6.
- Paired comparison values are deliberately withheld. `/compare` always returns `paired_values.available=false` in Phase 4 because no verified alignment method is registered. The frontend renders a chart only when a future backend returns a complete paired contract.

Run the service and tests as described in `docs/api-implementation.md`.

---

## 2. Base URL and versioning

| Environment | Base URL |
|---|---|
| Local | `http://localhost:8000/api/v1` |
| Staging | Assigned at deployment; not yet available |
| Production | Assigned at deployment; not yet available |

The path version is part of the URL (`/api/v1`). Breaking changes require `/api/v2`. Additive fields are allowed within `v1`; clients must ignore unknown fields.

OpenAPI is served at:

```text
GET /api/v1/openapi.json
GET /api/v1/docs
```

The OpenAPI schema is the machine-readable source of truth for the implemented surface. This document explains intent and examples; `docs/api-implementation.md` records the exact implemented paths and validation.

---

## 3. Conventions

### 3.1 Content type

- Requests: `application/json` for POST bodies.
- Responses: `application/json; charset=utf-8`.
- Errors: `application/json`.

### 3.2 Identifiers

| Identifier | Format | Example |
|---|---|---|
| `accession` | `PSI-<number>` | `PSI-159` |
| `dataset_id` | lowercase slug | `psi-159-gas-flame` |
| `run_id` | `<accession>::<file stem>` | `PSI-100::PSI-100_Raw Data_Raw telemetry file` |
| `observation_id` | `sha256:<64 hex>` | `sha256:...` |
| `citation_id` (file) | `cit_f_<16 hex>` | `cit_f_21df4ec92db1eca0` |
| `citation_id` (row) | `cit_r_<base64url>` | `cit_r_eyJhIjoiUFNJLTEwIi...` |
| `publication_id` | `pub_<16 hex>` | `pub_0c1b7d7e064074d9` |
| `limitation_id` | `lim_<scope>_<stable slug>` | `lim_d_psi_10_gas_flame_computed_tad_zst` |
| `field_id` | `<dataset_id>.<canonical_name>` | `psi-10-gas-flame.oxygen_mole_fraction` |
| `dataset_version` | 64-hex opaque version | `2a19f9f2e7dda7bb...` |

Identifiers are opaque to clients. Do not parse them beyond the documented accession pattern. Row citation IDs are reversible by the server only; clients must treat them as opaque keys.

### 3.3 Response envelope

Every successful response uses the same envelope:

```json
{
  "data": {},
  "meta": {
    "request_id": "req_01J...",
    "registry_snapshot": "2026-11-08",
    "dataset_version": null,
    "retrieved_at": "2026-11-08T00:00:00Z",
    "generated_at": "2026-11-08T00:00:00Z"
  },
  "provenance": [],
  "quality": {
    "status": "verified",
    "flags": []
  }
}
```

| Field | Type | Meaning |
|---|---|---|
| `data` | object or array | The requested resource. |
| `meta.request_id` | string | Correlation identifier for logs and support. |
| `meta.registry_snapshot` | date | Date of the committed PSI metadata snapshot. |
| `meta.dataset_version` | string or null | Canonical dataset version for data-bearing responses. The Phase 4 service reports the committed canonical version; metadata-only responses may use `null`. |
| `meta.retrieved_at` | timestamp or null | Source retrieval time. `null` when the response is derived from the committed registry only. |
| `meta.generated_at` | timestamp | Time the response was produced. |
| `provenance` | array | Source references for the data in this response. |
| `quality.status` | category | `verified`, `partial`, `blocked`, `experimental_table_only`, `not_available`. |
| `quality.flags` | array | Response-level flags such as `stale_registry`, `listed_404`, `missing_values`, `uncalibrated_channel`. |

### 3.4 Provenance object

```json
{
  "accession": "PSI-159",
  "file": "PSI-159_Experimental table_CFI-G_Normal Flames.csv",
  "sheet": null,
  "field": "Peak burner T (C )",
  "rows": [1],
  "sha256": "d95a621c3fbd27d204dd32ed29fa17d68f2b779d6a523cde8479ed7ebaa5251a",
  "retrieved_at": "2026-11-08T00:00:00Z",
  "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-159/download?file=..."
}
```

Rules:

- `file` is the exact source file name.
- `rows` are 1-based data rows after the header.
- `sha256` is the checksum of the exact file bytes.
- `source_url` is the public NASA download endpoint, URL-encoded. It contains no credentials.
- A response that mixes datasets includes one provenance object per source.

### 3.5 Field object

Every field endpoint and every value-bearing response uses this shape:

```json
{
  "raw_name": "Peak burner T (C )",
  "canonical_name": "peak_burner_temp_c",
  "type": "float",
  "unit": "°C",
  "computed": false,
  "missingness": ["sentinel_dash"],
  "description": "Measured peak burner temperature.",
  "source": {
    "accession": "PSI-159",
    "file": "PSI-159_Experimental table_CFI-G_Normal Flames.csv"
  }
}
```

| Field | Type | Meaning |
|---|---|---|
| `raw_name` | string | Exact source header, including spacing. |
| `canonical_name` | string | Stable name from `DATA_DICTIONARY.md`. |
| `type` | category | `string`, `integer`, `float`, `boolean`, `timestamp`, `category`, `json`. |
| `unit` | string | Unit, `dimensionless`, or `not stated`. Never guessed. |
| `computed` | boolean | `true` for `Tad`, `Zst`, derived rates, and aggregates. |
| `missingness` | array | Sentinel/quality flags observed for this field. |
| `description` | string | Short definition. |
| `source` | object | Accession and file. |

### 3.6 Quality flags

| Flag | Meaning |
|---|---|
| `missing_blank` | Source cell was empty. |
| `sentinel_dash` | Source used `-`. |
| `not_applicable` | Source used `n/a` or `N/A`. |
| `not_available` | Source used `none`. |
| `over_range` | Source used `OR`; in BASS-II, CO > 1000 ppm. |
| `qualifier_ramp` | Source used `RAMP` or `RAMPED`; not numeric. |
| `qualifier_low_o2` | Source used `LOW O2`; not numeric. |
| `spreadsheet_error_div0` | Source used `#DIV/0!`; invalid value. |
| `spreadsheet_error_value` | Source used `#VALUE!`; invalid value. |
| `sentinel_minus_999` | Instrument sentinel; not a negative concentration. |
| `sentinel_timestamp_footer` | Large negative time sentinel. |
| `constant_channel` | Channel is constant in the inspected export; not evidence of a physical constant. |
| `uncalibrated` | Raw sensor value without a documented calibration. |
| `not_stated_unit` | Source does not state a unit. |
| `listed_404` | File is listed but returned HTTP 404. |
| `experimental_table_only` | No `added` archive files are exposed, but a public experimental summary table is available. |
| `blocked` | Dataset failed a validation gate. |

### 3.7 Error model

```json
{
  "error": {
    "code": "invalid_query",
    "message": "start_ms and end_ms are required for telemetry series requests.",
    "details": {
      "parameter": "start_ms"
    },
    "request_id": "req_01J..."
  }
}
```

| HTTP | Code | When |
|---:|---|---|
| 400 | `invalid_query` | Missing, malformed, or contradictory parameters. |
| 404 | `not_found` | Accession, dataset, run, or observation does not exist. |
| 404 | `unknown_measurement` | Measurement identifier is not in the comparability registry. |
| 409 | `dataset_blocked` | Reserved target-contract code; not emitted by the Phase 4 API. Blocked comparisons return `200` with `data.status`. |
| 413 | `range_too_large` | Time range or page size exceeds the documented limit. |
| 422 | `validation_error` | Query or request validation failed. |
| 429 | `rate_limited` | The per-client request rate limit was exceeded. |
| 500 | `internal_error` | Unhandled server error; no source details are leaked. |
| 503 | `service_unavailable` | A required canonical table is absent. |
| 503 | `query_timeout` | A bounded query exceeded its time budget. |

Error messages never include secrets, raw rows, SQL, or filesystem paths.

### 3.8 Pagination

List endpoints accept:

| Parameter | Type | Default | Maximum |
|---|---|---:|---:|
| `limit` | integer | 50 | 200 |
| `offset` | integer | 0 | — |

Response:

```json
{
  "data": [],
  "meta": {
    "page": {
      "limit": 50,
      "offset": 0,
      "total": 24,
      "has_more": false
    }
  }
}
```

Pagination is offset-based in the MVP. Cursor pagination may be added for telemetry.

### 3.9 Filtering and sorting

- Filters are explicit query parameters. No filter expression language, no SQL.
- Repeated parameters are not allowed unless documented as a list.
- Sorting uses `sort=<field>` and `order=asc|desc` with an allowlist per endpoint.
- Unknown parameters return `400 invalid_query`.

### 3.10 Caching

Caching is enabled by default and is process-local. It applies to successful `GET` JSON responses except `/health`:

- `ETag` is a strong hash of a stable representation of the response body. `meta.request_id` and `meta.generated_at` are removed before hashing so repeated requests produce the same validator.
- `Cache-Control: public, max-age=60, must-revalidate` by default.
- Clients may send `If-None-Match`; the server returns `304 Not Modified` with the same `ETag` when the representation is unchanged.
- Error responses use `Cache-Control: no-store`.
- Health responses are excluded from ETag generation and always use `no-store`.
- `X-Request-ID` and rate-limit headers are returned on every response, including `304`.

Configuration:

| Variable | Default | Meaning |
|---|---|---|
| `FLAME_CACHE_ENABLED` | `true` | Enable ETag generation and conditional requests. When `false`, responses use `no-store`. |
| `FLAME_CACHE_MAX_AGE` | `60` | `max-age` seconds in the generated `Cache-Control` value. |
| `FLAME_CACHE_CONTROL` | unset | Full override for the `Cache-Control` header value. |

### 3.11 Rate limits

The API is public and read-only. Rate limiting is an abuse control, **not authentication**. Limits are process-local fixed windows keyed by client IP; behind a reverse proxy, set `FLAME_TRUST_PROXY=true` to use the first `X-Forwarded-For` address.

The API returns these headers on every response:

```text
X-RateLimit-Limit: <n>
X-RateLimit-Remaining: <n>
X-RateLimit-Reset: <seconds until the window resets>
Retry-After: <seconds>   (on 429)
```

A rejected request returns HTTP `429` with `error.code = "rate_limited"` and `Cache-Control: no-store`.

Configuration:

| Variable | Default | Meaning |
|---|---|---|
| `FLAME_RATE_LIMIT_ENABLED` | `true` | Enable the limiter. |
| `FLAME_RATE_LIMIT_REQUESTS` | `600` | Allowed requests per window per client. |
| `FLAME_RATE_LIMIT_WINDOW_SECONDS` | `60` | Fixed window length in seconds. |
| `FLAME_TRUST_PROXY` | `false` | Trust the first `X-Forwarded-For` value. |

Authentication decision: the public MVP has no authentication or user accounts. All data is public NASA PSI material; write operations do not exist. A deployment that adds private data or write operations must add authentication before exposing those capabilities.

---

## 4. Endpoints

### 4.1 Health and metadata

#### `GET /api/v1/health`

Liveness and readiness.

**Response `200`**

```json
{
  "data": {
    "status": "ok",
    "registry_snapshot": "2026-11-08",
    "database": "ok",
    "object_store": "ok",
    "assistant": "disabled"
  },
  "meta": {
    "request_id": "req_01J..."
  }
}
```

`status` is `ok`, `degraded`, or `unavailable`. A degraded service may still serve cached metadata.

#### `GET /api/v1/meta`

Returns the API version, registry snapshot, dataset versions, and counts.

```json
{
  "data": {
    "api_version": "v1",
    "registry_snapshot": "2026-11-08",
    "psi_investigations_total": 133,
    "combustion_investigations": 24,
    "current_files": 16354,
    "registered_total_gb_decimal": 13496.77,
    "datasets": {
      "PSI-10": {"dataset_version": null, "status": "metadata_only"},
      "PSI-159": {"dataset_version": null, "status": "metadata_only"}
    }
  }
}
```

The counts are generated from the registry, not hard-coded in the API.

### 4.2 Catalog and dataset metadata

#### `GET /api/v1/investigations`

List the NASA PSI combustion investigations. This is the catalog endpoint; `/datasets` is the curated dataset registry.

**Query parameters:** `role` (`primary`, `supporting`, `future`, `context`, `unreviewed`), `q` (accession, acronym, or title), `limit`, `offset`.

**Response `200`**

```json
{
  "data": [
    {
      "accession": "PSI-159",
      "acronym": "ACME CFI-G",
      "title": "Advanced Combustion via Microgravity Experiments / Cool Flames Investigation with Gases",
      "doi": "10.60555/cyt1-kh64",
      "mvp_role": "primary",
      "archive_status": "available",
      "file_count": 3756,
      "experimental_table_count": 2,
      "registered_total_gb_decimal": 2085.59
    }
  ],
  "meta": {
    "page": {"limit": 50, "offset": 0, "total": 24, "has_more": false}
  }
}
```

#### `GET /api/v1/investigations/{accession}`

Full investigation card, including its curated datasets. Unknown accessions return `404 not_found`.

#### `GET /api/v1/datasets`

List the curated datasets. **Query parameters:** `family`, `accession`, `state`, `use` (`exploration`, `quantitative_comparison`, `time_series`, `provenance`), `limit`, `offset`.

The response is an array of dataset summaries with `dataset_id`, `accession`, `display_name`, `experiment_family`, `canonical_tables`, `download_status`, `measurement_file_status`, `access_scope`, `base_state`, `use_states`, `measurement_count`, and reasons/restrictions.

#### `GET /api/v1/datasets/{dataset_id}`

Full curated dataset record. The `dataset_id` is a slug such as `psi-10-gas-flame`, not an accession.

**Response `200`** (abbreviated real record)

```json
{
  "data": {
    "dataset_id": "psi-10-gas-flame",
    "accession": "PSI-10",
    "display_name": "PSI-10 ACME Flame Design gas-flame tests",
    "experiment_family": "gas_flame",
    "canonical_tables": ["gas_flame_test"],
    "download_status": "available",
    "measurement_file_status": "available",
    "access_scope": "experimental_summary_table",
    "base_state": "available_with_warnings",
    "use_states": {
      "exploration": "available_with_warnings",
      "quantitative_comparison": "restricted",
      "time_series": "blocked",
      "provenance": "available"
    },
    "measurement_count": 11,
    "reasons": [
      {
        "code": "ramped_condition_rows",
        "message": "69 PSI-10 rows carry RAMP, RAMPED, or LOW O2 qualifiers in numeric columns; they are not fixed set points."
      }
    ],
    "restrictions": [
      "Do not aggregate ramped rows as fixed conditions.",
      "Do not treat Tad or Zst as measured temperatures or mixture fractions."
    ],
    "source_references": [
      {
        "kind": "nasa_psi_file",
        "accession": "PSI-10",
        "file_name": "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
        "sha256": "4a663292bd3f65201943cc71bd661a70383639276a9176f64105b285bf0b6deb",
        "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-10/download?file=PSI-10_Experimental%20table_Flame%20Design_Normal%20Flame.csv"
      }
    ],
    "serving": {}
  }
}
```

#### `GET /api/v1/datasets/{dataset_id}/files`

Curated file manifest. Only files selected by the download manifest are listed, plus known-unavailable files that are explicitly documented. The endpoint never exposes filesystem paths.

**Query parameters**

| Parameter | Type | Description |
|---|---|---|
| `kind` | string | Curated file kind such as `experimental_table` or `raw_data`. |
| `availability` | category | `available` or `unavailable`. |
| `limit`, `offset` | integer | Pagination. |

**Response `200`** (real PSI-98 excerpt)

```json
{
  "data": {
    "dataset_id": "psi-98-metadata",
    "accession": "PSI-98",
    "display_name": "PSI-98 SAFFIRE-I metadata and unavailable telemetry",
    "files": [
      {
        "file_id": "cit_f_2a9f8d907458d052",
        "citation_id": "cit_f_2a9f8d907458d052",
        "file_name": "PSI-98_Experimental table_SAFFIRE-1.csv",
        "accession": "PSI-98",
        "dataset_ids": ["psi-98-metadata"],
        "kind": "experimental_table",
        "priority": "supporting",
        "purpose": "Public experimental summary table. The exact source table is preserved; no archive files are implied for experimental_table_only records.",
        "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-98/download?file=PSI-98_Experimental%20table_SAFFIRE-1.csv",
        "availability": "available",
        "downloadable": true,
        "availability_reason": null,
        "download": {
          "status": "downloaded",
          "http_status": 200,
          "bytes": 469,
          "retrieved_at": "2026-11-08T22:19:13Z",
          "sha256": "c01f29c62455f0a3b512290ab85e5687ecded326733189f002f580368402308d",
          "checksum_match": true
        },
        "verification": {
          "status": "verified",
          "checks": [
            "manifest_checksum_recorded",
            "retrieved_checksum_recorded",
            "checksum_matches_manifest",
            "acquisition_status_confirmed"
          ]
        },
        "provenance": [
          {
            "kind": "nasa_psi_file",
            "accession": "PSI-98",
            "file_name": "PSI-98_Experimental table_SAFFIRE-1.csv",
            "sha256": "c01f29c62455f0a3b512290ab85e5687ecded326733189f002f580368402308d",
            "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-98/download?file=PSI-98_Experimental%20table_SAFFIRE-1.csv"
          }
        ]
      }
    ],
    "summary": {
      "curated_files": 3,
      "available_files": 1,
      "unavailable_files": 2,
      "downloadable_files": 1,
      "known_unavailable_files": 2,
      "experimental_tables": 1
    },
    "inventory": {
      "public_inventory_file_count": 74,
      "curated_file_count": 3,
      "not_selected_file_count": 71,
      "public_experimental_table_count": 1,
      "archive_status": "available",
      "note": "Only curated files are listed. The public inventory count is shown for context; unselected archive files are not exposed."
    },
    "page": {"limit": 50, "offset": 0, "total": 3, "has_more": false}
  }
}
```

Unavailable files have `availability: "unavailable"`, `downloadable: false`, `download.status: "known_unavailable"`, `download.http_status: 404`, `download.sha256: null`, and `verification.status: "unavailable"`. Clients must not render a download link for them. PSI-98's two known 404 files remain listed and unavailable by design.

#### `GET /api/v1/datasets/{dataset_id}/fields`

Field dictionary derived from the 93 comparability measurements, verified source-column mappings, and canonical-data integrity checks. Descriptions are never invented: when the source does not document a method, `measurement_method` says so.

**Query parameters:** `value_kind`, `physical_quantity`, `comparison_status`, `limit`, `offset`.

**Response `200`** (real excerpt)

```json
{
  "data": {
    "dataset_id": "psi-10-gas-flame",
    "accession": "PSI-10",
    "display_name": "PSI-10 ACME Flame Design gas-flame tests",
    "fields": [
      {
        "field_id": "psi-10-gas-flame.adiabatic_flame_temp_k",
        "measurement_id": "psi-10-gas-flame.adiabatic_flame_temp_k",
        "dataset_id": "psi-10-gas-flame",
        "accession": "PSI-10",
        "canonical_name": "adiabatic_flame_temp_k",
        "parameter": "adiabatic_flame_temp_k",
        "description": "Adiabatic flame temperature computed by the source.",
        "physical_quantity": "adiabatic_flame_temperature",
        "unit": "K",
        "unit_status": "stated",
        "value_kind": "computed",
        "measurement_method": "Source-computed field (Tad (K)).",
        "calibration": {"status": "not_applicable", "note": null},
        "missingness": {
          "availability": "available",
          "restrictions": ["computed_source_field", "method_not_documented", "ramped_condition_rows"],
          "canonical_presence": {
            "measurement_id": "psi-10-gas-flame.adiabatic_flame_temp_k",
            "checked": true,
            "status": "available",
            "reason": null,
            "table": "gas_flame_test",
            "field": "adiabatic_flame_temp_k",
            "accession": "PSI-10",
            "total_rows": 327,
            "non_null_count": 256,
            "alternatives": []
          },
          "policy": "Missing values are never zero; qualifiers and sentinels are preserved as documented in DATA_DICTIONARY.md."
        },
        "integrity": {
          "measurement_id": "psi-10-gas-flame.adiabatic_flame_temp_k",
          "checked": true,
          "status": "available",
          "reason": null,
          "table": "gas_flame_test",
          "field": "adiabatic_flame_temp_k",
          "accession": "PSI-10",
          "total_rows": 327,
          "non_null_count": 256,
          "alternatives": []
        },
        "alternatives": [],
        "flags": ["computed_source_field", "method_not_documented", "ramped_condition_rows"],
        "comparability": {
          "status": "blocked",
          "compatible_datasets": [],
          "incompatible_datasets": ["psi-10-gas-flame", "psi-159-gas-flame"],
          "rules": []
        },
        "source_columns": [
          {
            "raw_column": "Tad (K)",
            "source_file": "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
            "applies_to": "Normal flame rows"
          }
        ],
        "source_references": [],
        "serving_state": "available_with_warnings",
        "use_states": {
          "exploration": "available_with_warnings",
          "quantitative_comparison": "restricted",
          "time_series": "blocked",
          "provenance": "available"
        }
      }
    ],
    "summary": {
      "field_count": 11,
      "with_verified_source_column": 11,
      "with_canonical_values": 9,
      "without_canonical_values": 2,
      "presence_not_checked": 0,
      "value_kinds": {"computed": 2, "measured": 9},
      "comparison_statuses": {"blocked": 2, "not_comparable": 9}
    },
    "page": {"limit": 50, "offset": 0, "total": 11, "has_more": false}
  }
}
```

`integrity.status` is `available`, `missing`, `not_checked`, or `no_canonical_tables`. A registry field marked `available` that has zero canonical values is reported as `missing` and receives an alternative where one exists. Missing is never zero.

#### `GET /api/v1/datasets/{dataset_id}/limitations`

Scoped limitations with stable IDs, severity, evidence, affected operations, and resolution status.

**Query parameters:** `scope`, `category`, `severity`, `status`, `limit`, `offset`.

**Response `200`** (real excerpt)

```json
{
  "data": {
    "dataset_id": "psi-10-gas-flame",
    "accession": "PSI-10",
    "display_name": "PSI-10 ACME Flame Design gas-flame tests",
    "limitations": [
      {
        "limitation_id": "lim_d_psi_10_gas_flame_computed_tad_zst",
        "scope": "dataset",
        "scope_id": "psi-10-gas-flame",
        "dataset_id": "psi-10-gas-flame",
        "accession": "PSI-10",
        "category": "value_kind",
        "severity": "warning",
        "code": "computed_tad_zst",
        "explanation": "Tad (K) and Zst are computed by the source, not measured.",
        "affected_operations": ["exploration", "quantitative_comparison", "time_series"],
        "evidence": [
          {
            "kind": "nasa_psi_file",
            "accession": "PSI-10",
            "file_name": "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
            "sha256": "4a663292bd3f65201943cc71bd661a70383639276a9176f64105b285bf0b6deb",
            "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-10/download?file=PSI-10_Experimental%20table_Flame%20Design_Normal%20Flame.csv"
          }
        ],
        "resolution_status": "documented",
        "resolution_note": "Recorded as a dataset-level serving limitation."
      }
    ],
    "summary": {
      "total": 5,
      "by_scope": {"dataset": 4, "field": 1},
      "by_severity": {"warning": 4, "error": 1},
      "by_status": {"documented": 5}
    },
    "page": {"limit": 50, "offset": 0, "total": 5, "has_more": false}
  }
}
```

Limitations include serving restrictions, registry quality issues, unavailable files, and measurement-integrity findings. Fields already marked `missing` in the registry are not duplicated as integrity limitations.

#### Dataset publications

There is no `/datasets/{dataset_id}/publications` route. Use `GET /api/v1/publications?dataset_id=<dataset_id>` or `?accession=<accession>`; see §4.8.

### 4.3 Gas-flame tests

#### `GET /api/v1/gas-flame/tests`

Query PSI-10 and PSI-159 test rows.

**Query parameters**

| Parameter | Type | Description |
|---|---|---|
| `accession` | string | `PSI-10` or `PSI-159`. Required unless `datasets` is used. |
| `flame_type` | category | `Normal`, `Inverse` (preserve source case variants in the response). |
| `fuel` | string | Exact or case-insensitive source label. |
| `oxygen_min`, `oxygen_max` | float | Mole fraction, not percent. |
| `pressure_min`, `pressure_max` | float | Unit depends on dataset; the response states the unit. |
| `hot_ignition` | category | `Yes`, `No`, `yes`, `no`, `flash`. |
| `extinction_mode` | category | `SE`, `FT`, `-`. |
| `tfp` | category | `Yes`, `No`; categorical. |
| `include_qualified` | boolean | Include rows with `RAMP`/`RAMPED`/`LOW O2`. Default `false`. |
| `sort` | string | `source_row`, `oxygen_mole_fraction`, `pressure`, `peak_burner_temp_c`. |
| `order` | category | `asc`, `desc`. |
| `limit`, `offset` | integer | Pagination. |

**Rules**

- Oxygen is always a mole fraction in the canonical field. The API may accept `oxygen_percent` only with an explicit conversion flag; the MVP does not.
- Pressure filters apply only when the dataset has a compatible pressure field. A request that mixes `atm` and `bar` without a unit parameter returns `400 invalid_query`.
- `include_qualified=false` excludes rows whose numeric fields contain qualifiers. The response reports `excluded_qualified_rows`.

**Response `200`**

```json
{
  "data": [
    {
      "observation_id": "sha256:...",
      "accession": "PSI-159",
      "table_id": "PSI-159::CFI-G_Normal_Flames::csv",
      "source_row": 1,
      "flame_type": "Normal",
      "day": "1",
      "fuel": "ethane",
      "test_code": "21088A1",
      "pressure_approx_bar": 0.9443956,
      "oxygen_mole_fraction_before": 0.3939,
      "oxygen_mole_fraction_after": 0.389822946,
      "fuel_mole_fraction": 1.0,
      "fuel_mass_flow_mg_s": 2.0,
      "adiabatic_flame_temp_k": 2719.323211,
      "stoich_mixture_fraction": 0.102651783,
      "hot_ignition": "Yes",
      "cool_flame_flag": null,
      "tfp_flag": "No",
      "burn_time_s": 50.0,
      "extinction_mode": "SE",
      "peak_burner_temp_c": 290.617198,
      "quality_flags": []
    }
  ],
  "meta": {
    "page": {"limit": 50, "offset": 0, "total": 179, "has_more": true},
    "excluded_qualified_rows": 0,
    "dataset_version": "assigned-in-phase-2"
  },
  "provenance": [
    {
      "accession": "PSI-159",
      "file": "PSI-159_Experimental table_CFI-G_Normal Flames.csv",
      "rows": [1],
      "sha256": "d95a621c3fbd27d204dd32ed29fa17d68f2b779d6a523cde8479ed7ebaa5251a"
    }
  ]
}
```

`cool_flame_flag` is `null` for a blank source cell. It is not `"No"`.

#### `GET /api/v1/gas-flame/tests/{observation_id}`

One test row with full provenance.

**Errors**

- `404 not_found` — unknown observation.
- `409 dataset_blocked` — the source dataset failed validation.

#### `GET /api/v1/gas-flame/facets`

Returns allowlisted facet values and counts for the explorer filters.

```json
{
  "data": {
    "accession": "PSI-159",
    "fuel": [{"value": "ethane", "count": 14}],
    "flame_type": [{"value": "Normal", "count": 179}],
    "hot_ignition": [{"value": "Yes", "count": 132}],
    "extinction_mode": [{"value": "SE", "count": 102}]
  }
}
```

Facet counts are computed from the canonical table, not from the frontend.

### 4.4 Telemetry (SAFFIRE-III, PSI-100)

#### `GET /api/v1/telemetry/runs`

List telemetry exports.

**Query parameters:** `accession` (default `PSI-100`), `export_kind`, `limit`, `offset`.

```json
{
  "data": [
    {
      "run_id": "PSI-100::PSI-100_Raw Data_Raw telemetry file",
      "accession": "PSI-100",
      "source_file": "PSI-100_Raw Data_Raw telemetry file.csv",
      "export_kind": "raw_csv",
      "physical_rows": 3972,
      "valid_rows": 3966,
      "sentinel_rows": 6,
      "time_min_ms": 0,
      "time_max_ms": 9573373,
      "channel_count": 47,
      "sha256": "dfb204ce3bdf8b1749652549afcbad31d180902bc268dfbe782c70fa38d170a2"
    }
  ]
}
```

Exports are separate runs. The API never merges them into one series.

#### `GET /api/v1/telemetry/runs/{run_id}`

Run detail, including channel metadata.

```json
{
  "data": {
    "run_id": "PSI-100::PSI-100_Raw Data_Raw telemetry file",
    "source_file": "PSI-100_Raw Data_Raw telemetry file.csv",
    "export_kind": "raw_csv",
    "physical_rows": 3972,
    "valid_rows": 3966,
    "sentinel_rows": 6,
    "time_min_ms": 0,
    "time_max_ms": 9573373,
    "channels": [
      {
        "channel_name_raw": "P@sfsHk.Radiometer1value",
        "channel_name_canonical": "radiometer_1_raw",
        "unit": "not stated",
        "quality_flags": ["not_stated_unit"]
      }
    ],
    "limitations": [
      "RelativeSeconds contains milliseconds despite the name.",
      "This export is not interchangeable with the cleaned CSV or the XLSX."
    ]
  }
}
```

#### `GET /api/v1/telemetry/runs/{run_id}/series`

Time-series query.

**Query parameters**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `channels` | comma-separated string | Yes | Allowlisted canonical channel names. Maximum 8 per request. |
| `start_ms` | integer | Yes | Inclusive start in milliseconds. |
| `end_ms` | integer | Yes | Inclusive end in milliseconds. |
| `max_points` | integer | No | Default 5,000; maximum 20,000. |

**Rules**

- `start_ms < end_ms`.
- The range must fall within the run's valid time range.
- If the requested range produces more than `max_points`, return `413 range_too_large` with the actual count and a suggested narrower range. Do not silently downsample.
- A future `decimation=minmax` parameter may be added with a documented method. It is not in the MVP.
- Sentinel rows are excluded and reported in `meta.excluded_sentinel_rows`.

**Response `200`**

```json
{
  "data": {
    "run_id": "PSI-100::PSI-100_Raw Data_Raw telemetry file",
    "time_unit": "ms",
    "channels": [
      {
        "channel_name_raw": "P@PCM_ETS_TEMP_SIG",
        "channel_name_canonical": "pcm_air_temp_c",
        "unit": "°C",
        "quality_flags": []
      }
    ],
    "points": [
      {"time_ms": 0, "pcm_air_temp_c": 20.6}
    ]
  },
  "meta": {
    "returned_points": 1,
    "excluded_sentinel_rows": 6,
    "dataset_version": "assigned-in-phase-2"
  },
  "provenance": [
    {
      "accession": "PSI-100",
      "file": "PSI-100_Raw Data_Raw telemetry file.csv",
      "rows": [1, 2],
      "sha256": "dfb204ce3bdf8b1749652549afcbad31d180902bc268dfbe782c70fa38d170a2"
    }
  ]
}
```

The example shows one real source row from the first valid time step in the inspected raw export. A real request returns every point in the requested range, not a two-point sample.

**Errors**

- `400 invalid_query` — missing range, invalid channel, `start_ms >= end_ms`.
- `404 not_found` — unknown run.
- `413 range_too_large` — too many points.
- `409 dataset_blocked` — run failed validation.

### 4.5 Smoke (SAME-R, PSI-101)

#### `GET /api/v1/smoke/runs`

List SAME-R HKP runs.

```json
{
  "data": [
    {
      "run_id": "PSI-101::HKPData_gmt250_1",
      "accession": "PSI-101",
      "source_file": "PSI-101_Raw Data_HKPData_gmt250_1.csv",
      "test_number": 91,
      "sample_number": 0,
      "carousel_number": 0,
      "physical_rows": 558,
      "time_min_unix_s": 1283862804,
      "time_max_unix_s": 1283863362,
      "channel_count": 98,
      "sha256": "69c25a566b6af6b43fb263ceadad82499b6e18e69e5fdad928e8088124ee43a3"
    }
  ]
}
```

#### `GET /api/v1/smoke/runs/{run_id}/series`

Same contract as telemetry, with `elapsed_test_time_s` as the time axis and an allowlisted set of physical channels. Device-state columns are available only through the run detail, not as physical series.

**Query parameters:** `channels`, `start_s`, `end_s`, `max_points`.

**Rules**

- `PTrakMeasurement(PtPerCC)` values of `-999` are excluded and counted as `sentinel_minus_999`.
- `DustTrakA` all-zero is flagged `constant_channel` and `possibly_inactive`.
- Detector voltages are labeled as voltages, not converted to obscuration percentage without calibration.

### 4.6 Material test matrices (PSI-25, PSI-26)

#### `GET /api/v1/material/tests`

Query BASS/BASS-II test-matrix rows.

**Query parameters:** `accession` (`PSI-25` or `PSI-26`), `material`, `flow_restrictor`, `o2_min`, `o2_max`, `limit`, `offset`.

```json
{
  "data": [
    {
      "observation_id": "sha256:...",
      "accession": "PSI-25",
      "table_id": "PSI-25::BASS-II_Test.Matrices::Ferkul",
      "source_row": 1,
      "test_date": "2014-02-19",
      "gmt_day_2014": 50,
      "test_no": "F1",
      "sample_no": "227",
      "material": "Nomex natural (nomex III)",
      "flow_restrictor": "2",
      "fan_display": "82",
      "air_display": "9.5",
      "radiometer_gain": "250",
      "total_frames": "208",
      "initial_o2_pct": 22.2,
      "final_o2_pct": 22.2,
      "initial_co2_pct": 0.46,
      "final_co2_pct": 0.45,
      "initial_co_ppm": 0.0,
      "final_co_ppm": 2.0,
      "quality_flags": []
    }
  ]
}
```

**Rules**

- No spread rate is returned. The endpoint does not have a spread-rate field.
- `air_display` and `fan_display` are source display text unless a documented unit mapping exists.
- `OR` and `-1` are flagged, not converted.

### 4.7 Comparability and comparisons

#### `GET /api/v1/comparability`

Returns the comparability registry summary, state definitions, and rules.

```json
{
  "data": {
    "registry_version": "1.0.0",
    "dataset_version": "2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb",
    "default_policy": {
      "status": "not_comparable",
      "justification": "No explicit comparison rule means no approved comparison. A matching column name, unit, or experiment family is not sufficient evidence.",
      "engine_behavior": "Return not_comparable with a no_explicit_rule reason and never infer a comparison."
    },
    "state_definitions": {
      "comparable": {
        "definition": "The two measurements refer to the same physical quantity, use compatible units and value kinds, have no unresolved calibration or metadata restriction, and require no unverified condition.",
        "engine_behavior": "Returned only when every required condition is verified."
      },
      "conditionally_comparable": {
        "definition": "The measurements can be compared only after one or more explicit conditions are verified.",
        "engine_behavior": "Returned when a rule exists but at least one required condition has not been supplied or verified."
      },
      "not_comparable": {
        "definition": "The measurements do not share a valid comparison basis.",
        "engine_behavior": "Returned for explicit not-comparable rules and by default when no rule exists."
      },
      "blocked": {
        "definition": "The measurements might share a physical basis, but a hard integrity constraint prevents comparison.",
        "engine_behavior": "Returned for explicit blocked rules and for hard unit, value-kind, calibration, availability, or quantity conflicts."
      },
      "insufficient_metadata": {
        "definition": "The available metadata is not sufficient to decide whether a comparison is valid.",
        "engine_behavior": "Returned instead of guessing."
      }
    }
  }
}
```

#### `GET /api/v1/compare`

Compare two measurement identifiers. The request names registry measurements, not arbitrary columns.

**Query parameters**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `left` | string | Yes | Left measurement identifier, for example `psi-10-gas-flame.oxygen_mole_fraction`. |
| `right` | string | Yes | Right measurement identifier. |
| `conditions` | JSON string | No | Object mapping condition keys to `true`, `false`, or `null`. Unknown keys are rejected. |

**Response `200`** (real excerpt, conditions supplied)

```json
{
  "data": {
    "left": {
      "measurement_id": "psi-10-gas-flame.oxygen_mole_fraction",
      "dataset_id": "psi-10-gas-flame",
      "accession": "PSI-10",
      "experiment_family": "gas_flame",
      "parameter": "oxygen_mole_fraction",
      "canonical_field": "oxygen_mole_fraction",
      "physical_quantity": "oxygen_mole_fraction",
      "unit": "mole fraction",
      "unit_status": "stated",
      "value_kind": "measured",
      "calibration_status": "not_applicable",
      "availability": "available",
      "comparison_status": "conditionally_comparable",
      "quality_restrictions": ["ramped_condition_rows", "low_oxygen_rows"]
    },
    "right": {
      "measurement_id": "psi-159-gas-flame.oxygen_mole_fraction",
      "dataset_id": "psi-159-gas-flame",
      "accession": "PSI-159",
      "experiment_family": "gas_flame",
      "parameter": "oxygen_mole_fraction",
      "canonical_field": "oxygen_mole_fraction",
      "physical_quantity": "oxygen_mole_fraction",
      "unit": "mole fraction",
      "unit_status": "stated",
      "value_kind": "measured",
      "calibration_status": "not_applicable",
      "availability": "available",
      "comparison_status": "conditionally_comparable",
      "quality_restrictions": []
    },
    "status": "comparable",
    "rule_id": "psi10-psi159-oxygen",
    "reasons": [
      {
        "code": "conditions_verified",
        "message": "Every required comparison condition is verified."
      }
    ],
    "required_conditions": [
      {
        "key": "same_oxygen_basis",
        "description": "Both values are oxygen mole fraction, not percent or partial pressure.",
        "satisfied": true
      },
      {
        "key": "flame_configuration_documented",
        "description": "Normal or inverse configuration is known for both rows.",
        "satisfied": true
      }
    ],
    "warnings": [],
    "scientific_justification": "Both fields are controlled oxygen mole fractions in gas-flame experiments. Comparison is allowed only when both rows use the same oxygen basis and the normal or inverse configuration is known.",
    "source_references": [],
    "registry_version": "1.0.0",
    "dataset_version": "2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb",
    "integrity": {
      "status": "passed",
      "checks": [
        {
          "measurement_id": "psi-10-gas-flame.oxygen_mole_fraction",
          "checked": true,
          "status": "available",
          "reason": null,
          "table": "gas_flame_test",
          "field": "oxygen_mole_fraction",
          "accession": "PSI-10",
          "total_rows": 327,
          "non_null_count": 109,
          "alternatives": []
        }
      ],
      "failures": [],
      "not_checked": [],
      "messages": []
    },
    "paired_values": {
      "available": false,
      "status": "unavailable",
      "alignment": {
        "method_id": null,
        "verified": false,
        "keys": [],
        "value_fields": {},
        "unit_policy": null
      },
      "conditions": {
        "supplied": {
          "same_oxygen_basis": true,
          "flame_configuration_documented": true
        },
        "required": [
          {"key": "same_oxygen_basis", "satisfied": true},
          {"key": "flame_configuration_documented", "satisfied": true}
        ]
      },
      "observations": [],
      "series": [],
      "exclusions": [],
      "dataset_version": "2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb",
      "provenance": [],
      "reason": {
        "code": "no_verified_alignment",
        "message": "The comparison is approved, but no verified record-level alignment method is registered for this rule. The API does not pair by row number, interpolate, normalize silently, or convert ambiguous units.",
        "rule_id": "psi10-psi159-oxygen",
        "required_alignment": {
          "keys": [],
          "note": "A committed method must name exact alignment keys and value fields."
        }
      }
    }
  },
  "meta": {
    "request_id": "req_ff3be139e25c3efa76024fe5",
    "registry_snapshot": "2026-11-08",
    "dataset_version": "2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb",
    "registry_version": "1.0.0",
    "retrieved_at": null,
    "generated_at": "2026-11-09T18:56:19.801219Z",
    "page": null,
    "left": "psi-10-gas-flame.oxygen_mole_fraction",
    "right": "psi-159-gas-flame.oxygen_mole_fraction",
    "paired_values_available": false,
    "integrity_status": "passed"
  }
}
```

**Paired-value rules**

- `paired_values.available` is `false` unless a committed alignment method names exact keys and value fields, both sides pass integrity checks, all required conditions are verified, and every observation can be traced to real source rows.
- The API never pairs by arbitrary row number, interpolates, silently normalizes, or converts ambiguous units.
- When conditions are missing, `paired_values.reason.code` is `conditions_not_verified`; when the decision is approved but no alignment method exists, it is `no_verified_alignment`.
- `series` is empty unless a future executor produces chart-ready paired observations. Clients must not synthesize a paired series from unpaired left/right values.
- PSI-10 pressure is in atm and PSI-159 pressure is in bar; the API reports them per accession and never merges them.

**Errors**

- `400 invalid_query` — unknown measurement, malformed conditions, or unknown condition keys.
- `404 unknown_measurement` — measurement identifier is not in the comparability registry.

### 4.8 Provenance, citations, and publications

#### `GET /api/v1/provenance`

Resolve a source reference.

**Query parameters:** `accession`, `file`, optional `sheet`, optional `row`.

```json
{
  "data": {
    "accession": "PSI-159",
    "file": "PSI-159_Experimental table_CFI-G_Normal Flames.csv",
    "sheet": null,
    "sha256": "d95a621c3fbd27d204dd32ed29fa17d68f2b779d6a523cde8479ed7ebaa5251a",
    "retrieved_at": "2026-11-08T00:00:00Z",
    "bytes": 22166,
    "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-159/download?file=...",
    "citation_id": "cit_f_...",
    "file_citation_id": "cit_f_...",
    "row_citation_ids": ["cit_r_..."]
  }
}
```

A file that is not in the canonical file metadata returns `404 not_found`; the API does not substitute a fuzzy match.

#### `GET /api/v1/citations`

List file-level citations derived from the download manifest and acquisition report. **Query parameters:** `accession`, `dataset_id`, `kind`, `verification_status`, `availability`, `limit`, `offset`.

```json
{
  "data": [
    {
      "citation_id": "cit_f_21df4ec92db1eca0",
      "kind": "file",
      "accession": "PSI-10",
      "dataset_ids": ["psi-10-gas-flame"],
      "file": {
        "name": "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
        "kind": "experimental_table",
        "manifest_dataset": "gas_flame_test",
        "priority": "primary",
        "purpose": "Public experimental summary table. The exact source table is preserved; no archive files are implied for experimental_table_only records.",
        "in_added": true
      },
      "locator": {"type": "file", "sheet": null, "row": null},
      "source": {
        "kind": "nasa_psi_file",
        "accession": "PSI-10",
        "file_name": "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
        "sha256": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
        "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-10/download?file=PSI-10_Experimental%20table_Flame%20Design_Inverse%20Flame.csv"
      },
      "retrieval": {
        "retrieved_at": "2026-11-08T22:14:49Z",
        "http_status": null,
        "download_status": "already_present",
        "bytes": 17314,
        "expected_bytes": 17314,
        "checksum_expected": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
        "checksum_actual": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
        "checksum_match": true
      },
      "verification": {
        "status": "verified",
        "checks": [
          "manifest_checksum_recorded",
          "retrieved_checksum_recorded",
          "checksum_matches_manifest",
          "acquisition_status_confirmed"
        ]
      },
      "availability": {"status": "available", "downloadable": true, "reason": null},
      "provenance": []
    }
  ],
  "meta": {
    "page": {"limit": 50, "offset": 0, "total": 74, "has_more": true}
  }
}
```

#### `GET /api/v1/citations/{citation_id}`

Returns one file or row citation. Row citations are created on demand from an exact accession, file, sheet, and 1-based row; they decode to that locator and include `row_verification`.

```json
{
  "data": {
    "citation_id": "cit_r_eyJhIjoiUFNJLTEwIiwiZiI6IlBTSS0xMF9FeHBlcmltZW50YWwgdGFibGVfRmxhbWUgRGVzaWduX0ludmVyc2UgRmxhbWUuY3N2IiwiciI6MSwicyI6bnVsbH0",
    "kind": "row",
    "accession": "PSI-10",
    "dataset_ids": ["psi-10-gas-flame"],
    "file": {
      "name": "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
      "kind": "experimental_table",
      "manifest_dataset": "gas_flame_test",
      "priority": "primary",
      "purpose": "Public experimental summary table. The exact source table is preserved; no archive files are implied for experimental_table_only records.",
      "in_added": true
    },
    "locator": {"type": "row", "sheet": null, "row": 1, "row_range": [1, 1]},
    "source": {
      "kind": "nasa_psi_file",
      "accession": "PSI-10",
      "file_name": "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
      "sha256": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
      "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-10/download?file=PSI-10_Experimental%20table_Flame%20Design_Inverse%20Flame.csv"
    },
    "retrieval": {
      "retrieved_at": "2026-11-08T22:14:49Z",
      "http_status": null,
      "download_status": "already_present",
      "bytes": 17314,
      "expected_bytes": 17314,
      "checksum_expected": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
      "checksum_actual": "97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4",
      "checksum_match": true
    },
    "verification": {"status": "verified", "checks": ["canonical_row_located"]},
    "availability": {"status": "available", "downloadable": true, "reason": null},
    "row_verification": {
      "row_verified": true,
      "row_tables": ["gas_flame_test", "experimental_table_cell", "source_row"],
      "warnings": []
    },
    "provenance": []
  }
}
```

Citation IDs are stable and deterministic. File IDs are `cit_f_<hex>`; row IDs are `cit_r_<base64url>` and are treated as opaque by clients. A citation is derived only from verified metadata; unknown or unavailable files do not receive a fabricated checksum.

#### `GET /api/v1/publications`

List deduplicated publications from the NASA PSI investigation registry. **Query parameters:** `accession`, `dataset_id` (resolved to its accession; conflicting `accession` and `dataset_id` return `400`), `q`, `year`, `status`, `limit`, `offset`.

```json
{
  "data": {
    "publications": [
      {
        "publication_id": "pub_0c1b7d7e064074d9",
        "title": "A  Mechanistic Study of Soret Diffusion in Hydrogen-Air Flames",
        "title_variants": [],
        "authors": ["Yang Fan", "Law C.K", "Sung C.J", "Zhang Huiqiang"],
        "authors_raw": "Yang Fan, Law C.K., Sung C.J., Zhang Huiqiang",
        "authors_raw_variants": [],
        "author_parse": "source_comma_or_and_delimited",
        "doi": "10.2514/6.2009-988",
        "doi_url": "https://doi.org/10.2514/6.2009-988",
        "year": null,
        "venue": null,
        "status": "published",
        "related_investigations": [
          {
            "accession": "PSI-23",
            "title": "Advanced Combustion via Microgravity Experiments-Structure and Response of Spherical Diffusion Flames",
            "doi": "10.60555/k57n-p030",
            "acronym": "ACME s-Flame"
          }
        ],
        "source_references": [
          {
            "kind": "psi_investigation_registry",
            "path": "data/registry/psi_combustion_investigations.json",
            "accession": "PSI-23",
            "field": "publications"
          }
        ],
        "verification": {
          "status": "registry_verified",
          "source": "data/registry/psi_combustion_investigations.json",
          "snapshot_date": "2026-11-08",
          "verified_fields": ["title", "authors", "doi", "status"],
          "unavailable_fields": ["year", "venue"],
          "conflicts": {"title_variants": [], "authors_raw_variants": []}
        },
        "field_status": {
          "title": "source_provided",
          "authors": "source_provided",
          "doi": "source_provided",
          "year": "not_available_in_registry",
          "venue": "not_available_in_registry",
          "status": "source_provided"
        }
      }
    ],
    "page": {"limit": 50, "offset": 0, "total": 299, "has_more": true},
    "summary": {
      "publication_count": 299,
      "with_doi": 235,
      "without_doi": 64,
      "year_available": false,
      "venue_available": false,
      "note": "Year and venue are not present in the NASA PSI registry and are returned as unavailable."
    }
  }
}
```

Publication deduplication uses DOI when present, otherwise normalized title. Conflicts are preserved as `title_variants` and `authors_raw_variants`; they are never silently resolved. Missing year or venue is returned as `null` with an explicit `field_status`, never inferred from the DOI or title.

#### `GET /api/v1/publications/{publication_id}`

Returns one publication with the same shape as a list item. Unknown IDs return `404 not_found`.

### 4.9 Assistant

The assistant is a grounded layer over the Phase 1–4 artifacts. It works with
no LLM configured. An optional provider may only rephrase an already validated
deterministic draft; it never selects tools or creates citations.

#### `GET /api/v1/assistant/status`

Optional `include_index=true` loads the verified retrieval index and reports
its version. The response contains the contract version, enabled/mode/provider,
model, retrieval flag, fallback flag/reason, and allowlisted tool names. It
never contains a credential.

#### `GET /api/v1/assistant/suggestions?limit=9`

Returns up to nine curated questions from the versioned golden set. Each item
has `question_id`, `category`, `question`, and `answer_type_hint`. Suggestions
are prompts, not evidence.

#### `GET /api/v1/assistant/tools`

Returns the closed tool allowlist with name, description, category, and JSON
argument schema. Dangerous names such as `sql_query`, `read_file`, and
`fetch_url` do not exist.

#### `POST /api/v1/assistant/query`

**Request**

```json
{
  "question": "How many valid PSI-10 gas-flame records are available?",
  "conversation_id": null,
  "accession": null,
  "dataset_id": null,
  "include_retrieval": true,
  "max_tool_calls": 6
}
```

`question` is 1–1000 characters and may not be blank. `conversation_id` is
optional, bounded, non-authoritative memory. `max_tool_calls` is 1–12. Unknown
fields are rejected.

**Response `200`**

```json
{
  "data": {
    "contract_version": "1.0.0",
    "request_id": "req_...",
    "conversation_id": "conv_...",
    "answer": "PSI-10 has 256 valid included gas-flame records. 71 qualified rows are excluded by default, and the canonical table contains 327 rows in total.",
    "evidence_status": "fully_supported",
    "answer_type": "numerical",
    "citations": [
      {
        "citation_id": "cit_f_...",
        "citation_type": "file",
        "accession": "PSI-10",
        "dataset_ids": ["psi-10-gas-flame"],
        "file_name": "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
        "verification_status": "verified",
        "availability": "available",
        "downloadable": true,
        "resolved": true
      }
    ],
    "supporting_data": [],
    "claims": [],
    "limitations": [],
    "tools_used": [{"tool": "gas_flame_statistics", "status": "ok"}],
    "evidence": [],
    "confidence": "high",
    "confidence_basis": "The count comes from the canonical table and resolves to a verified source citation.",
    "dataset_version": "2a19f9f2...",
    "provider": "deterministic",
    "fallback_mode": false,
    "fallback_reason": null,
    "validation": {
      "passed": true,
      "citation_validation_passed": true,
      "claim_validation_passed": true
    },
    "generated_at": "2026-11-10T..."
  },
  "meta": {
    "request_id": "req_...",
    "dataset_version": "2a19f9f2...",
    "generated_at": "2026-11-10T...",
    "assistant_contract_version": "1.0.0",
    "conversation_id": "conv_...",
    "assistant_provider": "deterministic"
  },
  "provenance": [],
  "quality": {"status": "verified", "flags": []}
}
```

The abbreviated payload above omits empty details but does not change the
contract shape. The authoritative field list is in
`docs/assistant-answer-contract.md`.

**Rules**

- Every numerical claim comes from a deterministic allowlisted tool.
- Every citation resolves through `GET /api/v1/citations/{citation_id}`.
- Missing values are never zero; ambiguous units are never converted.
- Paired values are returned only when the registry confirms an alignment.
- Retrieved source text is untrusted evidence, never instructions.
- Validation failure withholds the draft instead of repairing it.
- `POST` responses are `Cache-Control: no-store`.
- Envelope `quality.status` is a transport summary derived from
  `data.evidence_status`; use the answer field for semantic meaning.

**Errors**

- `400 invalid_query` — invalid question or configuration limit.
- `422 validation_error` — schema violation or bounded field out of range.
- `429 rate_limited` — assistant rate limit.
- `500 internal_error` — unexpected failure; no secret or path is returned.

A provider failure is not a `503`. The API returns the deterministic answer
with `fallback_mode=true` and a safe `fallback_reason`.

---

## 5. Data contracts

### 5.1 Gas-flame test object

| Field | Type | Unit | Nullable | Notes |
|---|---|---|---|---|
| `observation_id` | string | — | no | Deterministic hash. |
| `accession` | string | — | no | `PSI-10` or `PSI-159`. |
| `table_id` | string | — | no | Source table. |
| `source_row` | integer | — | no | 1-based data row. |
| `flame_type` | category | — | no | Preserve source case. |
| `day` | string | — | yes | Source identifier. |
| `fuel` | string | — | yes | Source label. |
| `test_code` | string | — | yes | Source identifier. |
| `pressure_initial_atm` | float | atm | yes | PSI-10. |
| `pressure_final_atm` | float | atm | yes | PSI-10. |
| `pressure_mean_atm` | float | atm | yes | PSI-10. |
| `pressure_approx_bar` | float | bar | yes | PSI-159. |
| `oxygen_mole_fraction_initial` | float | mole fraction | yes | PSI-10. |
| `oxygen_mole_fraction_final` | float | mole fraction | yes | PSI-10. |
| `oxygen_mole_fraction_before` | float | mole fraction | yes | PSI-159. |
| `oxygen_mole_fraction_after` | float | mole fraction | yes | PSI-159. |
| `fuel_mole_fraction` | float | mole fraction | yes | PSI-10 `Xfuel`, PSI-159 `Xf`. |
| `fuel_mass_flow_mg_s` | float | mg/s | yes | PSI-10 `mfuel`, PSI-159 `mHC`. |
| `oxidizer_mass_flow_mg_s` | float | mg/s | yes | PSI-10 inverse `mO2`, PSI-159 `O2 flow rate`. |
| `diluent_mass_flow_mg_s` | float | mg/s | yes | `mN2`. |
| `total_mass_flow_mg_s` | float | mg/s | yes | `mtot`. |
| `stoich_mixture_fraction` | float | dimensionless | yes | Computed. |
| `adiabatic_flame_temp_k` | float | K | yes | Computed. |
| `hot_ignition` | category | — | yes | Preserve `Yes`/`No`/`yes`/`no`/`flash`. |
| `cool_flame_flag` | string | — | yes | Preserve PCI text. |
| `tfp_flag` | category | — | yes | `Yes`/`No`; not a temperature. |
| `burn_time_s` | float | s | yes | — |
| `extinction_mode` | category | — | yes | `SE`, `FT`, `-`. |
| `peak_burner_temp_c` | float | °C | yes | Measured. |
| `peak_burner_temp_k` | float | K | yes | Measured; do not derive from °C. |
| `color` | string | — | yes | Source description. |
| `comments` | string | — | yes | Untrusted free text. |
| `quality_flags` | array | — | no | Field/token flags. |

### 5.2 Telemetry series object

| Field | Type | Notes |
|---|---|---|
| `run_id` | string | Export identifier. |
| `time_unit` | category | `ms`. |
| `channels` | array | Raw name, canonical name, unit, quality flags. |
| `points` | array | One object per time step with requested channel keys. |
| `meta.returned_points` | integer | Actual count. |
| `meta.excluded_sentinel_rows` | integer | Sentinel rows removed from the series. |
| `meta.dataset_version` | string | Canonical version. |

No implicit interpolation, smoothing, or resampling. A future decimation method must be named in the response.

### 5.3 Comparison object

| Field | Type | Notes |
|---|---|---|
| `left`, `right` | object | Measurement metadata: ID, dataset, accession, family, quantity, unit, value kind, calibration, availability, comparison status, restrictions. |
| `status` | category | `comparable`, `conditionally_comparable`, `not_comparable`, `blocked`, `insufficient_metadata`. |
| `rule_id` | string or null | Committed comparability rule that produced the decision. |
| `reasons` | array | Stable code and message for the decision. |
| `required_conditions` | array | Condition key, description, and satisfaction state. |
| `scientific_justification` | string | Why the comparison is or is not valid. |
| `integrity` | object | Canonical-data presence checks, failures, and messages. |
| `paired_values` | object | Alignment, conditions, observations, series, exclusions, provenance, and a reason when unavailable. |
| `dataset_version` | string | Canonical version used for the decision. |

A comparison is not a correlation claim. The response must not include a correlation coefficient unless it was computed and its method, n, and uncertainty are documented. Paired observations are returned only when a verified alignment method exists; otherwise `paired_values.available` is `false` and `series` is empty.

---

## 6. Validation and blocking

The API serves a dataset version only after the Phase 1 gates pass. If a gate fails:

- the version is marked `blocked`;
- `GET /api/v1/datasets/{dataset_id}` returns a blocked serving state;
- data endpoints return `409 dataset_blocked`;
- the UI shows the last known good version with a stale badge, or an explicit error;
- the failure is logged with the source file, row, field, expected value, and actual value.

The API never serves partially validated data as `verified`. Blocked comparisons are decisions, not transport failures: `/compare` returns `200` with `data.status = "blocked"` and the reasons.

---

## 7. Security

- Public read-only role; no write endpoints and no authentication in the MVP.
- Rate limiting is an abuse control, not authentication.
- Allowlisted datasets, fields, channels, and concepts.
- Parameterized queries only.
- No arbitrary SQL, table names, file paths, or URLs.
- Request size limits and bounded time ranges.
- CORS allowlist per environment (`FLAME_CORS_ORIGINS`).
- Secrets injected at runtime; never in responses or logs.
- Free-text fields escaped in the UI and delimited in prompts.
- No directory traversal in provenance or file metadata endpoints.
- `source_url` values are generated from the accession and file name; they are not accepted from the client.
- Citation IDs are generated server-side; unknown or unverified files receive no fabricated checksum.

---

## 8. Testing contract

Phase 4 is complete when:

1. The OpenAPI schema validates.
2. Every endpoint has contract tests for success, empty, invalid, blocked, and rate-limited cases.
3. Pagination boundaries are tested.
4. Time-range limits return `413`, not a silent downsample.
5. Every data response includes provenance and quality flags.
6. Every numeric value includes a unit or `not stated`.
7. Unknown datasets, fields, channels, measurements, and publications return `404` or `400` with a stable code.
8. `TFP` is categorical in the schema and cannot be requested as a numeric temperature.
9. PSI-100 exports remain separate runs.
10. `experimental_table_only` datasets return their verified summary table with `quality.status = "experimental_table_only"`; records with no public artifacts return `quality.status = "not_available"`. Neither returns fabricated data.
11. Citation integrity tests confirm stable IDs, checksum linkage, row verification, and no download link for unavailable files.
12. Dataset field tests confirm canonical names, verified source columns, units, value kinds, missingness, and integrity alternatives.
13. Limitation tests confirm stable IDs, scopes, affected operations, evidence, and resolution status.
14. Publication tests confirm deduplication, DOI/title keys, preserved conflicts, and `null` year/venue with explicit field status.
15. Facet tests confirm counts come from canonical rows, qualified-row exclusion is reported, and PSI-10 atm / PSI-159 bar are never merged.
16. Comparison tests confirm the authoritative decision is used, invalid pairings return no series, and `paired_values.available=false` without a verified alignment.
17. Cache tests confirm ETag stability, `304` behavior, `no-store` on errors, and health exclusion.
18. Rate-limit tests confirm `429`, `Retry-After`, and rate headers.
19. The assistant golden set passes with 100% citation coverage for numeric claims, and every released citation resolves through the Phase 4 citation endpoint.
20. Assistant provider failures return the deterministic answer with `fallback_mode=true`; no secret, path, SQL, or arbitrary URL is exposed.

---

## 9. Open questions

Resolved in Phase 4:

1. **Dataset version format.** A 64-hex version derived from the canonical build is used; it is returned as `meta.dataset_version` and in provenance.
2. **Telemetry decimation.** The MVP returns `413` for oversized ranges. A future `minmax` method must document its bucket rule and point count.
3. **Authentication.** Not required for the public read-only MVP. Revisit if saved views or private annotations are added.
4. **Assistant exposure.** Implemented under `/api/v1/assistant` with a deterministic default and an optional rephrase-only provider. The catalog and explorers remain independent of it.
5. **Deployment URLs.** Not assigned. Do not hard-code a production host in the repository.
6. **Rate-limit values.** Defaults are 600 requests per 60 seconds per client; deployment may override them with environment variables.

---

## 10. Change control

Any change to this contract must:

1. update the OpenAPI schema and this document together;
2. add or update contract tests;
3. state whether the change is additive or breaking;
4. keep `v1` additive only; breaking changes go to `v2`;
5. preserve the provenance and quality envelope;
6. update the frontend client and its tests;
7. be reviewed by the data and frontend owners.

Do not add an endpoint that returns a value without a source citation.
