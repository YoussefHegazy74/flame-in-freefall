# Development Roadmap

**Project:** Flame in Freefall
**Team:** AFAQ
**Challenge:** Flame in Freefall: SI-Powered Fire Safety Insights from Microgravity Combustion Data
**Status date:** 2026-11-10

This roadmap is sequenced by dependency, not by calendar. It does not assume a competition deadline, a team size, or a deployment budget. Each phase has an exit gate; a phase is not "done" because a demo works, but because its acceptance criteria and tests pass.

The guiding rule is simple: **science first, interface second, AI last.** A chart or an answer is only as trustworthy as the parser and the provenance beneath it.

---

## 1. Status legend

| Status | Meaning |
|---|---|
| **Done** | Implemented, verified, and committed. |
| **In progress** | Work has started but the exit gate is not met. |
| **Planned** | Not started; depends on an earlier phase. |
| **Blocked** | Cannot proceed without a source, access, or decision. |
| **Deferred** | Explicitly out of the MVP; may return later. |

---

## 2. Phase overview

| Phase | Name | Status | Exit gate |
|---|---|---|---|
| 0 | Scientific foundation and metadata registry | **Complete** (commit `b927bac`, pushed to `origin/main`) | Registry validates against live PSI; docs agree; initialization commit pushed |
| 1 | Data acquisition and parser foundation | **Complete** (2026-11-09) | MVP files downloaded, checksummed, parsed, and tested on fixtures |
| 2 | Scientific validation and canonical data | **Complete** (2026-11-09) | Canonical tables pass data-quality gates; units and limitations resolved or labeled |
| 3 | Read-only API | **Complete** (2026-11-10) | OpenAPI contract, provenance, pagination, cache, rate limiting, and contract tests pass |
| 4 | Frontend exploration experience | **Complete** (2026-11-10) | Catalog, test explorer, telemetry/smoke views, citations, accessibility pass |
| 5 | Grounded insight layer | **Complete** (2026-11-10) | Golden-set evaluation passes; numeric claims are 100% cited |
| 6 | Hardening and deployment | **Complete** (2026-11-10) | Deployment, CI/CD, monitoring, security review, performance baseline, backups, and runbook verified; live-model evaluation pending credentials |
| 7 | Future extensions | Deferred | Separate decision record and validation plan |

---

## 3. Phase 0 — Scientific foundation and metadata registry

### 3.1 Goal

Establish a verified, reproducible inventory of NASA PSI combustion data and the scientific rules for using it. Do not build a frontend on unverified data.

### 3.2 Deliverables

- [x] Verify the NASA PSI API and the 24 combustion investigations.
- [x] Verify the detail and download endpoints.
- [x] Inventory 16,354 current `added` files, 22 experimental tables, and 13,496.77 GB registered total.
- [x] Record `experimental_table_only` records: PSI-22, PSI-68, PSI-69, PSI-99. No record is `no_public_files`.
- [x] Download and inspect all 22 experimental tables; record exact headers, row counts, missingness, and checksums.
- [x] Record listed-but-404 files: SAFFIRE-I telemetry/sensor XLSX; sampled CFI `.metadata`.
- [x] Download and inspect the MVP summary tables, telemetry samples, readmes, and metadata packages.
- [x] Record exact headers, row counts, missingness, sentinels, and checksums.
- [x] Write `scripts/fetch_psi_metadata.py` with `--check` and `experimentalTable` support.
- [x] Write `scripts/build_mvp_catalog.py` with `--check`.
- [x] Write `data/registry/annotations.json`.
- [x] Generate `data/registry/psi_combustion_investigations.json`, `data/registry/psi_file_inventory.csv`, and `data/registry/psi_experimental_tables.csv`.
- [x] Write `DATA_SOURCES.md`.
- [x] Write `DATA_DICTIONARY.md`.
- [x] Write `PROJECT_ARCHITECTURE.md`.
- [x] Write `DEVELOPMENT_ROADMAP.md`.
- [x] Write `README.md`, `AGENTS.md`, `API_DOCUMENTATION.md`, `CONTRIBUTING.md`, `.env.example`, `.gitignore`.
- [x] Write `data/registry/mvp_dataset_catalog.json`, `data/registry/README.md`, `scripts/README.md`.
- [x] Write `docs/research/source-verification-log.md` and `docs/decisions/0001-mvp-dataset-selection.md`.
- [x] Run `python scripts/fetch_psi_metadata.py --check` and `python scripts/build_mvp_catalog.py --check`.
- [x] Commit and push the initialization milestone; verify the remote SHA.

### 3.3 Acceptance criteria

1. The collector returns 24 combustion investigations from the live PSI API.
2. The committed snapshot has 16,354 files and 13,496.77 GB registered total.
3. `--check` reports no drift, or reports every drift with accession and field.
4. Every primary/supporting/future/context role is justified in `annotations.json` or the selection ADR. The `inaccessible` role is retired; records with no `added` files but a public experimental table are `experimental_table_only`.
5. Every checksum in `DATA_SOURCES.md` matches `annotations.json` and the generated registry.
6. `DATA_DICTIONARY.md` covers every field used by the MVP.
7. No raw NASA data, credentials, or `.env` file is committed.
8. The initialization commit is on `origin/main`; the remote SHA matches the local SHA.

### 3.4 Tests

- Run the collector with `--details-dir` against the cached detail JSON and compare the output with the committed snapshot.
- Run the collector with `--check` against the live API.
- Validate JSON syntax for all registry files.
- Verify the inventory row count equals the sum of `file_count`.
- Verify the total bytes equals the sum of `registered_total_bytes`.
- Verify no `.env`, raw data, or credential file is tracked.

---

## 4. Phase 1 — Data acquisition and parser foundation

**Status:** Complete (2026-11-09). See §4.6 for the verified result.

### 4.1 Goal

Turn the verified metadata into reproducible, checksummed, parsed source tables. Do not build charts yet.

### 4.2 Workstreams

#### 4.2.1 Download manifest

- [x] Define `data/registry/download_manifest.json` with the exact MVP files.
- [x] Include accession, file name, expected bytes, source URL, and intended use.
- [x] Exclude files known to return 404. Include `experimental_table_only` summary tables only within their documented limits; do not fabricate a replacement archive.
- [x] Record access status for every selected file.

#### 4.2.2 Downloader

- [x] Implement `scripts/download_psi_files.py` and `src/data_pipeline/downloader.py` with the standard library.
- [x] Stream downloads to `data/raw/<accession>/<file_name>`.
- [x] Verify HTTP status, content length when available, and SHA-256.
- [x] Write a checksum manifest with retrieval timestamps.
- [x] Support resume and rate limiting.
- [x] Never bypass authentication or access controls.
- [x] Record `listed_404` instead of failing silently.

#### 4.2.3 Parsers

- [x] CSV parser with exact-header validation.
- [x] XLSX parser using `openpyxl`; sheet selection by name.
- [x] XLS parser using `xlrd`.
- [x] PSI-10 normal/inverse parser.
- [x] PSI-159 normal/inverse parser.
- [x] PSI-100 raw/cleaned CSV parser.
- [x] PSI-100 XLSX sheet parser for `RawData`, `SaffireData`, and `CygnusData`. Chart-only sheets with nested headers or dummy data are documented and not parsed.
- [x] PSI-101 HKP CSV parser.
- [x] PSI-25 BASS-II workbook parser.
- [x] PSI-26 BASS experimental table and as-run workbook parser.
- [x] PSI-20, PSI-21, PSI-106, PSI-142 small tables through the generic summary-table parser; all 22 experimental tables are preserved cell-by-cell.
- [x] Emit provenance for every row.
- [x] Classify every missing/sentinel token.

#### 4.2.4 Fixtures

- [x] Commit small fixtures with exact headers and 3–4 rows.
- [x] Cover the parser-critical tokens with authentic excerpts: blank, dash, `RAMPED`, `#VALUE!`, `-999`, `-1.#IND`, cp1252 en dash, and a negative sentinel timestamp. Token-level tests cover the full sentinel vocabulary.
- [x] Do not commit full raw files or video.

#### 4.2.5 Canonical Parquet and reports

- [x] Build 13 canonical Parquet tables with explicit Arrow schemas, primary keys, and row-level provenance.
- [x] Generate `data/registry/canonical_schema.json`.
- [x] Generate `data/reports/acquisition_report.json`, `validation_report.json`, `dataset_quality_report.json`, and `processing_report.json`.
- [x] Generate `data/manifests/download_manifest.csv` and `data/processed/dataset_manifest.json`.
- [x] Evaluate DuckDB for local duplicate-primary-key checks; keep a pyarrow fallback so the pipeline does not depend on DuckDB being installed.

### 4.3 Acceptance criteria

1. [x] Every selected MVP file downloads successfully or is explicitly marked `listed_404`.
2. [x] Every downloaded file has a SHA-256 and a retrieval timestamp.
3. [x] Parsers fail on unexpected headers; they do not guess.
4. [x] Every parser has fixture tests for normal, missing, sentinel, and malformed rows.
5. [x] Parsed row counts match the committed table statistics, or the difference is explained.
6. [x] No parser writes to `data/raw/`.
7. [x] A clean checkout can reproduce the parsed interim tables from the manifest and raw files.

### 4.4 Tests

- [x] Unit tests for header validation and sentinel classification.
- [x] Fixture tests for each parser.
- [x] Checksum tests for each downloaded file.
- [x] A negative test that an unexpected header raises a typed error.
- [x] A negative test that a sentinel is not coerced to zero.
- [x] Full unit and integration suites pass.

### 4.5 Known blockers

- `gh` is unavailable in the environment; pushes must use the configured Git credential and the remote SHA must be verified separately.
- `www.spaceappschallenge.org` is not reachable from the environment, so the public AFAQ roster cannot be verified. Do not invent team members.
- PSI-98 SAFFIRE-I telemetry and sensor XLSX files are listed but return HTTP 404. Sampled PSI-39 `.metadata` also returns 404.
- PSI-159 `TFP` and `Xf` remain unexpanded by the source. They stay categorical/undefined until a source document confirms their meaning.
- PSI-26 `O2 % by volume` values are around 0.22 while the header says percent; they are stored as `o2_pct` and flagged `unit_ambiguity`, not relabeled.
- PSI-69 `Burning rate; mm` is preserved exactly as labeled and flagged `unit_ambiguity`; it is not converted to mm/s.
- Chart-only PSI-100 sheets are not parsed because they contain nested headers and dummy data, not measurements.

### 4.6 Phase 1 completion record

| Check | Verified result |
|---|---|
| Acquisition selection | 72 files, 56,238,344 expected bytes |
| Download outcome | 70 downloaded, 2 already present, 0 failed |
| Bytes downloaded | 56,194,097 |
| Checksum verification | 72 / 72 |
| Known 404s re-verified | 2 |
| Duplicate checksum groups | 0 |
| Parsed sources | 79 sources across 72 files |
| Interim outputs | 57 Parquet files plus `parse_report.json` |
| Parse issues | 4 source-attributed issues: PSI-69 encoding fallback (two tables), PSI-102 headerless log, PSI-101 truncated row |
| Canonical tables | 13 |
| Canonical rows | 8,058,206 |
| Canonical bytes | 82,953,195 |
| Dataset version | `2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb` |
| Acquisition validation | Pass, 72 / 72 verified |
| Canonical validation | Pass, 13 checks, 0 failed |
| Quality report | Pass, 6 issues, 0 errors, 5 warnings, 1 informational note |
| Test suite | 150 passed: 136 unit, 14 integration |

Reproducibility checks that passed:

```bash
python scripts/build_download_manifest.py --check
python scripts/build_et_schemas.py --check
python scripts/build_fixtures.py --check
python -m src.data_pipeline manifest --check
```

The full run commands are:

```bash
python -m src.data_pipeline download --all
python -m src.data_pipeline parse --force
python -m src.data_pipeline build-canonical
python -m src.data_pipeline validate
python -m src.data_pipeline report
```

---

## 5. Phase 2 — Scientific validation and canonical data

### 5.1 Goal

Produce canonical tables that are scientifically defensible, with units, missingness, and provenance. Resolve or explicitly label every ambiguity.

### 5.2 Workstreams

#### 5.2.1 Canonical tables

- [x] Implement the `gas_flame_test` table for PSI-10 and PSI-159.
- [x] Implement `telemetry_run` and `telemetry_point` for PSI-100.
- [x] Implement `smoke_run` and `smoke_point` for PSI-101.
- [x] Implement `material_test` for PSI-25 and PSI-26.
- [ ] Implement `derived_metric` and `citation`. (Deferred; no derived metrics are served, and citation records remain part of the target API contract.)
- [x] Write Parquet with a stable schema and dataset version.
- [ ] Load metadata and provenance into PostgreSQL. (Deferred; DuckDB over Parquet is the Phase 2 analytical store.)
- [x] Add DuckDB views over Parquet for local analytics.

#### 5.2.2 Unit and field audit

- [ ] Confirm PSI-159 `TFP` meaning from the readme/publication, or keep it as an undefined categorical flag.
- [ ] Confirm PSI-159 `Xf` definition.
- [ ] Confirm PSI-100 radiometer, anemometer, fan tach, smoke wire, and igniter units from flight documentation, or keep `not stated`.
- [ ] Confirm PSI-100 timestamp reconciliation and the authoritative export per sensor.
- [ ] Confirm PSI-101 `-999` sentinel and `DustTrakA` inactivity.
- [ ] Confirm PSI-25 `-1` initial CO meaning.
- [ ] Confirm PSI-20 oxygen text anomalies.
- [ ] Confirm PSI-21 MFC units.
- [ ] Confirm PSI-26 as-run `Air display` and `Fan display` units.

#### 5.2.3 Comparability

- [x] Implement the comparability matrix as a machine-readable allowlist.
- [x] Add tests that reject incompatible comparisons.
- [x] Add a UI/API reason for each rejected comparison.
- [x] Do not create a flame-spread axis for BASS/BASS-II or SAME/SAME-R.

#### 5.2.4 Data quality

- [x] Implement schema, row-count, checksum, time, range, and unit gates.
- [x] Implement a missingness report per table and field.
- [x] Implement a constant-channel report.
- [x] Implement a blocked-dataset state.
- [x] Add a data-quality dashboard or report artifact. (JSON report and API quality endpoints; no visual dashboard yet.)

### 5.3 Acceptance criteria

1. Every canonical field has a source field or a documented derivation.
2. Every displayed numeric field has a unit or `not stated`.
3. Every missing/sentinel token is classified.
4. `TFP` is never plotted as a temperature.
5. PSI-159 inverse valid rows are 154, not 1,015.
6. PSI-100 exports are not concatenated.
7. PSI-101 device states are not treated as physical measurements.
8. BASS/BASS-II have no spread-rate chart.
9. A blocked dataset cannot be served as valid.
10. The data-quality report is reproducible.

### 5.4 Tests

- Golden row counts and checksums for every canonical table.
- Missingness assertions for known sentinel fields.
- Unit assertions for every numeric field.
- Time monotonicity assertions for telemetry and smoke runs.
- Negative tests for incompatible comparisons.
- A test that `TFP` is categorical and not numeric.
- A test that PSI-159 inverse drops all-blank rows and reports 154 valid rows.

### 5.5 Phase 2 completion record (2026-11-09)

Completed:

- Comparability registry: 93 measurements, 60 pair-specific rules, five states, default `not_comparable`.
- Serving registry: 9 datasets, 93 measurement states, four uses, five states.
- Bounded DuckDB layer: 13 read-only views, parameterized filters, pagination, series caps, sentinel handling, provenance, quality slices, timeout watchdog.
- Read-only FastAPI service: 23 paths, strict query allowlist, shared envelopes, request IDs, CORS, OpenAPI.
- Tests: 120 new tests; 270 total (239 unit, 31 integration).
- Documentation: comparability, serving states, query contract, API implementation, frontend readiness, and ADR 0003.

Deferred, with no effect on the Phase 2 serving contract:

- `derived_metric` and citation tables.
- PostgreSQL metadata store.
- Confirmation of the remaining source questions in §5.2.2. Values stay labeled `not stated`, `ambiguous`, or categorical until confirmed.

---

## 6. Phase 3 — Read-only API

### 6.1 Goal

Expose canonical data with provenance, units, quality flags, and citations through a stable, documented API.

### 6.2 Workstreams

- [x] Scaffold FastAPI with Pydantic v2 and OpenAPI.
- [x] Implement `GET /api/v1/health`.
- [x] Implement catalog and dataset endpoints.
- [x] Implement field and limitation endpoints.
- [x] Implement gas-flame test query and detail endpoints.
- [x] Implement telemetry run/series endpoints with time range and channel allowlist.
- [x] Implement smoke run/series endpoints.
- [x] Implement curated comparison endpoints.
- [x] Implement provenance endpoints and file/row citation records.
- [ ] Implement assistant tool endpoints (internal or public, with auth). Phase 5.
- [x] Add pagination, filtering, and stable error codes.
- [x] Add ETag/`304`, `Cache-Control`, request IDs, and structured request logs.
- [x] Add configurable fixed-window rate limiting.
- [ ] Add embedded OpenAPI examples. Deferred; request and response examples are documented in `API_DOCUMENTATION.md`, `docs/api-implementation.md`, and `docs/phase4-contracts.md`.
- [x] Add contract tests.

### 6.3 Acceptance criteria

1. Every response includes dataset version and provenance.
2. Every numeric value includes a unit or `not stated`.
3. Every response with data includes quality flags.
4. No endpoint accepts arbitrary SQL, file paths, or table names.
5. Time-series requests require a bounded range and channel allowlist.
6. Error codes are stable and documented.
7. OpenAPI validates and is published.
8. Contract tests cover success, empty, invalid, blocked, and rate-limited cases.

### 6.4 Tests

- OpenAPI schema validation.
- Contract tests for every endpoint.
- Pagination tests.
- Time-range limit tests.
- Invalid dataset/field tests.
- Blocked-dataset tests.
- Provenance resolution tests.
- Cache-header and conditional-request tests.
- Rate-limit tests.
- Citation integrity and row-verification tests.

### 6.5 Phase 3 completion record (2026-11-10)

Delivered across the Phase 2 API commit and the Phase 4 metadata-contract commit:

- FastAPI app with 31 paths under `/api/v1`.
- Health, meta, investigations, datasets, dataset quality, dataset files, dataset fields, dataset limitations, measurements, gas-flame, gas-flame facets, material, droplet, telemetry, smoke, comparability, compare, citations, citation detail, publications, publication detail, and provenance.
- One success envelope and one error envelope.
- Strict query allowlisting; unknown and repeated parameters rejected.
- Pagination, series caps, `413 range_too_large`, and stable error codes.
- Request IDs, environment-driven CORS, OpenAPI schema, and 297 passing tests.
- ETag/`304` for stable success responses, `Cache-Control: no-store` for errors, and health responses excluded from ETag generation.
- Configurable fixed-window rate limiting with `429` and `Retry-After`.
- Structured request logs with `request_id`, method, path, status, and duration.
- File-level citations for the curated manifest and on-demand row citations verified against canonical tables.

Still open:

- Embedded OpenAPI request/response examples.
- Assistant endpoints, which belong to Phase 5.

The implemented route `/material/tests` remains the public path; it is documented as the material test list rather than renamed late in the cycle.

---

## 7. Phase 4 — Frontend exploration experience

### 7.1 Goal

Build an honest, accessible interface for exploring the verified data. Do not add decorative dashboards or unsupported rankings.

**Delivery status (2026-11-10):** complete. The frontend is implemented in `frontend/` and runs against the real API and canonical data. It renders citations, curated files, field dictionaries, limitations, publications, dynamic facets, comparison integrity, and paired-value eligibility from backend contracts. It never invents missing metadata or a paired series.

### 7.2 Workstreams

- [x] Scaffold Next.js + TypeScript + Tailwind.
- [x] Implement the design system and accessibility tokens.
- [x] Build the home page with project status and limitations.
- [x] Build the dataset catalog with role and access badges.
- [x] Build the dataset detail page with tables, provenance, serving states, file browser, field dictionary, limitations, and publications.
- [x] Build the gas-flame test explorer with dynamic facets, filters, and a data table.
- [x] Build the telemetry explorer with channel selection and time range.
- [x] Build the smoke explorer.
- [x] Build curated comparison views only for compatible fields, with integrity and paired-value panels.
- [x] Build the methods/limitations page from `DATA_SOURCES.md` and `DATA_DICTIONARY.md`.
- [x] Build the citation drawer for files, rows, and provenance records.
- [x] Build the publications list and detail routes.
- [x] Add empty, loading, error, blocked, unavailable, `experimental_table_only`, and `no_public_files` states.
- [x] Add keyboard navigation and screen-reader labels.
- [x] Add responsive layouts and automated mobile viewport coverage.
- [x] Add 54 unit/component tests, 24 real-backend Playwright flows, and 6 axe WCAG 2.1 A/AA scans.

### 7.3 Acceptance criteria

1. Every chart has a title, axis units, source accession, and provenance link.
2. Missingness is visible; no interpolation without a labeled method.
3. No dual axes.
4. No risk score or material ranking.
5. `experimental_table_only` datasets show their verified summary table with an explicit badge; `no_public_files` records show "No public files". Neither shows a zero-valued chart.
6. The citation drawer resolves to accession, file, field, row/range, checksum, and retrieval date.
7. WCAG 2.1 AA checks pass for the main flows.
8. The app works without the assistant.
9. The app does not compute scientific aggregates that the API does not expose.
10. A paired chart renders only when the backend returns a complete verified alignment contract.

**Delivery check:** all criteria are implemented. Criterion 6 is covered by file and row citation drawers. Criterion 10 is covered by the `isChartReady` guard and by Playwright assertions that the chart is withheld for `conditions_not_verified`.

### 7.4 Tests

- [x] Component tests for charts, badges, and scientific state panels.
- [x] End-to-end tests for catalog → dataset → chart → quality/provenance.
- [x] Accessibility tests with axe.
- [ ] Visual regression tests for key screens.
- [x] Responsive tests for mobile and desktop viewports.
- [x] Error-state tests for blocked, `experimental_table_only`, and `no_public_files` datasets.
- [x] Phase 4 tests for citations, files, fields, limitations, publications, facets, and paired-value withholding.

---

## 8. Phase 5 — Grounded insight layer

### 8.1 Goal

Add an assistant that answers questions from verified data and documents, with citations and explicit limitations. It must be optional and must not become the source of truth.

### 8.2 Workstreams

- [x] Build a retrieval index over dataset cards, data dictionary, limitations, and publication metadata.
- [x] Implement deterministic tools for catalog, tests, telemetry, smoke, comparison, and provenance.
- [x] Implement a planner that selects tools and never generates raw SQL.
- [x] Implement the answer contract (`answer`, `evidence_status`, `citations`, `limitations`, `method`).
- [x] Implement a citation validator.
- [x] Implement refusal behavior for `no_public_files` datasets and out-of-scope questions, and explicit summary-table limits for `experimental_table_only` datasets.
- [x] Implement prompt-injection defenses for free-text comments.
- [x] Implement a golden evaluation set.
- [x] Implement a deterministic fallback when the LLM is unavailable.
- [x] Document the provider interface and environment variables.

### 8.3 Acceptance criteria

1. Every numeric claim has a tool result and a citation.
2. Every answer includes limitations relevant to the data.
3. `no_public_files` datasets are refused with a specific reason; `experimental_table_only` datasets answer only from the verified summary table and state its limits.
4. Missingness questions return "not available" or "blank," not zero.
5. Unit questions do not confuse mole fraction with percent.
6. Incompatible comparisons are refused with a reason.
7. Prompt injection in comments does not change tool behavior.
8. The assistant works with the LLM disabled, using deterministic search and charts.
9. The golden set passes at the agreed threshold; numeric citation coverage is 100%.

### 8.4 Tests

- Golden questions with expected citations and evidence status.
- Missingness and experimental-table-limit tests.
- Unit and comparability tests.
- Prompt-injection tests.
- Citation-validator tests.
- Provider-failure tests.
- Latency and cost tests.

### 8.5 Phase 5 entry recommendations

Phase 5 can build on the Phase 4 contracts without changing them. Recommended order:

1. **Freeze the answer contract first.** Define `answer`, `evidence_status`, `citations`, `limitations`, and `method` before choosing a model provider. Every numeric claim must reference a tool result and a `cit_f_` or `cit_r_` citation.
2. **Build the retrieval index from verified artifacts only.** Use dataset cards, `DATA_DICTIONARY.md`, limitations, publications, and citation records. Do not index raw comments as instructions.
3. **Wrap existing service methods as tools.** Catalog, test queries, telemetry, smoke, comparison, citation resolution, and provenance already exist. The assistant should select tools, never generate SQL or file paths.
4. **Validate citations before returning an answer.** Resolve every citation ID through the citations endpoint and reject answers with unknown or mismatched file/row locators.
5. **Treat paired values as unavailable unless the API says otherwise.** If `paired_values.available` is false, the assistant must state the reason and must not infer a comparison from separate summaries.
6. **Add refusal tests for the known traps.** Missing values are not zero; PSI-10 atm is not PSI-159 bar; PSI-98's two telemetry files are unavailable; `experimental_table_only` answers are limited to the summary table.
7. **Implement the deterministic fallback early.** Search, catalog answers, and citation lookup must work with the LLM disabled.
8. **Keep the paired-comparison executor as a separate scientific milestone.** A verified alignment method with exact keys, value fields, and units must be committed before any series is computed. Until then, Phase 5 answers cite the withholding reason.

### 8.6 Phase 5 completion record (2026-11-10)

Phase 5 is complete. The assistant is deterministic by default, works with no LLM configured, and fails closed to deterministic mode when an optional provider is unavailable.

| Item | Verified result |
|---|---|
| Answer contract | `1.0.0` with evidence status, answer type, claims, citations, supporting data, limitations, tool audit, and validation |
| Deterministic tools | 22 typed, allowlisted tools over the Phase 1–4 service; no SQL, filesystem, URL, or code-execution tool |
| Retrieval | 1,391 chunks from committed documentation and metadata cards; BM25 + deterministic hashed TF-IDF hybrid; source-hash manifest |
| API paths | 35 under `/api/v1`; assistant `status`, `suggestions`, `tools`, and `query` |
| Golden questions | 36 questions, version `1.0.1`; 36 / 36 passed |
| Citation validity | 117 / 117 references resolved through Phase 4 citation endpoints |
| Supported claims | 59 / 59, each linked to a current tool call |
| Numerical exact match | 30 / 30 checks |
| Unit consistency | 30 / 30 checks |
| Correct refusals | 12 / 12 |
| Tool-selection accuracy | 35 / 35 |
| Retrieval evaluation | 7 labelled cases; precision@5 `0.602381`, recall@5 `1.0`, MRR `0.761905` |
| Deterministic latency | mean `115.024 ms`, p95 `335.201 ms` (local run; not an SLO) |
| Backend tests | 483 passing |
| Frontend tests | 68 unit/component tests; 27 Playwright tests, including 7 axe scans |
| Production build | Passes with the `/assistant` route |

Milestones are committed in order: contracts (`12e620f`), tools (`d1b5f21`), retrieval (`0f2d21c`), orchestration and API (`5f7e66a`), frontend (`7fbaf4a`), evaluation (`e794245`), and documentation/release (Milestone G).

The assistant preserves the Phase 1–4 limits:

- A real language model was **not** evaluated. The optional provider is exercised only through deterministic stubs; a real-model run must be reported separately.
- The paired-alignment registry remains empty, so paired values stay unavailable. The assistant states the withholding reason and computes no paired statistic.
- PSI-159 `pressure_initial_atm` and PSI-10 `pressure_approx_bar` have zero canonical values. They are never filled with zeros or silently converted.
- The two PSI-98 telemetry/sensor workbooks remain HTTP 404. They are shown as unavailable, never as downloadable.
- Retrieved documents are evidence, not instructions. They cannot select tools, create numbers or citations, or reach the optional provider as instructions.

The Phase 5 architecture, answer contract, tool catalog, retrieval design, evaluation method, and security model are documented in `docs/phase5-assistant-architecture.md`, `docs/assistant-answer-contract.md`, `docs/assistant-tools.md`, `docs/assistant-retrieval.md`, `docs/assistant-evaluation.md`, and `docs/assistant-security.md`.

---

## 9. Phase 6 — Hardening and deployment

### 9.1 Goal

Make the platform operable, observable, secure, and reproducible in a public deployment without changing Phase 1–5 scientific decisions.

### 9.2 Workstreams

- [x] Add production Dockerfiles and a Compose topology.
- [x] Add default data-free CI for compile, unit, contract, reproducibility, lint, type check, unit/component tests, build, and dependency audits.
- [x] Add a manual full-data CI workflow for integration, Playwright, axe, canonical validation, index freshness, and assistant evaluation.
- [x] Add dependency scanning for Python runtime and frontend production dependencies.
- [ ] Add automated secret scanning. No secret-scanning service is configured; secrets are excluded by `.gitignore` and reviewed manually.
- [ ] Add a hosted staging deployment. Native production startup and local Compose topology are documented; no hosting account or staging environment was available.
- [ ] Add PostgreSQL migrations with Alembic. The current canonical store is read-only Parquet plus committed metadata; no PostgreSQL deployment is required by Phase 6.
- [ ] Add object storage for raw/processed data. Deployment currently uses read-only filesystem mounts.
- [x] Add structured request/assistant logs and bounded operational metrics.
- [ ] Add distributed traces and alert delivery. Metrics and a runbook exist; no external alerting backend is configured.
- [ ] Add a separate operations data-quality dashboard. The existing `/quality` page covers scientific quality; no new ops dashboard was added.
- [x] Document backups and a recovery procedure. A destructive restore drill was not run against production data.
- [x] Add a runbook for PSI drift, 404s, blocked datasets, index staleness, validation failure, and provider outages.
- [ ] Add a dedicated privacy page. The `/about` page carries attribution and data-source limits; a separate privacy page is not implemented.
- [x] Add a release checklist in the security review and CI gates.

### 9.3 Acceptance criteria

1. Production deployment architecture is implemented and documented.
2. Native local production startup works for the backend and frontend.
3. Default CI passes from a clean, data-free checkout.
4. Existing scientific and application tests remain green on full data.
5. Provider retries, timeout, usage, cost, and safe fallback are implemented.
6. A real-model evaluation is completed if credentials exist; otherwise it is explicitly pending.
7. Retrieval changes are measured before adoption and preserve recall.
8. Readiness, metrics, structured logs, and a runbook are functional.
9. Security review is completed with residual risks documented.
10. Performance baselines are recorded with reproducible methodology.
11. Backup and recovery instructions exist.
12. Frontend production build and accessibility checks pass.
13. No Phase 1–5 scientific safeguard is weakened.
14. Documentation is updated.
15. Changes are committed and pushed.

### 9.4 Verified Phase 6 result

- Native Uvicorn plus Next.js standalone production startup verified; `/ready` returned 200 with the verified index.
- Dockerfiles and Compose are implemented. Image build and scan remain pending because the local Docker daemon was inaccessible.
- Default CI data-free gate: 362 passed, 131 integration tests deselected in a clean worktree.
- Full backend suite: 493 passed, 1 warning.
- Frontend: 68 unit/component tests, lint, typecheck, production build; 27 Playwright tests and 7 axe scans passed.
- Provider: bounded retries, `Retry-After`, request IDs, usage, optional cost, safe logs, deterministic fallback. Live model evaluation pending credentials.
- Retrieval: MRR improved from `0.761905` to `1.0`; recall stayed `1.0`; precision@5 `0.602381`.
- Operations: `/ready`, `/metrics`, bounded counters, request limits, security headers, structured logs, and runbook.
- Performance: 10 scenarios, 30 requests each, concurrency 8, 0 errors; telemetry p95 `604.966 ms`, assistant p95 `273.357 ms`.
- Security: Python runtime and frontend production dependency audits clean; full dev-only npm audit has documented follow-ups.
- Backup/recovery and deployment procedures documented; no production restore drill was possible.

### 9.5 Phase 6 tests

- Readiness 200/503 gates for dataset and index.
- Metrics aggregation without user content.
- Security headers and request-size limit.
- Provider retry, rate-limit, timeout, usage, and cost tests.
- Clean-checkout data-free test gate.
- Full-data integration, Playwright, and axe suites.
- Retrieval before/after evaluation.
- Performance scenarios for catalog, metadata, gas-flame, telemetry, citations, provenance, and assistant.

---

## 10. Phase 7 — Future extensions (deferred)

These are scientifically interesting but out of MVP scope. Each requires a separate decision record, data audit, and validation plan.

| Extension | Why deferred | Prerequisite |
|---|---|---|
| BASS/BASS-II video-derived spread rates | No processed table; requires computer vision and validation | Frame extraction, calibration, tracking, uncertainty analysis |
| FLEX/FLEX-2 raw-archive analysis | Zero `added` files; only summary tables are public | Public archive access or an approved alternate source |
| SAFFIRE-II raw-archive analysis | Zero `added` files; only a 15-row sample summary is public | Public archive access |
| ACME E-FIELD raw-archive analysis | Zero `added` files; only a 32-row test-day summary is public | Public archive access |
| ACME s-Flame soot/structure analysis | 4,163 files; no identified processed table | Format audit and parser |
| CFI droplet analysis | 2,831 raw files; no identified processed table; sampled 404 | Format audit and access audit |
| SPICE soot-point analysis | 186 files, mostly XLS/XLSX; no standardized table | Format audit |
| SLICE liftoff analysis | 12-row, 2-column table; no measured variables | Additional data |
| Predictive model or risk score | No validated target or method | Pre-registered method, held-out validation, uncertainty, review |

**Do not promote a deferred item into the MVP without updating the selection ADR and the data dictionary.**

---

## 11. Cross-cutting workstreams

### 11.1 Documentation

- Keep `DATA_SOURCES.md`, `DATA_DICTIONARY.md`, and the registry consistent.
- Update the roadmap when a phase gate changes.
- Record semantic decisions in `docs/decisions/`.
- Record source verification in `docs/research/source-verification-log.md`.

### 11.2 Testing

- Every parser has fixtures and negative tests.
- Every API endpoint has contract tests.
- Every chart has a provenance test.
- Every assistant release has a golden-set evaluation.
- Every deployment has a smoke test.

### 11.3 Security

- No secrets in Git.
- Read-only public API.
- Parameterized queries.
- Allowlisted datasets and fields.
- Rate limits and request size limits.
- Prompt-injection defenses.
- Dependency and container scanning.

### 11.4 Accessibility

- WCAG 2.1 AA for main flows.
- Keyboard navigation.
- Screen-reader labels for charts and tables.
- Color-blind-safe palettes.
- No color-only encoding.
- Reduced-motion support.

### 11.5 Scientific integrity

- No invented data.
- No unit guessing.
- No hidden aggregation.
- No unsupported causation.
- No arbitrary risk score.
- `experimental_table_only` datasets are labeled and limited to their verified summary tables; `no_public_files` datasets are labeled, not filled.

---

## 12. Milestone acceptance checklist

### Milestone 0 — Foundation

- [x] `python scripts/fetch_psi_metadata.py --check` passes.
- [x] 24 combustion investigations in the registry.
- [x] 16,354 `added` files, 22 experimental tables, 13,496.77 GB registered total.
- [x] `experimental_table_only` records documented: PSI-22, PSI-68, PSI-69, PSI-99. No `no_public_files` records.
- [x] Listed-but-404 files documented: SAFFIRE-I telemetry/sensor XLSX; sampled CFI `.metadata`.
- [x] All required docs exist and agree.
- [x] `data/registry/mvp_dataset_catalog.json` exists and matches the registry.
- [x] No raw data or secrets committed.
- [x] Initialization commit pushed; remote SHA verified.

### Milestone 1 — Parsed MVP

- [x] Download manifest and checksums complete.
- [x] Parsers for PSI-10, PSI-159, PSI-100, PSI-101, PSI-25, PSI-26 pass fixtures.
- [x] Small-table parsers for PSI-20, PSI-21, PSI-106, PSI-142 pass through the generic summary-table parser.
- [x] Missingness and sentinel report complete.
- [x] No raw data in Git.
- [x] Canonical Parquet tables built as a Phase 1 deliverable (13 tables, 8,058,206 rows).

### Milestone 2 — Canonical data

- [x] Canonical tables pass data-quality gates.
- [x] Units resolved or labeled `not stated`; unresolved unit ambiguities are flagged.
- [x] Comparability allowlist implemented.
- [x] Blocked-dataset state implemented.
- [x] Data-quality report reproducible.

### Milestone 3 — API

- [x] OpenAPI published.
- [x] Contract tests pass.
- [x] Provenance, units, quality flags, and citations in every response.
- [x] Bounded time-series queries.
- [x] Cache, rate limiting, request IDs, and structured logs.

### Milestone 4 — Frontend

- [x] Catalog, dataset detail, test explorer, telemetry, smoke, compare, methods.
- [x] Citation drawer, file browser, field dictionary, limitations, and publications.
- [x] Missingness and `experimental_table_only`/`no_public_files` states.
- [x] Accessibility checks pass.
- [x] No unsupported chart or ranking.
- [x] Paired chart withheld unless the backend returns a verified alignment.

### Milestone 5 — Insight

- [x] Golden set passes: 36 / 36 questions, version `1.0.1`.
- [x] Numeric citation coverage 100%: 117 / 117 citation references valid, 30 / 30 numerical and unit checks.
- [x] Refusal and missingness behavior correct: 12 / 12 refusals; missing values are not zero; unit and paired-value traps are refused.
- [x] Deterministic fallback works: no LLM required; failing providers fall back to the validated deterministic answer.
- [x] Prompt-injection and adversarial questions pass without changing tool behavior or exposing secrets.
- [x] `/assistant` frontend, evidence panel, citation drawer, suggested questions, and accessibility checks pass.

### Milestone 6 — Deployment

- [x] Data-free CI gate passes from a clean checkout; full-data workflow is provided.
- [x] Native production startup passes; Docker image build remains pending a Docker-capable host.
- [x] Readiness, metrics, structured logs, and runbook are implemented.
- [x] Backup and recovery procedure documented; production restore drill not possible.
- [x] Full backend, frontend, Playwright, axe, build, and reproducibility checks pass.
- [ ] Hosted staging deployment and external alert delivery.
- [ ] Live-model evaluation with real credentials.

---

## 13. Risk register

This register is qualitative. It does not assign arbitrary numeric risk scores.

| Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|
| NASA PSI metadata changes | Medium | Medium | `--check` drift detection; versioned snapshots; stale badge | Data lead |
| A listed file returns 404 | Medium | High | Access-status flag; no substitution; surface limitation | Data lead |
| Schema drift breaks a parser | Medium | High | Exact-header validation; fail closed; fixtures | Parser owner |
| Unit ambiguity leads to a wrong chart | High | High | `not stated` policy; review; no physical axis until resolved | Science lead |
| Missing values are mistaken for zeros | High | High | Quality flags; missingness UI; tests | Science lead |
| BASS spread-rate expectations exceed data | High | Medium | Label "not published"; defer computer vision | Science lead |
| LLM hallucination | Medium | High | Tool-only numbers; citation validator; golden eval | Insight lead |
| Prompt injection in comments | Low | Medium | Delimit data; no instruction following; tool allowlist | Security lead |
| Raw data accidentally committed | Medium | High | `.gitignore`; pre-commit check; size limits | Repo maintainer |
| Secret leak | Low | High | `.env` ignored; manual review; add automated scanning before a public release | Repo maintainer |
| Frontend implies NASA endorsement | Low | High | Attribution page; disclaimer; review | Communications lead |
| Scope creep into deferred datasets | High | Medium | Phase gates; ADR required | Project lead |
| Provider outage or rate limit | Medium | Medium | Bounded retries, timeout, deterministic fallback, metrics | Operations lead |
| Stale retrieval index after docs change | Medium | Medium | Source-hash validation, `--check`, readiness warning, rebuild instructions | Insight lead |
| Container build untested locally | Medium | Medium | Build and scan on a Docker-capable host before release | Operations lead |
| Development dependency vulnerabilities | Medium | Low | Production audit clean; upgrade test/lint toolchain in a dedicated change | Frontend lead |
| Multi-replica rate-limit/metrics split | Low | Medium | Keep single process or add shared stores before scaling | Operations lead |

Owners are generic roles because the public team roster is not available. Assign named owners in the repository's private project tracker, not by inventing names here.

---

## 14. Definition of done

A feature is done when:

1. Its data source and provenance are documented.
2. Its units and missingness are defined.
3. Its parser or query has tests, including negative cases.
4. Its API response includes citations and quality flags.
5. Its UI labels units, source, and limitations.
6. Its limitations are in `DATA_SOURCES.md` or `DATA_DICTIONARY.md`.
7. It does not introduce an unsupported comparison or risk score.
8. It passes accessibility and security checks.
9. It is documented in the README or a linked doc.
10. It is committed with a meaningful message and reviewed.

---

## 15. Immediate next actions

1. Record a real-model evaluation when provider credentials are available; report it separately from deterministic and mock-provider checks, with model, provider, date, cost, and configuration.
2. Build and scan the Docker images on a Docker-capable host, then run the Compose smoke test.
3. Treat the paired-comparison executor as a separate scientific milestone with its own committed alignment method, exact keys, value fields, units, and validation.
4. Re-run the golden evaluation and rebuild the retrieval index whenever the canonical dataset version or assistant documentation changes.
5. Upgrade the frontend test/lint toolchain to clear the documented development-only audit findings.
6. Revisit authentication only if private data or write operations are added; the public API remains read-only and rate limiting is not authentication.

The order matters: the gas-flame tables establish the test-level schema; the telemetry and smoke tables establish the time-series schema; the material matrices establish the context schema. The interface and assistant are built only after these contracts exist, so the data never has to be forced into the UI or the answer.
