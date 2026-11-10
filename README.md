# Flame in Freefall

**Team:** AFAQ
**Challenge:** Flame in Freefall: SI-Powered Fire Safety Insights from Microgravity Combustion Data
**Event:** NASA Space Apps Challenge 2026, Shebeen El-Kom, Egypt
**Repository:** <https://github.com/YoussefHegazy74/flame-in-freefall>

Flame in Freefall is a data platform for exploring NASA's microgravity combustion research with spacecraft fire safety in mind. It starts from verified data in the NASA Physical Sciences Informatics (PSI) repository, preserves the original values, units, missingness, and provenance, and builds analysis and interface layers only after the scientific foundation is reviewable.

This repository now includes **Phase 7: final release and competition readiness** on top of the completed Phase 1–6 platform. It contains verified source documentation, a curated 72-file acquisition manifest, a checksum-verifying downloader, modular CSV/XLSX/XLS parsers, 13 canonical Parquet tables, machine-readable validation and quality reports, two decision registries plus an empty paired-alignment registry, a read-only FastAPI service with citations, file and field metadata, limitations, publications, facets, and comparison-integrity contracts, a Next.js exploration interface with `/assistant`, production Docker/Compose configuration, CI quality gates, readiness and metrics endpoints, and bounded provider retries with token/cost reporting. The backend suite has **496 passing tests**; the frontend has **68 unit/component tests and 27 real-backend Playwright tests**, including seven axe scans. The assistant is deterministic by default and completes **36 / 36 golden questions** with 100% citation validity and 100% numerical/unit consistency; retrieval MRR is `1.0` after a measured source-aware ranking change. Phase 7 completed a successful isolated restore drill, a scientific integrity audit, a clean full `npm audit`, and the competition demo package. A real language model remains **pending** because no provider credentials were available, and Docker image verification remains pending because the local daemon was inaccessible. The platform does not claim results that have not been computed from source data.

> Phase numbering note: the delivery brief calls the frontend work Phase 3. The internal development roadmap tracks the same frontend work as Phase 4, after its Phase 3 read-only API. Both refer to the interface described in `frontend/README.md`.

---

## What is verified today

On **2026-11-08**, the public NASA PSI API returned:

| Fact | Value |
|---|---:|
| PSI investigations in the repository | 133 |
| Investigations matching Combustion Science | 24 |
| Current `added` archive files across those 24 records | 16,354 |
| Public experimental summary tables | 22 |
| Experimental tables not present in `added` | 14 |
| Distinct public artifacts (`added` + ET-only) | 16,368 |
| Registered total size (decimal GB, 10^9 bytes) | 13,496.77 GB |

These numbers are generated from the live API by `scripts/fetch_psi_metadata.py` and stored in `data/registry/psi_combustion_investigations.json`. They are not estimates.

PSI exposes two different public file lists: `added` (the archive inventory) and `experimentalTable` (curated summary tables). Four records have **zero `added` files but a public experimental table**. They are classified as `experimental_table_only`, not inaccessible, and their tables are analyzed only within the limits documented in `DATA_DICTIONARY.md`:

- PSI-22 — ACME E-FIELD Flames: 32-row test-day summary
- PSI-68 — FLEX-2: 8-row condition-range table (ranges, not measurements)
- PSI-69 — FLEX: 274-row droplet-combustion summary (promoted to supporting)
- PSI-99 — SAFFIRE-II: 15-row sample summary (1-g comparisons only)

No record in the 24-record collection is `no_public_files`. Some files that are listed in the `added` inventory still return HTTP 404 on download. Those are recorded as `listed_404` limitations. They are not silently replaced.

---

## Phase 1 results (2026-11-09)

The pipeline acquired only the curated selection. It never downloaded the full ~13.5 TB PSI archive.

| Acquisition check | Result |
|---|---:|
| Selected files | 72 |
| Expected bytes | 56,238,344 |
| Downloaded | 70 |
| Already present and verified | 2 |
| Failed | 0 |
| Bytes downloaded | 56,194,097 |
| Checksums verified | 72 / 72 |
| Known 404s re-verified | 2 |
| Duplicate checksum groups | 0 |

Parsing produced 57 interim outputs from 79 parse sources across the 72 selected files. The five SAFFIRE-III telemetry exports/sheets and 44 SAME-R HKP CSVs are separate runs; they are never concatenated. The canonical build produced 13 Parquet tables with **8,058,206 rows** and **82,953,195 bytes**, identified by dataset version:

```text
2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb
```

| Canonical table | Rows |
|---|---:|
| `psi_investigation` | 24 |
| `psi_file` | 16,354 |
| `experimental_table` | 22 |
| `gas_flame_test` | 660 |
| `telemetry_run` | 5 |
| `telemetry_point` | 1,762,436 |
| `smoke_run` | 44 |
| `smoke_point` | 6,251,427 |
| `smoke_test_log` | 119 |
| `material_test` | 259 |
| `droplet_test` | 274 |
| `experimental_table_cell` | 24,573 |
| `source_row` | 2,009 |

Acquisition validation passed for 72 of 72 selected files. Canonical validation passed all 13 table checks with 0 failures. The quality report records 6 issues: 0 errors, 5 warnings, and 1 informational note.

---

## Phase 2 results (2026-11-09)

Phase 2 adds scientific state and a read-only service on top of the canonical tables. It does not change a canonical value, unit, or quality flag. This delivery milestone completed the registry and query foundation; the full API contract, cache/rate-limit operations, and frontend integration were delivered in Phases 3 and 4.

| Phase 2 artifact | Result |
|---|---|
| Comparability registry | 93 measurements, 60 pair-specific rules |
| Serving registry | 9 curated datasets, 93 measurement states |
| DuckDB query layer | 13 read-only views over canonical Parquet |
| FastAPI service | 23 documented paths under `/api/v1` |
| Test suite | 270 tests: 239 unit, 31 integration |
| Canonical dataset | 8,058,206 rows, version `2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb` |

The registries make two decisions explicit:

- **Comparability.** An unregistered pair is `not_comparable` by default. A rule is downgraded or blocked when units differ without a declared conversion, value kinds differ, either side is uncalibrated, or the physical quantity differs. `GET /api/v1/compare` returns the decision as a normal `200` response.
- **Serving.** Every dataset and measurement is evaluated for `exploration`, `quantitative_comparison`, `time_series`, and `provenance`. A downloaded file can still be `blocked` for a use. Metadata-only records never render as zero-valued data.

The DuckDB layer exposes named operations only. It never accepts SQL, table names, file paths, or free-form filters. Pages are capped at 200 rows, series at 20,000 points and 8 channels, and oversized ranges return `413 range_too_large` instead of being silently downsampled. A watchdog interrupts queries that exceed the configured time budget.

The API is read-only, uses one success and one error envelope, rejects unknown or repeated query parameters, propagates `X-Request-ID`, and reads CORS origins from `FLAME_CORS_ORIGINS`. See `docs/api-implementation.md`.

---

## Phase 3 frontend results (2026-11-09)

The frontend is a read-only Next.js App Router application. It renders backend decisions and never reimplements comparability, serving, calibration, or quality logic.

| Frontend artifact | Result |
|---|---|
| Framework | Next.js 16.4.5, React 19.3.1, TypeScript 5.9.3, Tailwind CSS 4.3.5 |
| Data layer | TanStack Query 5.107.1 with one centralized, typed API client |
| Charts | Recharts 3.10.1, lazy-loaded time-series panels |
| Routes | 14 at delivery, including investigation/dataset detail and four experiment explorers |
| Unit and component tests | 41 passing at delivery (Vitest + React Testing Library) |
| End-to-end tests | 17 passing at delivery (Playwright against the real backend and canonical data) |
| Accessibility | 4 axe WCAG 2.1 A/AA scans at delivery, 0 serious or critical violations |
| Production build | `npm run build` succeeds with explicit webpack builder |

The interface keeps these scientific constraints visible:

- Missing values are never rendered as zero; raw and calibrated channels are grouped and labeled separately.
- Telemetry and smoke runs remain separate, preserve backend time units, and respect the 20,000-point and 8-channel caps. `413 range_too_large` responses show the actual point count and suggested span without silent retry.
- Gas-flame pressure filters and material oxygen filters require an explicit accession because the units and fields differ across PSI-10/PSI-159 and PSI-25/PSI-26.
- PSI-26 oxygen ambiguity, PSI-69 `Burning rate; mm`, uncalibrated PSI-100 channels, and SAME-R `-999` sentinels are surfaced on the relevant pages.
- Comparison status comes from `/compare`; blocked comparisons render reasons and no chart, and conditional comparisons require explicit condition checkboxes.
- No browser-side aggregation, interpolation, downsampling, unit conversion, risk score, or material ranking is performed.

Frontend setup, architecture, and test commands are in `frontend/README.md`. The interface deliberately does not invent capabilities the API lacks: the assistant is implemented, while the verified paired-comparison executor remains unimplemented.

---

## Phase 4 results (2026-11-10)

Phase 4 adds the scientific metadata contracts the frontend was missing and integrates them without changing Phase 1 canonical values or Phase 2 registry decisions.

| Phase 4 artifact | Result |
|---|---|
| API paths | 31 under `/api/v1` |
| Frontend routes | 16, including publications list/detail |
| Citations | 74 curated file citations plus on-demand row citations |
| Dataset files | Curated manifest with availability, checksum, and download status; PSI-98's two known 404 files remain unavailable |
| Fields | 93 measurement-derived field records with units, value kinds, source columns, integrity, and comparability |
| Limitations | Stable scoped records with evidence and affected operations |
| Publications | 352 source records, 299 unique after dedupe, 235 with DOI, 64 without; year and venue unavailable |
| Facets | PSI-10 327 total / 256 included / 71 excluded; PSI-159 333 / 333 / 0 |
| Comparison | Integrity checks and paired-value eligibility; values withheld without a verified alignment method |
| Operations | ETag/`304`, `Cache-Control`, configurable rate limiting, request IDs, structured logs |
| Backend tests | 297 passing |
| Frontend tests | 54 unit/component and 24 Playwright tests; 6 axe scans |

Phase 4 keeps the scientific constraints explicit:

- Citations use stable file and row IDs, verified checksums, retrieval dates, and provenance. A known 404 file is never downloadable.
- Field metadata derives from the comparability registry and verified source-column mappings. Descriptions and methods are not invented.
- Measurement integrity flags registry fields that have no canonical values and blocks misleading comparable decisions. PSI-159 `pressure_initial_atm` and PSI-10 `pressure_approx_bar` are surfaced as missing with unit-specific alternatives.
- Publications preserve conflicting title/author variants and return missing year or venue as `null` with an explicit field status.
- Facets are computed from canonical rows, report qualified-row exclusions, and never merge PSI-10 atm with PSI-159 bar.
- `/compare` returns `paired_values.available=false` with `conditions_not_verified` or `no_verified_alignment`; the frontend renders a chart only for a future complete, verified contract.
- The API is public and read-only with no authentication; rate limiting is an abuse control, not authentication.

---

## Phase 5 results at release (2026-11-10)

Phase 5 adds an optional grounded assistant over the verified Phase 1–4 artifacts. The deterministic pipeline remains authoritative: the assistant selects only allowlisted tools, composes a draft from their results, resolves citations through the Phase 4 registry, and validates every claim before returning an answer. The Phase 6 section below records the current test counts and the improved retrieval metric.

| Phase 5 artifact | Result |
|---|---|
| API paths | 35 under `/api/v1`, including four assistant routes |
| Assistant tools | 22 deterministic, typed, allowlisted tools |
| Retrieval | 1,391 chunks from committed documentation and metadata cards; BM25 + deterministic hashed TF-IDF hybrid |
| Answer contract | Version `1.0.0` with evidence status, claims, citations, supporting data, limitations, tools, and validation |
| Golden set | 36 questions, version `1.0.1`; 36 / 36 passed |
| Citation validity | 117 / 117 references resolved |
| Supported claims | 59 / 59, each linked to a current tool call |
| Numerical exact match | 30 / 30 checks |
| Unit consistency | 30 / 30 checks |
| Correct refusals | 12 / 12 |
| Retrieval evaluation | 7 labelled cases; precision@5 `0.602381`, recall@5 `1.0`, MRR `0.761905` |
| Deterministic latency | mean `115.024 ms`, p95 `335.201 ms` (local run, not an SLO) |
| Backend tests | 483 passing |
| Frontend tests | 68 unit/component and 27 Playwright tests; 7 axe scans |

The assistant keeps these constraints explicit:

- No LLM is required. The deterministic provider is the default and the fallback.
- An optional OpenAI-compatible provider may only rephrase an already validated draft. It cannot select tools, see retrieved source instructions, add numbers, add citations, or bypass validation.
- Every number comes from a deterministic tool. Retrieved documents explain concepts, structure, publications, limitations, and methodology; they are not a numerical source.
- Missing values are never zero. PSI-10 atm and PSI-159 bar are never converted or merged without an approved rule.
- Paired values remain unavailable while the alignment registry is empty. The assistant states the withholding reason and produces no paired statistic.
- Retrieved text is untrusted evidence. Prompt injection cannot change tools, citations, secrets, or filesystem access.
- The frontend `/assistant` route shows the conversation, evidence panel, citation drawer, suggested questions, validation status, and scientific transparency. Exact serialized values are displayed without frontend rounding.
- The evaluation harness reports separate metrics, not one aggregate score. Failing-provider and deterministic mock-provider checks are software checks, not a real-model benchmark.

See `docs/assistant-tools.md`, `docs/assistant-retrieval.md`, `docs/assistant-evaluation.md`, and `docs/assistant-security.md`.

---

## Phase 6 results (2026-11-10)

Phase 6 adds production deployment, CI gates, operational visibility, provider hardening, a measured retrieval improvement, and a performance baseline. It does not change Phase 1–5 scientific decisions.

| Phase 6 artifact | Verified result |
|---|---|
| Deployment | Backend and frontend Dockerfiles plus Compose; native `uvicorn` and Next.js standalone production startup verified |
| Docker image build | Not executed: the local Docker daemon was inaccessible; documented as pending |
| CI | Default data-free workflow and manual full-data workflow in `.github/workflows/` |
| Data-free backend gate | 362 passed, 131 integration tests deselected in a clean worktree |
| Full backend suite | 493 passed, 1 warning |
| Frontend | 68 unit/component tests; lint, typecheck, and production build pass |
| Playwright | 27 passed, including 7 axe scans |
| Readiness | `/api/v1/ready` returns 200/503 with dataset and assistant-index checks |
| Metrics | `/api/v1/metrics` exposes bounded request, latency, rate-limit, assistant, tool, and token counters |
| Provider hardening | Bounded retries, `Retry-After`, request IDs, token usage, optional cost estimation, safe logs, deterministic fallback |
| Real-model evaluation | **Pending**: no provider credentials were available |
| Retrieval | MRR `1.0` (up from `0.761905`), precision@5 `0.602381`, recall@5 `1.0`, index `assistant-index-v1-796b45cda220` |
| Performance | 10 scenarios, 30 requests each, concurrency 8, 0 errors; telemetry p95 `604.966 ms`, deterministic assistant p95 `273.357 ms` |
| Security audit | Python runtime and frontend dependencies have no known vulnerabilities; full `npm audit` is clean after the Phase 7 Vitest upgrade and tested minimatch override |
| Reproduction | Committed artifacts, canonical validation, retrieval index, and deterministic assistant evaluation all pass |

The Phase 6 documents are `docs/phase6-deployment.md`, `docs/phase6-ci-cd.md`, `docs/phase6-operations.md`, `docs/phase6-security-review.md`, `docs/phase6-performance.md`, and `docs/phase6-real-model-evaluation.md`.

---

## Phase 7 results (2026-11-10)

Phase 7 closes release and competition gaps without changing the scientific model.

| Phase 7 artifact | Verified result |
|---|---|
| Dependency security | Vitest `4.1.12`, tested `minimatch@11.0.1` override; full `npm audit` reports 0 vulnerabilities |
| Restore drill | Isolated rebuild: 310 s total pipeline, exact dataset version, readiness, citation, deterministic assistant, and fallback verified |
| Scientific integrity | Pass with documented limits; explicit safety-ranking refusal added and tested |
| Docker | Image build and scan remain pending; Docker daemon inaccessible |
| Staging | Deployment recipe prepared; no hosted environment or credentials available |
| Real model | Pending credentials; no live-model result claimed |
| Backend tests | 496 passed |
| Frontend tests | 68 passed |
| Playwright / axe | 27 passed / 7 scans passed |
| Competition package | Demo script, checklist, FAQ, technical overview, integrity audit, restore record, release checklist |

Phase 7 documents: `docs/competition-technical-overview.md`,
`docs/competition-demo-script.md`, `docs/competition-demo-checklist.md`,
`docs/competition-faq.md`, `docs/scientific-integrity-audit.md`,
`docs/phase7-restore-drill.md`, and `docs/final-release-checklist.md`.

---

## Dataset roles

The MVP is deliberately small. The selection is recorded in `docs/decisions/0001-mvp-dataset-selection.md` and mirrored in `data/registry/mvp_dataset_catalog.json`.

| Role | Accessions | Use |
|---|---|---|
| **Primary** | PSI-10, PSI-100, PSI-101, PSI-159 | Gas-flame test tables, SAFFIRE-III telemetry, SAME-R smoke/detector data |
| **Supporting** | PSI-20, PSI-21, PSI-25, PSI-26, PSI-69, PSI-98, PSI-102 | Burner test-day summaries, BASS/BASS-II material matrices, FLEX droplet summary, SAFFIRE-I and SAME records |
| **Future** | PSI-23, PSI-39, PSI-106, PSI-107 | Large or unprocessed archives that need a separate format and access audit |
| **Context** | PSI-22, PSI-47, PSI-60, PSI-62, PSI-68, PSI-99, PSI-115, PSI-117, PSI-142 | Campaign/test-day summaries, condition ranges, publications, modeling studies, and indexes; not per-test measurement tables |

The four primary datasets are not interchangeable:

- **PSI-10 (ACME Flame Design)** and **PSI-159 (ACME CFI-G)** contain test-level gas-flame summary tables. They support filtering by fuel, oxygen, pressure, ignition, cool-flame flag, and extinction mode.
- **PSI-100 (SAFFIRE-III)** contains 1 Hz spacecraft telemetry: radiometers, anemometers, igniter voltage/current, air temperature, pressures, smoke-detector obscuration/scatter, fan differential pressure, body rates, and accelerations. It is engineering sensor data, not a processed flame-spread rate.
- **PSI-101 (SAME-R)** contains smoke/aerosol housekeeping data and detector response. It is not a flame-spread dataset.

BASS and BASS-II (PSI-25, PSI-26) publish test matrices and video, not a processed spread-rate table. The platform must not draw a spread-rate chart from them without a separate, validated computer-vision program.

---

## Repository contents

```text
.
├── README.md                         This file
├── AGENTS.md                         Rules for AI agents and automated contributors
├── PROJECT_ARCHITECTURE.md           Target system, data model, security, deployment
├── DEVELOPMENT_ROADMAP.md            Phases 0–7, exit gates, acceptance criteria
├── DATA_SOURCES.md                   Verified NASA source inventory and limitations
├── DATA_DICTIONARY.md                Exact headers, units, sentinels, canonical schema
├── API_DOCUMENTATION.md              Target API contract and implementation status
├── CONTRIBUTING.md                   Contribution workflow and review rules
├── requirements.txt                  Pinned test and development dependencies
├── requirements-prod.txt             Pinned runtime dependencies for containers
├── pytest.ini                        Test configuration and integration marker
├── Dockerfile                        Production FastAPI image
├── docker-compose.yml                Backend + frontend production topology
├── .dockerignore                     Keeps raw data and build caches out of images
├── .github/workflows/                Data-free CI and manual full-data workflows
├── .env.example                      Placeholder environment variables only
├── .gitignore                        Excludes raw data, secrets, and build artifacts
├── data/
│   ├── registry/
│   │   ├── annotations.json          Curated roles, rationales, limitations, checksums
│   │   ├── canonical_schema.json     Implemented Arrow schema for 13 canonical tables
│   │   ├── download_manifest.json    Curated 72-file acquisition selection
│   │   ├── experimental_table_schemas.json  Exact headers and row counts for 22 tables
│   │   ├── mvp_dataset_catalog.json  Machine-readable MVP selection
│   │   ├── psi_combustion_investigations.json
│   │   ├── psi_experimental_tables.csv  22-row experimental-table manifest
│   │   ├── psi_file_inventory.csv    16,354-row `added` file manifest
│   │   └── README.md                 Registry file guide
│   ├── manifests/
│   │   └── download_manifest.csv     Acquisition status, checksums, timestamps
│   ├── reports/
│   │   ├── acquisition_report.json   HTTP, size, checksum, and 404 verification
│   │   ├── assistant_evaluation.json Golden questions, citations, retrieval, provider checks
│   │   ├── phase6_performance.json   Benchmark environment, latency, errors, resources
│   │   ├── dataset_quality_report.json  Missingness, flags, channels, provenance
│   │   ├── processing_report.json    Canonical table counts and dataset version
│   │   └── validation_report.json    Acquisition and canonical gate results
│   ├── metadata/
│   │   ├── comparability_registry.json  93 measurements and 60 comparison rules
│   │   ├── serving_registry.json     9 dataset states and 93 measurement states
│   │   └── paired_alignment_registry.json  Verified paired-comparison methods (empty)
│   └── fixtures/
│       ├── csv/                      Seven exact excerpts from NASA sources
│       ├── fixtures_manifest.json    Source rows, checksums, and purpose
│       └── README.md                 Fixture provenance and regeneration
├── docs/
│   ├── decisions/
│   │   ├── 0001-mvp-dataset-selection.md
│   │   ├── 0002-phase-1-pipeline-contracts.md
│   │   └── 0003-phase-2-comparability-serving-and-api.md
│   ├── comparability.md              States, registry, decision order, restrictions
│   ├── serving-states.md             Dataset and measurement states by use
│   ├── query-contract.md             DuckDB operations, bounds, timeout, provenance
│   ├── api-implementation.md         Running service, routes, envelopes, errors
│   ├── phase4-contracts.md           Citations, files, fields, limitations, publications, facets
│   ├── comparison-alignment.md       Paired-comparison eligibility and withholding rules
│   ├── frontend-readiness.md         What the frontend may rely on and must not infer
│   ├── known-limitations.md          Consolidated scientific and API limitations
│   ├── phase5-assistant-architecture.md  Assistant components, trust boundaries, API
│   ├── assistant-answer-contract.md  Versioned answer schema and validation rules
│   ├── assistant-tools.md            Deterministic tool catalog and execution limits
│   ├── assistant-retrieval.md        Verified index, ranking, manifest, and retrieval eval
│   ├── assistant-evaluation.md       Golden set, metrics, thresholds, and limits
│   ├── assistant-security.md         Threat model, prompt injection, provider boundary
│   ├── phase6-implementation-plan.md Audit findings and milestone plan
│   ├── phase6-deployment.md          Containers, readiness, storage, recovery
│   ├── phase6-ci-cd.md               CI gates and clean-checkout limitations
│   ├── phase6-operations.md          Logs, metrics, runbook, privacy
│   ├── phase6-security-review.md     Security findings and residual risks
│   ├── phase6-performance.md         Benchmark methodology and baseline
│   ├── phase6-real-model-evaluation.md  Provider status and pending live evaluation
│   ├── competition-technical-overview.md  Problem, data, architecture, limits, evaluation
│   ├── competition-demo-script.md    End-to-end competition demonstration
│   ├── competition-demo-checklist.md Pre-demo verification checklist
│   ├── competition-faq.md            Judge and reviewer questions
│   ├── scientific-integrity-audit.md Phase 7 scientific claim audit
│   ├── phase7-restore-drill.md       Isolated recovery commands and results
│   ├── final-release-checklist.md    Release status and pending external items
│   ├── screenshots/phase3/           Captured views of the running frontend
│   └── research/
│       └── source-verification-log.md
├── scripts/
│   ├── build_assistant_index.py      Build or check the verified retrieval index
│   ├── build_download_manifest.py    Build or check the 72-file selection
│   ├── build_et_schemas.py           Build or check the 22-table schema registry
│   ├── build_fixtures.py             Build or check authentic parser fixtures
│   ├── build_mvp_catalog.py          Reproducible MVP catalog generator
│   ├── benchmark_api.py              Reproducible local API performance baseline
│   ├── build_phase2_registries.py    Comparability and serving registry generator
│   ├── download_psi_files.py         Thin wrapper around the acquisition CLI
│   ├── evaluate_assistant.py         Golden, retrieval, and provider-boundary evaluation
│   ├── fetch_psi_metadata.py         Standard-library PSI metadata collector
│   ├── verify_reproducibility.sh     Data-free and full-data reproducibility gates
│   └── README.md                     Script and CLI usage
├── src/data_pipeline/
│   ├── __main__.py                   `download`, `validate`, `parse`, `build-canonical`, `report`
│   ├── downloader.py                 Resumable, checksum-verifying acquisition
│   ├── manifest.py                   Curated selection and URL construction
│   ├── pipeline.py                   Parse orchestration and interim Parquet
│   ├── canonical.py                  Canonical builders and dataset version
│   ├── validation.py                 Acquisition and canonical gates
│   ├── quality.py                    Missingness and channel quality report
│   ├── schemas.py                    Arrow schemas and Parquet I/O
│   ├── channels.py                   Telemetry channel unit mappings
│   ├── provenance.py                 Source hashes, URLs, and observation IDs
│   ├── config.py                     Paths and version constants
│   └── parsers/                      CSV, XLSX, XLS, gas-flame, telemetry, smoke, material, droplet
├── src/analytics/
│   ├── catalog.py                    Authoritative dataset, measurement, rule, serving definitions
│   ├── registry.py                   Registry loaders and strict validation
│   ├── comparability.py              Comparability engine and decisions
│   ├── serving.py                    Serving-state engine
│   ├── db.py                         Bounded read-only DuckDB operations
│   ├── service.py                    API-ready envelopes over registries and queries
│   ├── citations.py                  File and row citations with checksums and row verification
│   ├── dataset_metadata.py           Curated files, field dictionaries, and limitations
│   ├── publications.py               Publication deduplication and verification
│   ├── facets.py                     Gas-flame facet counts and per-accession distributions
│   ├── paired.py                     Paired-value eligibility and withholding
│   ├── integrity.py                  Canonical-data presence checks
│   ├── errors.py                     Typed analytics errors and HTTP mapping
│   └── logging.py                    Structured logger helper
├── src/assistant/
│   ├── contract.py                   Versioned answer, claim, and citation models
│   ├── config.py                     Environment validation and safe fallback
│   ├── planner.py                    Deterministic topic and tool selection
│   ├── tools.py                      22 allowlisted deterministic tools
│   ├── retrieval.py                  Verified index, BM25 + TF-IDF hybrid, manifest
│   ├── composer.py                   Grounded answer templates and claims
│   ├── citation_validation.py        Phase 4 citation resolution
│   ├── claim_validation.py           Number, unit, scope, and forbidden-claim checks
│   ├── providers.py                  Deterministic and optional rephrase providers
│   ├── orchestrator.py               End-to-end pipeline and safe fallback
│   ├── evaluation.py                 Golden, retrieval, and provider metrics
│   └── conversation.py               Bounded, non-authoritative conversation state
├── backend/
│   ├── app.py                        FastAPI app, routes, readiness, metrics, CORS, cache, rate limit
│   ├── operations.py                 ETag, rate limiter, request limits, bounded metrics
│   └── models.py                     Pydantic envelopes and error models
├── frontend/
│   ├── src/app/                      Next.js App Router pages and route states, including /assistant
│   ├── src/components/               Layout, scientific, assistant, chart, and UI components
│   ├── src/lib/api/                  Centralized typed API client and TanStack hooks
│   ├── src/lib/assistant.ts          Assistant labels, tones, and exact value serialization
│   ├── tests/                        Vitest and React Testing Library suites
│   ├── e2e/                          Playwright critical flows and axe scans
│   ├── Dockerfile                    Multi-stage standalone production image
│   ├── .env.example                  Public frontend environment placeholders
│   └── README.md                     Frontend architecture, setup, and tests
└── tests/
    ├── test_*.py                     Unit tests, including synthetic API/DB contracts
    ├── test_analytics_integration.py Real canonical Parquet checks
    └── test_integration.py           Full raw/processed-data checks
```

Raw NASA files (`data/raw/`), interim parses (`data/interim/`), and processed Parquet (`data/processed/`) are **not** committed. They are reproducible artifacts stored outside Git. See `PROJECT_ARCHITECTURE.md` §6.

---

## Quick start

Phases 1–6 use a local virtual environment with pinned dependencies. The metadata collector itself remains standard-library only.

```bash
git clone https://github.com/YoussefHegazy74/flame-in-freefall.git
cd flame-in-freefall

python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt

# Verify committed metadata, selection, schema, and fixture snapshots.
python3 scripts/fetch_psi_metadata.py --check
python3 scripts/build_mvp_catalog.py --check
python3 scripts/build_download_manifest.py --check
python3 scripts/build_et_schemas.py --check
python3 scripts/build_fixtures.py --check
python -m src.data_pipeline manifest --check
python3 scripts/build_phase2_registries.py --check

# Build and validate the verified assistant retrieval index (gitignored).
python3 scripts/build_assistant_index.py
python3 scripts/build_assistant_index.py --check

# Run the deterministic assistant evaluation (writes data/reports/assistant_evaluation.json).
python3 scripts/evaluate_assistant.py --check

# Check the 72-file selection and limits without downloading.
python -m src.data_pipeline download --all --dry-run

# Acquire the curated selection into data/raw/ (gitignored).
python -m src.data_pipeline download --all

# Parse, build canonical Parquet, validate, and write reports.
python -m src.data_pipeline parse
python -m src.data_pipeline build-canonical
python -m src.data_pipeline validate
python -m src.data_pipeline report

# Run unit tests, then full-data integration tests.
python -m pytest -m "not integration"
python -m pytest -m integration

# Verify committed artifacts without canonical data.
PYTHON=.venv/bin/python bash scripts/verify_reproducibility.sh

# Run the read-only API against the canonical data.
uvicorn backend.app:app --host 127.0.0.1 --port 8000
# OpenAPI: http://127.0.0.1:8000/api/v1/docs
# Readiness: http://127.0.0.1:8000/api/v1/ready
# Metrics:   http://127.0.0.1:8000/api/v1/metrics

# In a second terminal, run the frontend against that API.
cd frontend
cp .env.example .env.local
npm install
npm run dev
# Frontend: http://localhost:3000

# Production frontend (after npm ci):
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1 npm run build
npm start

# Production Docker topology (requires a Docker daemon):
docker compose up --build -d
curl http://127.0.0.1:8000/api/v1/ready
# Frontend: http://localhost:3000
```

`download --all` selects exactly the 72 files in `data/registry/download_manifest.json` (56,238,344 bytes). The downloader refuses selections above 100 files or 100,000,000 bytes unless `--allow-large` is passed. It never downloads the full archive.

The metadata collector does **not** download experimental data files. The pipeline downloader does, but only the curated selection. Raw files are chmod 444 and remain outside Git. The 22 experimental tables, telemetry exports, HKP CSVs, workbooks, and test log have exact checksums and retrieval timestamps in `data/manifests/download_manifest.csv` and `data/reports/acquisition_report.json`.

---

## Documentation map

| Question | Read |
|---|---|
| What NASA data exists, and what is missing? | `DATA_SOURCES.md` |
| What does each field mean, and in what unit? | `DATA_DICTIONARY.md` |
| How will the system be built? | `PROJECT_ARCHITECTURE.md` |
| What is the build order and what counts as done? | `DEVELOPMENT_ROADMAP.md` |
| What will the API look like? | `API_DOCUMENTATION.md` |
| What does the running API implement? | `docs/api-implementation.md` |
| What are the Phase 4 citation/file/field/publication/facet contracts? | `docs/phase4-contracts.md` |
| How are paired comparisons aligned or withheld? | `docs/comparison-alignment.md` |
| How are comparisons decided? | `docs/comparability.md` |
| When may a dataset be served? | `docs/serving-states.md` |
| How does DuckDB query the canonical tables? | `docs/query-contract.md` |
| How does the assistant work end to end? | `docs/phase5-assistant-architecture.md` |
| What can the assistant do, and what can it not do? | `docs/assistant-answer-contract.md` |
| Which tools may the assistant call? | `docs/assistant-tools.md` |
| How are documents retrieved and ranked? | `docs/assistant-retrieval.md` |
| How is the assistant evaluated? | `docs/assistant-evaluation.md` |
| How is prompt injection handled? | `docs/assistant-security.md` |
| How is the platform deployed? | `docs/phase6-deployment.md` |
| What does CI run, and what needs full data? | `docs/phase6-ci-cd.md` |
| How are logs, readiness, and metrics operated? | `docs/phase6-operations.md` |
| What did the security review find? | `docs/phase6-security-review.md` |
| What is the performance baseline? | `docs/phase6-performance.md` |
| Was a real model evaluated? | `docs/phase6-real-model-evaluation.md` |
| What is the competition technical overview? | `docs/competition-technical-overview.md` |
| How do I run the demo? | `docs/competition-demo-script.md` |
| What should I check before the demo? | `docs/competition-demo-checklist.md` |
| What are likely judge questions? | `docs/competition-faq.md` |
| What did the scientific integrity audit find? | `docs/scientific-integrity-audit.md` |
| Did the restore drill succeed? | `docs/phase7-restore-drill.md` |
| Is the release complete? | `docs/final-release-checklist.md` |
| What can the frontend rely on? | `docs/frontend-readiness.md` |
| How does the frontend work, and how is it tested? | `frontend/README.md` |
| What is known to be limited or unavailable? | `docs/known-limitations.md` |
| Why were these datasets selected? | `docs/decisions/0001-mvp-dataset-selection.md` |
| How was each source verified? | `docs/research/source-verification-log.md` |
| How do I contribute? | `CONTRIBUTING.md` |
| What are the rules for AI agents? | `AGENTS.md` |

---

## Scientific rules

These rules are binding for code, charts, prose, and assistant answers:

1. **Never invent data.** No synthetic rows, no estimated measurements, no fabricated test identifiers, no invented team members.
2. **Preserve provenance.** Every observation carries the accession, file, sheet, row, checksum, and retrieval date.
3. **Do not coerce missingness to zero.** Blank cells, `-`, `n/a`, `none`, `OR`, `RAMP`, `RAMPED`, `LOW O2`, `#DIV/0!`, `#VALUE!`, `-999`, and sentinel timestamps are flagged, not filled.
4. **Do not guess units.** If the source does not state a unit, the dictionary says `not stated`.
5. **Label computed values.** `Tad (K)` and `Zst` are computed; peak burner temperature is measured. They are different variables.
6. **Compare only equivalent fields.** Cross-dataset joins require a documented mapping. Mole fraction and percent by volume are convertible, but the conversion must be explicit.
7. **No arbitrary risk score.** The MVP does not rank materials or tests on an invented index. Any future ranking needs a published formula, validated inputs, uncertainty, and review.
8. **Do not imply NASA endorsement.** NASA data are used under their published terms; this is an independent challenge project.

---

## Current status and next steps

**Done in Phase 0**

- Verified the PSI API, the 24 combustion records, the download endpoint, the `added` inventory, and the `experimentalTable` inventory.
- Recorded exact headers, row counts, missingness, sentinel tokens, and SHA-256 checksums.
- Wrote the source inventory, data dictionary, architecture, roadmap, API contract, and contribution rules.
- Generated a reproducible metadata registry and MVP catalog.

**Done in Phase 1**

- Built a curated 72-file acquisition manifest (56,238,344 bytes) with explicit limits and two documented 404s.
- Implemented a resumable, checksum-verifying downloader with HTTP status, size, SHA-256, retrieval time, and duplicate detection.
- Implemented modular CSV/XLSX/XLS parsers for gas-flame, telemetry, smoke, material, droplet, test-log, and all 22 summary tables.
- Built 13 canonical Parquet tables with row-level provenance and explicit quality flags.
- Added seven authentic NASA fixtures and 150 tests, including failure behavior for missing files and unexpected headers.
- Wrote acquisition, validation, processing, schema, and dataset-quality reports.
- Verified all 72 selected files and all 13 canonical tables.

**Done in Phase 2**

- Added a committed comparability registry with 93 measurements and 60 pair-specific rules; unknown pairs default to `not_comparable`.
- Added a committed serving registry with 9 dataset states and 93 measurement states across `exploration`, `quantitative_comparison`, `time_series`, and `provenance`.
- Implemented a bounded, read-only DuckDB layer with parameterized filters, pagination, series caps, sentinel exclusion, provenance resolution, quality slices, and a timeout watchdog.
- Implemented a FastAPI service with 23 paths, one success envelope, one error envelope, strict query allowlisting, request IDs, environment-driven CORS, and OpenAPI.
- Added 120 tests for comparability, serving, DuckDB, API contracts, invalid inputs, blocked comparisons, and real canonical integration.
- Documented comparability, serving states, the query contract, the API implementation, and frontend readiness.

**Done in Phase 3 (frontend)**

- Built a Next.js App Router frontend with a responsive scientific interface, accessible navigation, breadcrumbs, and consistent loading, empty, error, and warning states.
- Implemented a centralized typed API client and TanStack Query hooks over the existing read-only API, preserving `data`, `meta`, `quality`, and `provenance` envelopes.
- Delivered the overview, investigation catalog and detail, dataset catalog and detail, gas-flame, material, droplet, telemetry, smoke, comparison, quality, provenance, and methods pages.
- Kept backend comparability and serving decisions authoritative; blocked comparisons render no chart, and conditional comparisons require explicit verified conditions.
- Preserved run identity, time units, raw/calibrated status, sentinel handling, unit ambiguities, and series caps in every scientific view.
- Added 41 unit/component tests, 17 real-backend Playwright flows, and 4 axe WCAG 2.1 A/AA scans at delivery.
- Verified the production build and documented the frontend architecture and known backend gaps.

**Done in Phase 4 (scientific metadata and comparison contracts)**

- Added citations, dataset files, field dictionaries, limitations, publications, gas-flame facets, and paired-value eligibility to the read-only API.
- Added measurement-integrity checks that surface registry fields with no canonical values and block misleading comparable decisions.
- Added ETag/`304`, `Cache-Control`, configurable rate limiting, request IDs, and structured request logs.
- Integrated the citation drawer, file browser, field dictionary, limitations panel, publications list/detail, dynamic facets, and comparison-integrity/paired-value panels into the frontend.
- Added 27 backend tests and 13 frontend unit/component tests; extended Playwright to 24 flows and axe to 6 scans.
- Documented the Phase 4 contracts, comparison alignment methodology, cache/rate-limit configuration, and known limitations.

**Done in Phase 5 (grounded research assistant)**

- Froze the versioned answer contract with evidence status, structured claims, citations, supporting data, limitations, tool calls, and validation.
- Added 22 allowlisted deterministic tools over the Phase 1–4 service; no arbitrary SQL, paths, URLs, or code execution.
- Built a reproducible retrieval index over committed documentation and metadata cards with BM25 + deterministic hashed TF-IDF ranking and a source-hash manifest.
- Implemented the deterministic planner, composer, citation validator, claim validator, bounded conversation memory, and safe provider fallback.
- Added an optional OpenAI-compatible provider that may only rephrase a validated deterministic draft; it cannot select tools, add numbers, add citations, or bypass validation.
- Added the `/assistant` frontend with conversation, evidence panel, citation drawer, suggested questions, provider/fallback status, and scientific transparency.
- Added 36 golden questions, 7 labelled retrieval cases, adversarial and prompt-injection tests, provider-failure tests, and an evaluation report with separate metrics.
- Verified 483 backend tests, 68 frontend unit/component tests, 27 Playwright tests, 7 axe scans, and a production build.

**Done in Phase 6 (production readiness)**

- Added production Dockerfiles, Compose topology, non-root users, read-only data/index mounts, and health checks.
- Verified native Uvicorn and Next.js standalone production startup; Docker image build remains pending because the local daemon was inaccessible.
- Added `/api/v1/ready` and `/api/v1/metrics`, bounded operational counters, request-size limits, and security headers.
- Added default data-free and manual full-data GitHub Actions workflows, dependency audits, and a reproducibility script.
- Hardened the optional provider with bounded retries, `Retry-After`, request IDs, token usage, optional cost estimation, and safe logs.
- Improved retrieval MRR from `0.761905` to `1.0` with a measured source-aware ranking change; recall stayed `1.0`.
- Recorded a 10-scenario performance baseline with 0 errors; 493 backend tests, 68 frontend tests, 27 Playwright tests, and 7 axe scans pass.
- Documented deployment, CI/CD, operations, security review, performance, backup/recovery, and the pending real-model evaluation.

**Done in Phase 7 (final release and competition readiness)**

- Audited the repository at `be777e7` and preserved the Phase 1–6 implementation.
- Upgraded Vitest to `4.1.12` and applied a tested `minimatch@11.0.1` override; full `npm audit` is clean.
- Completed an isolated restore drill: 310 s pipeline, exact dataset version, readiness, citation, deterministic assistant, and fallback verified.
- Completed the scientific integrity audit and added explicit safety-ranking refusals.
- Prepared the staging recipe, competition technical overview, demo script, checklist, FAQ, integrity audit, restore record, and final release checklist.
- Verified 496 backend tests, 68 frontend tests, 27 Playwright tests, 7 axe scans, canonical validation, retrieval index, and 36/36 golden questions.
- Docker image build/scan and hosted staging remain pending external environments; live-model evaluation remains pending credentials.

**Next (Phase 8 and later)**

1. Build and scan the Docker images on a Docker-capable host and run the Compose smoke test.
2. Deploy the prepared staging topology and verify HTTPS, CORS, readiness, and logging.
3. Record a live-model evaluation when provider credentials are available.
4. Add a verified paired-comparison executor only after a committed alignment method names exact keys, value fields, and units.
5. Revisit authentication only if private data or write operations are added.

The full sequence and exit gates are in `DEVELOPMENT_ROADMAP.md`.

---

## Attribution

Data source: **NASA Physical Sciences Informatics (PSI)**, <https://psi.nasa.gov/physci/repo>. Individual dataset DOIs are recorded in `DATA_SOURCES.md` §7.3 and in each record card.

NASA does not endorse this project. Any interpretation, visualization, or statement produced by this platform is the responsibility of Team AFAQ, not NASA.

Team member names and roles are not listed because the public challenge profile does not expose a verified roster. Do not add names without consent and a verifiable source.

---

## License

No license has been selected yet. Do not add a license file or reuse the code under a declared license until Team AFAQ makes that decision. NASA data remain subject to NASA's terms and the terms of the originating repository.
