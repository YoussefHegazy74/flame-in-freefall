# API Documentation

**Project:** Flame in Freefall
**Team:** AFAQ
**API version:** `v1`
**Status:** Read-only Phase 2 implementation exists under `backend/`. This document remains the target contract; the implemented surface, exact paths, and known gaps are recorded in `docs/api-implementation.md`. Endpoints below that are not implemented are marked in §1.1.

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

### 1.1 Implementation status (Phase 2)

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
| `GET /api/v1/measurements` | Measurement registry with serving states. |
| `GET /api/v1/measurements/{measurement_id}` | One measurement, serving decision, rules. |
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
| `GET /api/v1/compare` | One comparison decision. |
| `GET /api/v1/provenance` | Source-file and optional row provenance. |

Known differences from the target contract below:

- The investigation catalog is `/investigations`, not `/datasets`; `/datasets` now means curated datasets.
- The material path is `/material/tests`, not `/materials/tests`.
- `/datasets/{accession}/files`, `/fields`, `/limitations`, `/publications`, `/gas-flame/facets`, `/citations/{citation_id}`, and assistant endpoints are **not implemented**.
- ETag/cache headers, rate limiting, and authentication are **not implemented**.
- A blocked or not-comparable decision is returned as HTTP `200` from `/compare`, with the decision in `data.status`.
- The implemented success envelope always includes `data`, `meta`, `provenance`, and `quality`; `quality.status` uses the five values listed in §3.6.

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
| `run_id` | `<accession>::<file stem>` | `PSI-100::PSI-100_Raw Data_Raw telemetry file` |
| `observation_id` | `sha256:<64 hex>` | `sha256:...` |
| `citation_id` | `cite_<stable hash>` | `cite_...` |
| `dataset_version` | Opaque version string | Assigned in Phase 2 |

Identifiers are opaque to clients. Do not parse them beyond the documented accession pattern.

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
| `meta.dataset_version` | string or null | Canonical dataset version for data-bearing responses. The Phase 2 service reports the committed canonical version; the target contract allows `null` for metadata-only responses. |
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
| 409 | `dataset_blocked` | Target-contract code; not emitted by the Phase 2 API. |
| 413 | `range_too_large` | Time range or page size exceeds the documented limit. |
| 422 | `validation_error` | Query or request validation failed. |
| 429 | `rate_limited` | Target-contract code; rate limiting is not implemented yet. |
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

- Metadata responses: `ETag` derived from the registry snapshot and resource path.
- Test queries: `ETag` derived from dataset version and filter hash.
- Telemetry series: `ETag` derived from run, channel set, and time range.
- `Cache-Control: public, max-age=300` for catalog metadata; `private, no-store` for assistant responses.
- Clients may send `If-None-Match`; the server returns `304` when unchanged.

### 3.11 Rate limits

The MVP uses per-IP limits. Exact values are set at deployment and documented in the release notes. The API returns:

```text
X-RateLimit-Limit: <n>
X-RateLimit-Remaining: <n>
X-RateLimit-Reset: <unix seconds>
Retry-After: <seconds>   (on 429)
```

The assistant endpoint has a stricter limit than the catalog.

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

### 4.2 Catalog

#### `GET /api/v1/datasets`

List the 24 combustion investigations.

**Query parameters**

| Parameter | Type | Description |
|---|---|---|
| `role` | category | `primary`, `supporting`, `future`, `context`, `unreviewed`. |
| `archive_status` | category | `available`, `experimental_table_only`, `no_public_files`. |
| `q` | string | Case-insensitive search over accession, acronym, and title. |
| `limit`, `offset` | integer | Pagination. |

**Response `200`**

```json
{
  "data": [
    {
      "accession": "PSI-159",
      "acronym": "ACME CFI-G",
      "title": "Advanced Combustion via Microgravity Experiments / Cool Flames Investigation with Gases",
      "doi": "10.60555/cyt1-kh64",
      "role": "primary",
      "archive_status": "available",
      "file_count": 3756,
      "experimental_table_count": 2,
      "experimental_table_only_count": 0,
      "registered_total_gb_decimal": 2085.59,
      "tabular_file_count": 2,
      "limitations_count": 9
    }
  ],
  "meta": {
    "page": {"limit": 50, "offset": 0, "total": 24, "has_more": false}
  }
}
```

`archive_status` is `available` when `file_count > 0`, `experimental_table_only` when `file_count == 0` and `experimental_table_count > 0`, and `no_public_files` when both are zero. `file_count` counts only `added` files; experimental tables are counted separately.

#### `GET /api/v1/datasets/{accession}`

Full record card.

**Response `200`**

```json
{
  "data": {
    "accession": "PSI-159",
    "acronym": "ACME CFI-G",
    "title": "Advanced Combustion via Microgravity Experiments / Cool Flames Investigation with Gases",
    "doi": "10.60555/cyt1-kh64",
    "research_area": "Combustion Science",
    "sub_research_area": "Flames of Gaseous Fuels",
    "project_type": "Microgravity Investigation",
    "start_date": null,
    "end_date": null,
    "version": 1,
    "public": true,
    "restricted": false,
    "file_count": 3756,
    "removed_file_count": 0,
    "experimental_table_count": 2,
    "experimental_table_only_count": 0,
    "archive_status": "available",
    "registered_total_bytes": 2085592429259,
    "registered_total_gb_decimal": 2085.59,
    "role": "primary",
    "rationale": "The largest gas-flame summary dataset in the combustion collection...",
    "limitations": [
      "The inverse CSV contains 861 trailing blank rows; 154 rows contain data...",
      "TFP is a categorical Yes/No field, not a numeric temperature..."
    ],
    "access_notes": "Both experimental tables and the ISA-Tab metadata package downloaded and inspected on 2026-11-08.",
    "experimental_tables": [],
    "publications": [],
    "files_url": "/api/v1/datasets/PSI-159/files"
  }
}
```

Values shown are illustrative of the schema. The API must return the exact registry values, not this abbreviated example.

**Errors**

- `404 not_found` — unknown accession.
- `503 service_unavailable` — registry unavailable.

#### `GET /api/v1/datasets/{accession}/files`

Paginated file manifest.

**Query parameters**

| Parameter | Type | Description |
|---|---|---|
| `format` | string | Extension such as `.csv`, `.xlsx`, `.zip`. |
| `category` | string | Source subcategory. |
| `access_status` | category | `available`, `listed_404`, `not_attempted`. |
| `limit`, `offset` | integer | Pagination. |

**Response `200`**

```json
{
  "data": [
    {
      "file_name": "PSI-159_Experimental table_CFI-G_Normal Flames.csv",
      "file_size_bytes": 22166,
      "format": ".csv",
      "category": "Experimental Data",
      "restricted": false,
      "visible": true,
      "version": 1,
      "sha256": "d95a621c3fbd27d204dd32ed29fa17d68f2b779d6a523cde8479ed7ebaa5251a",
      "retrieved_at": "2026-11-08T00:00:00Z",
      "access_status": "available"
    }
  ]
}
```

`sha256` is `null` until the file is downloaded and checked. This endpoint lists `added` archive files only. Experimental tables are returned through the dataset detail `experimental_tables` array, because a table may exist without being in `added`.

#### `GET /api/v1/datasets/{accession}/fields`

Field dictionary for the dataset's tabular artifacts.

**Response `200`**

```json
{
  "data": [
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
  ]
}
```

#### `GET /api/v1/datasets/{accession}/limitations`

Curated limitations, with source references where applicable.

```json
{
  "data": [
    {
      "limitation": "The Cool flame? column is blank in 171 of 179 normal-flame rows; blank must not be interpreted as 'no cool flame'.",
      "scope": "field",
      "field": "Cool flame?",
      "source": {
        "accession": "PSI-159",
        "file": "PSI-159_Experimental table_CFI-G_Normal Flames.csv"
      }
    }
  ]
}
```

#### `GET /api/v1/datasets/{accession}/publications`

Publication metadata attached to the PSI record.

```json
{
  "data": [
    {
      "title": "Cool flames in microgravity...",
      "doi": "10.0000/example",
      "author_list": "...",
      "status": "Published"
    }
  ]
}
```

The API returns only publications present in the PSI detail record. It does not invent missing bibliographic fields.

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

#### `GET /api/v1/materials/tests`

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

Returns the machine-readable comparability matrix.

```json
{
  "data": {
    "fields": [
      {
        "concept": "oxygen_mole_fraction",
        "datasets": ["PSI-10", "PSI-159"],
        "compatible": true,
        "unit": "mole fraction",
        "conversion": "none",
        "notes": "Both are mole fractions. Percent by volume requires an explicit x100 conversion."
      },
      {
        "concept": "flame_spread_rate",
        "datasets": ["PSI-25", "PSI-26"],
        "compatible": false,
        "reason": "No processed spread-rate table was identified in the public PSI record."
      }
    ]
  }
}
```

#### `GET /api/v1/compare`

Curated comparison only. The request names a concept, not arbitrary columns.

**Query parameters**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `concept` | string | Yes | Allowlisted concept such as `oxygen_mole_fraction` or `adiabatic_flame_temp_k`. |
| `datasets` | comma-separated string | Yes | Two or more allowlisted accessions. |
| `filters` | JSON string | No | Allowlisted filters per dataset. |

**Response `200`**

```json
{
  "data": {
    "concept": "oxygen_mole_fraction",
    "unit": "mole fraction",
    "series": [
      {
        "accession": "PSI-10",
        "field": "XO2 (init)",
        "n": 207,
        "missing": 0,
        "values": [0.207128374]
      },
      {
        "accession": "PSI-159",
        "field": " XO2 before test",
        "n": 179,
        "missing": 0,
        "values": [0.3939]
      }
    ],
    "method": "Raw source values, no aggregation, no interpolation.",
    "limitations": [
      "PSI-10 and PSI-159 test different fuels and burner configurations; a shared axis is not a causal comparison."
    ]
  }
}
```

**Errors**

- `400 invalid_query` — concept not allowlisted, incompatible datasets, or a filter not allowed for the concept.
- `409 dataset_blocked` — one dataset failed validation.

### 4.8 Provenance and citations

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
    "source_url": "https://psi.nasa.gov/geode-py/ws/studies/PSI-159/download?file=..."
  }
}
```

#### `GET /api/v1/citations/{citation_id}`

```json
{
  "data": {
    "citation_id": "cite_...",
    "kind": "dataset",
    "accession": "PSI-159",
    "title": "Advanced Combustion via Microgravity Experiments / Cool Flames Investigation with Gases",
    "doi": "10.60555/cyt1-kh64",
    "url": "https://psi.nasa.gov/physci/repo/data/investigations/PSI-159",
    "retrieved_at": "2026-11-08T00:00:00Z"
  }
}
```

### 4.9 Assistant (optional)

The assistant is optional. The core catalog and explorers must work without it.

#### `POST /api/v1/assistant/query`

**Request**

```json
{
  "question": "Which PSI-159 normal flames used ethane and hot ignition?",
  "max_citations": 10
}
```

**Response `200`**

```json
{
  "data": {
    "answer": "PSI-159 normal-flame rows include ethane tests with hot ignition. The exact count and rows are cited below.",
    "evidence_status": "measured",
    "citations": [
      {
        "accession": "PSI-159",
        "file": "PSI-159_Experimental table_CFI-G_Normal Flames.csv",
        "field": "Fuel, Hot ignition",
        "rows": [1],
        "sha256": "d95a621c3fbd27d204dd32ed29fa17d68f2b779d6a523cde8479ed7ebaa5251a"
      }
    ],
    "limitations": [
      "The Cool flame? field is blank in 171 of 179 normal-flame rows; blank is not 'no'."
    ],
    "method": "Filtered PSI-159 normal-flame rows where Fuel = 'ethane' and Hot ignition = 'Yes'.",
    "tool_calls": [
      {"tool": "query_gas_flame_tests", "status": "ok"}
    ]
  },
  "meta": {
    "dataset_version": "assigned-in-phase-2",
    "model": "provider/model-or-null"
  }
}
```

**Rules**

- Every numeric claim must have a citation.
- `evidence_status` is `measured`, `computed`, `derived`, or `not_available`.
- The answer must include limitations relevant to the data.
- Datasets with no raw archive but a public experimental table return `quality.status = "experimental_table_only"` and only the verified summary table; they never return fabricated values.
- Free-text comments are delimited and never treated as instructions.
- If the LLM is unavailable, the endpoint returns `503 service_unavailable` and the UI falls back to deterministic search. It does not return a model-memory answer.

**Errors**

- `400 invalid_query` — empty or oversized question.
- `429 rate_limited` — assistant rate limit.
- `503 service_unavailable` — LLM or tool backend unavailable.

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
| `concept` | string | Allowlisted concept. |
| `unit` | string | Shared unit after explicit conversion. |
| `series` | array | Per-dataset field, n, missing, values. |
| `method` | string | Exact operation. |
| `limitations` | array | Why the comparison is or is not causal. |

A comparison is not a correlation claim. The response must not include a correlation coefficient unless it was computed and its method, n, and uncertainty are documented.

---

## 6. Validation and blocking

The API serves a dataset version only after the Phase 2 gates pass. If a gate fails:

- the version is marked `blocked`;
- `GET /api/v1/datasets/{accession}` returns `quality.status = "blocked"`;
- data endpoints return `409 dataset_blocked`;
- the UI shows the last known good version with a stale badge, or an explicit error;
- the failure is logged with the source file, row, field, expected value, and actual value.

The API never serves partially validated data as `verified`.

---

## 7. Security

- Public read-only role; no write endpoints.
- Allowlisted datasets, fields, channels, and concepts.
- Parameterized queries only.
- No arbitrary SQL, table names, file paths, or URLs.
- Request size limits and bounded time ranges.
- CORS allowlist per environment.
- Rate limiting per IP; stricter for the assistant.
- Secrets injected at runtime; never in responses or logs.
- Free-text fields escaped in the UI and delimited in prompts.
- No directory traversal in provenance or file metadata endpoints.
- `source_url` values are generated from the accession and file name; they are not accepted from the client.

---

## 8. Testing contract

Phase 3 is complete when:

1. The OpenAPI schema validates.
2. Every endpoint has contract tests for success, empty, invalid, blocked, and rate-limited cases.
3. Pagination boundaries are tested.
4. Time-range limits return `413`, not a silent downsample.
5. Every data response includes provenance and quality flags.
6. Every numeric value includes a unit or `not stated`.
7. Unknown datasets, fields, channels, and concepts return `404` or `400` with a stable code.
8. `TFP` is categorical in the schema and cannot be requested as a numeric temperature.
9. PSI-100 exports remain separate runs.
10. `experimental_table_only` datasets return their verified summary table with `quality.status = "experimental_table_only"`; records with no public artifacts return `quality.status = "not_available"`. Neither returns fabricated data.
11. The assistant golden set passes with 100% citation coverage for numeric claims.

---

## 9. Open questions

These are unresolved until Phase 2/3:

1. **Dataset version format.** Proposed: `sha256` prefix over sorted source checksums plus parser/schema/config versions. Confirm before publishing.
2. **Telemetry decimation.** The MVP returns `413` for oversized ranges. If a `minmax` method is added, its bucket rule and point count must be documented and tested.
3. **Authentication.** Not required for the public read-only MVP. Revisit if saved views or private annotations are added.
4. **Assistant exposure.** The assistant may be internal-only for the demo. The public API contract is written so it can be disabled without breaking the catalog.
5. **Deployment URLs.** Not assigned. Do not hard-code a production host in the repository.
6. **Rate-limit values.** Set at deployment based on capacity; document in release notes.

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
