# Development Roadmap

**Project:** Flame in Freefall
**Team:** AFAQ
**Challenge:** Flame in Freefall: SI-Powered Fire Safety Insights from Microgravity Combustion Data
**Status date:** 2026-11-08

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
| 1 | Data acquisition and parser foundation | Planned | MVP files downloaded, checksummed, parsed, and tested on fixtures |
| 2 | Scientific validation and canonical data | Planned | Canonical tables pass data-quality gates; units and limitations resolved or labeled |
| 3 | Read-only API | Planned | OpenAPI contract, provenance, pagination, and contract tests pass |
| 4 | Frontend exploration experience | Planned | Catalog, test explorer, telemetry/smoke views, citations, accessibility pass |
| 5 | Grounded insight layer | Planned | Golden-set evaluation passes; numeric claims are 100% cited |
| 6 | Hardening and deployment | Planned | CI/CD, observability, security, backups, and runbook verified |
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

### 4.1 Goal

Turn the verified metadata into reproducible, checksummed, parsed source tables. Do not build charts yet.

### 4.2 Workstreams

#### 4.2.1 Download manifest

- [ ] Define `data/registry/download_manifest.json` with the exact MVP files.
- [ ] Include accession, file name, expected bytes, source URL, and intended use.
- [ ] Exclude files known to return 404. Include `experimental_table_only` summary tables only within their documented limits; do not fabricate a replacement archive.
- [ ] Record access status for every selected file.

#### 4.2.2 Downloader

- [ ] Implement `scripts/download_psi_files.py` with standard library or `httpx`.
- [ ] Stream downloads to `data/raw/<accession>/<file_name>`.
- [ ] Verify HTTP status, content length when available, and SHA-256.
- [ ] Write a checksum manifest with retrieval timestamps.
- [ ] Support resume and rate limiting.
- [ ] Never bypass authentication or access controls.
- [ ] Record `listed_404` instead of failing silently.

#### 4.2.3 Parsers

- [ ] CSV parser with exact-header validation.
- [ ] XLSX parser using `openpyxl`; sheet selection by name.
- [ ] XLS parser using `xlrd` or a documented converter.
- [ ] PSI-10 normal/inverse parser.
- [ ] PSI-159 normal/inverse parser.
- [ ] PSI-100 raw/cleaned CSV parser.
- [ ] PSI-100 XLSX sheet parser (`RawData`, `SaffireData`, `CygnusData`, smoke/pressure/temperature sheets).
- [ ] PSI-101 HKP CSV parser.
- [ ] PSI-25 BASS-II workbook parser.
- [ ] PSI-26 BASS CSV and as-run workbook parser.
- [ ] PSI-20, PSI-21, PSI-106, PSI-142 small-table parsers.
- [ ] Emit provenance for every row.
- [ ] Classify every missing/sentinel token.

#### 4.2.4 Fixtures

- [ ] Commit small fixtures with exact headers and 3–10 rows.
- [ ] Include at least one fixture per sentinel: blank, `-`, `n/a`, `none`, `OR`, `RAMP`, `RAMPED`, `LOW O2`, `#DIV/0!`, `#VALUE!`, `-999`, sentinel timestamp.
- [ ] Do not commit full raw files or video.

### 4.3 Acceptance criteria

1. Every selected MVP file downloads successfully or is explicitly marked `listed_404`.
2. Every downloaded file has a SHA-256 and a retrieval timestamp.
3. Parsers fail on unexpected headers; they do not guess.
4. Every parser has fixture tests for normal, missing, sentinel, and malformed rows.
5. Parsed row counts match the committed table statistics, or the difference is explained.
6. No parser writes to `data/raw/`.
7. A clean checkout can reproduce the parsed interim tables from the manifest and raw files.

### 4.4 Tests

- Unit tests for header validation and sentinel classification.
- Fixture tests for each parser.
- Checksum tests for each downloaded file.
- A negative test that an unexpected header raises a typed error.
- A negative test that a sentinel is not coerced to zero.

### 4.5 Known blockers

- `pandas`, `openpyxl`, and `xlrd` are not installed in the current environment. The parser phase must add pinned dependencies.
- Legacy `.xls` files require `xlrd` or a converter.
- SAFFIRE-I telemetry files are listed but return 404. Do not plan around them.

---

## 5. Phase 2 — Scientific validation and canonical data

### 5.1 Goal

Produce canonical tables that are scientifically defensible, with units, missingness, and provenance. Resolve or explicitly label every ambiguity.

### 5.2 Workstreams

#### 5.2.1 Canonical tables

- [ ] Implement the `gas_flame_test` table for PSI-10 and PSI-159.
- [ ] Implement `telemetry_run` and `telemetry_point` for PSI-100.
- [ ] Implement `smoke_run` and `smoke_point` for PSI-101.
- [ ] Implement `material_test` for PSI-25 and PSI-26.
- [ ] Implement `derived_metric` and `citation`.
- [ ] Write Parquet with a stable schema and dataset version.
- [ ] Load metadata and provenance into PostgreSQL.
- [ ] Add DuckDB views over Parquet for local analytics.

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

- [ ] Implement the comparability matrix as a machine-readable allowlist.
- [ ] Add tests that reject incompatible comparisons.
- [ ] Add a UI/API reason for each rejected comparison.
- [ ] Do not create a flame-spread axis for BASS/BASS-II or SAME/SAME-R.

#### 5.2.4 Data quality

- [ ] Implement schema, row-count, checksum, time, range, and unit gates.
- [ ] Implement a missingness report per table and field.
- [ ] Implement a constant-channel report.
- [ ] Implement a blocked-dataset state.
- [ ] Add a data-quality dashboard or report artifact.

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

---

## 6. Phase 3 — Read-only API

### 6.1 Goal

Expose canonical data with provenance, units, quality flags, and citations through a stable, documented API.

### 6.2 Workstreams

- [ ] Scaffold FastAPI with Pydantic v2 and OpenAPI.
- [ ] Implement `GET /api/v1/health`.
- [ ] Implement catalog and dataset endpoints.
- [ ] Implement field and limitation endpoints.
- [ ] Implement gas-flame test query and detail endpoints.
- [ ] Implement telemetry run/series endpoints with time range and channel allowlist.
- [ ] Implement smoke run/series endpoints.
- [ ] Implement curated comparison endpoints.
- [ ] Implement provenance and citation endpoints.
- [ ] Implement assistant tool endpoints (internal or public, with auth).
- [ ] Add pagination, filtering, and stable error codes.
- [ ] Add ETag/cache headers.
- [ ] Add OpenAPI examples.
- [ ] Add contract tests.

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
- Cache-header tests.

---

## 7. Phase 4 — Frontend exploration experience

### 7.1 Goal

Build an honest, accessible interface for exploring the verified data. Do not add decorative dashboards or unsupported rankings.

### 7.2 Workstreams

- [ ] Scaffold Next.js + TypeScript + Tailwind.
- [ ] Implement the design system and accessibility tokens.
- [ ] Build the home page with project status and limitations.
- [ ] Build the dataset catalog with role and access badges.
- [ ] Build the dataset detail page with files, tables, publications, and provenance.
- [ ] Build the gas-flame test explorer with filters and a data table.
- [ ] Build the telemetry explorer with channel selection and time range.
- [ ] Build the smoke explorer.
- [ ] Build curated comparison views only for compatible fields.
- [ ] Build the methods/limitations page from `DATA_SOURCES.md` and `DATA_DICTIONARY.md`.
- [ ] Build the citation drawer.
- [ ] Add empty, loading, error, blocked, `experimental_table_only`, and `no_public_files` states.
- [ ] Add keyboard navigation and screen-reader labels.
- [ ] Add responsive layouts.

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

### 7.4 Tests

- Component tests for charts, badges, and citation drawer.
- End-to-end tests for catalog → dataset → chart → citation.
- Accessibility tests with axe or equivalent.
- Visual regression tests for key screens.
- Responsive tests for mobile and desktop.
- Error-state tests for blocked, `experimental_table_only`, and `no_public_files` datasets.

---

## 8. Phase 5 — Grounded insight layer

### 8.1 Goal

Add an assistant that answers questions from verified data and documents, with citations and explicit limitations. It must be optional and must not become the source of truth.

### 8.2 Workstreams

- [ ] Build a retrieval index over dataset cards, data dictionary, limitations, and publication metadata.
- [ ] Implement deterministic tools for catalog, tests, telemetry, smoke, comparison, and provenance.
- [ ] Implement a planner that selects tools and never generates raw SQL.
- [ ] Implement the answer contract (`answer`, `evidence_status`, `citations`, `limitations`, `method`).
- [ ] Implement a citation validator.
- [ ] Implement refusal behavior for `no_public_files` datasets and out-of-scope questions, and explicit summary-table limits for `experimental_table_only` datasets.
- [ ] Implement prompt-injection defenses for free-text comments.
- [ ] Implement a golden evaluation set.
- [ ] Implement a deterministic fallback when the LLM is unavailable.
- [ ] Document the provider interface and environment variables.

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

---

## 9. Phase 6 — Hardening and deployment

### 9.1 Goal

Make the platform operable, observable, secure, and reproducible in a public deployment.

### 9.2 Workstreams

- [ ] Add Dockerfiles and Docker Compose.
- [ ] Add CI for lint, type check, unit, fixture, contract, accessibility, and assistant evals.
- [ ] Add secret scanning and dependency scanning.
- [ ] Add staging and production deployment.
- [ ] Add PostgreSQL migrations with Alembic.
- [ ] Add object storage for raw/processed data.
- [ ] Add structured logs, metrics, traces, and alerts.
- [ ] Add data-quality dashboard.
- [ ] Add backups and a restore drill.
- [ ] Add a runbook for PSI drift, 404s, blocked datasets, and provider outages.
- [ ] Add a privacy and attribution page.
- [ ] Add a release checklist.

### 9.3 Acceptance criteria

1. CI passes on a clean checkout.
2. Staging deploy passes smoke tests and data-quality checks.
3. Production deploy is reproducible by image digest.
4. Backups restore successfully in a drill.
5. Alerts fire for metadata drift, 404s, blocked datasets, and citation-coverage failure.
6. No secrets or raw data are in the image.
7. The runbook covers the known failure modes.
8. The public site displays NASA attribution and does not imply endorsement.

### 9.4 Tests

- Container build and scan.
- Migration up/down tests.
- Smoke tests in staging.
- Load tests for catalog, test query, and bounded telemetry series.
- Restore drill.
- Alert simulation.
- Security headers and CORS tests.

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

- [ ] Download manifest and checksums complete.
- [ ] Parsers for PSI-10, PSI-159, PSI-100, PSI-101, PSI-25, PSI-26 pass fixtures.
- [ ] Small-table parsers for PSI-20, PSI-21, PSI-106, PSI-142 pass.
- [ ] Missingness and sentinel report complete.
- [ ] No raw data in Git.

### Milestone 2 — Canonical data

- [ ] Canonical tables pass data-quality gates.
- [ ] Units resolved or labeled `not stated`.
- [ ] Comparability allowlist implemented.
- [ ] Blocked-dataset state implemented.
- [ ] Data-quality report reproducible.

### Milestone 3 — API

- [ ] OpenAPI published.
- [ ] Contract tests pass.
- [ ] Provenance, units, quality flags, and citations in every response.
- [ ] Bounded time-series queries.

### Milestone 4 — Frontend

- [ ] Catalog, dataset detail, test explorer, telemetry, smoke, compare, methods.
- [ ] Citation drawer.
- [ ] Missingness and `experimental_table_only`/`no_public_files` states.
- [ ] Accessibility checks pass.
- [ ] No unsupported chart or ranking.

### Milestone 5 — Insight

- [ ] Golden set passes.
- [ ] Numeric citation coverage 100%.
- [ ] Refusal and missingness behavior correct.
- [ ] Deterministic fallback works.

### Milestone 6 — Deployment

- [ ] CI/CD passes.
- [ ] Staging smoke tests pass.
- [ ] Observability and alerts active.
- [ ] Backup restore drill passes.
- [ ] Runbook complete.

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
| Secret leak | Low | High | `.env` ignored; secret scan; rotation runbook | Repo maintainer |
| Frontend implies NASA endorsement | Low | High | Attribution page; disclaimer; review | Communications lead |
| Scope creep into deferred datasets | High | Medium | Phase gates; ADR required | Project lead |

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

1. Finish the remaining foundation documents and registry catalog.
2. Run the metadata drift check.
3. Commit and push the initialization milestone; verify the remote SHA.
4. Build the download manifest for the MVP files.
5. Add pinned parser dependencies and fixtures.
6. Implement the PSI-10 and PSI-159 parsers first, because they are the smallest and most testable.
7. Implement the PSI-100 and PSI-101 parsers next.
8. Implement the BASS/BASS-II test-matrix parsers last.
9. Only then start the API and frontend.

The order matters: the gas-flame tables establish the test-level schema; the telemetry and smoke tables establish the time-series schema; the material matrices establish the context schema. Building the UI before these contracts exist would force the data into the interface, which is the opposite of the project's principle.
