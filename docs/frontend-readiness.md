# Frontend Readiness

**Project:** Flame in Freefall
**Team:** AFAQ
**Status:** Implemented in Phase 4. The frontend described here exists in `frontend/`; this document remains the backend contract and state-handling reference.
**API:** `v1`, read-only, FastAPI

This document tells the frontend team what the API guarantees, which states must be visible, and what must not be inferred in the browser. See `frontend/README.md` for the implemented architecture, routes, and test commands.

---

## 1. What is ready

| Capability | Endpoint |
|---|---|
| Investigation catalog | `GET /api/v1/investigations`, `/investigations/{accession}` |
| Curated dataset registry | `GET /api/v1/datasets`, `/datasets/{dataset_id}` |
| Dataset quality | `GET /api/v1/datasets/quality`, `/datasets/{dataset_id}/quality` |
| Measurement registry | `GET /api/v1/measurements`, `/measurements/{measurement_id}` |
| Gas-flame rows | `GET /api/v1/gas-flame/tests`, `/gas-flame/tests/{observation_id}` |
| Material matrices | `GET /api/v1/material/tests` |
| Droplet summary | `GET /api/v1/droplet/tests` |
| SAFFIRE-III telemetry | `GET /api/v1/telemetry/runs`, `/runs/{run_id}`, `/runs/{run_id}/series` |
| SAME-R smoke | `GET /api/v1/smoke/runs`, `/runs/{run_id}`, `/runs/{run_id}/series` |
| Comparability | `GET /api/v1/comparability`, `/compare` |
| Comparison integrity and paired eligibility | Included in `GET /api/v1/compare` as `integrity` and `paired_values` |
| Citations | `GET /api/v1/citations`, `/citations/{citation_id}` |
| Dataset files | `GET /api/v1/datasets/{dataset_id}/files` |
| Dataset fields | `GET /api/v1/datasets/{dataset_id}/fields` |
| Dataset limitations | `GET /api/v1/datasets/{dataset_id}/limitations` |
| Publications | `GET /api/v1/publications`, `/publications/{publication_id}` |
| Gas-flame facets | `GET /api/v1/gas-flame/facets` |
| Provenance | `GET /api/v1/provenance` |

Every success response has `data`, `meta`, `provenance`, and `quality`. Every list has `meta.page`. Every series has a bounded time range and a point cap. Dataset file, field, limitation, citation, publication, facet, and comparison-integrity contracts are documented in `docs/phase4-contracts.md` and `docs/comparison-alignment.md`.

---

## 2. State handling

The UI must render the API state, not derive its own.

### Serving state

| State | UI treatment |
|---|---|
| `available` | Normal presentation. Still show provenance. |
| `available_with_warnings` | Show a visible warning badge and the API warnings. |
| `restricted` | Show a restriction badge and the approved use. Do not present as comparison-ready. |
| `blocked` | Disable the data view for that use and show the reason. Do not render an empty chart that looks like zero. |
| `metadata_only` | Show metadata and source references only. If an experimental table exists, label it `experimental_table_only`. |

### Quality status

| `quality.status` | UI treatment |
|---|---|
| `verified` | Normal. |
| `partial` | Show warnings. |
| `blocked` | Show the block reason; no numeric comparison. |
| `experimental_table_only` | Show the verified summary table with a badge. |
| `not_available` | Show "No public measurement data"; no chart. |

### Comparability

`/compare` returns `200` for every state. The UI must branch on `data.status`:

- `comparable`: enable the comparison view with conditions shown as verified.
- `conditionally_comparable`: show the required conditions and ask the user to confirm each one.
- `not_comparable`, `blocked`, `insufficient_metadata`: show the decision and reasons; do not plot a shared axis.

Never treat a non-200 transport error as the only blocked state. The scientific decision is in the payload.

### File availability

| File state | UI treatment |
|---|---|
| `available` + `downloadable: true` | Show the source link and checksum. |
| `unavailable` + `downloadable: false` | Show "Unavailable" with `availability_reason`, HTTP status, and verification evidence. Do not render a download link. |
| `known_unavailable` | Show the documented 404 or access limitation. Never substitute another file. |
| Missing checksum | Show `checksum_not_available`; do not invent a digest. |

PSI-98's two telemetry/sensor XLSX files are the canonical example: they are listed in the curated record but return HTTP 404, so they remain unavailable and non-downloadable.

### Field integrity

| `integrity.status` | UI treatment |
|---|---|
| `available` | Normal field metadata. |
| `missing` | Show that the registry field has no canonical values and name any `alternatives`. Do not convert or merge units. |
| `not_checked` | Show "presence not checked" and the reason. |
| `no_canonical_tables` | Show that the dataset has no canonical tables, such as PSI-98 metadata-only. |

A missing registry field must never be rendered as a zero-valued series.

### Publications

- Render only fields with `field_status: "source_provided"`.
- Year and venue are `null` with `field_status: "not_available_in_registry"`; display "Not available in registry", not an inferred year or venue.
- Preserve `title_variants` and `authors_raw_variants` when the source records conflict. Do not silently choose one.

### Paired comparison values

`paired_values.available` is authoritative. Render a chart only when all of the following hold:

1. `available` is `true`.
2. `alignment.verified` is `true`.
3. `observations` or `series` contain numeric points with matching left/right units.

When `available` is `false`, show `reason.code` and `reason.message`, the required alignment keys, and any exclusions. Do not derive a series from separate summaries, interpolate, pair by row number, or convert units. Current reasons include `conditions_not_verified`, `no_verified_alignment`, `comparison_not_approved`, and `measurement_unavailable`.

### Citations

- File citations use stable `cit_f_<hex>` IDs; row citations use `cit_r_<base64url>` IDs.
- Treat IDs as opaque and resolve them through `/citations/{citation_id}`.
- Show accession, file, sheet, row/range, SHA-256 when present, retrieval date, and source URL.
- A row citation includes `row_verification`; show whether the row was found in a canonical table.
- Never construct a citation from a filename or row number on the client.

---

## 3. Chart and table rules

1. Every chart has a title, x-axis unit, y-axis unit, accession, and provenance link.
2. Do not use dual y-axes. Use stacked panels for different units.
3. Do not interpolate, smooth, bin, or aggregate without a visible method note.
4. Do not compute a scientific aggregate in the browser. Use API values.
5. Do not convert units in the browser. If the API does not provide a converted value, show the labeled unit.
6. Do not label `Tad` or `Zst` as measured. They are computed by the source.
7. Do not draw a flame-spread rate for PSI-25, PSI-26, PSI-100, or PSI-101.
8. Do not treat `TFP`, fuel labels, or extinction modes as numeric.
9. Do not treat PSI-26 `o2_pct` as a percent just because the header says percent.
10. Do not concatenate PSI-100 telemetry runs or PSI-101 HKP runs.
11. Show sentinel and missingness counts that the API returns.
12. Show the dataset version and registry snapshot from `meta`.
13. Observation row endpoints return canonical field names. Numeric names encode their unit (`pressure_initial_atm`, `adiabatic_flame_temp_k`, `burning_rate_mm_as_labeled`) or are documented in `DATA_DICTIONARY.md`. For registry-level `unit` and `unit_status`, use `/api/v1/measurements`. If no unit is documented, display `not stated`; do not infer one.

---

## 4. Telemetry and smoke series

Request shape:

```text
GET /api/v1/telemetry/runs/{run_id}/series
  ?channels=pcm_air_temp_c
  &start_ms=0
  &end_ms=100000
  &max_points=5000
```

```text
GET /api/v1/smoke/runs/{run_id}/series
  ?channels=gas_plume_temp_c
  &start_s=79
  &end_s=400
  &max_points=5000
```

The API returns `413 range_too_large` with `actual_points` and a suggested narrower span when the range is too dense. The frontend should catch this, narrow the range, and tell the user. It must not silently downsample.

Channel metadata in the run detail response includes `unit` and `quality_flags`. Use those labels directly. A channel with `uncalibrated` is not a physical measurement.

---

## 5. Provenance and citation drawer

Row-level responses include `provenance` entries with:

- `accession`
- `file`
- `sheet`
- `rows` or `row_range`
- `sha256`
- `retrieved_at`
- `source_url`
- `citation_id`
- `file_citation_id`
- `row_citation_ids`

The drawer should show these values and link to the source URL. Use `GET /api/v1/provenance?accession=...&file=...&row=...` to verify a row. Use `GET /api/v1/citations/{citation_id}` to resolve a file or row citation. A missing checksum is reported as `checksum_not_available`; show that warning rather than hiding it.

Citation IDs are deterministic but opaque. The client must not parse `cit_r_` payloads or construct a row citation from an accession, file, and row number.

---

## 6. Environment, cache, and rate limits

The API allows these origins by default:

```text
http://localhost:3000
http://localhost:5173
```

Override with a comma-separated `FLAME_CORS_ORIGINS`. Credentials are disabled. The frontend sends no cookies. The API is public and read-only with no authentication; rate limiting is an abuse control, not authentication.

Cache behavior:

- Success responses include `ETag` and `Cache-Control`.
- Default cache control is `public, max-age=60, must-revalidate`.
- Conditional requests with `If-None-Match` return `304`.
- Error responses use `Cache-Control: no-store`.
- Health responses are excluded from ETag generation.

Rate limiting:

- Default is 600 requests per 60 seconds per client, process-local.
- `429` includes `Retry-After`.
- Configure with `FLAME_RATE_LIMIT_ENABLED`, `FLAME_RATE_LIMIT_REQUESTS`, `FLAME_RATE_LIMIT_WINDOW_SECONDS`, and `FLAME_TRUST_PROXY`.

`X-Request-ID` is exposed. Log it for client-side error reports. The backend logs structured request records with `request_id`, `method`, `path`, `status`, and `duration_ms`.

---

## 7. What the frontend must not assume

- There is no authentication. The API is public and read-only.
- Rate limiting exists but is not an authorization mechanism.
- There is no assistant endpoint; Phase 5 is not implemented.
- There is no verified paired-comparison executor. `/compare` may return eligibility, but `paired_values.available` is currently false.
- There is no full public-file inventory in the file browser. It exposes the curated manifest plus documented known-unavailable files, with inventory counts for context.
- The material path is `/material/tests`, not `/materials/tests`.
- The API does not expose arbitrary SQL, paths, or table names.
- The API does not return raw NASA files.
- The API does not compute new scientific aggregates beyond what the service exposes.
- The consolidated scientific and API limitations are in `docs/known-limitations.md`; read them before designing a comparison or quality screen.

---

## 8. Implemented page and component structure

This section started as a handoff proposal. It is retained for contract context; the implemented app uses the route names below and the components listed in `frontend/README.md`.

### 8.1 Pages

| Route | Purpose | Primary API calls |
|---|---|---|
| `/` | Overview: nine curated datasets, state summary, quality counts. | `/meta`, `/datasets`, `/datasets/quality`, `/measurements` |
| `/investigations` | NASA PSI catalog with role and text search. | `/investigations` |
| `/investigations/[accession]` | Investigation detail and curated datasets. | `/investigations/{accession}` |
| `/datasets` | Curated dataset catalog with role and access badges. | `/datasets` |
| `/datasets/[dataset_id]` | Four use-specific states, files, fields, limitations, publications. | `/datasets/{dataset_id}`, `/files`, `/fields`, `/limitations` |
| `/experiments/gas-flame` | PSI-10/PSI-159 row explorer with dynamic facets and filters. | `/gas-flame/tests`, `/gas-flame/facets` |
| `/experiments/materials` | PSI-25/PSI-26 matrices with unit warnings. | `/material/tests` |
| `/experiments/droplets` | PSI-69 droplet summary. | `/droplet/tests` |
| `/telemetry` | PSI-100 run and bounded series explorer. | `/telemetry/runs`, `/telemetry/runs/{run_id}/series` |
| `/smoke` | PSI-101 run and bounded series explorer. | `/smoke/runs`, `/smoke/runs/{run_id}/series` |
| `/compare` | Measurement picker, conditions, decision, integrity, paired eligibility. | `/measurements`, `/comparability`, `/compare` |
| `/quality` | Data-quality center across datasets. | `/datasets/quality`, `/datasets/{dataset_id}/quality`, `/datasets/{dataset_id}/limitations` |
| `/provenance` | Exact source-file and row resolution with citations. | `/provenance`, `/citations/{citation_id}` |
| `/publications` | Verified publication list with filters. | `/publications` |
| `/publications/[publication_id]` | Publication detail with source references. | `/publications/{publication_id}` |
| `/about` | Comparability, serving, limitations, sources. | Static docs plus registry metadata |

### 8.2 Components

| Component | Responsibility |
|---|---|
| `StateBadge` | Render the five serving states and five comparability states with the API's labels and reasons. |
| `QualityBanner` | Render `quality.status`, flags, and warnings without reinterpretation. |
| `RestrictionNotice` | Render `restricted` and `blocked` decisions with their reason codes. |
| `ProvenanceDrawer` | Show accession, file, sheet, row or row range, SHA-256, retrieval time, and source URL. |
| `UnitLabel` | Show the unit from the measurement registry or channel profile; show `not stated` when absent. |
| `BoundedSeriesChart` | Plot one bounded series; handle `413` by asking for a narrower range. |
| `ComputedFieldTag` | Mark `Tad` and `Zst` as computed. |
| `ConditionChecklist` | Collect the named conditions required by a `conditionally_comparable` decision. |
| `DecisionPanel` | Show the comparison state, reasons, required conditions, and scientific justification. |
| `DatasetCard` | Show dataset name, accession, family, measurement count, and use-specific state. |
| `EmptyState` | Distinguish `metadata_only`, `blocked`, and genuinely empty results. |
| `CitationDrawer` | Resolve and show file or row citation details, checksum, retrieval date, and source URL. |
| `DatasetFilesPanel` | Render curated files, availability, checksum, and download status without exposing paths. |
| `DatasetFieldsPanel` | Render canonical fields, units, value kinds, calibration, missingness, integrity, and alternatives. |
| `DatasetLimitationsPanel` | Render scoped limitations, severity, affected operations, evidence, and resolution status. |
| `PublicationsPanel` | Render verified publication metadata and preserve conflicts. |
| `GasFlameFacetsPanel` | Render backend facet counts, exclusions, and accession-specific units. |
| `ComparisonIntegrityPanel` | Render canonical-presence checks and block misleading comparisons. |
| `PairedValuesPanel` | Render eligibility, alignment requirements, exclusions, and the withholding reason. |
| `PairedScatterChart` | Render only a complete verified paired contract; lazy-loaded and unit-guarded. |

### 8.3 Client rules

1. Generate request and response types from `/api/v1/openapi.json`; do not hand-maintain a divergent schema.
2. Keep scientific decisions server-side. The client renders `data.status`, `quality.status`, reasons, and warnings; it does not recompute them.
3. Keep units and value kinds server-side. The client does not convert units or promote a computed value to measured.
4. Centralize fetch handling for the error envelope, `X-Request-ID`, `429 Retry-After`, and `413 range_too_large`.
5. Never concatenate runs or draw a flame-spread series for a dataset that the API marks unavailable for it.
6. Resolve citation IDs through the API; do not parse or construct them in the browser.
7. Draw a paired chart only when `paired_values.available`, `alignment.verified`, and numeric points all pass the client guard.

---

## 9. Verification checklist for frontend integration

- [x] The app reads `quality.status` and `data.status` instead of inventing badges.
- [x] Blocked datasets show a reason, not an empty chart.
- [x] Metadata-only datasets show no numeric series.
- [x] Series requests use bounded ranges and handle `413`.
- [x] Charts show units and provenance.
- [x] No browser-side scientific aggregation or unit conversion.
- [x] No flame-spread chart for BASS/BASS-II, SAME/SAME-R, or telemetry.
- [x] Citations resolve to accession, file, sheet, row/range, checksum, and retrieval date.
- [x] Unavailable files are never downloadable.
- [x] Missing registry fields are not rendered as zero.
- [x] Facets preserve accession-specific pressure units.
- [x] Paired charts render only for a complete verified contract.
- [ ] `429` and `Retry-After` have dedicated UI. The client currently shows the generic error envelope and does not retry automatically; a rate-limit-specific message is still open.
- [ ] CORS origin is configured for the deployed frontend. (Local development is configured; no deployment exists yet.)
- [x] Request IDs appear in client error reports.

The Playwright suite exercises the scientific-state checklist against the real backend. See `frontend/e2e/app.spec.ts` and `frontend/e2e/accessibility.spec.ts`.
