# Data Sources

**Project:** Flame in Freefall
**Team:** AFAQ
**Challenge:** Flame in Freefall: SI-Powered Fire Safety Insights from Microgravity Combustion Data
**Snapshot date:** 2026-11-08
**Status:** Verified source inventory and access assessment. No raw NASA data files are committed to this repository.

This document records what NASA actually publishes, how it can be retrieved, what is missing, and which records are suitable for the MVP. It deliberately separates **verified facts** from **open questions**. No measurements, file counts, or access claims in this document are invented.

---

## 1. Scope and verification rules

The scientific scope is NASA's microgravity combustion research, with emphasis on spacecraft fire safety. The primary source is the **NASA Physical Sciences Informatics (PSI)** repository.

The following rules apply to every dataset in this project:

1. A dataset is usable only if it has a public NASA source and a reproducible download path.
2. File names, sizes, formats, row counts, and checksums are recorded from the source, not estimated.
3. Empty cells, `n/a`, `none`, `OR` (over range), `?`, and sentinel values are preserved as missing or flagged values. They are never converted to zero.
4. Raw values and original units are stored alongside any canonical field. Unit conversions, if any, are explicit, reversible, and documented.
5. PSI exposes two different public file lists: `added` (archive files) and `experimentalTable` (curated summary tables). A record with zero `added` files but a public experimental table is **`experimental_table_only`**, not inaccessible. A record with neither is **`no_public_files`**.
6. Summary tables are not treated as raw measurements. A test-day count is not a per-test flame measurement.
7. Publications can support interpretation, but they do not replace experimental data.
8. Cross-experiment comparisons use only fields that are semantically equivalent and explicitly mapped.

The verification date for every HTTP check, file inventory, and checksum in this document is **2026-11-08** unless stated otherwise.

---

## 2. How NASA PSI is accessed

### 2.1 Public repository UI

- PSI landing page: <https://science.nasa.gov/physical-sciences-informatics-psi/>
- PSI investigations by research area: <https://www.nasa.gov/physical-sciences-informatics-psi/psi-investigations-by-research-area/>
- Repository UI: <https://psi.nasa.gov/physci/repo>
- Investigation page pattern: `https://psi.nasa.gov/physci/repo/data/investigations/{PSI-ID}`

The UI is a client-side application. The underlying public API is the reliable machine-readable interface.

### 2.2 Public search API

```text
GET https://psi.nasa.gov/geode-py/ws/repo/search?source=psi&type=investigation&size=200&from=0
```

The response is Elasticsearch-style JSON. On 2026-11-08 it returned **133 investigations**, of which **24** matched `Research Area = Combustion Science` (or a combustion-related sub-area).

### 2.3 Investigation detail API

```text
GET https://psi.nasa.gov/geode-py/ws/repo/investigations/{PSI-ID}
```

The detail object includes:

- investigation metadata (`title`, `investigationAcronym`, `doi`, `researchArea`, `subResearchArea`, `projectType`, dates, abstract/objective/hypothesis/approach, impacts, contacts, publications);
- `added`: the current public archive inventory (file name, size, category, S3 path, version, restriction flag);
- `removed`: prior-version files no longer in the current inventory;
- `experimentalTable`: a separate list of curated summary tables (file name, size, S3 path, restriction flag);
- `totalFileSize`: the registered total size in bytes.

**The two file lists are different.** An `experimentalTable` entry may also appear in `added`, or it may be the record's only public artifact. On 2026-11-08:

- 22 experimental tables were exposed across 20 records;
- 8 of those entries also appeared in `added`;
- 14 were exposed only through `experimentalTable`;
- 4 records had zero `added` files but a public experimental table: PSI-22, PSI-68, PSI-69, PSI-99.

**Important:** `totalFileSize` is not the sum of the currently exposed `added` files in every record. Several records register terabytes but expose zero `added` files, and some records report `0` registered bytes despite a small metadata file. The inventory and the registered total are reported separately throughout this project.

### 2.4 File download endpoint

```text
GET https://psi.nasa.gov/geode-py/ws/studies/{PSI-ID}/download?file={url-encoded-filename}
```

Behavior verified on 2026-11-08:

- Without `redirect=false`, the endpoint follows a redirect and returns the file bytes.
- With `redirect=false`, it returns a presigned S3 URL as plain text.
- The endpoint does not require an API key or login for public, unrestricted files.
- A file listed in either inventory can still return **HTTP 404** if the underlying object is missing. This was observed for SAFFIRE-I telemetry files and a sampled CFI raw metadata file.

The download endpoint is therefore necessary but not sufficient evidence of access. Each file used by the platform must pass a retrieval check and a checksum check.

### 2.5 Reproducible collector

The repository contains `scripts/fetch_psi_metadata.py`, a standard-library-only collector that:

- queries the public search API;
- selects the 24 combustion investigations;
- fetches each detail record;
- writes `data/registry/psi_combustion_investigations.json`, `data/registry/psi_file_inventory.csv` (the `added` manifest), and `data/registry/psi_experimental_tables.csv` (the 22-entry experimental-table manifest);
- supports `--check` to detect metadata drift without rewriting the snapshot;
- supports `--details-dir` for offline reproduction from cached detail JSON;
- optionally saves full detail JSON outside the repository with `--raw-dir`.

It never downloads raw experimental files and never writes credentials.

`scripts/build_mvp_catalog.py` regenerates `data/registry/mvp_dataset_catalog.json` from the registry and annotations. It embeds only curated role/use text; every count, size, checksum, and archive status comes from the registry.

---

## 3. Collection-level inventory

On 2026-11-08, the 24 combustion records contained:

- **16,354** current `added` archive files;
- **22** public experimental tables, totaling **211,116 bytes**;
- **14** experimental tables not present in `added`;
- **16,368** distinct public artifacts when the 14 ET-only entries are counted alongside the 16,354 `added` files;
- **13,496.77 GB** (decimal, 10^9 bytes) of registered total size;
- a wide range of formats, dominated by ZIP, MP4, PDF, CSV, TXT, XLSX, XLS, DOCX, and instrument-specific extensions (`.mdipsug`, `.ts`, `.asc`, `.log`, `.meta`).

The registered total is not the size of the files a user can download today. It is the size the investigation reports. The difference is a documented limitation, not a reason to fabricate data.

### 3.1 All 24 combustion investigations

| Accession | Acronym | Current `added` files | Experimental tables | Registered GB | Archive status | MVP role |
|---|---|---:|---:|---:|---|---|
| PSI-10 | ACME/Flame Design | 3,807 | 2 | 2,180.44 | available | **Primary** |
| PSI-20 | ACME BRE | 1 | 1 | 2,035.57 | available | Supporting |
| PSI-21 | ACME CLD Flame | 1 | 1 | 2,005.54 | available | Supporting |
| PSI-22 | ACME E-FIELD Flames | 0 | 1 | 950.21 | experimental_table_only | Context |
| PSI-23 | ACME s-Flame | 4,163 | 1 | 782.17 | available | Future |
| PSI-25 | BASS-II | 694 | 1 | 274.63 | available | Supporting |
| PSI-26 | BASS | 211 | 1 | 163.55 | available | Supporting |
| PSI-39 | CFI | 2,831 | 1 | 718.89 | available | Future |
| PSI-47 | DAFT / DAFT-2 | 32 | 1 | 0.04 | available | Context |
| PSI-60 | — | 1 | 0 | 0.00 | available | Context |
| PSI-62 | — | 1 | 0 | 0.00 | available | Context |
| PSI-68 | FLEX-2 | 0 | 1 | 1,224.75 | experimental_table_only | Context |
| PSI-69 | FLEX | 0 | 1 | 923.83 | experimental_table_only | Supporting |
| PSI-98 | SAFFIRE-I | 74 | 1 | 12.25 | available | Supporting |
| PSI-99 | SAFFIRE-II | 0 | 1 | 16.93 | experimental_table_only | Context |
| PSI-100 | SAFFIRE-III | 85 | 1 | 35.21 | available | **Primary** |
| PSI-101 | SAME-R | 342 | 1 | 6.31 | available | **Primary** |
| PSI-102 | SAME | 104 | 1 | 0.66 | available | Supporting |
| PSI-106 | SLICE | 1 | 1 | 72.91 | available | Future |
| PSI-107 | SPICE | 186 | 1 | 6.95 | available | Future |
| PSI-115 | — | 47 | 0 | 0.26 | available | Context |
| PSI-117 | — | 15 | 0 | 0.07 | available | Context |
| PSI-142 | — | 2 | 1 | 0.00 | available | Context |
| PSI-159 | ACME CFI-G | 3,756 | 2 | 2,085.59 | available | **Primary** |

Counts and sizes are from the PSI detail API on 2026-11-08. The full machine-readable inventory is in `data/registry/psi_combustion_investigations.json`; the per-file `added` manifest is in `data/registry/psi_file_inventory.csv`; the experimental-table manifest is in `data/registry/psi_experimental_tables.csv`.

### 3.2 Experimental-table inventory

Every table below was downloaded and inspected on 2026-11-08. `Rows` counts non-empty data rows after the header. `Physical rows` counts every row after the header, including blank rows. `In added` records whether the same file name also appears in the archive inventory.

| Accession | File | Rows | Physical rows | Columns | In added |
|---|---|---:|---:|---:|---|
| PSI-10 | `PSI-10_Experimental table_Flame Design_Normal Flame.csv` | 207 | 207 | 15 | yes |
| PSI-10 | `PSI-10_Experimental table_Flame Design_Inverse Flame.csv` | 120 | 120 | 14 | yes |
| PSI-20 | `PSI-20_Experimental table_ACME BRE.csv` | 18 | 18 | 8 | yes |
| PSI-21 | `PSI-21_Experimental table_CLD Flame.csv` | 32 | 32 | 8 | yes |
| PSI-22 | `PSI-22_Experimental table_ACME E-FIELD Flames.csv` | 32 | 32 | 10 | no |
| PSI-23 | `PSI-23_Experimental table_ACME s-Flame.csv` | 18 | 18 | 9 | no |
| PSI-25 | `PSI-25_Experimental table_BASS-II.csv` | 129 | 129 | 17 | no |
| PSI-26 | `PSI-26_Experimental table_BASS.csv` | 122 | 122 | 6 | no |
| PSI-39 | `PSI-39_Experimental table_CFI.csv` | 87 | 87 | 10 | no |
| PSI-47 | `PSI-47_Experimental table_DAFT.csv` | 2 | 2 | 5 | no |
| PSI-68 | `PSI-68_Experimental table_Flex2.csv` | 8 | 8 | 7 | no |
| PSI-69 | `PSI-69_Experimental table_FLEX.csv` | 274 | 274 | 15 | no |
| PSI-98 | `PSI-98_Experimental table_SAFFIRE-1.csv` | 4 | 4 | 13 | no |
| PSI-99 | `PSI-99_Experimental table_SAFFIRE-2.csv` | 15 | 15 | 17 | no |
| PSI-100 | `PSI-100_Experimental table_SAFFIRE-3.csv` | 2 | 2 | 9 | no |
| PSI-101 | `PSI-101_Experimental table_SAME-R.csv` | 109 | 109 | 10 | no |
| PSI-102 | `PSI-102_Experimental table_SAME.csv` | 8 | 8 | 5 | no |
| PSI-106 | `PSI-106_Experimental table_Slice.csv` | 12 | 12 | 2 | yes |
| PSI-107 | `PSI-107_Experimental table_Spice.csv` | 469 | 469 | 9 | no |
| PSI-142 | `PSI-142_Experimental table_Data Summary Table.csv` | 8 | 8 | 4 | yes |
| PSI-159 | `PSI-159_Experimental table_CFI-G_Normal Flames.csv` | 179 | 179 | 18 | yes |
| PSI-159 | `PSI-159_Experimental table_CFI-G_Inverse Flames.csv` | 154 | 1,015 | 20 | yes |

The 14 ET-only entries are the tables for PSI-22, PSI-23, PSI-25, PSI-26, PSI-39, PSI-47, PSI-68, PSI-69, PSI-98, PSI-99, PSI-100, PSI-101, PSI-102, and PSI-107. They are public artifacts even though they are absent from the `added` archive list.

### 3.3 Record relationships

The 24 records are not 24 independent experiments. Important relationships:

- **ACME** is a program containing several investigations: Flame Design (PSI-10), BRE (PSI-20), CLD Flame (PSI-21), E-FIELD (PSI-22), s-Flame (PSI-23), and CFI-G (PSI-159).
- **BASS** (PSI-26) and **BASS-II** (PSI-25) are separate flight investigations with different test matrices and hardware campaigns.
- **SAFFIRE-I** (PSI-98), **SAFFIRE-II** (PSI-99), and **SAFFIRE-III** (PSI-100) are separate flights. SAFFIRE-I and SAFFIRE-III share the SIBAL cloth material and image-set conventions; SAFFIRE-II is a different sample and its public table is a 15-row summary, not telemetry.
- **SAME** (PSI-102) and **SAME-R** (PSI-101) are the original and reflight smoke experiments. SAME-R has a much richer raw HKP CSV series.
- **FLEX** (PSI-69) and **FLEX-2** (PSI-68) are separate flame-extinguishment investigations. Both have zero `added` files but public experimental summary tables; FLEX has a 274-row droplet table, FLEX-2 an 8-row condition-range table.
- **CFI** (PSI-39) is a droplet-combustion investigation; **CFI-G** (PSI-159) is the gas-phase cool-flame investigation. They are not the same dataset and must not be merged.
- PSI-60, PSI-62, PSI-115, PSI-117, and PSI-142 are **ground investigations** or data indices. They are context, not microgravity measurements.

---

## 4. Experiment family profiles

### 4.1 ACME — Advanced Combustion via Microgravity Experiments

**Official NASA sources**

- ACME program page: <https://gipoc.grc.nasa.gov/wp/fcf-cir/acme/>
- Combustion science program: <https://www.nasa.gov/glenn/glenn-expertise-space-exploration/physical-sciences-program/combustion-science/>
- PSI records: PSI-10, PSI-20, PSI-21, PSI-22, PSI-23, PSI-159
- Hardware: Combustion Integrated Rack (CIR) and Multi-User Droplet Combustion Apparatus (MDCA), International Space Station.

**What ACME provides in PSI**

ACME is not one dataset. The PSI records split it into separate investigations with different levels of access:

| Record | Investigation | Public tabular data | Access assessment |
|---|---|---|---|
| PSI-10 | Flame Design | 207 normal-flame rows + 120 inverse-flame rows | Usable summary tables |
| PSI-20 | BRE | 18-row test-day summary | Very limited; no raw files |
| PSI-21 | CLD Flame | 32-row test-day summary | Very limited; no raw files |
| PSI-22 | E-FIELD Flames | 32-row test-day summary | `experimental_table_only`; no `added` archive |
| PSI-23 | s-Flame | 18-row test-day summary | Large raw archive plus small summary; not assessed |
| PSI-159 | CFI-G | 179 normal-flame rows + 154 valid inverse-flame rows | Usable summary tables |

**Why ACME matters for the MVP**

PSI-10 and PSI-159 provide the cleanest per-test gas-flame observations in the entire collection: fuel, oxygen mole fraction, pressure, mass flows, stoichiometric mixture fraction, adiabatic flame temperature, ignition, cool-flame flag, burn time, extinction mode, and comments. They are the best foundation for cross-condition comparison and for an AI layer that must cite actual rows.

**ACME limitations**

- The summary tables are small relative to the 2 TB raw archives. The MVP uses the summary tables, not the raw image/telemetry streams.
- `Tad (K)` is a computed adiabatic flame temperature, not a measured temperature.
- `XO2` is a mole fraction, not a percentage by volume. BASS uses percentage by volume. Conversion is possible but must be explicit.
- `TFP` in PSI-159 is a categorical `Yes`/`No` field, not a numeric temperature. The source header does not expand the acronym or define what the flag denotes; it must not be plotted on a temperature axis or assigned a unit.
- PSI-10 summary tables contain non-numeric qualifiers inside otherwise numeric columns: `RAMP`/`RAMPED` in 60 normal-flame rows and `RAMP`/`LOW O2` in 11 inverse-flame rows. These are experiment qualifiers, not missing blanks and not zeros.
- PSI-159 normal flames contain `#DIV/0!` in `Tad (K)` and `Zst` for 2 rows; PSI-159 inverse flames contain `#VALUE!` in `Peak burner temp (K)` for 2 rows. These are spreadsheet error tokens and must be preserved as invalid values, not coerced.
- PSI-20, PSI-21, and PSI-22 explicitly note that chamber pressure varied but is not identified in the summary table. They cannot support pressure-response analysis.
- PSI-22 and PSI-23 are context/future records, not interchangeable with the usable per-test summary tables.

---

### 4.2 BASS and BASS-II — Burning and Suppression of Solids

**Official NASA sources**

- BASS-M page: <https://gipoc.grc.nasa.gov/wp/msg/bass-m/>
- BASS-II summary report (NTRS): <https://ntrs.nasa.gov/citations/20210011385>
- BASS results (NTRS): <https://ntrs.nasa.gov/citations/20160000593>
- PSI records: PSI-26 (BASS), PSI-25 (BASS-II)
- Hardware: Microgravity Science Glovebox (MSG), International Space Station.

**What BASS provides in PSI**

- **PSI-26 BASS:** 211 `added` files, 163.55 GB, plus a 122-row, 6-column experimental table. The table records Date, GMT, As Run Test #, Test #, Sample #, and Fuel Sample Material. There are 114 MP4 videos, 60 ZIP archives, 32 PDFs, and a detailed as-run test matrix XLSX. The test matrix includes material, igniter, flow restrictor, fan/air display, radiometer gain, camera settings, O2, pressure, CO2, and free-text observations.
- **PSI-25 BASS-II:** 694 `added` files, 274.63 GB, plus a 129-row, 17-column combined experimental table. The test-matrix workbook has six PI-specific sheets (Bhattacharjee, Ferkul, Miller, Olson, Fernandez-Pello, T'ien) with 129 test rows in total and 16 columns. Columns include material, flow restrictor, fan display, air display, radiometer gain, total frames, calibrated initial/final O2, initial/final CO2, and initial/final CO. There are 296 MP4 videos, 265 ZIP archives, and 127 PDFs.

**Why BASS matters for the MVP**

BASS/BASS-II supply the solid-fuel and material dimension that the gas-flame ACME tables lack. The test matrices can support material/flow/O2 context, video indexing, and qualitative comparison. They are also central to the challenge narrative about spacecraft fire safety.

**BASS limitations**

- **There is no processed flame-spread table.** Flame-spread rates are not published as a tidy CSV. Deriving them requires computer vision on the video archive, which is out of MVP scope.
- The BASS experimental table is a test log, not a measurement table. It must not be presented as a quantitative flammability dataset.
- BASS-II test matrices are XLSX workbooks with six PI-specific sheets and inconsistent free-text notes. Column meanings are documented in the BASS-II readme, but the sheets are not normalized.
- The combined BASS-II experimental CSV has 17 columns and 129 rows; the six-sheet workbook has 16 columns and 129 rows. They are two views of the same campaign. Choose one as canonical, not both.
- Air display is a slow-response duct reading, not an instantaneous velocity.
- Radiometer gain is uncalibrated and useful only for relative intensity.
- 438 GB across the two records is mostly video/ZIP. The repository must not clone the raw archive.

---

### 4.3 SAFFIRE — Spacecraft Fire Experiment

**Official NASA sources**

- SAFFIRE program page: <https://gipoc.grc.nasa.gov/wp/other-iss/saffire/>
- NASA TechPort: <https://techport.nasa.gov/projects/13543>
- NASA news release for SAFFIRE-III: <https://www.nasa.gov/news-release/nasa-prepares-to-ignite-third-saffire-experiment/>
- NTRS SAFFIRE objectives/development/status: <https://ntrs.nasa.gov/api/citations/20170001636/downloads/20170001636.pdf>
- PSI records: PSI-98 (SAFFIRE-I), PSI-99 (SAFFIRE-II), PSI-100 (SAFFIRE-III)

**What SAFFIRE provides in PSI**

- **PSI-100 SAFFIRE-III:** 85 `added` files, 35.21 GB, plus a 2-row sample summary table. Two telemetry CSVs (47 columns each) and six XLSX workbooks, plus image ZIPs and documents. The telemetry includes radiometers, anemometers, fan tachometer, smoke-wire voltage/current, nine igniter voltage/current pairs, PCM air temperature, three pressure channels, a pressure/temperature composite, two smoke-detector obscuration channels, two scatterometer channels, two cabin-fan differential pressures, body rates, and accelerations. This is the strongest time-series dataset for spacecraft fire-safety analysis.
- **PSI-98 SAFFIRE-I:** 74 `added` files, 12.25 GB, plus a 4-row sample summary. Documents and image ZIPs are available. The two telemetry XLSX files and the two sensor-data XLSX files are listed in the inventory but return **HTTP 404** from the download endpoint. They cannot be treated as ingested.
- **PSI-99 SAFFIRE-II:** 0 `added` files, 16.93 GB registered, plus a 15-row sample summary. `experimental_table_only`; the table records material, thickness, flow, oxygen, ignition, burn time, flow direction, 1-g burn length, 1-g spread rate, and camera identifiers. The 1-g spread rate is normal gravity, and the microgravity spread columns are incomplete or use non-numeric placeholders.

**SAFFIRE-III telemetry exports (important)**

There are at least three different exports, and they do not agree row-for-row:

| Artifact | Physical rows | Valid rows | Time span (RelativeSeconds, ms) | Notes |
|---|---:|---:|---:|---|
| `PSI-100_Raw Data_Raw telemetry file.csv` | 3,972 | 3,966 | 0 to 9,573,373 | 6 negative/sentinel rows, including a large footer sentinel |
| `PSI-100_Raw Data_Saffire_Data_Table2017.161.00.42.03-EU.csv` | 11,450 | 11,449 | 0 to 6,899,845 | One sentinel footer row |
| `PSI-100_Raw Data_Saffire-III 1 Hz Telemetry Data.xlsx`, `RawData` sheet | 73,462 | 11,449 | 0 to 6,899,845 | The remaining rows are empty formatting rows, not data |

**Do not concatenate these exports.** Reconcile timestamps and sensor definitions first. The column name `RelativeSeconds` is misleading: the values are milliseconds in the inspected exports.

**SAFFIRE limitations**

- Telemetry is engineering sensor data, not a processed flame-spread rate. Image-derived spread rates require separate processing and validation.
- The raw CSV uses raw signal names (`P@sfsHk.*`, `P@CDH_*`); the XLSX uses human-readable headers with units. Mapping between them must be documented and tested.
- Some channels are raw voltages or uncalibrated values. Do not present them as physical concentrations without calibration documentation.
- SAFFIRE-I telemetry is inaccessible via the download endpoint despite being listed. The SAFFIRE-I image sets and documents are available, but image-derived measurements are not in the MVP.
- SAFFIRE-II's public table is a sample summary, not telemetry. The 1-g spread rate must not be relabeled as microgravity data.

---

### 4.4 SAME and SAME-R — Smoke Aerosol Measurement Experiment

**Official NASA sources**

- PSI records: PSI-102 (SAME), PSI-101 (SAME-R)
- Hardware: SAME payload, International Space Station; SAME-R is the reflight.
- Related context: PSI-47 DAFT/DAFT-2 (P-Trak microgravity feasibility), PSI-115 (ground simulation of SAME smoke).

**What SAME/SAME-R provide in PSI**

- **PSI-101 SAME-R:** 342 `added` files, 6.31 GB, plus a 109-row sample/test table. A representative raw HKP CSV has 98 columns and 558 rows, including gas-plume temperature (°C), sample resistance (Ω), ISS detector obscuration/scatter (V), STS detector (V), ion detector A/B (V), P-Trak concentration (pt/cc), DustTrak A/B concentrations (mg/m³), analog voltages, LFE flow (SCCM), MFC setpoint/flow (LPM), MFC temperature (°C) and pressure (PSIA), GN2 main/regulated pressures (PSIA/PSIG), vacuum/drive/sample pressures (PSIA), and many device states and solenoid commands. There are multiple runs (different GMT days) and a 43-sheet results workbook. The 109-row table records sample type, SAME test number, description, date, inlet velocity, Rt/R0, duration, and aging times.
- **PSI-102 SAME:** 104 `added` files, 0.66 GB, plus an 8-row sample table. Legacy `.xls` analyzed workbooks and logs, with 43 sheets in the combined results workbook. No raw HKP CSV series comparable to SAME-R. The 8-row table records material, air flow, weight-loss rate, and aging duration.

**Why SAME/SAME-R matter for the MVP**

They add the smoke-detection and aerosol dimension: detector response, particle counts, mass concentrations, flow, and pressure. This supports evidence-based insight about how smoke behaves in microgravity and how spacecraft detectors respond.

**SAME/SAME-R limitations**

- This is not a flame-spread dataset. Do not compare it to BASS or ACME on a flame-spread axis.
- Many of the 98 HKP columns are device states, solenoid commands, or power flags, not physical measurements.
- Legacy `.xls` files require a converter or `xlrd`; they are not all CSV.
- Run metadata and test logs are in separate files. A CSV row does not identify the material or aging condition by itself.
- The results workbook has 43 sheets with inconsistent naming; sheet-level validation is required before loading.

---

### 4.5 FLEX and FLEX-2 — Flame Extinguishment Experiment

**Official NASA sources**

- FLEX page: <https://gipoc.grc.nasa.gov/wp/fcf-cir/flex/>
- FLEX-2 page: <https://gipoc.grc.nasa.gov/wp/fcf-cir/flex-2/>
- PSI records: PSI-69 (FLEX), PSI-68 (FLEX-2)

**Access assessment**

Both records expose **zero `added` files**, but both expose a public experimental summary table:

- **PSI-69 FLEX:** 0 `added` files, 923.83 GB registered, 51 publications, and a **274-row, 15-column** droplet-combustion summary table with fuel, ambient pressure and composition, initial droplet diameter, visible flame extinction diameter, burning rate, burn time, and test end.
- **PSI-68 FLEX-2:** 0 `added` files, 1,224.75 GB registered, 48 publications, and an **8-row, 7-column** test-condition range table listing fuel types, droplet diameters, ambient gas mixtures, oxygen mole fractions, pressures, temperatures, and flow velocities.

The FLEX table is a real measured summary and is promoted to **supporting** for droplet-combustion context. The FLEX-2 table contains ranges, not per-test measurements, so it remains **context**. Neither table is a flame-spread dataset.

This is still a hard archive limitation: the raw FLEX/FLEX-2 telemetry, images, and video are not exposed. The publications and summary tables can support context, but the platform must not claim to analyze the missing raw archive. If the archive becomes available later, the collector's `--check` mode will detect the change in `file_count`.

---

### 4.6 CFI — Cool Flames Investigation (droplet)

**Official NASA sources**

- CFI page: <https://gipoc.grc.nasa.gov/wp/fcf-cir/mdca/cfi/>
- PSI record: PSI-39
- Hardware: Multi-User Droplet Combustion Apparatus (MDCA), Combustion Integrated Rack (CIR).

**Access assessment**

PSI-39 contains 2,831 `added` files, 718.89 GB, 2,698 removed files, and an **87-row, 10-column** experimental test-condition table with flex number, date, pressure, oxygen, nitrogen, helium, fiber, and fuel. The archive is dominated by raw TXT, META, TS, ZIP, and MP4 files. A sampled `.metadata` download returned HTTP 404. CFI is scientifically relevant to cool flames and droplet extinction, but the table is a test-condition log, not a processed result table. It remains a **future** dataset, not an MVP dataset.

**Important distinction:** CFI (PSI-39, droplet combustion) and CFI-G (PSI-159, gas-phase cool flames) are different investigations. They must not be merged.

---

### 4.7 Other combustion records

| Record | What it is | Public table | Why it is not in the MVP |
|---|---|---|---|
| PSI-47 DAFT/DAFT-2 | P-Trak microgravity feasibility | 2-row session table | Instrument context, not a combustion measurement dataset |
| PSI-60 | Ground analysis of SPICE data | none | Ground investigation; one metadata file |
| PSI-62 | Ground FGM modeling compared to BASS | none | Ground investigation; one metadata file |
| PSI-106 SLICE | Flame liftoff experiment | 12 rows × 2 columns (Test Date, Fuel Type) | No measured variables |
| PSI-107 SPICE | Smoke point in coflow | 469 rows × 9 columns (flame length/airflow) | Needs a format audit; no processed smoke-point result table |
| PSI-115 | Ground simulation of SAME smoke | none | Ground investigation; model context |
| PSI-117 | Ground cool-flame analyzed data | none | Ground investigation; small publication-specific CSVs |
| PSI-142 | Figure/data index for CFE/HFE studies | 8 rows × 4 columns | Index only, no measurements |

These records are still catalogued because they may support interpretation, citation tracing, or a later phase. They must be labeled as ground/context data, not microgravity measurements.

---

## 5. Cross-experiment comparability

The platform may compare experiments only where the fields are semantically equivalent. The following matrix is the current assessment.

| Field | ACME PSI-10 | ACME CFI-G PSI-159 | SAFFIRE-III PSI-100 | SAME-R PSI-101 | BASS-II PSI-25 | BASS PSI-26 |
|---|---|---|---|---|---|---|
| Fuel / material | Gas fuel (e.g., C2H4) | Gas fuel (e.g., ethane, n-butane) | SIBAL cloth (75% cotton / 25% fiberglass) | Synthetic smoke sources (Teflon, Kapton, silicone, lampwick, Pyrell) | PMMA, Nomex, SIBAL, candle, PMMA rods | SIBAL, PMMA, Nomex, Ultem |
| Oxygen | `XO2` mole fraction | `XO2` mole fraction / `XO2 before/after` | Not a direct O2 channel in the telemetry | Not a direct O2 channel | Calibrated O2 % by volume | Not in the 6-column table |
| Pressure | `pinit`, `pfinal`, `pmean` (atm) | `approx p (bar)` | PCM pressures (psi), pressure/temp composite | MFC/GN2/vacuum pressures (PSIA/PSIG) | Test matrix does not include pressure | Test matrix includes pressure (atm) |
| Flow | `mfuel`, `mN2`, `mtot` (mg/s) | `mHC`, `O2 flow rate` (mg/s) | Anemometers, fan tachometer, fan delta P (Pa) | LFE (SCCM), MFC (LPM) | Air display (cm/s), flow restrictor | Air display (cm/s), flow restrictor |
| Temperature | `Tad` (K, computed) | `Tad` (K, computed), peak burner T (C/K, measured) | PCM air temp (°C), radiometers | Gas plume temp (°C) | No temperature column in test matrix | No temperature column in test matrix |
| Test flag | — | `TFP` (categorical Yes/No; meaning not expanded in the source header) | — | — | — | — |
| Ignition | Implicit in test outcome | `Hot ignition`, `burn time` | Nine igniter voltage/current channels | Heater/sample resistance, test state | Igniter type in as-run matrix | Igniter in as-run matrix |
| Flame behavior | Flame type, comments | Cool flame?, color, comments | Radiometers, smoke detectors, images | Smoke detector/aerosol response | Video only | Video only |
| Spread rate | Not in summary table | Not in summary table | Not in telemetry table | Not applicable | **Not published as a table** | **Not published as a table** |
| Suppression outcome | Not in summary table | `Self-ext or flow term` | Burn-to-completion telemetry; no suppression table | Not applicable | Extinguish flag in as-run matrix | Extinguish flag in as-run matrix |

**Rules derived from the matrix**

1. `Tad` is computed, peak burner temperature is measured, `TFP` is a categorical Yes/No flag, and `PCM Air Temp` is an engineering sensor reading. They are not the same variable and must never share a y-axis without explicit labels.
2. `XO2` mole fraction and O2 % by volume are convertible, but the conversion must be explicit and reversible.
3. `mHC`/`mfuel` (mg/s) and air display (cm/s) are not convertible without geometry and calibration. Do not put them on the same axis.
4. BASS/BASS-II do not have a published spread-rate table. Any spread-rate visualization must be labeled "not available" or deferred until a validated computer-vision pipeline exists.
5. SAME/SAME-R measure smoke and detector response, not flame spread. They belong in a separate comparison domain.
6. SAFFIRE telemetry measures the spacecraft fire environment; it does not directly measure flame spread. Image-derived spread rates are a separate derived product.
7. FLEX and FLEX-2 are droplet-combustion records. Their summary tables do not contain flame-spread rates and must not be merged with BASS or ACME spread discussions.

---

## 6. Access limitations

### 6.1 Experimental-table-only records

| Record | Registered GB | Publications | Public table | Status |
|---|---:|---:|---|---|
| PSI-22 ACME E-FIELD Flames | 950.21 | 25 | 32 rows × 10 columns | `experimental_table_only` |
| PSI-68 FLEX-2 | 1,224.75 | 48 | 8 rows × 7 columns | `experimental_table_only` |
| PSI-69 FLEX | 923.83 | 51 | 274 rows × 15 columns | `experimental_table_only` |
| PSI-99 SAFFIRE-II | 16.93 | 7 | 15 rows × 17 columns | `experimental_table_only` |

These records must be shown in the catalog with an explicit `experimental_table_only` badge. The platform may analyze the public summary table, but it must not imply that the missing raw archive was analyzed. For PSI-68 and PSI-99, the table is condition/sample context rather than a per-test measurement; for PSI-22 it is a test-day summary; for PSI-69 it is a measured droplet summary.

No record in the 24-record collection currently has `no_public_files`.

### 6.2 Listed-but-unavailable files

| Record | File | Observed behavior |
|---|---|---|
| PSI-98 | `PSI-98_Raw Data_Saffire-I Telemetry Data Good Process Version.xlsx` | HTTP 404 on 2026-11-08 |
| PSI-98 | `PSI-98_Raw Data_Saffire-I Sample 1 Sensor Data Complete TM graphs.xlsx` | HTTP 404 on 2026-11-08 |
| PSI-39 | Sampled `.metadata` file | HTTP 404 on 2026-11-08 |
| PSI-142 | Experimental table | Initial request failed; a retry succeeded. Treat as flaky and verify checksums on every fetch. |

A 404 is not proof that the file never existed. It means the public download path did not return the object at verification time. The platform must handle it as an access error and surface the source URL and status to the user.

### 6.3 Records with only a small summary table

PSI-20, PSI-21, PSI-22, PSI-68, PSI-99, PSI-106, and PSI-142 expose only one small tabular file each. Their registered totals are much larger than the exposed files. They are useful as context but cannot support a quantitative per-test MVP. PSI-69 is the exception among the `experimental_table_only` records: its 274-row table contains measured droplet-combustion values and is classified as supporting.

### 6.4 Removed files

The API's `removed` array is not part of the current public inventory. Some records have large removed counts:

- PSI-23: 6,814 removed files.
- PSI-39: 2,698 removed files.
- PSI-101: 379 removed files.
- PSI-25: 131 removed files.
- PSI-100: 97 removed files.
- PSI-98: 85 removed files.

The platform uses the current `added` inventory plus the current `experimentalTable` list. Removed files are recorded only as version history and are not silently substituted.

---

## 7. NASA official pages and publications

### 7.1 Program and experiment pages verified

| Resource | URL | Use |
|---|---|---|
| PSI landing | <https://science.nasa.gov/physical-sciences-informatics-psi/> | Program overview and access |
| PSI investigations by research area | <https://www.nasa.gov/physical-sciences-informatics-psi/psi-investigations-by-research-area/> | Combustion record discovery |
| NASA combustion science | <https://www.nasa.gov/glenn/glenn-expertise-space-exploration/physical-sciences-program/combustion-science/> | Program context |
| ACME | <https://gipoc.grc.nasa.gov/wp/fcf-cir/acme/> | Experiment context |
| FLEX | <https://gipoc.grc.nasa.gov/wp/fcf-cir/flex/> | Experiment context |
| FLEX-2 | <https://gipoc.grc.nasa.gov/wp/fcf-cir/flex-2/> | Experiment context |
| CFI | <https://gipoc.grc.nasa.gov/wp/fcf-cir/mdca/cfi/> | Experiment context |
| SAFFIRE | <https://gipoc.grc.nasa.gov/wp/other-iss/saffire/> | Experiment context |
| BASS-M | <https://gipoc.grc.nasa.gov/wp/msg/bass-m/> | BASS context |
| SAFFIRE TechPort | <https://techport.nasa.gov/projects/13543> | Mission/project metadata |
| SAFFIRE-III news release | <https://www.nasa.gov/news-release/nasa-prepares-to-ignite-third-saffire-experiment/> | Flight context |

### 7.2 Key publications attached to the PSI records

The registry contains the full publication list for each record (title, DOI, authors, status). Representative examples:

- **ACME Flame Design:** Waddell et al., "The kinetics and warm flame chemistry associated with radiative extinction of spherical diffusion flames," *Combustion Theory and Modelling* (2024), DOI [10.1080/13647830.2024.2326830](https://doi.org/10.1080/13647830.2024.2326830).
- **ACME CFI-G:** Kim et al., "Spherical gas-fueled cool diffusion flames," *Proceedings of the Combustion Institute* (2022), DOI [10.1016/j.proci.2022.07.015](https://doi.org/10.1016/j.proci.2022.07.015); Waddell et al., "Cool diffusion flames in a stably stratified stagnation flow," *Combustion and Flame* (2023), DOI [10.1016/j.combustflame.2023.112852](https://doi.org/10.1016/j.combustflame.2023.112852).
- **BASS-II:** Olson and Ferkul, "Microgravity flammability boundary for PMMA rods in axial stagnation flow: Experimental results and energy balance analyses," *Combustion and Flame* 180 (2017), DOI [10.1016/j.combustflame.2017.03.001](https://doi.org/10.1016/j.combustflame.2017.03.001).
- **BASS:** Bhattacharjee et al., "Opposed-flow flame spread: A comparison of microgravity and normal gravity experiments to establish the thermal regime," *Fire Safety Journal* 79 (2016), DOI [10.1016/j.firesaf.2015.11.011](https://doi.org/10.1016/j.firesaf.2015.11.011).
- **SAME:** Urban et al., "Measurement of Smoke Particle Size under Low-Gravity Conditions," SAE Technical Paper 2008-01-2089, DOI [10.4271/2008-01-2089](https://doi.org/10.4271/2008-01-2089).
- **SAFFIRE:** Schoren, Ruff, and Urban, "The Spacecraft Fire Experiment (SAFFIRE) — Objectives, Development and Status," NTRS 20170001636, <https://ntrs.nasa.gov/api/citations/20170001636/downloads/20170001636.pdf>.

The PSI detail JSON is the authoritative source for the complete publication list. The registry stores every attached publication, not just these examples.

### 7.3 Data DOIs

Each PSI record has a DOI. The full set is in the registry. Examples:

- PSI-10 ACME/Flame Design: `10.60555/w4zy-bt45`
- PSI-25 BASS-II: `10.60555/4qc4-de67`
- PSI-26 BASS: `10.60555/58h4-dy80`
- PSI-39 CFI: `10.60555/m6pj-a914`
- PSI-98 SAFFIRE-I: `10.60555/0t15-1z43`
- PSI-99 SAFFIRE-II: `10.60555/2chp-m469`
- PSI-100 SAFFIRE-III: `10.60555/040q-4h36`
- PSI-101 SAME-R: `10.60555/2np7-jv14`
- PSI-102 SAME: `10.60555/gd4k-8h62`
- PSI-159 ACME CFI-G: `10.60555/cyt1-kh64`

---

## 8. Verification log

### 8.1 API checks

| Check | Result |
|---|---|
| PSI search API reachable | HTTP 200 |
| Total investigations | 133 |
| Combustion investigations | 24 |
| Detail endpoint for all 24 | HTTP 200 |
| `experimentalTable` entries found | 22 across 20 records |
| `experimentalTable` downloads | 22 of 22 returned HTTP 200 with file bytes |
| ET-only records | PSI-22, PSI-68, PSI-69, PSI-99 |
| Download endpoint for sampled experimental tables | HTTP 200 with file bytes |
| Download endpoint with `redirect=false` | HTTP 200 with presigned S3 URL |
| Records with zero public artifacts | none |
| Listed-but-404 files | SAFFIRE-I telemetry/sensor XLSX; sampled CFI `.metadata` |

### 8.2 Checksums of inspected tabular files

These SHA-256 values are recorded in `data/registry/annotations.json` and the generated registry. The complete set is in `data/registry/psi_experimental_tables.csv`.

| File | SHA-256 |
|---|---|
| PSI-10 normal flames CSV | `4a663292bd3f65201943cc71bd661a70383639276a9176f64105b285bf0b6deb` |
| PSI-10 inverse flames CSV | `97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4` |
| PSI-159 normal flames CSV | `d95a621c3fbd27d204dd32ed29fa17d68f2b779d6a523cde8479ed7ebaa5251a` |
| PSI-159 inverse flames CSV | `d4d44f8b9896936728748e34d1b6ad0812032a92fa5289599b708c138e3a9b39` |
| PSI-20 ACME BRE CSV | `4aa5d3f98708ceacced5c620d46858b9965f8d4d941b203229f46467d53e5ab7` |
| PSI-21 ACME CLD CSV | `9fafbc5b3dddaf715ce8025ed9154ce297803f7b69a935f077ec26c8249e44c0` |
| PSI-22 E-FIELD CSV | `69090c357b83ae38d161d29001d1d32b40fd77b13324ca6585ee990cdceef524` |
| PSI-25 BASS-II combined CSV | `71e792bf6b5fb5ea620c5dd70fbbac05515992e12aefcf5dff47312caa48c042` |
| PSI-26 BASS CSV | `ccfc3c54d948b64a1c5d2596a63c7c8019e51df0c91a1d62f039f48fa28c300f` |
| PSI-39 CFI CSV | `fb898e28762353aa132c16b886dbd207a024b1dd3c9bed5928d70d8036d2ec7e` |
| PSI-68 FLEX-2 CSV | `cc57ad1bd9977aa13e7ac6c3aa618303012686e232b36c052c6a9f1a74e5f528` |
| PSI-69 FLEX CSV | `37c88ce8ae9391b7544ff630a45ce87543d04d317cdbfbed104fe7d5c27e1b96` |
| PSI-98 SAFFIRE-I CSV | `c01f29c62455f0a3b512290ab85e5687ecded326733189f002f580368402308d` |
| PSI-99 SAFFIRE-II CSV | `3c24390b9ef86f3d1ebaab911a1a3cc95a8759aebf42062371370e6d4b31b8ac` |
| PSI-100 SAFFIRE-III sample CSV | `4d3c717ec20dd0247db670b2784a9fd7d746788bc54a936f80693e48eb8cd117` |
| PSI-101 SAME-R sample CSV | `87164b7dc9168a4273c159f7a9f23699afbd06ad97b77974377e79b9bf8a3bef` |
| PSI-102 SAME CSV | `268d1e121d2f211b124407dd32b9475617bd269ede2c2d1749441da3e949a2af` |
| PSI-106 SLICE CSV | `89ef980810ca6d9aa8be817b42e36cd2adff23f5e9058361b5a33d18b4363f4d` |
| PSI-107 SPICE CSV | `fb0d7e60cf5367afb429089e9901d27288f78038efd26c8de1db4fbe04117136` |
| PSI-142 data index CSV | `c66d135b0053590d239f06b9e8627d826e3d726b8443fd2cbccc37484b6a8e7f` |
| PSI-100 raw telemetry CSV | `dfb204ce3bdf8b1749652549afcbad31d180902bc268dfbe782c70fa38d170a2` |
| PSI-100 cleaned telemetry CSV | `71f8d11a2e040c22924b1c6320384cdcf58e945fe66c993876c44158bf6f57c5` |
| PSI-101 HKP gmt250_1 CSV | `69c25a566b6af6b43fb263ceadad82499b6e18e69e5fdad928e8088124ee43a3` |

### 8.3 Row-count checks

| File | Physical rows | Valid rows | Notes |
|---|---:|---:|---|
| PSI-10 normal | 207 | 207 | 20 rows missing final XO2/pressure; 60 rows contain `RAMP`/`RAMPED` qualifiers |
| PSI-10 inverse | 120 | 120 | No blank cells; 11 rows contain `RAMP`/`LOW O2` qualifiers in numeric columns |
| PSI-159 normal | 179 | 179 | `Cool flame?` blank in 171 rows; 2 rows contain `#DIV/0!` |
| PSI-159 inverse | 1,015 | 154 | 861 trailing blank rows; 2 rows contain `#VALUE!` |
| PSI-26 BASS | 122 | 122 | 1 row missing test/sample identifiers |
| PSI-69 FLEX | 274 | 274 | Droplet-combustion summary; `Burning rate; mm` unit is not a rate |
| PSI-99 SAFFIRE-II | 15 | 15 | 1-g spread rate only; microgravity columns incomplete |
| PSI-100 raw telemetry | 3,972 | 3,966 | 6 negative/sentinel rows |
| PSI-100 cleaned telemetry | 11,450 | 11,449 | 1 sentinel row |
| PSI-101 HKP gmt250_1 | 558 | 558 | Representative run |

---

## 9. Attribution and licensing

- NASA PSI data are publicly accessible. The repository does not redistribute the raw files; it stores metadata, file names, sizes, and checksums.
- Each investigation has a DOI and a citation list in the PSI record. Publications must be cited when their findings are used.
- The platform must display the NASA source, PSI accession, file name, and retrieval date for every displayed measurement.
- Do not describe NASA data as "ours." Do not imply NASA endorsement of Team AFAQ or the project.
- The code license for this repository has not been selected. Do not add a license file without a team decision. NASA data remain subject to NASA's terms and the terms of the original publications.

---

## 10. Open questions and next verification tasks

These are known unknowns, not assumptions:

1. **SAFFIRE-I telemetry access:** The XLSX files are listed but return 404. Can they be retrieved from an alternate NASA path, or are they permanently unavailable?
2. **PSI-100 timestamp reconciliation:** The raw CSV, cleaned CSV, and 1 Hz XLSX have different row counts and time spans. Which export is authoritative for each sensor?
3. **PSI-100 sensor calibration:** The raw signal names and the human-readable XLSX headers need a documented mapping and calibration source.
4. **PSI-159 `TFP` meaning:** The field is a categorical `Yes`/`No` flag. The source header does not expand the acronym. Confirm its meaning from the CFI-G readme or publication before using it in analysis; do not assign a unit.
5. **BASS-II video-derived spread rates:** Is there a published processed table, or would all spread rates have to be derived? Do not claim spread rates until this is resolved.
6. **SAME-R run-to-material mapping:** The HKP CSV has run/test numbers but not material names. The test logs and results workbook must be joined carefully.
7. **FLEX/FLEX-2/SAFFIRE-II/E-FIELD archive access:** The `added` archive is empty for all four, but public summary tables exist. Monitor with `--check`; do not substitute other data or imply the missing archive was analyzed.
8. **PSI-23 and PSI-39 format audit:** Large raw archives with only a small summary/test-condition table. A dedicated parser assessment is required before archive inclusion.
9. **Experimental-table provenance:** The 14 ET-only tables are not in the `added` inventory. Confirm whether PSI intends them as permanent public artifacts or as a separate curated layer that may change independently of the archive version.
10. **Team profile:** The public Space Apps team page shows the team name, local event, challenge, and a "Team Owner" label, but does not expose a member roster in the server-rendered content. This repository does not invent member names or roles. See `docs/research/source-verification-log.md`.

---

## 11. Summary

The verified foundation is strong enough to build a scientifically honest MVP:

- **Gas flames:** PSI-10 and PSI-159 summary tables.
- **Spacecraft fire telemetry:** PSI-100 SAFFIRE-III.
- **Smoke and detector response:** PSI-101 SAME-R.
- **Material/flow context:** PSI-25 BASS-II and PSI-26 BASS test matrices.
- **Droplet-combustion context:** PSI-69 FLEX summary table.
- **Comparison and limitations:** PSI-98 SAFFIRE-I, PSI-102 SAME, PSI-20, PSI-21, PSI-22, PSI-23, PSI-39, PSI-47, PSI-68, PSI-99, PSI-106, PSI-107, PSI-142.
- **No record is entirely without a public artifact.** Four records are `experimental_table_only`; none is `no_public_files`.

The next phase must download and checksum the MVP files, build parsers with row-level provenance, and validate every field against the source documentation before any chart or AI answer is exposed.
