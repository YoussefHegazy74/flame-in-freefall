# Flame in Freefall

**Team:** AFAQ
**Challenge:** Flame in Freefall: SI-Powered Fire Safety Insights from Microgravity Combustion Data
**Event:** NASA Space Apps Challenge 2026, Shebeen El-Kom, Egypt
**Repository:** <https://github.com/YoussefHegazy74/flame-in-freefall>

Flame in Freefall is a data platform for exploring NASA's microgravity combustion research with spacecraft fire safety in mind. It starts from verified data in the NASA Physical Sciences Informatics (PSI) repository, preserves the original values, units, missingness, and provenance, and builds analysis and interface layers only after the scientific foundation is reviewable.

This repository is currently at **Milestone 0: scientific foundation and metadata registry**. It contains verified source documentation, a reproducible metadata collector, a machine-readable inventory, and the target architecture and API contract. It does **not** yet contain a running API, frontend, or assistant, and it does not claim results that have not been computed from source data.

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
├── .env.example                      Placeholder environment variables only
├── .gitignore                        Excludes raw data, secrets, and build artifacts
├── data/
│   ├── registry/
│   │   ├── annotations.json          Curated roles, rationales, limitations, checksums
│   │   ├── mvp_dataset_catalog.json  Machine-readable MVP selection
│   │   ├── psi_combustion_investigations.json
│   │   ├── psi_experimental_tables.csv  22-row experimental-table manifest
│   │   ├── psi_file_inventory.csv    16,354-row `added` file manifest
│   │   └── README.md                 Registry file guide
│   └── fixtures/                     Small real-header fixtures (added in Phase 1)
├── docs/
│   ├── decisions/
│   │   └── 0001-mvp-dataset-selection.md
│   └── research/
│       └── source-verification-log.md
└── scripts/
    ├── build_mvp_catalog.py          Reproducible MVP catalog generator
    ├── fetch_psi_metadata.py         Standard-library PSI metadata collector
    └── README.md                     Script usage
```

Raw NASA files, interim parses, and processed Parquet tables are **not** committed. They are reproducible artifacts stored outside Git. See `PROJECT_ARCHITECTURE.md` §6.

---

## Quick start

The metadata collector uses only the Python 3 standard library. No virtual environment is required for the foundation milestone.

```bash
git clone https://github.com/YoussefHegazy74/flame-in-freefall.git
cd flame-in-freefall

# Verify that the committed snapshot still matches the live NASA PSI API.
python3 scripts/fetch_psi_metadata.py --check

# Regenerate the snapshot from the live API (writes into data/registry/).
python3 scripts/fetch_psi_metadata.py

# Regenerate from cached detail JSON without hitting the API.
python3 scripts/fetch_psi_metadata.py --details-dir /tmp/psi_details

# Regenerate the MVP catalog and verify it matches the committed file.
python3 scripts/build_mvp_catalog.py
python3 scripts/build_mvp_catalog.py --check
```

`--check` exits with status 1 and prints every changed accession, field, and value when the live API drifts from the committed snapshot. It never rewrites the snapshot.

The collector does **not** download experimental data files. It records file names, sizes, formats, categories, and versions only. The 22 experimental tables were downloaded and inspected during the research phase; their row counts, column counts, and SHA-256 checksums are recorded in `data/registry/annotations.json` and `data/registry/psi_experimental_tables.csv`.

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

**Done**

- Verified the PSI API, the 24 combustion records, the download endpoint, the `added` inventory, and the `experimentalTable` inventory.
- Downloaded and inspected all 22 experimental tables plus the MVP telemetry samples, readmes, and metadata packages.
- Recorded exact headers, row counts, missingness, sentinel tokens, and SHA-256 checksums.
- Wrote the source inventory, data dictionary, architecture, roadmap, API contract, and contribution rules.
- Generated a reproducible metadata registry and MVP catalog.

**Next**

1. Run `python3 scripts/fetch_psi_metadata.py --check` and confirm no drift.
2. Build the download manifest and checksum manifest for the MVP files.
3. Add pinned parser dependencies (`polars`, `pyarrow`, `openpyxl`, `xlrd`) and small real-header fixtures.
4. Implement and test the PSI-10 and PSI-159 parsers first.
5. Implement the PSI-100 and PSI-101 parsers next.
6. Build the read-only API, then the frontend, then the grounded insight layer.

The full sequence and exit gates are in `DEVELOPMENT_ROADMAP.md`.

---

## Attribution

Data source: **NASA Physical Sciences Informatics (PSI)**, <https://psi.nasa.gov/physci/repo>. Individual dataset DOIs are recorded in `DATA_SOURCES.md` §7.3 and in each record card.

NASA does not endorse this project. Any interpretation, visualization, or statement produced by this platform is the responsibility of Team AFAQ, not NASA.

Team member names and roles are not listed because the public challenge profile does not expose a verified roster. Do not add names without consent and a verifiable source.

---

## License

No license has been selected yet. Do not add a license file or reuse the code under a declared license until Team AFAQ makes that decision. NASA data remain subject to NASA's terms and the terms of the originating repository.
