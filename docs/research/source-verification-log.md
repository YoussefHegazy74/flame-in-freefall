# Source Verification Log

**Project:** Flame in Freefall
**Team:** AFAQ
**Verification date:** 2026-11-08
**Scope:** Every NASA source, endpoint, file inventory, experimental table, and access claim used by the foundation milestone.

This log records what was checked, how, and what was observed. It separates verified facts from unresolved questions. It does not contain invented measurements, team members, or competition details.

---

## 1. Verification environment

| Item | Value |
|---|---|
| Operating system | Linux |
| Python | Python 3 standard library only |
| HTTP client | `curl`, `urllib.request`, and the `r.jina.ai` text proxy where direct access failed |
| Repository | `https://github.com/YoussefHegazy74/flame-in-freefall.git` |
| Local clone | `/mnt/data/flame-in-freefall` |
| Working branch | `main` |
| Commit state at verification | No commits yet; all files untracked |

`pandas`, `openpyxl`, `xlrd`, and `gh` were not installed. CSV and XLSX inspection was done with the standard library and manual ZIP/XML parsing. Legacy `.xls` files were not fully parsed.

---

## 2. Repository verification

| Check | Result |
|---|---|
| GitHub repository exists | Yes |
| Visibility | Public |
| Default branch | `main` |
| Initial state | Empty |
| Remote | `origin` → `https://github.com/YoussefHegazy74/flame-in-freefall.git` |
| Git identity | `joe` / `youssefhegazy7410@email.com` |

No push was attempted before the verification described in this log. Push authentication was not independently verified during the research phase.

---

## 3. Challenge profile verification

Direct requests to `www.spaceappschallenge.org` failed with HTTP 000 / transport errors. The profile was read through the `r.jina.ai` text proxy.

| Field | Observed value |
|---|---|
| Team | AFAQ |
| Local event | Shebeen El-Kom, Egypt |
| Challenge | Flame in Freefall: SI-Powered Fire Safety Insights from Microgravity Combustion Data |
| Member list | Only a "Team Owner" placeholder/avatar was exposed in the server-rendered content |

**Decision:** the repository does not list member names or roles. The public profile does not expose a verified roster, and inventing one would violate the project's integrity rules.

---

## 4. NASA PSI API verification

### 4.1 Search endpoint

```text
GET https://psi.nasa.gov/geode-py/ws/repo/search?source=psi&type=investigation&size=200&from=0
```

| Check | Result |
|---|---|
| HTTP status | 200 |
| Response shape | Elasticsearch-style JSON with `hits.hits[]._source` |
| Total investigations | 133 |
| Combustion matches | 24 |
| Selection rule | `Research Area` contains `Combustion Science` or `SubResearch Area` contains `combust` |

### 4.2 Detail endpoint

```text
GET https://psi.nasa.gov/geode-py/ws/repo/investigations/{PSI-ID}
```

| Check | Result |
|---|---|
| All 24 combustion detail requests | HTTP 200 |
| Fields used | `accession`, `investigationAcronym`, `title`, `doi`, dates, `version`, `public`, `restricted`, `added`, `removed`, `experimentalTable`, `totalFileSize`, publications, contacts, description/objective/hypothesis/approach/impacts |
| `added` semantics | Current public archive inventory |
| `removed` semantics | Prior-version files, not part of the current inventory |
| `experimentalTable` semantics | Separate curated summary-table list |
| `totalFileSize` semantics | Registered total, not the sum of currently exposed `added` files |

### 4.3 Download endpoint

```text
GET https://psi.nasa.gov/geode-py/ws/studies/{PSI-ID}/download?file={url-encoded-filename}
```

| Check | Result |
|---|---|
| Public file without API key | HTTP 200 with file bytes |
| `redirect=false` | HTTP 200 with a presigned S3 URL as plain text |
| Listed file that returns 404 | Observed for SAFFIRE-I telemetry/sensor XLSX and a sampled CFI `.metadata` file |
| Credentials required | None for public, unrestricted files |

The endpoint is necessary but not sufficient evidence of access. Every file used by the platform must pass a retrieval check and a checksum check.

---

## 5. Inventory verification

### 5.1 Collection totals

| Metric | Verified value |
|---|---:|
| Combustion investigations | 24 |
| Current `added` files | 16,354 |
| Registered total bytes | 13,496,771,103,733 |
| Registered total GB (decimal, 10^9 bytes) | 13,496.77 |
| Public experimental tables | 22 |
| Experimental-table bytes | 211,116 |
| Experimental tables also in `added` | 8 |
| Experimental tables only | 14 |
| Distinct public artifacts | 16,368 |
| `archive_status = available` | 20 |
| `archive_status = experimental_table_only` | 4 |
| `archive_status = no_public_files` | 0 |

### 5.2 Per-record inventory

| Accession | Acronym | `added` files | Experimental tables | Registered GB | Archive status | Version |
|---|---|---:|---:|---:|---|---:|
| PSI-10 | ACME/Flame Design | 3,807 | 2 | 2,180.44 | available | 1 |
| PSI-20 | ACME BRE | 1 | 1 | 2,035.57 | available | 4 |
| PSI-21 | ACME CLD Flame | 1 | 1 | 2,005.54 | available | 4 |
| PSI-22 | ACME E-FIELD Flames | 0 | 1 | 950.21 | experimental_table_only | 7 |
| PSI-23 | ACME s-Flame | 4,163 | 1 | 782.17 | available | 4 |
| PSI-25 | BASS-II | 694 | 1 | 274.63 | available | 4 |
| PSI-26 | BASS | 211 | 1 | 163.55 | available | 4 |
| PSI-39 | CFI | 2,831 | 1 | 718.89 | available | 4 |
| PSI-47 | DAFT / DAFT-2 | 32 | 1 | 0.04 | available | 5 |
| PSI-60 | — | 1 | 0 | 0.00 | available | 1 |
| PSI-62 | — | 1 | 0 | 0.00 | available | 1 |
| PSI-68 | FLEX-2 | 0 | 1 | 1,224.75 | experimental_table_only | 6 |
| PSI-69 | FLEX | 0 | 1 | 923.83 | experimental_table_only | 5 |
| PSI-98 | SAFFIRE-I | 74 | 1 | 12.25 | available | 4 |
| PSI-99 | SAFFIRE-II | 0 | 1 | 16.93 | experimental_table_only | 5 |
| PSI-100 | SAFFIRE-III | 85 | 1 | 35.21 | available | 4 |
| PSI-101 | SAME-R | 342 | 1 | 6.31 | available | 4 |
| PSI-102 | SAME | 104 | 1 | 0.66 | available | 4 |
| PSI-106 | SLICE | 1 | 1 | 72.91 | available | 3 |
| PSI-107 | SPICE | 186 | 1 | 6.95 | available | 4 |
| PSI-115 | — | 47 | 0 | 0.26 | available | 3 |
| PSI-117 | — | 15 | 0 | 0.07 | available | 2 |
| PSI-142 | — | 2 | 1 | 0.00 | available | 2 |
| PSI-159 | ACME CFI-G | 3,756 | 2 | 2,085.59 | available | 1 |

The generated registry is the authority for these values. This table is a review aid.

### 5.3 Experimental-table verification

All 22 experimental tables were requested from the download endpoint and returned HTTP 200 with file bytes. Each was inspected for exact header text, physical rows, non-empty data rows, column count, and SHA-256.

| Accession | File | Data rows | Physical rows | Columns | In `added` |
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

**Correction recorded:** an earlier research pass treated the four zero-`added` records as inaccessible. That was wrong. PSI publishes a summary table for each. The roles were corrected to `experimental_table_only` on 2026-11-08, and the `inaccessible` role was retired.

---

## 6. Per-dataset inspection

### 6.1 PSI-10 ACME Flame Design

| Check | Result |
|---|---|
| Normal table | 207 physical/data rows, 15 columns |
| Inverse table | 120 physical/data rows, 14 columns |
| Normal qualifiers | 60 rows contain `RAMP` or `RAMPED` in numeric-looking columns |
| Inverse qualifiers | 11 rows contain `RAMP` or `LOW O2` |
| Missingness | 20 normal rows missing final `XO2`/pressure |
| Fuels | C2H4 (187 normal rows), C3H8 (20 normal rows) |
| Units | `XO2` is a mole fraction; pressure in atm; mass flows in mg/s; `Tad` in K (computed) |

### 6.2 PSI-159 ACME CFI-G

| Check | Result |
|---|---|
| Normal table | 179 physical/data rows, 18 columns |
| Inverse table | 1,015 physical rows, 154 valid, 861 trailing blank rows |
| `Cool flame?` | Blank in 171 of 179 normal rows; blank is not "no" |
| Spreadsheet errors | 2 `#DIV/0!` rows in normal `Tad`/`Zst`; 2 `#VALUE!` rows in inverse `Peak burner temp (K)` |
| `TFP` | Categorical `Yes`/`No`; not a temperature and has no unit |
| Temperature | Peak burner temperature is measured in C and K; `Tad` is computed |

### 6.3 PSI-100 SAFFIRE-III

| Check | Result |
|---|---|
| Raw CSV | 3,972 physical rows, 3,966 valid; 47 columns; raw signal names such as `P@sfsHk.*` and `P@CDH_*` |
| Cleaned CSV | 11,450 physical rows, 11,449 valid |
| 1 Hz XLSX `RawData` | 73,462 physical rows, 11,449 valid; 50 columns with human-readable headers and units |
| XLSX-only columns | `Cyg-Saf TS (ms)`, `Saffire Repeat?`, `Row to Row Delta T (ms)`; the latter two had no populated values in the inspected workbook |
| Time column | `RelativeSeconds` values are milliseconds, despite the name |
| Concatenation | The three exports must not be concatenated without timestamp reconciliation |
| Sample table | 2 rows, 9 columns; SIBAL fabric samples S1/S2 |

### 6.4 PSI-101 SAME-R

| Check | Result |
|---|---|
| Representative HKP CSV | 98 columns, 558 rows |
| Channels | Gas-plume temperature, sample resistance, ISS/STS detector voltages, P-Trak and DustTrak, LFE/MFC flows, GN2/vacuum/drive/sample pressures, device states |
| `PTrakMeasurement(PtPerCC)` | Contains `-999`; this is a sentinel, not a negative concentration |
| `DustTrakA` | All zero in the inspected run; not evidence of a measured zero |
| Sample/test table | 109 rows, 10 columns; `n/a` appears in net aging time; the year is not stated |

### 6.5 PSI-25 BASS-II

| Check | Result |
|---|---|
| Test-matrix workbook | 6 PI-specific sheets, 16 columns, 129 data rows |
| Combined experimental table | 17 columns, 129 rows |
| Readme | Defines flow-restrictor codes 0/1/2, fan display as voltage×10, air display in cm/s, radiometer gain as uncalibrated, `OR` as CO over range >1000 ppm |
| Missingness | `none`, `OR`, `>500`, `over`, `-1`, blanks in fan/air/final CO2/final CO |
| Spread rate | Not published as a processed table |

### 6.6 PSI-26 BASS

| Check | Result |
|---|---|
| As-run matrix | Header row 3; 130 non-empty data rows after header; 2012 sheet 82 rows, 2013 sheet 48 rows |
| Experimental table | 122 rows, 6 columns (Date, GMT, As Run Test #, Test #, Sample #, Fuel Sample Material) |
| Spread rate | Not published as a processed table |
| Numeric columns | Free text and `n/a` appear in numeric-looking columns; per-column parsing is required |

### 6.7 PSI-69 FLEX

| Check | Result |
|---|---|
| Table | 274 rows, 15 columns |
| Variables | Fuel, ambient pressure/composition, initial droplet diameter, visible flame extinction diameter, burning rate, burn time, test end |
| Encoding | `�` (U+FFFD) appears in 6 initial-diameter and 28 extinction-diameter cells; preserve and flag as `invalid_encoding` |
| `Burning rate; mm` | The header says mm, not mm/s; do not relabel as a rate without source confirmation |
| Pressure | mmHg; do not merge with atm/bar/psi axes without conversion |
| Approximate text | `~6`, `~9` in burn time; parse only with a documented approximation flag |

### 6.8 PSI-99 SAFFIRE-II

| Check | Result |
|---|---|
| Table | 15 rows, 17 columns |
| Microgravity columns | Incomplete or non-numeric (`n/a`, `~ 0`, `Insignificant`, `Complete`, `Acceleratory`) |
| `1-g Spread Rate` | Normal-gravity comparison only; must not be labeled microgravity |
| Headers | Literal `?` in `?-g Burn Length` and `?-g Spread Length`, likely a lost micro sign; preserve the raw header |
| Source typo | `Samle Thickness` is preserved as published |

### 6.9 PSI-68 FLEX-2

| Check | Result |
|---|---|
| Table | 8 rows, 7 columns |
| Contents | Condition ranges and lists, not per-test measurements |
| Example | Initial droplet diameter `1.5 - 5` mm; oxygen `0.17; 0.21;0.25; 0.3`; pressure `0.5; 1.0; 1.5; 2.0; or 3.0` atm |
| Use | Context only; do not compute means or plot ranges as individual test points |

### 6.10 Other tables

| Accession | Rows × columns | Inspection note |
|---|---|---|
| PSI-20 | 18 × 8 | Test-day summary; notes blank 16; oxygen text anomalies `3400%`, `2100%` |
| PSI-21 | 32 × 8 | Test-day summary; notes blank 31; MFC units not stated |
| PSI-22 | 32 × 10 | Test-day summary; 11 continuation rows with blank test identity |
| PSI-23 | 18 × 9 | Test-day summary; notes blank 15 |
| PSI-39 | 87 × 10 | Test-condition log; fiber blank 9; pressure is text with units |
| PSI-47 | 2 × 5 | Instrument session log |
| PSI-98 | 4 × 13 | 2 sample rows + 2 pre-test flow-visualization rows |
| PSI-102 | 8 × 5 | Numeric blanks in rows 5–8 mean "same conditions as 1–4" |
| PSI-106 | 12 × 2 | Test date and fuel type only; no measured variables |
| PSI-107 | 469 × 9 | Flame-length/airflow table; flame-off blank 11, fuel rate blank 12, air rate blank 25 |
| PSI-142 | 8 × 4 | Figure/data index, not measurements |

---

## 7. Access failures and anomalies

| Record | File or check | Observed behavior | Handling |
|---|---|---|---|
| PSI-98 | `PSI-98_Raw Data_Saffire-I Telemetry Data Good Process Version.xlsx` | HTTP 404 on 2026-11-08 | Recorded as `listed_404`; not ingested |
| PSI-98 | `PSI-98_Raw Data_Saffire-I Sample 1 Sensor Data Complete TM graphs.xlsx` | HTTP 404 on 2026-11-08 | Recorded as `listed_404`; not ingested |
| PSI-39 | Sampled `.metadata` file | HTTP 404 on 2026-11-08 | Recorded as `listed_404`; not ingested |
| PSI-142 | Experimental table | Initial request failed; a retry succeeded | Treat as flaky; verify checksum on every fetch |
| PSI-159 inverse | 861 trailing blank rows | Blank rows after data | Preserve physical row count and valid row count separately |
| PSI-69 | `�` replacement characters | Non-UTF-8 source bytes | Preserve raw value; flag `invalid_encoding` |
| PSI-100 | Three exports with different row counts | Raw, cleaned, and XLSX differ | Keep separate; never concatenate without reconciliation |
| PSI-101 | `DustTrakA` all zero | Constant channel | Flag `constant_channel`; do not infer a physical zero |
| PSI-101 | `PTrakMeasurement(PtPerCC)` `-999` | Sentinel | Flag `sentinel_minus_999`; do not plot as a concentration |

---

## 8. Checksums

SHA-256 values for every inspected experimental table are recorded in `data/registry/annotations.json` and `data/registry/psi_experimental_tables.csv`. The full list is also in `DATA_SOURCES.md` §8.2. The registry generator copies the checksums; it does not recompute them. A checksum mismatch on a later download is a source change and must be reviewed, not silently accepted.

---

## 9. Corrections made during verification

1. **Experimental tables were initially missed.** The first pass read only `added` and labeled PSI-22, PSI-68, PSI-69, and PSI-99 as inaccessible. A second pass read `experimentalTable` and found 22 public tables. The roles were corrected: PSI-22, PSI-68, and PSI-99 are context; PSI-69 is supporting. The `inaccessible` role was retired.
2. **`file_count` was ambiguous.** It now always means `added` entries only. Experimental tables have their own count, byte total, and manifest.
3. **`distinct_public_artifacts` was added.** It counts 16,354 `added` files plus the 14 experimental tables that are not in `added`, for 16,368. Adding the full 22 would double-count 8 tables.
4. **The collector was updated** to emit `experimental_table_count`, `experimental_table_bytes`, `experimental_table_only_count`, `archive_status`, and `psi_experimental_tables.csv`.
5. **The catalog generator was added** so the MVP catalog is reproducible rather than hand-edited.

---

## 10. Open questions

1. **SAFFIRE-I telemetry access:** the XLSX files are listed but return 404. Is there an alternate NASA path, or are they permanently unavailable?
2. **PSI-100 authoritative export:** which of the raw CSV, cleaned CSV, and 1 Hz XLSX is authoritative for each sensor?
3. **PSI-100 calibration:** the raw signal names and human-readable headers need a documented mapping and calibration source.
4. **PSI-159 `TFP` meaning:** the source header does not expand the acronym. Confirm from the CFI-G readme or publication before analysis.
5. **BASS-II video-derived spread rates:** is there a published processed table, or must all spread rates be derived?
6. **SAME-R run-to-material mapping:** the HKP CSV has run/test numbers but not material names. The test logs and results workbook must be joined carefully.
7. **Experimental-table permanence:** the 14 ET-only tables are not in `added`. Confirm whether PSI treats them as permanent public artifacts or as a curated layer that can change independently.
8. **PSI-23 and PSI-39 format audit:** large raw archives with small summary/test-condition tables. A parser assessment is required before archive inclusion.
9. **Team roster:** the public challenge profile does not expose a verified member list. Do not add names without consent and a verifiable source.

---

## 11. Verification commands

```bash
# Search the PSI API.
curl -sS 'https://psi.nasa.gov/geode-py/ws/repo/search?source=psi&type=investigation&size=200&from=0'

# Fetch one detail record.
curl -sS 'https://psi.nasa.gov/geode-py/ws/repo/investigations/PSI-159'

# Inspect a download redirect without following it.
curl -sS 'https://psi.nasa.gov/geode-py/ws/studies/PSI-159/download?file=PSI-159_Experimental%20table_CFI-G_Normal%20Flames.csv&redirect=false'

# Regenerate and verify the committed registry.
python3 scripts/fetch_psi_metadata.py --check
python3 scripts/build_mvp_catalog.py --check
```

For a full source narrative, see `DATA_SOURCES.md`. For field-level meaning, see `DATA_DICTIONARY.md`.
