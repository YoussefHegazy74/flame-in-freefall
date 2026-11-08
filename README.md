# Flame in Freefall

**Team:** AFAQ
**Challenge:** Flame in Freefall: SI-Powered Fire Safety Insights from Microgravity Combustion Data
**Event:** NASA Space Apps Challenge 2026, Shebeen El-Kom, Egypt
**Repository:** <https://github.com/YoussefHegazy74/flame-in-freefall>

Flame in Freefall is a data platform for exploring NASA's microgravity combustion research with spacecraft fire safety in mind. It starts from verified data in the NASA Physical Sciences Informatics (PSI) repository, preserves the original values, units, missingness, and provenance, and builds analysis and interface layers only after the scientific foundation is reviewable.

This repository is currently at **Phase 1: NASA data acquisition, validation, parsing, and canonical Parquet outputs**. It contains verified source documentation, a curated 72-file acquisition manifest, a checksum-verifying downloader, modular CSV/XLSX/XLS parsers, 13 canonical Parquet tables, machine-readable validation and quality reports, and 150 passing tests. It does **not** yet contain a running API, frontend, or assistant, and it does not claim results that have not been computed from source data.

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

Acquisition validation passed for 72 of 72 selected files. Canonical validation passed all 13 table checks with 0 failures. The quality report records 6 issues: 0 errors, 5 warnings, and 1 informational note. The test suite passes **150 tests**: 136 unit tests and 14 integration tests.

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
├── API_DOCUMENTATION.md              Target read-only API contract (not implemented yet)
├── CONTRIBUTING.md                   Contribution workflow and review rules
├── requirements.txt                  Pinned Phase 1 runtime and test dependencies
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
│   └── fixtures/
│       ├── csv/                      Seven exact excerpts from NASA sources
│       ├── fixtures_manifest.json    Source rows, checksums, and purpose
│       └── README.md                 Fixture provenance and regeneration
├── docs/
│   ├── decisions/
│   │   ├── 0001-mvp-dataset-selection.md
│   │   └── 0002-phase-1-pipeline-contracts.md
│   └── research/
│       └── source-verification-log.md
├── scripts/
│   ├── build_download_manifest.py    Build or check the 72-file selection
│   ├── build_et_schemas.py           Build or check the 22-table schema registry
│   ├── build_fixtures.py             Build or check authentic parser fixtures
│   ├── build_mvp_catalog.py          Reproducible MVP catalog generator
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
└── tests/
    ├── test_*.py                     Unit tests
    └── test_integration.py           Full raw/processed-data checks
```

Raw NASA files (`data/raw/`), interim parses (`data/interim/`), and processed Parquet (`data/processed/`) are **not** committed. They are reproducible artifacts stored outside Git. See `PROJECT_ARCHITECTURE.md` §6.

---

## Quick start

Phase 1 uses a local virtual environment with pinned dependencies. The metadata collector itself remains standard-library only.

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

**Next (Phase 2 and later)**

1. Add the comparability allowlist and blocked-dataset serving state described in `DEVELOPMENT_ROADMAP.md` Phase 2.
2. Evaluate DuckDB query patterns over the canonical Parquet tables and document the serving contract.
3. Build the read-only API.
4. Build the frontend only after the API contract and data gates are stable.
5. Add the grounded insight layer last, with citations and a golden-set evaluation.

The full sequence and exit gates are in `DEVELOPMENT_ROADMAP.md`.

---

## Attribution

Data source: **NASA Physical Sciences Informatics (PSI)**, <https://psi.nasa.gov/physci/repo>. Individual dataset DOIs are recorded in `DATA_SOURCES.md` §7.3 and in each record card.

NASA does not endorse this project. Any interpretation, visualization, or statement produced by this platform is the responsibility of Team AFAQ, not NASA.

Team member names and roles are not listed because the public challenge profile does not expose a verified roster. Do not add names without consent and a verifiable source.

---

## License

No license has been selected yet. Do not add a license file or reuse the code under a declared license until Team AFAQ makes that decision. NASA data remain subject to NASA's terms and the terms of the originating repository.
