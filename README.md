# Flame in Freefall

**Team:** AFAQ
**Challenge:** Flame in Freefall: SI-Powered Fire Safety Insights from Microgravity Combustion Data
**Event:** NASA Space Apps Challenge 2026, Shebeen El-Kom, Egypt
**Repository:** <https://github.com/YoussefHegazy74/flame-in-freefall>

Flame in Freefall is a data platform for exploring NASA's microgravity combustion research with spacecraft fire safety in mind. It starts from verified data in the NASA Physical Sciences Informatics (PSI) repository, preserves the original values, units, missingness, and provenance, and builds analysis and interface layers only after the scientific foundation is reviewable.

This repository now includes **Phase 3: a working scientific frontend over the Phase 2 service**. It contains verified source documentation, a curated 72-file acquisition manifest, a checksum-verifying downloader, modular CSV/XLSX/XLS parsers, 13 canonical Parquet tables, machine-readable validation and quality reports, two committed scientific registries, a read-only FastAPI service, and a Next.js exploration interface. The backend suite has **270 passing tests**; the frontend has **41 unit/component tests and 17 real-backend Playwright tests**. It does **not** yet contain the grounded assistant, and it does not claim results that have not been computed from source data.

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

Phase 2 adds scientific state and a read-only service on top of the canonical tables. It does not change a canonical value, unit, or quality flag. This delivery milestone completes roadmap Phase 2 and the core of roadmap Phase 3; the remaining API contract gaps are tracked in `DEVELOPMENT_ROADMAP.md` §6.5.

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
| Charts | Recharts 3.10.1, lazy-loaded, time-series panels only |
| Routes | 14 required pages, including investigation/dataset detail and four experiment explorers |
| Unit and component tests | 41 passing (Vitest + React Testing Library) |
| End-to-end tests | 17 passing (Playwright against the real backend and canonical data) |
| Accessibility | 4 axe WCAG 2.1 A/AA scans, 0 serious or critical violations |
| Production build | `npm run build` succeeds with explicit webpack builder |

The interface keeps these scientific constraints visible:

- Missing values are never rendered as zero; raw and calibrated channels are grouped and labeled separately.
- Telemetry and smoke runs remain separate, preserve backend time units, and respect the 20,000-point and 8-channel caps. `413 range_too_large` responses show the actual point count and suggested span without silent retry.
- Gas-flame pressure filters and material oxygen filters require an explicit accession because the units and fields differ across PSI-10/PSI-159 and PSI-25/PSI-26.
- PSI-26 oxygen ambiguity, PSI-69 `Burning rate; mm`, uncalibrated PSI-100 channels, and SAME-R `-999` sentinels are surfaced on the relevant pages.
- Comparison status comes from `/compare`; blocked comparisons render reasons and no chart, and conditional comparisons require explicit condition checkboxes.
- No browser-side aggregation, interpolation, downsampling, unit conversion, risk score, or material ranking is performed.

Frontend setup, architecture, and test commands are in `frontend/README.md`. The interface deliberately does not invent capabilities the API lacks: there is no citation drawer, file/publication browser, paired comparison chart, or assistant.

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
├── requirements.txt                  Pinned Phase 1 and Phase 2 dependencies
├── pytest.ini                        Test configuration and integration marker
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
│   │   ├── dataset_quality_report.json  Missingness, flags, channels, provenance
│   │   ├── processing_report.json    Canonical table counts and dataset version
│   │   └── validation_report.json    Acquisition and canonical gate results
│   ├── metadata/
│   │   ├── comparability_registry.json  93 measurements and 60 comparison rules
│   │   └── serving_registry.json     9 dataset states and 93 measurement states
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
│   ├── frontend-readiness.md         What the frontend may rely on and must not infer
│   ├── known-limitations.md          Consolidated scientific and API limitations
│   ├── screenshots/phase3/           Captured views of the running frontend
│   └── research/
│       └── source-verification-log.md
├── scripts/
│   ├── build_download_manifest.py    Build or check the 72-file selection
│   ├── build_et_schemas.py           Build or check the 22-table schema registry
│   ├── build_fixtures.py             Build or check authentic parser fixtures
│   ├── build_mvp_catalog.py          Reproducible MVP catalog generator
│   ├── build_phase2_registries.py    Comparability and serving registry generator
│   ├── download_psi_files.py         Thin wrapper around the acquisition CLI
│   ├── fetch_psi_metadata.py         Standard-library PSI metadata collector
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
│   ├── errors.py                     Typed analytics errors and HTTP mapping
│   └── logging.py                    Structured logger helper
├── backend/
│   ├── app.py                        FastAPI app, routes, strict query validation, CORS
│   └── models.py                     Pydantic envelopes and error models
├── frontend/
│   ├── src/app/                      Next.js App Router pages and route states
│   ├── src/components/               Layout, scientific, chart, and UI components
│   ├── src/lib/api/                  Centralized typed API client and TanStack hooks
│   ├── tests/                        Vitest and React Testing Library suites
│   ├── e2e/                          Playwright critical flows and axe scans
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

Phase 1 and Phase 2 use a local virtual environment with pinned dependencies. The metadata collector itself remains standard-library only.

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

# Run the read-only API against the canonical data.
uvicorn backend.app:app --host 127.0.0.1 --port 8000
# OpenAPI: http://127.0.0.1:8000/api/v1/docs

# In a second terminal, run the frontend against that API.
cd frontend
cp .env.example .env.local
npm install
npm run dev
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
| How are comparisons decided? | `docs/comparability.md` |
| When may a dataset be served? | `docs/serving-states.md` |
| How does DuckDB query the canonical tables? | `docs/query-contract.md` |
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
- Added 41 unit/component tests, 17 real-backend Playwright flows, and 4 axe WCAG 2.1 A/AA scans.
- Verified the production build and documented the frontend architecture and known backend gaps.

**Next (remaining API gaps, then Phase 5 and later)**

1. Finish the remaining API gaps: citation records, file/field/publication endpoints, facets, ETag/cache headers, and rate limiting.
2. Add the citation drawer, file/publication browsing, and paired comparison values once those contracts exist.
3. Add the Phase 5 grounded insight layer last, with citations and a golden-set evaluation.
4. Add Phase 6 CI/CD, deployment, and observability.

The full sequence and exit gates are in `DEVELOPMENT_ROADMAP.md`.

---

## Attribution

Data source: **NASA Physical Sciences Informatics (PSI)**, <https://psi.nasa.gov/physci/repo>. Individual dataset DOIs are recorded in `DATA_SOURCES.md` §7.3 and in each record card.

NASA does not endorse this project. Any interpretation, visualization, or statement produced by this platform is the responsibility of Team AFAQ, not NASA.

Team member names and roles are not listed because the public challenge profile does not expose a verified roster. Do not add names without consent and a verifiable source.

---

## License

No license has been selected yet. Do not add a license file or reuse the code under a declared license until Team AFAQ makes that decision. NASA data remain subject to NASA's terms and the terms of the originating repository.
