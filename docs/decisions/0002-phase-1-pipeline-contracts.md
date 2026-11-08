# ADR 0002 — Phase 1 Pipeline Contracts

- **Status:** Accepted
- **Date:** 2026-11-09
- **Decision owners:** Team AFAQ
- **Supersedes:** None
- **Related:** `README.md`, `PROJECT_ARCHITECTURE.md`, `DEVELOPMENT_ROADMAP.md`, `DATA_SOURCES.md`, `DATA_DICTIONARY.md`, `data/registry/download_manifest.json`, `data/registry/canonical_schema.json`

---

## 1. Context

Phase 0 established a verified metadata registry: 24 Combustion Science investigations, 16,354 current `added` files, 22 public experimental summary tables, and a curated MVP role catalog. It did not acquire data or implement parsers.

Phase 1 had to turn that registry into reproducible analytical tables without crossing three lines:

1. **Scope.** The full PSI archive is roughly 13.5 TB. The project must not download it.
2. **Scientific integrity.** Missingness, sentinel tokens, units, and ambiguous headers must be preserved or explicitly flagged, never invented or silently coerced.
3. **Reproducibility.** Every selected byte must be checksummed, every output row must carry provenance, and the canonical dataset must have a deterministic version.

This ADR records the contracts that the Phase 1 implementation enforces. It is deliberately specific: a later change to any of these rules requires a version bump and regenerated reports.

---

## 2. Decision summary

| Area | Decision |
|---|---|
| Acquisition selection | A curated 72-file manifest, 56,238,344 expected bytes, with hard selection limits. |
| Download behavior | Stream to `data/raw/<accession>/`, verify HTTP status, expected size, and SHA-256, record retrieval time, never overwrite silently. |
| Parsing | Fail closed on unexpected headers; preserve raw cells, raw values, source rows, and per-source issues. |
| Sentinels | Channel-specific classification; no global numeric sentinel rule; never coerce missingness to zero. |
| Telemetry | Each PSI-100 export/sheet and each PSI-101 HKP file is a separate run; never concatenate. |
| Canonical storage | 13 explicit-schema Parquet tables with primary keys and row-level provenance. |
| Versioning | Dataset version = SHA-256 over source file IDs and checksums plus parser, pipeline, and canonical-schema versions. |
| Validation | Fail with a non-zero exit code on missing files, size/checksum drift, missing tables, row-count drift, or duplicate primary keys. |
| Tests | 150 tests: 136 unit and 14 full-data integration; fixtures are authentic excerpts, never synthetic data. |

---

## 3. Manifest selection contract

### 3.1 Selected set

The committed manifest selects exactly **72 files / 56,238,344 bytes** across 20 investigations:

- all 22 public experimental summary tables;
- PSI-100's three published telemetry exports:
  - `PSI-100_Raw Data_Raw telemetry file.csv`;
  - `PSI-100_Raw Data_Saffire_Data_Table2017.161.00.42.03-EU.csv`;
  - `PSI-100_Raw Data_Saffire-III 1 Hz Telemetry Data.xlsx`;
- all 44 PSI-101 `HKPData` CSV runs;
- the PSI-25 BASS-II and PSI-26 BASS test-matrix workbooks;
- one small PSI-102 legacy `.xls` test log.

### 3.2 Explicit exclusions

- No file is selected merely because it exists in the archive inventory.
- Files known to return HTTP 404 are not selected. The two PSI-98 SAFFIRE-I telemetry/sensor XLSX files remain documented as `listed_404` and are re-verified during acquisition.
- Chart-only workbook sheets with nested headers or dummy data are not parsed.
- Analyzed PSI-101 `.xls` files are not selected; the raw HKP CSV series is the coherent acquisition set.
- Video, PDF, DOCX, ZIP, and the rest of the 13.5 TB archive are out of scope.

### 3.3 Limits

The downloader refuses a selection above:

- 100 files;
- 100,000,000 total bytes;
- 50,000,000 bytes for a single file.

`--allow-large` is the only override, and it is an explicit operator action, not a default. The manifest builder validates the same limits. A dry run prints the selection without network access.

### 3.4 Why these files

The set is chosen for analytical value and testability, not narrative convenience:

- PSI-10 and PSI-159 provide test-level gas-flame summaries with fuel, oxygen, pressure, ignition, cool-flame, and extinction fields.
- PSI-100 provides 1 Hz spacecraft fire-environment telemetry.
- PSI-101 provides smoke/aerosol housekeeping data and detector response.
- PSI-25/26 provide material/test context but no published spread-rate table.
- PSI-102 provides a small legacy test-log fixture for the `.xls` path.

---

## 4. Acquisition contract

### 4.1 Storage

Raw files are written to `data/raw/<accession>/<file_name>`. The directory is gitignored. Files are set read-only (`chmod 444`) after verification. Parsers never write to `data/raw/`.

### 4.2 Verification

Every retrieval records:

- HTTP status;
- expected bytes and actual bytes;
- expected SHA-256 and actual SHA-256;
- retrieval timestamp in UTC;
- source URL;
- attempts and error text.

A file is accepted only when the HTTP status is successful, the byte count matches the manifest when an expected size is known, and the SHA-256 matches. A mismatch is a failure, not a warning.

### 4.3 Resume and replacement

- An existing file is re-hashed and accepted only if it matches the manifest; it is recorded as `already_present`.
- `--force` replaces an existing file only after the replacement verifies.
- Partial or failed downloads are not recorded as successful.
- Duplicate checksums across selected files are reported; identical content is not silently treated as two independent measurements.

### 4.4 Known unavailable files

Known 404s are verified with a bounded request and recorded as `listed_404` with the observed status. They are never replaced with synthetic data or an unverified mirror.

### 4.5 Phase 1 result

| Check | Result |
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

---

## 5. Parsing and provenance contract

### 5.1 Fail-closed headers

CSV parsers require an exact header match against the committed schema registry. A mismatch raises a typed error; the parser does not guess, reorder, or fuzzy-match columns. XLSX sheets are selected by name, not by position.

### 5.2 Source-row preservation

Every non-empty source row is preserved in `source_row` or a domain table with:

- accession;
- file name;
- sheet, when applicable;
- 1-based source row after the header;
- source SHA-256;
- retrieval timestamp;
- parser version.

Blank rows still consume a source-row number so that row counts are auditable. For example, the PSI-159 inverse table has 1,015 physical rows but only 154 valid test rows.

### 5.3 Cell preservation

All 22 experimental tables are preserved cell-by-cell in `experimental_table_cell` (24,573 non-empty cells), regardless of whether a dedicated domain parser also handles the table. This is a provenance backstop and prevents a specialized parser from hiding source content.

### 5.4 Observation identifiers

Observation IDs are deterministic and include a short SHA-1 digest over the full source key. The digest prevents collisions when long file names, sheets, rows, or channels are truncated for display.

### 5.5 Raw and numeric values

Point tables keep both:

- `raw_value`: the exact source text;
- `value`: the parsed numeric value, or null;
- `quality_flag`: the classification of the raw token.

A null `value` never erases the source text.

### 5.6 Issue attribution

Parse issues are attributed to the source that produced them. A single PSI-69 encoding warning is reported once for the droplet parser and once for the summary-table parser, not copied onto all 22 summary-table sources. The top-level `issue_count` is the sum of per-source issue counts.

---

## 6. Sentinel and missingness policy

### 6.1 Channel-specific, not global

A token is interpreted in its channel and dataset context. The pipeline does not apply a global rule such as "all `-999` values are missing" or "all negative values are sentinels."

| Token | Flag | Scope |
|---|---|---|
| empty string | `missing` | All sources |
| `-`, `--`, `–`, `—` | `sentinel_dash` | All text fields; dashes are never numeric zero |
| `n/a`, `na`, `not applicable` | `not_applicable` | Text/condition fields |
| `none` | `not_measured` | Test-matrix context |
| `OR`, `over range` | `over_range` | BASS-II CO columns |
| `RAMP`, `RAMPED` | `ramped_condition` | PSI-10 qualifiers |
| `LOW O2` | `low_oxygen_condition` | PSI-10 inverse qualifiers |
| `#DIV/0!`, `#VALUE!`, `#N/A`, `#REF!`, `#NAME?`, `#NUM!`, `#NULL!` | `spreadsheet_error` | Spreadsheet cells |
| `-999` | `sentinel` | SAME-R P-Trak channel only |
| `-1` | `sentinel_minus_one` | BASS-II initial CO context |
| `-1.#IND` | `invalid_indefinite` | SAME-R numeric channels |
| `~0`, `~6`, `~9` | `approximate` | Numeric text with an explicit approximation |
| `>500` | `inequality_text` | CO text |
| `1.5 - 5`, `0.5; 1.0; ...` | `range_text` | Condition lists, not single observations |

### 6.2 No sentinel-to-zero coercion

A sentinel produces a null numeric `value` and a flag. It never becomes `0`. A real zero remains `0.0` with `ok` or an appropriate channel flag. The tests include a negative case that a sentinel is not coerced to zero.

### 6.3 Encoding

- Plain UTF-8 is reported as `utf-8`.
- A UTF-8 BOM is reported as `utf-8-sig`.
- PSI-69 is Windows-1252. Its `0x96` bytes are en dashes, not U+FFFD replacement characters. The fallback is explicit and reported.
- Replacement decoding is the last resort and is always flagged. The authenticated Phase 1 files do not require it.

### 6.4 Versioning sentinel semantics

`PARSER_VERSION` is `1.0.1`. Any change to token classification, encoding behavior, or categorical handling requires a parser-version bump, a full reparse, a canonical rebuild, and regenerated reports. The en-dash and `categorical()` corrections in Phase 1 are the reason the version is not `1.0.0`.

---

## 7. Separate telemetry runs

### 7.1 PSI-100

The raw CSV, cleaned CSV, and 1 Hz XLSX are different exports with different row counts and time spans. Within the XLSX, `RawData`, `SaffireData`, and `CygnusData` are separate sheets. They are stored as five distinct `telemetry_run` rows and are never concatenated into one series.

| Run | Valid rows |
|---|---:|
| Raw CSV | 3,966 |
| Cleaned CSV | 11,449 |
| XLSX `RawData` | 11,449 |
| XLSX `SaffireData` | 11,449 |
| XLSX `CygnusData` | 11,449 |

The difference between the raw CSV and the other exports is documented, not reconciled by assumption. The canonical `telemetry_point` table has 1,762,436 rows.

### 7.2 PSI-101

All 44 HKP CSVs share the exact 98-column header. They are 44 separate `smoke_run` rows and 6,251,427 `smoke_point` rows. One truncated final row in `gmt251_5` (25 fields instead of 98) is preserved as a `row_shape` issue and is not emitted as points.

### 7.3 Why not concatenate

Concatenation would imply a continuous time base and comparable calibration that the exports do not establish. Keeping runs separate lets the API expose run identity and lets a later comparability layer decide what may be joined.

---

## 8. Canonical Parquet contract

### 8.1 Tables and keys

The canonical build produces 13 tables under `data/processed/`:

| Table | Rows | Primary key |
|---|---:|---|
| `psi_investigation` | 24 | `accession` |
| `psi_file` | 16,354 | `file_id` |
| `experimental_table` | 22 | `table_id` |
| `gas_flame_test` | 660 | `observation_id` |
| `telemetry_run` | 5 | `run_id` |
| `telemetry_point` | 1,762,436 | `observation_id` |
| `smoke_run` | 44 | `run_id` |
| `smoke_point` | 6,251,427 | `observation_id` |
| `smoke_test_log` | 119 | `log_id` |
| `material_test` | 259 | `observation_id` |
| `droplet_test` | 274 | `observation_id` |
| `experimental_table_cell` | 24,573 | `cell_id` |
| `source_row` | 2,009 | `source_row_id` |

Total: **8,058,206 rows / 82,953,195 bytes**.

### 8.2 Schema

Each table has an explicit Arrow schema in `src/data_pipeline/schemas.py`, exported to `data/registry/canonical_schema.json`. The schema records field names, types, nullability, primary keys, and descriptions. There is no schema inference at write time.

### 8.3 Point-table shape

Telemetry and smoke points are tidy long tables. Each point carries:

- run ID;
- channel name and canonical channel name;
- unit and unit status (`stated`, `not stated`, `uncalibrated`);
- raw value, numeric value, and quality flag;
- source accession, file, sheet, row, checksum, retrieval time, and parser version.

### 8.4 Dataset version

The dataset version is:

```text
sha256(
  JSON of sorted [file_id, sha256] source pairs
  + parser_version
  + pipeline_version
  + canonical_schema_version
)
```

The current version is:

```text
2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb
```

It is stored in `data/processed/dataset_manifest.json` and `data/reports/processing_report.json`. Changing a source checksum, a parser semantic, or the canonical schema produces a new version.

### 8.5 `psi_file` coverage

`psi_file` contains 16,354 inventory rows. Only 58 of those rows intersect the 72-file acquisition manifest. The other 14 selected experimental tables are not in the current `added` inventory; they are covered by `experimental_table` rather than being forced into `psi_file` with invented inventory metadata. This is documented in the table builder and tested.

---

## 9. Validation and quality gates

### 9.1 Acquisition validation

For every selected file, validation checks presence, expected size, and SHA-256 against the acquisition manifest. It also re-verifies known 404s and reports duplicate checksum groups. Phase 1 result: **72 / 72 verified, 0 failed**.

### 9.2 Canonical validation

For every canonical table, validation checks presence, readable Parquet metadata, expected row count, non-null primary key, and primary-key uniqueness. Phase 1 result: **13 checks, 0 failed**.

### 9.3 Quality report

The quality report summarizes:

- table and point counts;
- missingness by field;
- quality-flag distributions;
- channel unit coverage;
- provenance completeness;
- cross-table issue attribution.

Phase 1 result: **pass**, with 6 issues: 0 errors, 5 warnings, 1 informational note. The issues are:

1. PSI-26 `O2 % by volume` values are around 0.22 while the header says percent; stored as `o2_pct` and flagged `unit_ambiguity`.
2. PSI-69 `Burning rate; mm` is preserved as labeled and flagged `unit_ambiguity`.
3. Some gas-flame tests have a missing final O2/pressure state.
4. Spreadsheet error tokens are preserved as non-numeric values.
5. Some telemetry channels are raw/uncalibrated and labeled as such.
6. SAME-R `-999` sentinels are preserved with null numeric values.

### 9.4 Failure behavior

`validate` and `report` exit non-zero on a failed gate. A missing raw file, an unexpected header, a size or checksum mismatch, a missing canonical table, a row-count mismatch, or a duplicate primary key stops the pipeline rather than producing a partial "success" report.

---

## 10. Test strategy

### 10.1 Layers

| Layer | Count | What it covers |
|---|---:|---|
| Unit | 136 | Token classification, header validation, encoding, Excel dates, manifest limits, downloader safety, schemas, canonical builders, CLI routing, validation failure paths |
| Integration | 14 | Full raw/processed-data counts, checksums, registry reproducibility, fixture reproducibility |

The integration tests require the downloaded raw files and built tables. They are marked `integration` and can be excluded with `-m "not integration"`.

### 10.2 Authentic fixtures

Seven fixtures under `data/fixtures/csv/` are exact excerpts from authenticated NASA sources. The source header is unchanged and the selected rows are copied without editing values. `fixtures_manifest.json` records the source checksum, 1-based source rows, fixture checksum, byte size, encoding, column count, and purpose. The fixture builder refuses to build if a source checksum does not match the acquisition manifest.

The fixtures cover:

- PSI-10 normal rows with `RAMPED` and missing final state;
- PSI-159 normal rows with categorical `TFP` and dash sentinels;
- PSI-159 inverse rows with `#VALUE!` and dash sentinels;
- PSI-69 Windows-1252 en dashes;
- PSI-100 telemetry with a negative sentinel timestamp;
- PSI-101 HKP rows with `-999` and `-1.#IND`;
- a PSI-102-style headerless log excerpt.

### 10.3 Failure tests

Tests assert that:

- an unexpected header raises a typed error;
- a missing file fails rather than being skipped;
- a sentinel is not coerced to zero;
- a checksum mismatch fails verification;
- a downloader response is closed correctly;
- a duplicate primary key fails canonical validation;
- `--check` modes are read-only and exit 1 on drift.

### 10.4 No synthetic data

Fixtures are never fabricated to make a parser pass. When a source file is unavailable (for example the PSI-98 XLSX files), the test covers the documented unavailable state instead of inventing contents.

---

## 11. Consequences and limitations

### 11.1 Accepted limitations

- PSI-98 SAFFIRE-I telemetry and sensor XLSX files return 404. SAFFIRE-I telemetry is not ingested.
- PSI-159 `TFP` and `Xf` remain unexpanded by the source. `TFP` is categorical; `Xf` is treated as the labeled fuel mole fraction.
- PSI-26 `O2 % by volume` and PSI-69 `Burning rate; mm` are unit-ambiguous; they are preserved and flagged, not converted.
- PSI-101 HKP data do not include material names or aging conditions; joining to test logs requires a later validated mapping.
- BASS/BASS-II have no published spread-rate table. No spread rate is derived.
- Chart-only PSI-100 sheets are not parsed.
- The public AFAQ member roster cannot be verified from the environment; no members are invented.

### 11.2 What this enables

- A serving layer can read only `data/processed/` and never touch raw files.
- Every displayed point can be traced to a source file, sheet, row, checksum, and retrieval time.
- Comparability decisions can be made explicitly in Phase 2 instead of being hidden in parser joins.
- A changed source or parser produces a new dataset version instead of silently mutating an old one.

### 11.3 What this does not enable

- No API, frontend, chart, or AI answer is implemented in Phase 1.
- No risk score, spread rate, or cross-dataset equivalence is claimed.
- No calibration is invented for uncalibrated channels.

---

## 12. Alternatives considered

| Alternative | Why rejected |
|---|---|
| Download the full archive | ~13.5 TB, outside the project's scope and resources. |
| Commit raw data to Git | Bloats the repository and mixes reproducible artifacts with source code. |
| Use pandas for parsing | Adds a large dependency and encourages implicit type coercion. The standard library plus `openpyxl`/`xlrd`/`pyarrow` keeps raw values explicit. |
| Concatenate PSI-100 exports | Implies a shared time base and calibration that the exports do not establish. |
| Apply global sentinel rules | `-999` is channel-specific; a global rule would corrupt valid negative values and hide context. |
| Coerce sentinels to zero | Falsifies measurements and biases aggregates. |
| Infer Parquet schemas at write time | Hides type drift and makes downstream contracts unstable. |
| Use DuckDB as a hard dependency | DuckDB is useful for local queries, but pyarrow must remain sufficient for the pipeline. DuckDB is optional for duplicate-key checks. |
| Fabricate fixtures for unavailable files | Violates scientific integrity and hides access failures. |

---

## 13. Compliance checklist

- [x] Only explicitly selected NASA files were downloaded.
- [x] No full-archive download.
- [x] Raw files are outside Git and read-only.
- [x] Every selected file has HTTP status, size, SHA-256, retrieval time, and source URL.
- [x] Known 404s are recorded, not replaced.
- [x] Parsers fail on unexpected headers.
- [x] Raw values, units, missingness, and sentinels are preserved.
- [x] No measurement, unit, team member, or competition detail was invented.
- [x] Canonical tables have explicit schemas and primary keys.
- [x] Validation and quality reports are machine-readable.
- [x] Tests use authentic excerpts and cover failure behavior.
- [x] The dataset version is deterministic.
- [x] No frontend or LLM integration was started.

---

## 14. Phase 2 follow-up

Phase 2 should decide, with source citations:

1. The comparability allowlist: which datasets may be joined or compared, and on what keys.
2. The blocked-dataset serving state for unavailable or non-comparable sources.
3. The DuckDB query contract over the canonical Parquet tables.
4. The API response envelope for provenance and dataset version.
5. Any unit resolution that Phase 1 deliberately left flagged.
