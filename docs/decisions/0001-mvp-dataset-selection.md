# ADR 0001 — MVP Dataset Selection

- **Status:** Accepted
- **Date:** 2026-11-08
- **Decision owners:** Team AFAQ
- **Supersedes:** None
- **Related:** `DATA_SOURCES.md`, `DATA_DICTIONARY.md`, `data/registry/mvp_dataset_catalog.json`

---

## 1. Context

The challenge asks for fire-safety insights from NASA microgravity-combustion data. NASA PSI exposes 24 Combustion Science investigations. They differ by:

- experiment family (ACME, BASS, SAFFIRE, SAME, FLEX, CFI, SPICE, SLICE, DAFT);
- public artifact type (`added` archive, `experimentalTable` summary, both, or neither);
- size (from 0.00 GB to 2,180.44 GB registered);
- format (CSV, XLSX, XLS, MP4, ZIP, PDF, DOCX, TXT, instrument-specific files);
- whether the public table is a per-test measurement table, a test-day summary, a condition list, or an index;
- access failures (some listed files return HTTP 404).

A small, defensible MVP is better than a broad catalog that implies analysis the public data cannot support. The selection must be reproducible and must not be driven by narrative convenience.

---

## 2. Decision

Use four **primary** datasets, seven **supporting** datasets, four **future** datasets, and nine **context** datasets. Do not use an `inaccessible` role. Classify each record with `archive_status`:

- `available` — at least one `added` file is exposed;
- `experimental_table_only` — zero `added` files but at least one public `experimentalTable`;
- `no_public_files` — neither.

No record in the current 24-record collection is `no_public_files`.

### 2.1 Primary datasets

| Accession | Dataset | Why primary | What it supports |
|---|---|---|---|
| PSI-10 | ACME Flame Design | 207 normal + 120 inverse per-test gas-flame rows; fuel, oxygen, pressure, mass flows, `Zst`, computed `Tad`, flame type, comments | Gas-flame condition comparison and test-level exploration |
| PSI-159 | ACME CFI-G | 179 normal + 154 valid inverse per-test gas-flame rows; cool-flame flag, hot ignition, extinction mode, burn time, measured peak burner temperature, computed `Tad`/`Zst` | Cool-flame and ignition/extinction exploration |
| PSI-100 | SAFFIRE-III | 1 Hz spacecraft telemetry: radiometers, anemometers, igniters, air temperature, pressures, smoke detectors, fan differential pressure, body rates, accelerations | Time-series fire-environment exploration |
| PSI-101 | SAME-R | 98-channel HKP smoke/aerosol telemetry plus a 109-row sample/test log | Smoke-detector and aerosol-response exploration |

These four cover four different physical domains: gas-flame conditions, cool-flame ignition/extinction, spacecraft fire telemetry, and smoke/detector response. They are not interchangeable and must not be merged on a single axis.

### 2.2 Supporting datasets

| Accession | Dataset | Why supporting | Limit |
|---|---|---|---|
| PSI-20 | ACME BRE | Burner-size and test-day context | 18-row summary; chamber pressure not identified |
| PSI-21 | ACME CLD Flame | Coflow test-day context | 32-row summary; MFC units not stated |
| PSI-25 | BASS-II | Solid-material test matrix; 129 rows, 17-column combined table; flow, O2/CO2/CO, frame counts | No processed spread-rate table |
| PSI-26 | BASS | Solid-material test log and as-run matrix | No processed spread-rate table; free-text numeric columns |
| PSI-69 | FLEX | 274-row droplet-combustion summary: burning rate, burn time, extinction diameter | Droplet combustion, not flame spread; `experimental_table_only` |
| PSI-98 | SAFFIRE-I | Mission/sample context and image-set documentation | Telemetry XLSX files return 404 |
| PSI-102 | SAME | Earlier smoke/aerosol workbooks and 8-row sample summary | Legacy `.xls`; not a standardized table |

### 2.3 Future datasets

| Accession | Dataset | Why deferred | Prerequisite |
|---|---|---|---|
| PSI-23 | ACME s-Flame | 4,163 `added` files; 18-row test-day summary only | Archive format audit |
| PSI-39 | CFI | 2,831 raw files; 87-row test-condition log only; sampled 404 | Parser and access audit |
| PSI-106 | SLICE | 12-row, 2-column table with no measured variables | Additional data |
| PSI-107 | SPICE | 469-row flame-length/airflow table; raw XLS/XLSX need audit | Format audit |

### 2.4 Context datasets

| Accession | Dataset | Why context |
|---|---|---|
| PSI-22 | ACME E-FIELD Flames | `experimental_table_only`; 32-row test-day summary; no per-test measurements |
| PSI-47 | DAFT / DAFT-2 | 2-row instrument session log; not a combustion measurement dataset |
| PSI-60 | Ground SPICE analysis | One metadata file; modeling context |
| PSI-62 | Ground BASS flame-spread modeling | One metadata file; modeling context |
| PSI-68 | FLEX-2 | `experimental_table_only`; 8-row condition-range table, not measurements |
| PSI-99 | SAFFIRE-II | `experimental_table_only`; 15-row sample summary; 1-g comparisons only |
| PSI-115 | Ground SAME smoke modeling | Model context |
| PSI-117 | Ground cool-flame CFD | Model context |
| PSI-142 | CFE/HFE data index | 8-row figure/publication index; no measurements |

---

## 3. Selection rules

A dataset is **primary** only if all of the following hold:

1. It is a NASA PSI Combustion Science investigation with a public detail endpoint.
2. It exposes at least one public artifact, either an `added` file or an `experimentalTable` entry.
3. It contains a public tabular artifact that supports test-level or time-series analysis.
4. The table is not merely a test-day count, condition list, sample list, or publication index.
5. Its fields can be mapped to the data dictionary with explicit units and missingness.

A dataset is **supporting** if it adds material, flow, mission, droplet, or comparison context but cannot carry the primary analysis alone.

A dataset is **future** if it is scientifically relevant but needs a format, parser, or access audit before use.

A dataset is **context** if it is a publication, model, index, test-day summary, condition range, or sample list rather than a per-test measurement table.

A dataset is **not selected to fill a narrative gap.** If the public data do not support a claim, the claim is removed or labeled as a limitation.

---

## 4. Alternatives considered

### 4.1 Use all 24 records as equal datasets

Rejected. It would imply that a 2-row instrument log and a 469-row flame-length table have the same analytical weight. It would also invite invalid comparisons across flame spread, droplet combustion, smoke, and telemetry.

### 4.2 Use only the four primary datasets

Rejected. BASS/BASS-II provide the solid-material dimension, FLEX provides droplet context, and SAFFIRE-I/SAME provide mission and smoke context. Removing them would make the platform less honest about the breadth of the NASA collection, not more focused.

### 4.3 Treat zero-`added` records as inaccessible

Rejected after verification. PSI publishes an `experimentalTable` for PSI-22, PSI-68, PSI-69, and PSI-99. They are `experimental_table_only`, not inaccessible. Their tables are usable within their documented limits. The `inaccessible` role was retired.

### 4.4 Promote PSI-69 FLEX to primary

Rejected. The 274-row table is a real measured droplet-combustion summary, but it is not a flame-spread or spacecraft fire-safety table, and the raw archive is absent. It is supporting context.

### 4.5 Include BASS/BASS-II spread rates

Rejected for the MVP. No processed spread-rate table was identified. Deriving one requires computer vision, calibration, tracking, and uncertainty analysis. The platform must not draw a spread-rate chart from video without that work.

### 4.6 Build a composite risk score

Rejected. No validated formula, target, or uncertainty model exists. A score would be an arbitrary ranking dressed as science.

---

## 5. Consequences

### Positive

- The MVP has a clear scientific spine: gas flames, cool flames, spacecraft telemetry, and smoke response.
- Every primary dataset has a public, inspectable tabular artifact.
- The selection is reproducible from `data/registry/mvp_dataset_catalog.json`.
- Limitations are explicit: no processed spread rates, no fabricated archive, no risk score.

### Negative

- The MVP cannot answer flame-spread questions quantitatively from BASS/BASS-II.
- The MVP cannot analyze the missing FLEX/FLEX-2/SAFFIRE-II/E-FIELD raw archives.
- The MVP cannot treat test-day summaries as per-test measurements.
- The MVP cannot compare smoke, droplet, and gas-flame results on one axis.

### Neutral

- Four datasets are deferred to a future phase.
- Nine datasets are context only.
- The catalog is intentionally smaller than the 24-record collection.

---

## 6. Data provenance requirements

Every selected artifact must carry:

- accession;
- exact source file name;
- sheet name where applicable;
- row or row range;
- SHA-256 of the exact file bytes;
- retrieval date;
- source URL without credentials;
- unit or `not stated`;
- missingness/sentinel flags;
- computed/measured status.

A dataset version that fails schema, checksum, row-count, or unit gates is blocked and not served as valid.

---

## 7. Review and change control

- Adding a primary dataset requires a new ADR or an amendment to this one.
- Promoting a future dataset requires a format audit, parser tests, and a data-dictionary update.
- Changing a role requires updating `data/registry/annotations.json` and regenerating the catalog.
- The registry's mechanical fields must never be hand-edited.
- The `inaccessible` role must not be reintroduced. Use `archive_status` plus a documented limitation.

---

## 8. Verification

The decision is verified by:

```bash
python3 scripts/fetch_psi_metadata.py --check
python3 scripts/build_mvp_catalog.py --check
```

Both commands must pass before the initialization commit is pushed. The catalog totals must equal the registry totals:

- 24 records;
- 16,354 `added` files;
- 22 experimental tables;
- 14 experimental-table-only entries;
- 16,368 distinct public artifacts;
- 13,496.77 GB registered total.

---

## 9. References

- `DATA_SOURCES.md` — source inventory, access status, comparability matrix.
- `DATA_DICTIONARY.md` — field dictionaries, units, missingness, canonical schema.
- `data/registry/psi_combustion_investigations.json` — generated registry.
- `data/registry/psi_experimental_tables.csv` — experimental-table manifest.
- `data/registry/annotations.json` — curated roles and limitations.
- `docs/research/source-verification-log.md` — verification evidence.
