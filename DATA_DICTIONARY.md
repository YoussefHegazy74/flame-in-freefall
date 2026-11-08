# Data Dictionary

**Project:** Flame in Freefall
**Team:** AFAQ
**Challenge:** Flame in Freefall: SI-Powered Fire Safety Insights from Microgravity Combustion Data
**Snapshot date:** 2026-11-08
**Status:** Source-verified dictionary and proposed canonical schema. No parser or frontend is implemented in this milestone.

This document defines every field used by the MVP, the original header text, the unit or absence of a unit, the missing-value conventions, and the proposed canonical name. It is the contract between the data pipeline, the API, and the interface. If a field is not defined here, it must not be displayed as a measured quantity.

The companion documents are:

- `DATA_SOURCES.md` — verified NASA source inventory, access status, comparability, and limitations.
- `data/registry/psi_combustion_investigations.json` — machine-readable investigation and file metadata.
- `data/registry/psi_file_inventory.csv` — 16,354-row `added` archive manifest.
- `data/registry/psi_experimental_tables.csv` — 22-row experimental-table manifest.
- `data/registry/annotations.json` — curated roles, limitations, table statistics, and checksums.
- `docs/decisions/0001-mvp-dataset-selection.md` — why these datasets were selected.

---

## 1. Reading rules

1. **Raw header first.** The original field name is preserved exactly, including spacing, capitalization, and unit text. Canonical names are additions, never replacements.
2. **Unit honesty.** A unit is recorded only when the source states it or when it is unambiguously encoded in the field name. If the source does not state a unit, the dictionary says `not stated`. It is not guessed.
3. **Missingness is data.** Blank cells, `-`, `n/a`, `none`, `OR`, `RAMP`, `RAMPED`, `LOW O2`, `#DIV/0!`, `#VALUE!`, `-999`, and sentinel timestamps are preserved and flagged. They are never silently converted to zero or dropped without a documented rule.
4. **Computed is not measured.** `Tad (K)`, `Zst`, `mean Zst`, and any derived statistic are computed values. They must be labeled as computed wherever displayed.
5. **One row, one source.** Every canonical observation carries `source_accession`, `source_file`, `source_sheet`, `source_row`, `source_sha256`, and `retrieved_at`.
6. **No cross-dataset identity assumptions.** A field with the same word in two datasets is not automatically the same measurement. See the comparability matrix in `DATA_SOURCES.md`.
7. **Decimal gigabytes.** `GB` means 10^9 bytes throughout this repository.
8. **No invented identifiers.** Test codes, sample numbers, day numbers, and file names are copied from the source. They are not normalized into new identifiers without a mapping table.

---

## 2. Global conventions

### 2.1 Identifiers

| Identifier | Definition | Example |
|---|---|---|
| `accession` | NASA PSI investigation accession, `PSI-<number>` | `PSI-159` |
| `table_id` | Stable identifier for a source table: `accession` + file name + optional sheet name | `PSI-159::CFI-G_Normal_Flames::csv` |
| `source_row` | 1-based data row number after the header row, as read from the source | `1` for the first data row |
| `test_code` | The published test identifier in the `Test` column; preserve spacing and case | `21102 C1` |
| `run_id` | Dataset-specific run identifier, usually a GMT day or file stem | `gmt250_1` |
| `observation_id` | Deterministic hash of `table_id` + `source_row` + canonical field name | `sha256:...` |
| `sha256` | SHA-256 of the exact downloaded file bytes | 64 hex characters |

### 2.2 Data types

| Type | Meaning |
|---|---|
| `string` | Free text, identifier, or categorical value. Never trimmed in the raw layer. |
| `integer` | Whole number. A decimal point in the source is preserved as text if it is not a valid integer. |
| `float` | Numeric value that may be fractional. `NaN` is not used for missingness in the raw layer; missingness is explicit. |
| `boolean` | `true` / `false`, only when the source provides an unambiguous two-state field. |
| `timestamp` | Absolute time with a documented epoch and unit. |
| `category` | A controlled set of source values, preserved exactly; case variants remain distinct until a documented mapping exists. |
| `json` | Structured metadata or a list of flags. |

### 2.3 Missingness and sentinel codes

The following tokens were observed in the inspected MVP files. The canonical `quality_flag` records the token and its meaning. A token is not a numeric zero.

| Source token | Canonical flag | Meaning | Where observed |
|---|---|---|---|
| empty string | `missing_blank` | No value was entered in the source cell. | PSI-10, PSI-159, PSI-20, PSI-21, PSI-26 |
| `-` | `sentinel_dash` | A dash entered by the source author. It usually means not applicable or not measured, but the source does not define it per column. Preserve and inspect context. | PSI-159 peak burner temperature, extinction mode, color |
| `n/a`, `N/A` | `not_applicable` | Not applicable for that test or configuration. | PSI-26 as-run matrix |
| `none` | `not_available` | No value or no frame count was recorded. | PSI-25 BASS-II matrices |
| `OR` | `over_range` | Over range. In BASS-II, the readme defines it as CO > 1000 ppm. | PSI-25 CO columns |
| `RAMP`, `RAMPED` | `qualifier_ramp` | The test used a ramped condition rather than a fixed set point. This is an experiment qualifier, not a number. | PSI-10 normal and inverse tables |
| `LOW O2` | `qualifier_low_o2` | The test was flagged as a low-oxygen condition. Not a numeric value. | PSI-10 inverse table |
| `#DIV/0!` | `spreadsheet_error_div0` | A spreadsheet division-by-zero error. The value is invalid. | PSI-159 normal `Tad (K)`, `Zst` |
| `#VALUE!` | `spreadsheet_error_value` | A spreadsheet type error. The value is invalid. | PSI-159 inverse `Peak burner temp (K)` |
| `-999` | `sentinel_minus_999` | Instrument sentinel observed in the SAME-R P-Trak channel. It is not a negative concentration. | PSI-101 `PTrakMeasurement(PtPerCC)` |
| `-1` | `raw_negative_one` | A negative value observed in BASS-II initial CO. The source does not define it; do not treat it as a physical concentration without confirmation. | PSI-25 `Initial CO (ppm)` |
| `~ 0` | `approx_zero_text` | An approximate-zero text value. It is not a numeric zero and cannot be averaged. | PSI-99 microgravity burn/spread columns |
| `Insignificant` | `qualifier_insignificant` | A non-numeric burn-time outcome. Preserve as text. | PSI-99 `Burn Time (s)` |
| `Complete`, `Acceleratory` | `qualifier_outcome_text` | Non-numeric burn/spread outcome descriptions. Preserve as text. | PSI-99 1-g columns |
| `n/a (Nomex)` | `not_applicable` | Not applicable for the Nomex sample. The parenthetical is part of the source text. | PSI-99 spread columns |
| `~6`, `~9` | `approx_value_text` | Approximate numeric text. Parse only with a documented rule that preserves the approximation flag. | PSI-69 `Burn time; s` |
| `�` (U+FFFD) | `invalid_encoding` | A replacement character produced by a non-UTF-8 byte in the source. It is not a measurement. Preserve the raw byte and flag the field. | PSI-69 droplet/extinction diameter columns |
| `>500`, `over` | `over_range_text` | Non-numeric over-range text in a CO column. Do not coerce to 500 or to a numeric value. | PSI-25 final CO |
| `1.5 - 5`, `0.1 - 5`, `0.5; 1.0; ...` | `range_text` | A range or semicolon-separated condition list. It is not a single observation. | PSI-68 condition table |
| `?` in a header | `literal_question_mark_header` | A literal question mark in the source header, likely a lost micro sign (`µ`). Preserve the raw header; do not invent a replacement label. | PSI-99 `?-g Burn Length`, `?-g Spread Length` |
| `-63632300000000` | `sentinel_timestamp_footer` | A large negative footer/sentinel value in the SAFFIRE raw telemetry `RelativeSeconds` column. | PSI-100 raw CSV |
| `-63632288338155` | `sentinel_timestamp_footer` | A large negative footer/sentinel value in the SAFFIRE cleaned telemetry `RelativeSeconds` column. | PSI-100 cleaned CSV |
| `?` | `unknown` | A question mark entered by the source author. Not observed in the inspected MVP tables, but reserved. | — |

**Zero is not a missing code.** A zero can be a real zero, an off channel, a commanded state, or an uninstrumented channel. The pipeline must not label all zeros as missing. Channel-level context is required.

### 2.4 Time conventions

| Source field | Source unit | Canonical field | Notes |
|---|---|---|---|
| `RelativeSeconds` (PSI-100) | Milliseconds in the inspected exports, despite the name | `relative_time_ms`, `relative_time_s` | The name is misleading. Values run from 0 to 9,573,373 in the raw CSV and 0 to 6,899,845 in the cleaned CSV/XLSX. Do not label the raw column as seconds. |
| `CygnusTimestamp` (PSI-100) | Unix epoch milliseconds | `cygnus_timestamp_ms` | Verified by converting `1496691300155` to a 2017 UTC date. The CSV header does not state the unit. |
| `SaffireTimestamp` (PSI-100) | Not stated; mixed/zero values observed | `saffire_timestamp_raw` | Do not use as a primary time axis until reconciled. |
| `Cyg-Saf TS (ms)` (PSI-100 XLSX) | Milliseconds | `cygnus_minus_saffire_ms` | Header present in `RawData`; no values were populated in the inspected workbook. |
| `Time` (PSI-101) | Unix seconds | `unix_time_s` | Example `1283862804` corresponds to 2010-09-07. |
| `TimeString` (PSI-101) | `YYYY/DDD/HH:MM:SS` | `source_time_string` | `2010/250/12:33:24` is year 2010, day-of-year 250, 12:33:24. |
| `ElapsedTestTime(Secs)` (PSI-101) | Seconds | `elapsed_test_time_s` | Elapsed time within the run. |
| `Actual Date` (PSI-25) | Excel serial date | `test_date` | Example `41689` is 2014-02-19. The header instructs adding one day for leap-year video display dates. |
| `GMT 2014-` (PSI-25) | Day-of-year suffix | `gmt_day_2014` | Example `50` means 2014 day 50. Combine with the year 2014 only after checking the sheet. |
| `Date` (PSI-26) | `M/D/YYYY` string | `test_date` | Example `3/30/2012`. |
| `GMT` (PSI-26) | Integer day identifier | `gmt_day` | Values such as `90`; the source does not label the field as day-of-year, so preserve it as an integer identifier. |

### 2.5 Pressure conventions

| Source unit | Canonical unit | Conversion |
|---|---|---|
| `atm` | `atm` | None. Preserve. |
| `bar` | `bar` | None. Preserve. |
| `psi` | `psi` | None. Preserve. |
| `PSIA` | `psia` | Absolute pressure. Do not convert to psig. |
| `PSIG` | `psig` | Gauge pressure. Do not convert to psia without the local atmospheric reference. |
| `psi/K` | `psi/K` | Composite pressure/temperature channel. Do not split without calibration documentation. |
| `Pa` | `Pa` | None. Preserve. |

**Do not merge `atm`, `bar`, `psi`, `PSIA`, and `PSIG` into one axis.** If a comparison requires a common unit, convert explicitly and record the conversion factor and source.

### 2.6 Temperature conventions

| Source unit | Canonical unit | Notes |
|---|---|---|
| `K` | `K` | Absolute temperature. `Tad (K)` is computed; peak burner `K` is measured. |
| `C`, `DegC` | `°C` | Celsius. Preserve the source label. |
| `(C )` | `°C` | PSI-159 normal has an extra space in the header; canonical `peak_burner_temp_c`. |
| `(C)` | `°C` | PSI-159 inverse header. Same canonical field, but do not merge the C and K columns. |

### 2.7 Flow and concentration conventions

| Source field | Unit | Notes |
|---|---|---|
| `mfuel (mg/s)`, `mN2 (mg/s)`, `mtot (mg/s)` | mg/s | Gas mass flow. |
| `mO2 (mg/s)` | mg/s | Oxygen mass flow in the inverse Flame Design table. |
| `mHC (mg/s)` | mg/s | Hydrocarbon mass flow. |
| `HC burnrate (mg/s)` | mg/s | Hydrocarbon burn rate, as labeled. |
| `O2 flow rate (mg/s)` | mg/s | Oxygen mass flow in the inverse CFI-G table. |
| `XO2`, `XO2 (init)`, `XO2 (final)`, `XO2 before test`, `XO2 after test` | Mole fraction (dimensionless) | Not percent by volume. A value of `0.21` is 21% by volume. Conversion is explicit and reversible. |
| `Xfuel`, `Xf`, `Xf before test`, `Xf after test`, `XC2H4 initial`, `XC2H4 final` | Mole fraction (dimensionless) | The source does not expand `Xf`; treat it as the fuel mole fraction as labeled. |
| `Oxygen Conc (percent)` (PSI-20) | Percent by volume, free text | Semicolon-separated values such as `21; 26.5; 34`. Anomalies `3400%` and `2100%` are preserved raw and flagged. |
| `O2 % by vol` (PSI-25) | Percent by volume | Calibrated initial/final values. |
| `O2 % by volume` (PSI-26) | Percent by volume | As-run matrix. |
| `Air display` (PSI-25) | cm/s | The BASS-II readme defines it as duct flow speed in cm/s with a slow response (~1 min). The header itself does not state the unit. |
| `Air display` (PSI-26) | Displayed flow setting | The BASS experiment description gives a 5–50 cm/s airflow range. The as-run header does not state the unit. Preserve the raw display text. |
| `LFE... (SCCM)` | SCCM | Standard cubic centimeters per minute. |
| `MFC... (LPM)` | LPM | Liters per minute. |
| `MFC... (PSIA)` | PSIA | Absolute pressure. |
| `GN2... (PSIG)` | PSIG | Gauge pressure. |

### 2.8 Computed versus measured

| Field | Status | Why |
|---|---|---|
| `Tad (K)` | Computed | Adiabatic flame temperature calculated from the test conditions. It is not a thermocouple reading. |
| `Zst`, `mean Zst` | Computed | Stoichiometric mixture fraction. |
| `Peak burner T (C )`, `Peak burner Temp (C)`, `Peak burner temp (K)` | Measured | Burner temperature measurements, subject to the source's sensor limits. |
| `TFP` | Categorical flag | `Yes`/`No`; the source header does not expand the acronym. It is not a temperature. |
| `Radiometer1Value` … `Radiometer4Value` | Raw sensor | Relative radiometer output. The inspected headers do not state a calibrated unit. |
| `FIZ1/2 Smoke Detector Obscuration/Scatterometer (V)` | Raw sensor voltage | Volts, as stated in the XLSX headers. Calibration to obscuration percentage is not provided in the inspected files. |
| `PCM Press EPS1/2/3` | Raw sensor pressure | psi, as stated. Calibration and zero offsets are not documented in the inspected files. |
| `body rate`, `acceleration` | Raw inertial measurement | rad/s and m/s^2, as stated in the XLSX headers. |
| `PTrakMeasurement(PtPerCC)` | Raw instrument count | Particles per cubic centimeter, with `-999` sentinel. |
| `DustTrak... (MgPerM3)` | Raw instrument concentration | mg/m³, as stated. Check whether the channel is active; `DustTrakA` is all zero in the inspected run. |

---

## 3. Proposed canonical schema

The canonical schema is a target contract. It is not implemented in this milestone. The purpose is to make provenance explicit and to prevent the API or frontend from inventing joins.

### 3.1 `psi_investigation`

One row per PSI investigation.

| Column | Type | Description |
|---|---|---|
| `accession` | string, PK | `PSI-<number>` |
| `acronym` | string | Source acronym, exactly as published. Empty when the source has none. |
| `title` | string | Source title. |
| `doi` | string | Dataset DOI. |
| `research_area` | string | Source research area. |
| `sub_research_area` | string | Source sub-area. |
| `project_type` | string | Source project type. |
| `start_date` | date, nullable | Source start date. Empty when not provided. |
| `end_date` | date, nullable | Source end date. Empty when not provided. |
| `version` | integer | PSI record version. |
| `public` | boolean | Source public flag. |
| `restricted` | boolean | Source restriction flag. |
| `file_count` | integer | Count of current `added` files. |
| `removed_file_count` | integer | Count of prior-version `removed` files. |
| `experimental_table_count` | integer | Count of current `experimentalTable` entries. |
| `experimental_table_bytes` | integer | Sum of the experimental-table file sizes in bytes. |
| `experimental_table_only_count` | integer | Count of experimental tables not present in `added`. |
| `archive_status` | category | `available`, `experimental_table_only`, `no_public_files`. |
| `registered_total_bytes` | integer | Source `totalFileSize` in bytes. |
| `mvp_role` | category | `primary`, `supporting`, `future`, `context`, `unreviewed`. The `inaccessible` role was retired on 2026-11-08 after experimental tables were verified for the four affected records. |
| `rationale` | string | Curated rationale from `annotations.json`. |
| `limitations` | json | Curated limitation list. |

### 3.2 `psi_file`

One row per current public file.

| Column | Type | Description |
|---|---|---|
| `file_id` | string, PK | `accession` + `/` + `file_name` |
| `accession` | string, FK | Investigation accession. |
| `file_name` | string | Exact source file name. |
| `file_size_bytes` | integer | Source size. |
| `format` | string | Lowercase extension, or `(none)`. |
| `category` | string | Source subcategory, when present. |
| `restricted` | boolean | Source restriction flag. |
| `visible` | boolean | Source visibility flag. |
| `version` | integer | Source file version. |
| `sha256` | string, nullable | Checksum after download; null until retrieved. |
| `retrieved_at` | timestamp, nullable | Retrieval time. |
| `access_status` | category | `available`, `listed_404`, `not_attempted`. The `zero_file_record` value is retired; use `archive_status` on the investigation instead. |
| `source_url` | string | Download endpoint URL, without credentials. |

### 3.2.1 `experimental_table`

One row per current `experimentalTable` entry. This is a separate public artifact list from `added`; an entry may appear in both.

| Column | Type | Description |
|---|---|---|
| `table_id` | string, PK | `accession` + `/` + `file_name` |
| `accession` | string, FK | Investigation accession. |
| `file_name` | string | Exact source file name. |
| `file_size_bytes` | integer | Source size. |
| `in_added` | boolean | Whether the same file name also appears in the `added` archive inventory. |
| `restricted` | boolean | Source restriction flag. |
| `data_rows` | integer, nullable | Non-empty data rows after the header, when inspected. |
| `physical_rows` | integer, nullable | All rows after the header, including blank rows, when inspected. |
| `columns` | integer, nullable | Column count, when inspected. |
| `sha256` | string, nullable | Checksum of the exact file bytes, when downloaded. |
| `notes` | string, nullable | Curated note about blank rows, range text, encoding, or unit ambiguity. |
| `retrieved_at` | timestamp, nullable | Retrieval time. |

### 3.3 `gas_flame_test`

One row per test in PSI-10 or PSI-159.

| Column | Type | Description |
|---|---|---|
| `observation_id` | string, PK | Deterministic identifier. |
| `accession` | string, FK | `PSI-10` or `PSI-159`. |
| `table_id` | string, FK | Source table. |
| `source_row` | integer | 1-based data row. |
| `flame_type` | category | `Normal` or `Inverse`, preserving case variants. |
| `day` | string | Source day identifier. |
| `fuel` | string | Source fuel label. |
| `test_code` | string | Source test identifier. |
| `pressure_mean_atm` | float, nullable | From `pmean (atm)`; null for `approx p (bar)` until converted. |
| `pressure_mean_bar` | float, nullable | From `approx p (bar)`. |
| `oxygen_mole_fraction` | float, nullable | From `XO2` variants. |
| `fuel_mole_fraction` | float, nullable | From `Xfuel` / `Xf` variants. |
| `fuel_mass_flow_mg_s` | float, nullable | From `mfuel` / `mHC` / `HC burnrate`. |
| `oxidizer_mass_flow_mg_s` | float, nullable | From `mO2` / `O2 flow rate`. |
| `diluent_mass_flow_mg_s` | float, nullable | From `mN2`. |
| `total_mass_flow_mg_s` | float, nullable | From `mtot`. |
| `stoich_mixture_fraction` | float, nullable | From `mean Zst` / `Zst`. |
| `adiabatic_flame_temp_k` | float, nullable | From `Tad (K)`; computed. |
| `hot_ignition` | category, nullable | Source value, preserving `Yes`, `No`, `yes`, `no`, `flash`. |
| `cool_flame_flag` | string, nullable | Source `Cool flame?` value, preserving PCI stage text. |
| `tfp_flag` | category, nullable | Source `TFP` value (`Yes`/`No`); meaning not expanded. |
| `burn_time_s` | float, nullable | From `burn time (sec)`. |
| `extinction_mode` | category, nullable | `SE`, `FT`, `-`, preserving source. |
| `peak_burner_temp_c` | float, nullable | From the Celsius column. |
| `peak_burner_temp_k` | float, nullable | From the Kelvin column; do not derive from Celsius without a documented conversion. |
| `color` | string, nullable | Source color description. |
| `comments` | string, nullable | Source comments. |
| `quality_flags` | json | List of `{field, token, flag}` entries. |
| `source_sha256` | string | Checksum of the source file. |
| `retrieved_at` | timestamp | Retrieval time. |

### 3.4 `telemetry_run` and `telemetry_point`

`telemetry_run` describes one SAFFIRE-III export.

| Column | Type | Description |
|---|---|---|
| `run_id` | string, PK | `PSI-100::<file stem>` |
| `accession` | string, FK | `PSI-100` |
| `source_file` | string | Exact file name. |
| `export_kind` | category | `raw_csv`, `cleaned_csv`, `xlsx_rawdata`, `xlsx_saffire`, `xlsx_cygnus` |
| `physical_rows` | integer | Rows after the header. |
| `valid_rows` | integer | Rows with a non-negative, non-sentinel time value. |
| `sentinel_rows` | integer | Rows with a sentinel time value. |
| `time_min_ms` | float | Minimum valid `RelativeSeconds`. |
| `time_max_ms` | float | Maximum valid `RelativeSeconds`. |
| `sha256` | string | File checksum. |
| `retrieved_at` | timestamp | Retrieval time. |

`telemetry_point` is a tidy long table. It is intentionally narrow so that channel-level provenance is explicit.

| Column | Type | Description |
|---|---|---|
| `observation_id` | string, PK | Deterministic identifier. |
| `run_id` | string, FK | Telemetry run. |
| `source_row` | integer | 1-based data row. |
| `relative_time_ms` | float | From `RelativeSeconds`. |
| `relative_time_s` | float | `relative_time_ms / 1000`, derived and labeled. |
| `channel_name_raw` | string | Exact CSV signal name. |
| `channel_name_canonical` | string | Proposed canonical name. |
| `value` | float | Numeric value. |
| `unit` | string | Unit or `not stated`. |
| `quality_flag` | category | `ok`, `constant`, `sentinel`, `uncalibrated`, `not_stated_unit`. |
| `source_sha256` | string | File checksum. |

### 3.5 `smoke_run` and `smoke_point`

`smoke_run` describes one SAME-R HKP CSV.

| Column | Type | Description |
|---|---|---|
| `run_id` | string, PK | `PSI-101::<file stem>` |
| `accession` | string, FK | `PSI-101` |
| `source_file` | string | Exact file name. |
| `test_number` | integer | Source `TestNumber`. |
| `sample_number` | integer | Source `SampleNumber`. |
| `carousel_number` | integer | Source `CarouselNumber`. |
| `run_mode_codes` | json | Distinct `RunMode` codes in the run. |
| `time_min_unix_s` | integer | Minimum `Time`. |
| `time_max_unix_s` | integer | Maximum `Time`. |
| `physical_rows` | integer | Rows after the header. |
| `sha256` | string | File checksum. |
| `retrieved_at` | timestamp | Retrieval time. |

`smoke_point` mirrors `telemetry_point` with `elapsed_test_time_s` and the same provenance fields.

### 3.6 `material_test`

One row per BASS/BASS-II test-matrix row.

| Column | Type | Description |
|---|---|---|
| `observation_id` | string, PK | Deterministic identifier. |
| `accession` | string, FK | `PSI-25` or `PSI-26`. |
| `table_id` | string, FK | Source workbook/sheet or CSV. |
| `source_row` | integer | 1-based data row. |
| `test_date` | date, nullable | Excel serial or `M/D/YYYY` parsed with a documented rule. |
| `gmt_day` | string | Source GMT identifier. |
| `as_run_test_no` | string | Source as-run test number. |
| `test_no` | string | Source test number. |
| `sample_no` | string | Source sample number. |
| `material` | string | Source material description. |
| `flow_restrictor` | string | Source code or text. |
| `fan_display` | string | Source fan display text. |
| `air_display` | string | Source air display text. |
| `radiometer_gain` | string | Source gain text. |
| `total_frames` | string | Source frame count or `none`. |
| `initial_o2_pct` | float, nullable | Calibrated initial O2 % by volume. |
| `final_o2_pct` | float, nullable | Calibrated final O2 % by volume. |
| `initial_co2_pct` | float, nullable | Initial CO2 % by volume. |
| `final_co2_pct` | float, nullable | Final CO2 % by volume. |
| `initial_co_ppm` | float, nullable | Initial CO in ppm; `OR` and `-1` are flagged. |
| `final_co_ppm` | float, nullable | Final CO in ppm; `OR` is flagged. |
| `pressure_atm` | float, nullable | BASS as-run matrix only. |
| `co2_mm_hg` | float, nullable | BASS as-run matrix only. |
| `observations` | string, nullable | Source free-text observations. |
| `quality_flags` | json | Sentinel and parsing flags. |
| `source_sha256` | string | File checksum. |
| `retrieved_at` | timestamp | Retrieval time. |

### 3.7 `derived_metric`

Any computed statistic, rate, comparison, or aggregate.

| Column | Type | Description |
|---|---|---|
| `metric_id` | string, PK | Deterministic identifier. |
| `metric_name` | string | Human-readable name. |
| `domain` | category | `gas_flame`, `telemetry`, `smoke`, `material`. |
| `input_observation_ids` | json | Exact rows used. |
| `method` | string | Formula or algorithm, including exclusions and missingness handling. |
| `method_version` | string | Version of the implementation. |
| `value` | float | Result. |
| `unit` | string | Unit or `dimensionless`. |
| `uncertainty` | json, nullable | Uncertainty or confidence interval, only if computed from documented inputs. |
| `limitations` | json | What the metric does not establish. |
| `created_at` | timestamp | Computation time. |

**No arbitrary risk score.** The MVP does not define a "fire risk score" or rank materials on an invented index. Any future ranking must have a published formula, validated inputs, documented uncertainty, and a clear statement that it is not a NASA product.

### 3.8 `citation`

One row per source or publication used in an answer.

| Column | Type | Description |
|---|---|---|
| `citation_id` | string, PK | Deterministic identifier. |
| `kind` | category | `dataset`, `file`, `publication`, `readme`, `program_page`. |
| `accession` | string, nullable | PSI accession. |
| `title` | string | Citation title. |
| `doi` | string, nullable | DOI. |
| `url` | string | Stable URL. |
| `retrieved_at` | timestamp, nullable | Retrieval time for data files. |

---

## 4. Dataset field dictionaries

### 4.1 PSI-10 ACME Flame Design — normal flames

**Source:** `PSI-10_Experimental table_Flame Design_Normal Flame.csv`
**Rows:** 207 data rows; 15 columns.
**Checksum:** `4a663292bd3f65201943cc71bd661a70383639276a9176f64105b285bf0b6deb`
**Access:** verified on 2026-11-08.

| # | Raw field | Canonical field | Type | Unit | Missing / sentinel | Description |
|---:|---|---|---|---|---|---|
| 0 | `Flame Type` | `flame_type` | category | — | none | `Normal` for all 207 rows. |
| 1 | `Day` | `day` | string | — | none | Source test-day identifier. |
| 2 | `Fuel` | `fuel` | category | — | none | `C2H4` (187 rows) or `C3H8` (20 rows). |
| 3 | `Test` | `test_code` | string | — | none | Source test identifier, e.g. `19115A1`. |
| 4 | `Xfuel` | `fuel_mole_fraction` | float | mole fraction | `RAMP` (57), `RAMPED` (3) | Fuel mole fraction. The qualifier is not a number. |
| 5 | `mfuel (mg/s)` | `fuel_mass_flow_mg_s` | float | mg/s | `RAMP` (57), `RAMPED` (3) | Fuel mass flow. |
| 6 | `mN2 (mg/s)` | `diluent_mass_flow_mg_s` | float | mg/s | `RAMP` (57), `RAMPED` (3) | Nitrogen diluent mass flow. |
| 7 | `mtot (mg/s)` | `total_mass_flow_mg_s` | float | mg/s | `RAMP` (57), `RAMPED` (3) | Total mass flow. |
| 8 | `XO2 (init)` | `oxygen_mole_fraction_initial` | float | mole fraction | none | Initial oxygen mole fraction. `0.21` = 21% by volume. |
| 9 | `XO2 (final)` | `oxygen_mole_fraction_final` | float | mole fraction | blank (20) | Final oxygen mole fraction. Blank is missing, not zero. |
| 10 | `pinit (atm)` | `pressure_initial_atm` | float | atm | none | Initial pressure. |
| 11 | `pfinal (atm)` | `pressure_final_atm` | float | atm | blank (20) | Final pressure. |
| 12 | `pmean (atm)` | `pressure_mean_atm` | float | atm | blank (20) | Mean pressure. |
| 13 | `mean Zst` | `stoich_mixture_fraction` | float | dimensionless | `RAMP` (57), `RAMPED` (3) | Computed mean stoichiometric mixture fraction. |
| 14 | `Tad (K)` | `adiabatic_flame_temp_k` | float | K | `RAMP` (57), `RAMPED` (3) | Computed adiabatic flame temperature. Not measured. |

**Row-level flags:** 60 of 207 rows contain `RAMP` or `RAMPED` in all six numeric columns (`Xfuel`, `mfuel`, `mN2`, `mtot`, `mean Zst`, `Tad`). These rows must be excluded from numeric aggregation unless a documented ramped-condition method is applied. The 20 rows with blank final oxygen/pressure fields are still valid for initial conditions, but not for final-state comparison.

### 4.2 PSI-10 ACME Flame Design — inverse flames

**Source:** `PSI-10_Experimental table_Flame Design_Inverse Flame.csv`
**Rows:** 120 data rows; 14 columns.
**Checksum:** `97933ee9ae0b9ebc6b948a67485a0fe2f8218f753253a4f2be93c40d374c44e4`
**Access:** verified on 2026-11-08.

| # | Raw field | Canonical field | Type | Unit | Missing / sentinel | Description |
|---:|---|---|---|---|---|---|
| 0 | `Flame Type` | `flame_type` | category | — | none | `Inverse` for all 120 rows. |
| 1 | `Day` | `day` | string | — | none | Source test-day identifier. |
| 2 | `Test` | `test_code` | string | — | none | Source test identifier. |
| 3 | `XO2` | `oxygen_mole_fraction` | float | mole fraction | `RAMP` (9), `LOW O2` (2) | Oxygen mole fraction. |
| 4 | `mO2 (mg/s)` | `oxidizer_mass_flow_mg_s` | float | mg/s | `RAMP` (6), `LOW O2` (2) | Oxygen mass flow. |
| 5 | `mN2 (mg/s)` | `diluent_mass_flow_mg_s` | float | mg/s | `RAMP` (9), `LOW O2` (2) | Nitrogen diluent mass flow. |
| 6 | `mtot (mg/s)` | `total_mass_flow_mg_s` | float | mg/s | `RAMP` (9), `LOW O2` (2) | Total mass flow. |
| 7 | `XC2H4 initial` | `fuel_mole_fraction_initial` | float | mole fraction | none | Initial ethylene mole fraction. |
| 8 | `XC2H4 final` | `fuel_mole_fraction_final` | float | mole fraction | none | Final ethylene mole fraction. |
| 9 | `pinit (atm)` | `pressure_initial_atm` | float | atm | none | Initial pressure. |
| 10 | `pfinal (atm)` | `pressure_final_atm` | float | atm | none | Final pressure. |
| 11 | `pmean (atm)` | `pressure_mean_atm` | float | atm | none | Mean pressure. |
| 12 | `mean Zst` | `stoich_mixture_fraction` | float | dimensionless | `RAMP` (9), `LOW O2` (2) | Computed mean stoichiometric mixture fraction. |
| 13 | `Tad (K)` | `adiabatic_flame_temp_k` | float | K | `RAMP` (9), `LOW O2` (2) | Computed adiabatic flame temperature. Not measured. |

**Row-level flags:** 11 of 120 rows contain at least one non-numeric qualifier. The table has no blank cells, but "no blanks" does not mean "all numeric." `LOW O2` is a condition flag; `RAMP` is a ramped-condition flag.

### 4.3 PSI-159 ACME CFI-G — normal flames

**Source:** `PSI-159_Experimental table_CFI-G_Normal Flames.csv`
**Rows:** 179 data rows; 18 columns.
**Checksum:** `d95a621c3fbd27d204dd32ed29fa17d68f2b779d6a523cde8479ed7ebaa5251a`
**Access:** verified on 2026-11-08.

| # | Raw field | Canonical field | Type | Unit | Missing / sentinel | Description |
|---:|---|---|---|---|---|---|
| 0 | `Flame Type` | `flame_type` | category | — | none | `Normal` for all 179 rows. |
| 1 | `Day` | `day` | string | — | none | Source test-day identifier. |
| 2 | `Fuel` | `fuel` | category | — | none | `ethane`, `propane`, `30% butane`, `30% ethane`, `30% propane`, `50% butane`. |
| 3 | `Test` | `test_code` | string | — | none | Source test identifier. |
| 4 | `Cool flame?` | `cool_flame_flag` | string | — | blank (171) | `yes, PCI-A` … `yes, PCI-G`, `no, PCI-hot`. Blank must not be read as "no cool flame." |
| 5 | ` XO2 before test` | `oxygen_mole_fraction_before` | float | mole fraction | none | Leading space in the source header is preserved. |
| 6 | `XO2  after test` | `oxygen_mole_fraction_after` | float | mole fraction | none | Double space in the source header is preserved. |
| 7 | `approx p (bar)` | `pressure_approx_bar` | float | bar | none | Approximate test pressure. |
| 8 | `Xf` | `fuel_mole_fraction` | float | mole fraction | none | Fuel mole fraction as labeled. The source does not expand `Xf`. |
| 9 | `mHC (mg/s)` | `fuel_mass_flow_mg_s` | float | mg/s | none | Hydrocarbon mass flow. |
| 10 | `TFP` | `tfp_flag` | category | — | none | `Yes` (18) or `No` (161). A categorical flag, not a temperature. The source does not expand the acronym. |
| 11 | `Tad (K)` | `adiabatic_flame_temp_k` | float | K | `#DIV/0!` (2) | Computed adiabatic flame temperature. |
| 12 | `Zst` | `stoich_mixture_fraction` | float | dimensionless | `#DIV/0!` (2) | Computed stoichiometric mixture fraction. |
| 13 | `Hot ignition` | `hot_ignition` | category | — | none | `Yes` (132) or `No` (47). |
| 14 | `burn time (sec)` | `burn_time_s` | float | s | blank (4) | Burn duration. |
| 15 | `Self-ext or flow term` | `extinction_mode` | category | — | `-` (46) | `SE` (self-extinguished, 102), `FT` (flow terminated, 31), `-` (46). |
| 16 | `Peak burner T (C )` | `peak_burner_temp_c` | float | °C | `-` (46) | Measured peak burner temperature. The header has an extra space before `)`. |
| 17 | `Comments` | `comments` | string | — | blank (135) | Free-text operator comments. |

**Row-level flags:** `#DIV/0!` appears in both `Tad (K)` and `Zst` for rows 69 and 77 (1-based data rows). These are spreadsheet errors, not values. The `-` in peak burner temperature is a source sentinel, not 0 °C.

### 4.4 PSI-159 ACME CFI-G — inverse flames

**Source:** `PSI-159_Experimental table_CFI-G_Inverse Flames.csv`
**Physical rows:** 1,015; **valid rows:** 154; 861 trailing all-blank rows.
**Columns:** 20.
**Checksum:** `d4d44f8b9896936728748e34d1b6ad0812032a92fa5289599b708c138e3a9b39`
**Access:** verified on 2026-11-08.

| # | Raw field | Canonical field | Type | Unit | Missing / sentinel | Description |
|---:|---|---|---|---|---|---|
| 0 | `Flame Type` | `flame_type` | category | — | blank (861) | `inverse` (90) or `Inverse` (64). Preserve the case variants. |
| 1 | `Day` | `day` | string | — | blank (861) | Source test-day identifier. |
| 2 | `Fuel` | `fuel` | category | — | blank (861) | `butane`, `ethane`, `propane`. |
| 3 | `Test` | `test_code` | string | — | blank (861) | Source test identifier. |
| 4 | `Xf  before test` | `fuel_mole_fraction_before` | float | mole fraction | blank (861) | Fuel mole fraction before the test. |
| 5 | `Xf  after test` | `fuel_mole_fraction_after` | float | mole fraction | blank (861) | Fuel mole fraction after the test. |
| 6 | `approx p (bar)` | `pressure_approx_bar` | float | bar | blank (861) | Approximate test pressure. |
| 7 | `XO2` | `oxygen_mole_fraction` | float | mole fraction | blank (861) | Oxygen mole fraction. |
| 8 | `HC burnrate (mg/s)` | `fuel_burn_rate_mg_s` | float | mg/s | blank (861) | Hydrocarbon burn rate. |
| 9 | `O2 flow rate (mg/s)` | `oxidizer_mass_flow_mg_s` | float | mg/s | blank (861) | Oxygen mass flow. |
| 10 | `TFP` | `tfp_flag` | category | — | blank (861) | `Yes` (12) or `No` (142) among valid rows. Categorical flag, not a temperature. |
| 11 | `Tad (K)` | `adiabatic_flame_temp_k` | float | K | blank (861) | Computed adiabatic flame temperature. |
| 12 | `Zst` | `stoich_mixture_fraction` | float | dimensionless | blank (861) | Computed stoichiometric mixture fraction. |
| 13 | `Hot ignition` | `hot_ignition` | category | — | blank (861) | `Yes` (114), `yes` (17), `No` (13), `no` (2), `flash` (8). Preserve case and `flash`. |
| 14 | `burn time (sec)` | `burn_time_s` | float | s | blank (861) | Burn duration. |
| 15 | `Self -ext or flow term` | `extinction_mode` | category | — | blank (861) | `SE` (81), `FT` (58), `-` (15). The source has a space in `Self -ext`. |
| 16 | `Peak burner Temp (C)` | `peak_burner_temp_c` | float | °C | blank (861), `-` (2) | Measured peak burner temperature in Celsius. |
| 17 | `Peak burner temp (K)` | `peak_burner_temp_k` | float | K | blank (861), `#VALUE!` (2) | Measured peak burner temperature in Kelvin. Do not derive from the Celsius column. |
| 18 | `Color` | `color` | string | — | blank (871 total; 10 among valid), `-` (24) | `blue`, `Blue`, `yellow`, `Yellow`, `Yellow-Blue`, `yellow then blue`, `limit`, `-`. |
| 19 | `Comments` | `comments` | string | — | blank (976 total; 115 among valid) | Free-text operator comments. |

**Valid-row missingness:** among the 154 valid rows, `Peak burner Temp (C)` is missing in 1, `Color` in 10, and `Comments` in 115. `Peak burner temp (K)` has `#VALUE!` in 2 rows.

### 4.5 PSI-100 SAFFIRE-III — raw telemetry CSV

**Source:** `PSI-100_Raw Data_Raw telemetry file.csv`
**Rows:** 3,972 physical; 3,966 valid (non-negative `RelativeSeconds`); 6 sentinel/negative rows.
**Columns:** 47.
**Checksum:** `dfb204ce3bdf8b1749652549afcbad31d180902bc268dfbe782c70fa38d170a2`
**Access:** verified on 2026-11-08.

**Important:** `RelativeSeconds` contains milliseconds in this export. The raw CSV has no units in its headers. The human-readable names and units below come from the verified XLSX `RawData` header, not from the CSV. Mapping raw signal names to XLSX names is a proposed canonical mapping; it is not yet validated against flight documentation.

| # | Raw CSV field | Human-readable XLSX field | Canonical field | Unit | Notes |
|---:|---|---|---|---|---|
| 0 | `RelativeSeconds` | `RelativeSeconds` | `relative_time_ms` | ms (despite name) | 0 to 9,573,373 in the raw CSV. Six negative/sentinel rows. |
| 1 | `CygnusTimestamp` | `CygnusTimestamp` | `cygnus_timestamp_ms` | Unix epoch ms | Verified by conversion; header does not state unit. |
| 2 | `SaffireTimestamp` | `SaffireTimestamp` | `saffire_timestamp_raw` | not stated | Mixed/zero values observed. Reconcile before use. |
| 3 | `P@sfsHk.Radiometer1value` | `Radiometer1Value` | `radiometer_1_raw` | not stated | Raw radiometer output. Relative intensity only. |
| 4 | `P@sfsHk.Radiometer2value` | `Radiometer2Value` | `radiometer_2_raw` | not stated | Raw radiometer output. |
| 5 | `P@sfsHk.Radiometer3value` | `Radiometer3Value` | `radiometer_3_raw` | not stated | Raw radiometer output. |
| 6 | `P@sfsHk.Radiometer4value` | `Radiometer4Value` | `radiometer_4_raw` | not stated | Raw radiometer output. |
| 7 | `P@sfsHk.Anemometer1` | `Anemometer1` | `anemometer_1_raw` | not stated | Raw anemometer output. |
| 8 | `P@sfsHk.Anemometer2` | `Anemometer2` | `anemometer_2_raw` | not stated | Raw anemometer output. |
| 9 | `P@sfsHk.FanTachometer` | `FanTachometer` | `fan_tachometer_raw` | not stated | `SaffireData` includes `Tach/100`; do not assume the raw value is rpm. |
| 10 | `P@sfsHk.SmokeWireVoltage` | `SmokeWireV` | `smoke_wire_voltage_raw` | not stated | Voltage channel by name. |
| 11 | `P@sfsHk.SmokeWireCurrent` | `SmokeWireI` | `smoke_wire_current_raw` | not stated | Current channel by name. |
| 12 | `P@sfsHk.Sample1IgniterVoltage` | `Sample1IgniterV` | `igniter_1_voltage_raw` | not stated | Igniter voltage channel. |
| 13 | `P@sfsHk.Sample1IgniterCurrent` | `Sample1IgniterI` | `igniter_1_current_raw` | not stated | Igniter current channel. |
| 14 | `P@sfsHk.Sample2IgniterVoltage` | `Sample2IgniterV` | `igniter_2_voltage_raw` | not stated | Igniter voltage channel. |
| 15 | `P@sfsHk.Sample2IgniterCurrent` | `Sample2IgniterI` | `igniter_2_current_raw` | not stated | Igniter current channel. |
| 16 | `P@sfsHk.Sample3IgniterVoltage` | `Sample3IgniterV` | `igniter_3_voltage_raw` | not stated | Constant in the inspected export; do not treat as active without flight documentation. |
| 17 | `P@sfsHk.Sample3IgniterCurrent` | `Sample3IgniterI` | `igniter_3_current_raw` | not stated | Constant in the inspected export. |
| 18 | `P@sfsHk.Sample4IgniterVoltage` | `Sample4IgniterV` | `igniter_4_voltage_raw` | not stated | Constant in the inspected export. |
| 19 | `P@sfsHk.Sample4IgniterCurrent` | `Sample4IgniterI` | `igniter_4_current_raw` | not stated | Constant in the inspected export. |
| 20 | `P@sfsHk.Sample5IgniterVoltage` | `Sample5IgniterV` | `igniter_5_voltage_raw` | not stated | Constant in the inspected export. |
| 21 | `P@sfsHk.Sample5IgniterCurrent` | `Sample5IgniterI` | `igniter_5_current_raw` | not stated | Constant in the inspected export. |
| 22 | `P@sfsHk.Sample6IgniterVoltage` | `Sample6IgniterV` | `igniter_6_voltage_raw` | not stated | Constant in the inspected export. |
| 23 | `P@sfsHk.Sample6IgniterCurrent` | `Sample6IgniterI` | `igniter_6_current_raw` | not stated | Constant in the inspected export. |
| 24 | `P@sfsHk.Sample7IgniterVoltage` | `Sample7IgniterV` | `igniter_7_voltage_raw` | not stated | Constant in the inspected export. |
| 25 | `P@sfsHk.Sample7IgniterCurrent` | `Sample7IgniterI` | `igniter_7_current_raw` | not stated | Constant in the inspected export. |
| 26 | `P@sfsHk.Sample8IgniterVoltage` | `Sample8IgniterV` | `igniter_8_voltage_raw` | not stated | Constant in the inspected export. |
| 27 | `P@sfsHk.Sample8IgniterCurrent` | `Sample8IgniterI` | `igniter_8_current_raw` | not stated | Constant in the inspected export. |
| 28 | `P@sfsHk.Sample9IgniterVoltage` | `Sample9IgniterV` | `igniter_9_voltage_raw` | not stated | Constant in the inspected export. |
| 29 | `P@sfsHk.Sample9IgniterCurrent` | `Sample9IgniterI` | `igniter_9_current_raw` | not stated | Constant in the inspected export. |
| 30 | `P@PCM_ETS_TEMP_SIG` | `PCM Air Temp (degC)` | `pcm_air_temp_c` | °C | Air temperature. |
| 31 | `P@F1PCM_AIR_PRES_EPS1_SIG_POS` | `PCM Press EPS1 (psi)` | `pcm_pressure_eps1_psi` | psi | Pressure channel. |
| 32 | `P@F2PCM_AIR_PRES_EPS2_SIG_POS` | `PCM Press EPS2 (Psi)` | `pcm_pressure_eps2_psi` | psi | Header case variant `Psi`. |
| 33 | `P@F3PCM_AIR_PRES_EPS3_SIG_POS` | `PCM Press EPS3 (PSI)` | `pcm_pressure_eps3_psi` | psi | Header case variant `PSI`. |
| 34 | `P@OPS_PCM_PRES_AVG_BY_TEMP` | `PCM Press/Temp (psi/K)` | `pcm_pressure_temp_psi_k` | psi/K | Composite channel. Do not split without calibration. |
| 35 | `P@CDH_F1PCM_SMK_DET_OBS_SENS_P` | `FIZ1 Smoke Detector Obscuration  (V)` | `fiz1_smoke_obscuration_v` | V | Constant in the inspected export. |
| 36 | `P@CDH_F2PCM_SMK_DET_OBS_SENS_P` | `FIZ 2 Smoke Detector Obscuration (V)` | `fiz2_smoke_obscuration_v` | V | Smoke detector obscuration voltage. |
| 37 | `P@CDH_F1PCM_SMK_DET_SCAT_SENS_P` | `FIZ 1 Smoke Detector Scatterometer (V)` | `fiz1_smoke_scatter_v` | V | Near-constant in the inspected export. |
| 38 | `P@CDH_F2PCM_SMK_DET_SCAT_SENS_P` | `FIZ 2 Smoke Detector Scatterometer (V)` | `fiz2_smoke_scatter_v` | V | Smoke detector scatter voltage. |
| 39 | `P@CDH_F1PCM_ECLS_FAN_PRESSURE_P` | `FIZ 1 Cabin Fan delta P (Pa)` | `fiz1_cabin_fan_delta_p_pa` | Pa | Near-constant in the inspected export. |
| 40 | `P@CDH_F2PCM_ECLS_FAN_PRESSURE_P` | `FIZ 2 Cabin Fan Delta P (Pa)` | `fiz2_cabin_fan_delta_p_pa` | Pa | Fan differential pressure. |
| 41 | `P@GNCAttitudeNavigatorShared.omegaEst_bdy.elements[0]` | `body rate x axis (rad/s)` | `body_rate_x_rad_s` | rad/s | Attitude estimate. |
| 42 | `P@GNCAttitudeNavigatorShared.omegaEst_bdy.elements[1]` | `body rate y axis (rad/s)` | `body_rate_y_rad_s` | rad/s | Attitude estimate. |
| 43 | `P@GNCAttitudeNavigatorShared.omegaEst_bdy.elements[2]` | `body rate z axis (rad/s)` | `body_rate_z_rad_s` | rad/s | Attitude estimate. |
| 44 | `P@GNCImuSensor.imu[0].currentMeas_Bdy.acc.elements[0]` | `acceleration x axis (m/s^2)` | `acceleration_x_m_s2` | m/s² | IMU acceleration. |
| 45 | `P@GNCImuSensor.imu[0].currentMeas_Bdy.acc.elements[1]` | `acceleration y axis (m/s^2)` | `acceleration_y_m_s2` | m/s² | IMU acceleration. |
| 46 | `P@GNCImuSensor.imu[0].currentMeas_Bdy.acc.elements[2]` | `acceleration z axis (m/s^2)` | `acceleration_z_m_s2` | m/s² | IMU acceleration. |

**XLSX `RawData` extra columns (not in the CSV):**

| XLSX column | Canonical field | Unit | Notes |
|---|---|---|---|
| `Cyg-Saf TS (ms)` | `cygnus_minus_saffire_ms` | ms | Header present; no values populated in the inspected workbook. |
| `Saffire Repeat?` | `saffire_repeat_flag` | — | Header present; no values populated in the inspected workbook. |
| `Row to Row Delta T (ms)` | `row_to_row_delta_t_ms` | ms | Header present; no values populated in the inspected workbook. |

**SAFFIRE-III workbook sheet map:**

| Sheet | Sheet rows | Header / content | Notes |
|---|---:|---|---|
| `RawData` | 73,463 | 50 columns | Combined export; 73,462 data rows; only 11,449 have a valid `RelativeSeconds`. The rest are empty formatting rows. |
| `SaffireData` | 11,450 | 33 columns | Saffire housekeeping subset: 4 time columns, radiometers, anemometers, fan tach, smoke wire, 9 igniter pairs, `Rel-to-Cygnus Time (s)`, `Tach/100`. |
| `CygnusData` | 69,870 | 25 columns | Cygnus PCM, smoke detector, fan delta P, body-rate, and acceleration subset. |
| `CygnusSmokeDetectorData` | 58,307 | Two blocks | FIZ 2 obscuration and FIZ 2 scatter blocks, each with its own time columns. |
| `CygnusPressureData` | 58,306 | 4 columns + chart annotation | EPS 1/2/3 pressures. The H/I/J cells contain a small igniter chart annotation, not tabular data. |
| `CygnusTemperatureData` | 58,306 | 4 columns | PCM air temperature. |
| `Cygnus-Saffire Timestamp Graph` | 0 | empty | No rows. |
| `RadiometerGraph` | 0 | empty | No rows. |
| `FlowGraph` | 0 | empty | No rows. |
| `CygnusPressTempGraph` | 0 | empty | No rows. |
| `CygnusSmokeDetectorGraph` | 0 | empty | No rows. |
| `timedelta` | 0 | empty | No rows. |

**Other PSI-100 telemetry exports:**

| File | Physical rows | Valid rows | Time range (ms) | Notes |
|---|---:|---:|---:|---|
| `PSI-100_Raw Data_Raw telemetry file.csv` | 3,972 | 3,966 | 0–9,573,373 | 6 negative/sentinel rows. |
| `PSI-100_Raw Data_Saffire_Data_Table2017.161.00.42.03-EU.csv` | 11,450 | 11,449 | 0–6,899,845 | 1 sentinel row (`-63632288338155`). |
| `PSI-100_Raw Data_Saffire-III 1 Hz Telemetry Data.xlsx`, `RawData` | 73,462 | 11,449 | 0–6,899,845 | Empty formatting rows inflate the physical count. |

**Do not concatenate these exports.** They have different row counts, time ranges, and sensor coverage. Reconcile timestamps and channel definitions first.

### 4.6 PSI-101 SAME-R — HKP housekeeping CSV

**Source:** `PSI-101_Raw Data_HKPData_gmt250_1.csv` (representative run)
**Rows:** 558 data rows; 98 columns.
**Checksum:** `69c25a566b6af6b43fb263ceadad82499b6e18e69e5fdad928e8088124ee43a3`
**Access:** verified on 2026-11-08.

This is one run. The record contains multiple HKP CSV files with the same 98-column schema. `TestNumber` is `91` and `SampleNumber`/`CarouselNumber` are `0` in this run; other runs will differ.

**Identifiers and time (columns 0–8):**

| # | Raw field | Canonical field | Type | Unit | Description |
|---:|---|---|---|---|---|
| 0 | `TimeString` | `source_time_string` | string | — | `YYYY/DDD/HH:MM:SS`, e.g. `2010/250/12:33:24`. |
| 1 | `Time` | `unix_time_s` | integer | Unix seconds | Example `1283862804`. |
| 2 | `RunMode` | `run_mode_code` | integer | — | Codes `3` (544 rows) and `4` (14 rows) in this run. Meaning not defined in the inspected file. |
| 3 | `TestNumber` | `test_number` | integer | — | `91` in this run. |
| 4 | `ElapsedTestTime(Secs)` | `elapsed_test_time_s` | integer | s | 66 to 609 in this run. |
| 5 | `SampleNumber` | `sample_number` | integer | — | `0` in this run. |
| 6 | `CarouselNumber` | `carousel_number` | integer | — | `0` in this run. |
| 7 | `DriveKBRemaining` | `drive_kb_remaining` | integer | KB | Remaining drive space. |
| 8 | `CycleCounter` | `cycle_counter` | integer | — | Monotonic cycle counter. |

**Status and diagnostics (columns 9–18):**

| # | Raw field | Canonical field | Type | Unit | Description |
|---:|---|---|---|---|---|
| 9 | `WatchdogReset` | `watchdog_reset` | integer | — | Watchdog reset flag/code. |
| 10 | `EnetSelect` | `enet_select` | integer | — | Ethernet select state. |
| 11 | `EnetOverride` | `enet_override` | integer | — | Ethernet override state. |
| 12 | `OKStatus` | `ok_status` | integer | — | Status flag; `1` throughout this run. |
| 13 | `EventSet` | `event_set` | integer | — | Event set code. |
| 14 | `EventCode` | `event_code` | integer | — | Codes `0` (323 rows) and `32` (235 rows). Meaning not defined in the inspected file. |
| 15 | `TestRunning` | `test_running` | integer | — | Test-running flag. |
| 16 | `12VDCHeaterEnable` | `heater_12vdc_enable` | integer | — | Heater enable flag. |
| 17 | `HeatingInProgress` | `heating_in_progress` | integer | — | Heating flag. |
| 18 | `SampleHeaterOverride` | `sample_heater_override` | integer | — | Heater override flag. |

**Physical measurements (columns 19–44):**

| # | Raw field | Canonical field | Type | Unit | Description |
|---:|---|---|---|---|---|
| 19 | `GasPlumeTemperature(DegC)` | `gas_plume_temp_c` | float | °C | Gas plume temperature; 23.509–110.023 °C in this run. |
| 20 | `SampleResistance(Ohms)` | `sample_resistance_ohm` | float | Ω | Sample resistance; 0.000762951–0.913539 Ω in this run. |
| 21 | `ISSDetectorObscurationMeasurement(Volts)` | `iss_detector_obscuration_v` | float | V | ISS detector obscuration voltage; 2.2287–3.4259 V. |
| 22 | `ISSDetectorScatterMeasurement(Volts)` | `iss_detector_scatter_v` | float | V | ISS detector scatter voltage; negative values observed (-6.24634 to -0.179138 V). Preserve sign. |
| 23 | `STSDetectorMeasurement(Volts)` | `sts_detector_v` | float | V | STS detector voltage; 4.09027–5.30548 V. |
| 24 | `IonDetectorAMeasurement(Volts)` | `ion_detector_a_v` | float | V | Ion detector A voltage. |
| 25 | `IonDetectorBMeasurement(Volts)` | `ion_detector_b_v` | float | V | Ion detector B voltage. |
| 26 | `PTrakMeasurement(PtPerCC)` | `ptrak_concentration_pt_cc` | float | pt/cc | P-Trak particle count; `-999` sentinel observed. |
| 27 | `DustTrakAMeasurement(MgPerM3)` | `dusttrak_a_mg_m3` | float | mg/m³ | All zero in this run; likely inactive. Do not treat as a measured zero without context. |
| 28 | `DustTrakBMeasurement(MgPerM3)` | `dusttrak_b_mg_m3` | float | mg/m³ | 0–225.455 mg/m³ in this run. |
| 29 | `DustTrakAAnalogMeasurement(Volts)` | `dusttrak_a_analog_v` | float | V | Analog channel. |
| 30 | `DustTrakBAnalogMeasurement(Volts)` | `dusttrak_b_analog_v` | float | V | Analog channel. |
| 31 | `LFEFlowRate[AT08](SCCM)` | `lfe_flow_rate_sccm` | float | SCCM | Laminar flow element flow rate. |
| 32 | `VSOSetpoint[PN23](Volts)` | `vso_setpoint_v` | float | V | Valve/setpoint channel. |
| 33 | `ZeroLFE` | `zero_lfe` | integer | — | LFE zero flag. |
| 34 | `MFCSetpoint(LPM)` | `mfc_setpoint_lpm` | float | LPM | Mass-flow controller setpoint. |
| 35 | `MFCMassFlowRate(LPM)` | `mfc_mass_flow_lpm` | float | LPM | Mass-flow controller flow. |
| 36 | `MFCTemperature(DegC)` | `mfc_temperature_c` | float | °C | MFC temperature. |
| 37 | `MFCPressure(PSIA)` | `mfc_pressure_psia` | float | PSIA | MFC absolute pressure. |
| 38 | `MFCAnalogSetpoint[BN19](LPM)` | `mfc_analog_setpoint_lpm` | float | LPM | Analog setpoint. |
| 39 | `MFCAnalogFlowRate(LPM)` | `mfc_analog_flow_lpm` | float | LPM | Analog flow. |
| 40 | `GN2MainPressure[PN02](PSIA)` | `gn2_main_pressure_psia` | float | PSIA | GN2 main pressure. |
| 41 | `GN2RegulatedPressure[PN12](PSIG)` | `gn2_regulated_pressure_psig` | float | PSIG | GN2 regulated gauge pressure. |
| 42 | `VacuumPressure[VR04](PSIA)` | `vacuum_pressure_psia` | float | PSIA | Vacuum pressure. |
| 43 | `DriveSidePressure[BN02](PSIA)` | `drive_side_pressure_psia` | float | PSIA | Drive-side pressure. |
| 44 | `SampleSidePressure[AT20](PSIA)` | `sample_side_pressure_psia` | float | PSIA | Sample-side pressure. |

**Device states and actuators (columns 45–97):**

| # | Raw field | Canonical field | Type | Unit | Description |
|---:|---|---|---|---|---|
| 45 | `ThermalPrecipitatorPreAgeChannel` | `thermal_precipitator_pre_age_channel` | integer | — | Thermal precipitator pre-age channel state. |
| 46 | `ThermalPrecipitatorPostAgeChannel` | `thermal_precipitator_post_age_channel` | integer | — | Thermal precipitator post-age channel state. |
| 47 | `PTrakState` | `ptrak_state` | integer | — | P-Trak state code. |
| 48 | `PTrakKeySelect` | `ptrak_key_select` | integer | — | P-Trak key selection. |
| 49 | `PTrakPowerMeasurement(Volts)` | `ptrak_power_v` | float | V | P-Trak power measurement. |
| 50 | `DustTrakAState` | `dusttrak_a_state` | integer | — | DustTrak A state. |
| 51 | `DustTrakAKeySelect` | `dusttrak_a_key_select` | integer | — | DustTrak A key selection. |
| 52 | `DustTrakBState` | `dusttrak_b_state` | integer | — | DustTrak B state. |
| 53 | `DustTrakBKeySelect` | `dusttrak_b_key_select` | integer | — | DustTrak B key selection. |
| 54 | `ProximitySensor1(Volts)` | `proximity_sensor_1_v` | float | V | Proximity sensor. |
| 55 | `ProximitySensor2(Volts)` | `proximity_sensor_2_v` | float | V | Proximity sensor. |
| 56 | `ProximitySensor4(Volts)` | `proximity_sensor_4_v` | float | V | Proximity sensor. |
| 57 | `CarouselProximitySensor(Volts)` | `carousel_proximity_sensor_v` | float | V | Carousel proximity sensor. |
| 58 | `MixingFanPower` | `mixing_fan_power` | integer | — | Mixing fan power state. |
| 59 | `PTrakPower` | `ptrak_power_state` | integer | — | P-Trak power state. |
| 60 | `DustTrakAPower` | `dusttrak_a_power_state` | integer | — | DustTrak A power state. |
| 61 | `DustTrakBPower` | `dusttrak_b_power_state` | integer | — | DustTrak B power state. |
| 62 | `STSDetectorPower` | `sts_detector_power_state` | integer | — | STS detector power state. |
| 63 | `CarouselPower` | `carousel_power_state` | integer | — | Carousel power state. |
| 64 | `PositionerEnable` | `positioner_enable` | integer | — | Positioner enable. |
| 65 | `PositionerDirectionIn` | `positioner_direction_in` | integer | — | Positioner direction. |
| 66 | `PositionerClock` | `positioner_clock` | integer | — | Positioner clock. |
| 67 | `GN2MainSolenoid[PN03]` | `gn2_main_solenoid` | integer | — | Solenoid state. |
| 68 | `GateEnableSolenoid[PN07]` | `gate_enable_solenoid` | integer | — | Solenoid state. |
| 69 | `InletGateSolenoid[BN08]` | `inlet_gate_solenoid` | integer | — | Solenoid state. |
| 70 | `OutletGateSolenoid[BN09]` | `outlet_gate_solenoid` | integer | — | Solenoid state. |
| 71 | `PistonControlSolenoid[BN17]` | `piston_control_solenoid` | integer | — | Solenoid state. |
| 72 | `DynamicDilutorSolenoid[PN15]` | `dynamic_dilutor_solenoid` | integer | — | Solenoid state. |
| 73 | `PTrakSolenoid[VR06]` | `ptrak_solenoid` | integer | — | Solenoid state. |
| 74 | `CommDiagASolenoid[VR11]` | `comm_diag_a_solenoid` | integer | — | Solenoid state. |
| 75 | `CommDiagBSolenoid[VR12]` | `comm_diag_b_solenoid` | integer | — | Solenoid state. |
| 76 | `CommDiagADilutionSolenoid[PN24]` | `comm_diag_a_dilution_solenoid` | integer | — | Solenoid state. |
| 77 | `CommDiagBDilutionSolenoid[PN27]` | `comm_diag_b_dilution_solenoid` | integer | — | Solenoid state. |
| 78 | `PurgeSolenoid[VM09]` | `purge_solenoid` | integer | — | Solenoid state. |
| 79 | `PistonGN2Solenoid[BN18]` | `piston_gn2_solenoid` | integer | — | Solenoid state. |
| 80 | `PistonVentSolenoid[BN20]` | `piston_vent_solenoid` | integer | — | Solenoid state. |
| 81 | `PistonVacuumSolenoid[BN16]` | `piston_vacuum_solenoid` | integer | — | Solenoid state. |
| 82 | `ThermalPrecipitatorSolenoid[VM06]` | `thermal_precipitator_solenoid` | integer | — | Solenoid state. |
| 83 | `ThermalPrecipitatorPreAgeHeater` | `thermal_precipitator_pre_age_heater` | integer | — | Heater state. |
| 84 | `ThermalPrecipitatorPostAgeHeater` | `thermal_precipitator_post_age_heater` | integer | — | Heater state. |
| 85 | `ThermalPrecipitatorPreAgeValve` | `thermal_precipitator_pre_age_valve` | integer | — | Valve state. |
| 86 | `ThermalPrecipitatorPostAgeValve` | `thermal_precipitator_post_age_valve` | integer | — | Valve state. |
| 87 | `ThermalPrecipitatorPreAgeCableSense` | `thermal_precipitator_pre_age_cable_sense` | integer | — | Cable sense state. |
| 88 | `ThermalPrecipitatorPostAgeCableSense` | `thermal_precipitator_post_age_cable_sense` | integer | — | Cable sense state. |
| 89 | `STSDetectorSelfTest` | `sts_detector_self_test` | integer | — | Self-test state. |
| 90 | `STSDetectorAlarmReset` | `sts_detector_alarm_reset` | integer | — | Alarm reset state. |
| 91 | `STSDetectorAlarm` | `sts_detector_alarm` | integer | — | Alarm state. |
| 92 | `ISSDetectorSelfTest` | `iss_detector_self_test` | integer | — | Self-test state. |
| 93 | `VideoPower` | `video_power` | integer | — | Video power state. |
| 94 | `VideoRecording` | `video_recording` | integer | — | Recording state. |
| 95 | `VideoPaused` | `video_paused` | integer | — | Pause state. |
| 96 | `CameraPower` | `camera_power` | integer | — | Camera power state. |
| 97 | `IlluminationLEDPower` | `illumination_led_power` | integer | — | Illumination LED state. |

**SAME-R limitations:** this table is smoke/aerosol and detector response, not flame spread. Many columns are device states or commands, not physical measurements. Run metadata and material identity are in separate files. The 43-sheet results workbook has inconsistent sheet names and requires sheet-level validation.

### 4.7 PSI-25 BASS-II — test matrices

**Source:** `PSI-25_Science Documents_BASS-II_Test.Matrices.xlsx`
**Sheets:** `Bhattacharjee` (23 sheet rows), `Ferkul` (5), `Miller` (21), `Olson` (28), `Fernandez-Pello` (28), `T'ien` (30). Total 129 data rows across six sheets.
**Access:** verified on 2026-11-08.

All six sheets share the same 16-column header:

| # | Raw field | Canonical field | Type | Unit | Description |
|---:|---|---|---|---|---|
| 0 | `Actual Date  (for Video Display Date, add 1 for Leap Year)` | `test_date_excel_serial` | integer | Excel serial date | Convert with a documented Excel epoch. |
| 1 | `GMT 2014-` | `gmt_day_2014` | integer | day-of-year | Combine with 2014. The `Olson` header notes the last 3 tests are from 2016. |
| 2 | `Test no.` | `test_no` | string | — | PI-specific test code, e.g. `B1`, `F1`, `M1`, `O1`, `P1`, `T1`. |
| 3 | `Sample no.` | `sample_no` | string | — | Sample identifier; may include a suffix such as `m`. |
| 4 | `Material` | `material` | string | — | Free-text material description. |
| 5 | `Flow restrictor` | `flow_restrictor` | string | code | `0` = highest flow/lowest restriction; `2` = lowest flow/highest restriction (BASS-II readme). |
| 6 | `Fan display` | `fan_display` | string | fan voltage ×10 | Instantaneous fan voltage ×10 on the video display; maximum 122 = 12.2 V. Pot settings may also appear. |
| 7 | `Air display` | `air_display` | string | cm/s | Duct flow speed on the video display; slow response (~1 min). Multiple values may appear. |
| 8 | `Radiometer gain   (1000, 250, 50, 10)` | `radiometer_gain` | string | — | Uncalibrated gain; relative intensity only. Values may be sequences such as `250>50>250`. |
| 9 | `total frames shot` | `total_frames` | string | count | Digital Nikon still frames; may be `none`. |
| 10 | `calibrated  initial O2 % by vol ` | `initial_o2_pct` | float | % by volume | Calibrated initial O2; the sensor was out of calibration and the MCA ISS reading was used for a constant offset. |
| 11 | `calibrated final O2 % by vol` | `final_o2_pct` | float | % by volume | Calibrated final O2; may be `none`. |
| 12 | `Initial CO2 % by vol` | `initial_co2_pct` | float | % by volume | CDM sensor reading. |
| 13 | `Final CO2 % by vol` | `final_co2_pct` | float | % by volume | CDM sensor reading; may be `none`. |
| 14 | `Initial CO (ppm)` | `initial_co_ppm` | float | ppm | CSA-CP reading; `OR` = over range (>1000 ppm); `-1` observed and undefined. |
| 15 | `Final CO (ppm)` | `final_co_ppm` | float | ppm | CSA-CP reading; `OR` = over range (>1000 ppm); may be `none`. |

**BASS-II limitations:** this is a test matrix, not a processed flame-spread table. It records material, flow, gain, frame counts, and calibrated gas concentrations. It does not contain a measured spread rate. Free-text fields are inconsistent across the six PI sheets.

### 4.8 PSI-26 BASS — experimental table

**Source:** `PSI-26_Experimental table_BASS.csv`
**Rows:** 122 data rows; 6 columns.
**Checksum:** `ccfc3c54d948b64a1c5d2596a63c7c8019e51df0c91a1d62f039f48fa28c300f`
**Access:** verified on 2026-11-08.

| # | Raw field | Canonical field | Type | Unit | Missing | Description |
|---:|---|---|---|---|---|---|
| 0 | `Date` | `test_date` | string | — | none | `M/D/YYYY`, e.g. `3/30/2012`. |
| 1 | `GMT` | `gmt_day` | integer | — | none | Integer day identifier, e.g. `90`. |
| 2 | `As Run Test #` | `as_run_test_no` | string | — | 1 blank | As-run test number. |
| 3 | `Test #` | `test_no` | string | — | 1 blank | Planned test number. |
| 4 | `Sample #` | `sample_no` | string | — | 1 blank | Sample number. |
| 5 | `Fuel Sample Material` | `material` | string | — | none | Free-text material label; 34 distinct values including case variants. |

**BASS limitations:** this is a test log, not a measurement table. It has no oxygen, pressure, flame behavior, or spread-rate columns. Do not present it as a quantitative flammability dataset.

### 4.9 PSI-26 BASS — as-run test matrix

**Source:** `PSI-26_Science Documents_As Run_Test Matrix.xlsx`
**Sheets:** `as run matrix` (134 sheet rows; 131 rows after the title/group/header block, of which 130 are non-empty), `2012` (85 sheet rows; 82 non-empty data rows), `2013` (51 sheet rows; 48 non-empty data rows), `Data without TP` (40), `TP without Data` (8).
**Header row:** row 3 in the data sheets; row 1 is a title, row 2 contains group labels (`Setup`, `Expt settings`, `Camera Settings`, `ISS environment`).
**Access:** verified on 2026-11-08.

| # | Raw field | Canonical field | Type | Unit | Notes |
|---:|---|---|---|---|---|
| 0 | `Actual Date  (for SPICE Display Date, add 1 for Leap Year)` | `test_date_excel_serial` | integer | Excel serial date | Convert with a documented epoch. |
| 1 | `Approx Start Time ( with GMT)` | `approx_start_time_gmt` | string | — | Free text, e.g. `90 - 11:10`. |
| 2 | `As run test no.` | `as_run_test_no` | string | — | Source test number. |
| 3 | `Test no.` | `test_no` | string | — | Planned test number. |
| 4 | `Sample no.` | `sample_no` | string | — | Sample identifier. |
| 5 | `material` | `material` | string | — | Free text. |
| 6 | `Igniter` | `igniter` | string | — | Igniter type/code. |
| 7 | `Flow restrictor` | `flow_restrictor` | string | code | 0/1/2, same convention as BASS-II. |
| 8 | `Sample distance` | `sample_distance` | string | — | Free text, e.g. `farthest downstream`. |
| 9 | `Fan display` | `fan_display` | string | — | Fan display text; scale not stated in the as-run header. |
| 10 | `Air display` | `air_display` | string | — | Airflow display; BASS description gives a 5–50 cm/s range, but the header does not state the unit. |
| 11 | `Radiometer gain ( 1000, 250, 50, 10)` | `radiometer_gain` | string | — | Uncalibrated gain. |
| 12 | `Radiometer display` | `radiometer_display` | string | — | Display reading, e.g. `saturated`, `~ 1.2 max`, `n/a`. |
| 13 | `GN2 Pot` | `gn2_pot` | string | — | Pot setting. |
| 14 | `GN2 display` | `gn2_display` | string | — | Display value, e.g. `n/a`. |
| 15 | `Filter y/n` | `filter` | category | — | `y` / `n`. |
| 16 | `Release Mode (CH/CL)` | `release_mode` | category | — | `CH` / `CL`. |
| 17 | `Exposure Mode (M/A)` | `exposure_mode` | category | — | `M` / `A`. |
| 18 | `Exposure compensation   (-#EV)` | `exposure_compensation_ev` | string | EV | Negative values. |
| 19 | `Bracket frames and exposure bracket (#F/ 1.0)` | `bracket_frames` | string | — | Free text. |
| 20 | `shutter speed (1/s)` | `shutter_speed_inv_s` | string | 1/s | Free text, e.g. `best 1/25s 10 cm/s`. |
| 21 | `F stop` | `f_stop` | string | — | Aperture. |
| 22 | `ISO` | `iso` | string | — | Camera ISO. |
| 23 | `shutter hold s /cont` | `shutter_hold_s` | string | s | Free text. |
| 24 | `SD card S/N` | `sd_card_sn` | string | — | Card serial number. |
| 25 | `total frames shot` | `total_frames` | string | count | May be `5 brackets`, `6 brackets`, `135`. |
| 26 | `O2 % by volume` | `o2_pct` | float | % by volume | As-run oxygen concentration. |
| 27 | `pressure, atm` | `pressure_atm` | float | atm | As-run pressure. |
| 28 | `CO2, mm Hg` | `co2_mm_hg` | float | mm Hg | As-run CO2. |
| 29 | `Test Observations and Anomalies (ignited, spread, extinguished, burn time, color, etc.)` | `observations` | string | — | Free-text operator observations. |

**BASS as-run limitations:** free text is mixed with numeric fields; `n/a`, `tbd`, `-`, and descriptive text appear in numeric-looking columns. Parse only with per-column rules, and preserve the raw text.

### 4.10 PSI-20 ACME BRE — test-day summary

**Source:** `PSI-20_Experimental table_ACME BRE.csv`
**Rows:** 18 data rows; 8 columns.
**Checksum:** `4aa5d3f98708ceacced5c620d46858b9965f8d4d941b203229f46467d53e5ab7`
**Access:** verified on 2026-11-08.

| # | Raw field | Canonical field | Type | Unit | Missing | Description |
|---:|---|---|---|---|---|---|
| 0 | `Year` | `year` | integer | — | none | Test year. |
| 1 | `Month` | `month` | string | — | none | Test month name. |
| 2 | `Date` | `day_of_month` | string | — | none | Day of month. |
| 3 | `Burner Size (mm)` | `burner_size_mm` | integer | mm | none | Burner diameter; 25 or 50 mm. |
| 4 | `Fuel Bottle` | `fuel_bottle` | string | — | none | Fuel label; includes `100% C2H4`, `50% C2H4`, `100%C2H4`, `100% CH4`. |
| 5 | `Oxygen Conc (percent)` | `oxygen_concentration_text` | string | % by volume | none | Semicolon-separated values, e.g. `21; 26.5; 40`. Anomalies `3400%` and `2100%` are preserved raw. |
| 6 | `Flames Ignited` | `flames_ignited` | integer | count | none | Number of flames ignited that day; `0` is a valid count. |
| 7 | `Notes` | `notes` | string | — | blank (16) | Free-text notes. |

**Limitations:** this is a test-day summary, not a per-test measurement table. The notes explicitly state that chamber pressure varied but is not identified in the summary table. Do not use it for pressure-response analysis.

### 4.11 PSI-21 ACME CLD Flame — test-day summary

**Source:** `PSI-21_Experimental table_CLD Flame.csv`
**Rows:** 32 data rows; 8 columns.
**Checksum:** `9fafbc5b3dddaf715ce8025ed9154ce297803f7b69a935f077ec26c8249e44c0`
**Access:** verified on 2026-11-08.

| # | Raw field | Canonical field | Type | Unit | Missing | Description |
|---:|---|---|---|---|---|---|
| 0 | `Test Type` | `test_type` | category | — | none | `Methane based test`, `Ethylene based test`, `Improved coflow tests`. |
| 1 | `Test Day` | `test_day` | string | — | none | Test-day identifier. |
| 2 | `Fuel MFC` | `fuel_mfc` | float | not stated | none | Fuel mass-flow-controller setting. The header does not state a unit. |
| 3 | `N2 MFC` | `n2_mfc` | float | not stated | none | Nitrogen mass-flow-controller setting. The header does not state a unit. |
| 4 | `Fuel Bottle` | `fuel_bottle` | string | — | none | Fuel bottle label; 30 distinct values. |
| 5 | `Fuel conc. Range` | `fuel_concentration_range` | string | % | none | Text range, e.g. `30%-40%`, `100%`, `0%-30%`. |
| 6 | `Flames ignited` | `flames_ignited` | integer | count | none | Number of flames ignited. |
| 7 | `Notes` | `notes` | string | — | blank (31) | Free-text notes. |

**Limitations:** only 32 test-day rows; it records counts and ranges, not per-test flame measurements. Do not assign units to `Fuel MFC` or `N2 MFC` without source confirmation.

### 4.12 PSI-106 SLICE — experimental table

**Source:** `PSI-106_Experimental table_Slice.csv`
**Rows:** 12 data rows; 2 columns.
**Checksum:** `89ef980810ca6d9aa8be817b42e36cd2adff23f5e9058361b5a33d18b4363f4d`
**Access:** verified on 2026-11-08.

| # | Raw field | Canonical field | Type | Unit | Description |
|---:|---|---|---|---|---|
| 0 | `Test Date` | `test_date` | string | — | Test date, e.g. `2012-FEB-09`. |
| 1 | `Fuel Type` | `fuel_type` | string | — | Free-text fuel description. |

**Limitations:** no measured variables. It cannot support quantitative analysis.

### 4.13 PSI-142 — data index

**Source:** `PSI-142_Experimental table_Data Summary Table.csv`
**Rows:** 8 data rows; 4 columns.
**Checksum:** `c66d135b0053590d239f06b9e8627d826e3d726b8443fd2cbccc37484b6a8e7f`
**Access:** verified on 2026-11-08 after a retry.

| # | Raw field | Canonical field | Type | Unit | Description |
|---:|---|---|---|---|---|
| 0 | `Data ID` | `data_id` | integer | — | Index identifier. |
| 1 | `Data Description` | `data_description` | string | — | Description of the figure/data item. |
| 2 | `Reference Publication Link` | `reference_url` | string | — | DOI or publication URL. |
| 3 | `Figure ID in Reference` | `figure_id` | string | — | Figure number in the reference. |

**Limitations:** this is a bibliography/figure index, not a measurement table.

### 4.14 Experimental summary tables

The 22 `experimentalTable` entries are the curated summary layer of PSI. They are separate from the `added` archive inventory. The tables already described in §4.1–§4.13 are not repeated here; this section covers the 13 tables that did not have a field dictionary. Every table was downloaded and inspected on 2026-11-08.

| Accession | File | Rows | Columns | In `added` | Role of the table |
|---|---|---:|---:|---|---|
| PSI-22 | `PSI-22_Experimental table_ACME E-FIELD Flames.csv` | 32 | 10 | no | Test-day campaign summary |
| PSI-23 | `PSI-23_Experimental table_ACME s-Flame.csv` | 18 | 9 | no | Test-day campaign summary |
| PSI-25 | `PSI-25_Experimental table_BASS-II.csv` | 129 | 17 | no | Combined BASS-II test matrix |
| PSI-39 | `PSI-39_Experimental table_CFI.csv` | 87 | 10 | no | Test-condition log |
| PSI-47 | `PSI-47_Experimental table_DAFT.csv` | 2 | 5 | no | Instrument session log |
| PSI-68 | `PSI-68_Experimental table_Flex2.csv` | 8 | 7 | no | Condition-range table |
| PSI-69 | `PSI-69_Experimental table_FLEX.csv` | 274 | 15 | no | Droplet-combustion summary |
| PSI-98 | `PSI-98_Experimental table_SAFFIRE-1.csv` | 4 | 13 | no | Sample summary |
| PSI-99 | `PSI-99_Experimental table_SAFFIRE-2.csv` | 15 | 17 | no | Sample summary |
| PSI-100 | `PSI-100_Experimental table_SAFFIRE-3.csv` | 2 | 9 | no | Sample summary |
| PSI-101 | `PSI-101_Experimental table_SAME-R.csv` | 109 | 10 | no | Sample/test log |
| PSI-102 | `PSI-102_Experimental table_SAME.csv` | 8 | 5 | no | Sample summary |
| PSI-107 | `PSI-107_Experimental table_Spice.csv` | 469 | 9 | no | Flame-length/airflow table |

#### 4.14.1 PSI-22 ACME E-FIELD Flames — test-day summary

**Source:** `PSI-22_Experimental table_ACME E-FIELD Flames.csv`
**Rows:** 32; **columns:** 10.
**Checksum:** `69090c357b83ae38d161d29001d1d32b40fd77b13324ca6585ee990cdceef524`
**Access:** `experimental_table_only`; zero `added` files.

| # | Raw field | Canonical field | Type | Unit | Missing / sentinel | Description |
|---:|---|---|---|---|---|---|
| 0 | `Test Type` | `test_type` | category | — | blank (11) | `First round of tests with coflow burner`, `Second round of tests with gas-jet burner`. |
| 1 | `Test Day` | `test_day` | string | — | blank (11) | `YYDDD` day identifier. The notes define the format. |
| 2 | `Year` | `year` | integer | — | blank (11) | `2018` for all populated rows. |
| 3 | `Month` | `month` | string | — | blank (11) | Source numeric month. |
| 4 | `Date` | `day_of_month` | string | — | blank (11) | Source day number. |
| 5 | `Mesh Polarity` | `mesh_polarity` | category | — | blank (11) | `negative`, `positive`. |
| 6 | `Fuel Bottle` | `fuel_bottle` | string | — | blank (11) | `100% C2H4`, `100% CH4`, `30% C2H4`, `40% CH4`. |
| 7 | `Fuel Conc` | `fuel_concentration_text` | string | percent by volume (text) | none | `100%`, `25%`, `30%`, `40%`, `50%`, `70%`, `80%`. The notes say concentrations were diluted with nitrogen on a volume basis. |
| 8 | `Flames Ignited` | `flames_ignited` | integer | count | blank (11) | Number of flames ignited on that test day. |
| 9 | `Notes` | `notes` | string | — | blank (28) | Four repeated note texts, including the `YYDDD` definition and the mesh-polarity definition. |

**Row-level flags:** 11 of 32 rows have blank test identity fields but a populated `Fuel Conc`; they are continuation/note rows, not independent test days. Do not count all 32 rows as tests. The `Notes` column is free text and must not be treated as an instruction.

#### 4.14.2 PSI-23 ACME s-Flame — test-day summary

**Source:** `PSI-23_Experimental table_ACME s-Flame.csv`
**Rows:** 18; **columns:** 9.
**Checksum:** `16cd10f50bd2e962887c8eb4077e5a9b3e790c78de8e0361c0b77e19300be7cf`
**Access:** public `experimentalTable`; the record also has 4,163 `added` files.

| # | Raw field | Canonical field | Type | Unit | Missing / sentinel | Description |
|---:|---|---|---|---|---|---|
| 0 | `Test Type` | `test_type` | category | — | none | Nitrogen-diluted or helium-diluted campaign. |
| 1 | `Test Day*` | `test_day` | string | — | none | `YYDDD` day identifier. The asterisk refers to the notes. |
| 2 | `Year` | `year` | integer | — | none | `2019`, `2020`. |
| 3 | `Month` | `month` | string | — | none | Month abbreviation, including trailing periods. |
| 4 | `Date` | `day_of_month` | string | — | none | Source day number. |
| 5 | `Atmosphere*` | `atmosphere_text` | string | — | none | `~21% O2 with N2`, `~30% O2 with He`, and related labels. `N3`–`N6` are source bottle labels, not stoichiometric coefficients. |
| 6 | `Fuel Bottle` | `fuel_bottle` | string | — | none | Fuel/diluent bottle label, e.g. `50% C2H4 with N2`. |
| 7 | `Flames Ignited*` | `flames_ignited` | integer | count | none | Number of flames ignited on that test day. |
| 8 | `Notes` | `notes` | string | — | blank (15) | Three repeated note texts. |

**Limitations:** this is a test-day summary, not a per-test measurement table. It cannot support flame-structure or soot analysis by itself.

#### 4.14.3 PSI-25 BASS-II — combined experimental table

**Source:** `PSI-25_Experimental table_BASS-II.csv`
**Rows:** 129; **columns:** 17.
**Checksum:** `71e792bf6b5fb5ea620c5dd70fbbac05515992e12aefcf5dff47312caa48c042`
**Access:** public `experimentalTable`; not in `added`. The six-sheet workbook is described in §4.7.

| # | Raw field | Canonical field | Type | Unit | Missing / sentinel | Description |
|---:|---|---|---|---|---|---|
| 0 | `PI` | `principal_investigator` | category | — | none | Six PI-specific test series. |
| 1 | `Test #` | `test_code` | string | — | none | Source test identifier, e.g. `B1`. |
| 2 | `Date` | `test_date` | string | — | none | `M/D/YYYY`. |
| 3 | `GMT` | `gmt_day` | integer | day-of-year | none | Source GMT day. |
| 4 | `Sample #` | `sample_id` | string | — | none | Source sample identifier; some values have a trailing `m` or `M`. |
| 5 | `Fuel Sample Material` | `material` | string | — | none | Material description, including thickness and geometry. |
| 6 | `Flow restrictor` | `flow_restrictor` | category | code | none | `0`, `1`, `2`; the readme defines the codes. |
| 7 | `Fan display` | `fan_display_text` | string | not stated | blank (13) | Display text; the header does not state a unit. Do not parse as a single number when it contains sequences. |
| 8 | `Air display` | `air_display_text` | string | cm/s (readme) | blank (4) | Slow-response duct display; the readme gives cm/s, the header does not. Preserve sequences. |
| 9 | `Radiometer gain   (1000   250   50   10)` | `radiometer_gain_text` | string | uncalibrated | none | Gain setting text, including transitions such as `250>50`. |
| 10 | `Total Frames Shot` | `total_frames_text` | string | frames (text) | none | Frame count text; `none`, `video`, and arithmetic expressions occur. |
| 11 | `Calibrated  initial O2 % by vol ` | `initial_o2_pct` | float | percent by volume | none | Calibrated initial O2. |
| 12 | `Calibrated final O2 % by vol` | `final_o2_pct` | float | percent by volume | `none` (2) | Calibrated final O2. |
| 13 | `Initial CO2 % by vol` | `initial_co2_pct` | float | percent by volume | `none` (2) | Initial CO2. |
| 14 | `Final CO2 % by vol` | `final_co2_pct` | float | percent by volume | blank (1), `none` (5) | Final CO2. |
| 15 | `Initial CO (ppm)` | `initial_co_ppm` | float | ppm | `none` (2), `OR` (1) | Initial CO; `OR` means over range. |
| 16 | `Final CO (ppm)` | `final_co_ppm` | float | ppm | blank (1), `none` (4), `OR` (2), `>500` (1), `over` (1) | Final CO; `OR` and `over` mean over range. |

**Limitations:** this is a test matrix, not a processed spread-rate table. The combined CSV and the six-sheet workbook are two views of the same campaign; choose one as canonical.

#### 4.14.4 PSI-39 CFI — test-condition log

**Source:** `PSI-39_Experimental table_CFI.csv`
**Rows:** 87; **columns:** 10.
**Checksum:** `fb898e28762353aa132c16b886dbd207a024b1dd3c9bed5928d70d8036d2ec7e`
**Access:** public `experimentalTable`; the record also has 2,831 `added` files.

| # | Raw field | Canonical field | Type | Unit | Missing / sentinel | Description |
|---:|---|---|---|---|---|---|
| 0 | `Flex Number` | `flex_number` | string | — | none | Source test identifier. |
| 1 | `Test Date` | `test_date` | string | — | none | `D-Mon-YY`, e.g. `9-Mar-17`. |
| 2 | `Local Time` | `local_time_text` | string | EST (text) | none | Local time with `am`/`pm` and `est`. |
| 3 | `CIR ` | `cir_configuration` | string | — | none | CIR configuration identifier. |
| 4 | `Pressure` | `pressure_text` | string | atm (text) | none | `0.5 atm`, `0.75 atm`, `1 atm`, `1.25 atm`, `2 atm`, `3 atm`, `5 atm`. Parse the numeric value only with a documented unit rule. |
| 5 | `Oxygen` | `oxygen_mole_fraction` | float | mole fraction | none | `0.17` or `0.21`. |
| 6 | `Nitrogen` | `nitrogen_mole_fraction` | float | mole fraction | none | `0.2`, `0.5`, `0.76`, `0.79`, `0.83`. |
| 7 | `Helium` | `helium_mole_fraction` | float | mole fraction | none | `0`, `0.29`, `0.59`. |
| 8 | `Fiber` | `fiber_flag` | category | — | blank (9) | `Yes`, `No`. Blank means not recorded; it is not `No`. |
| 9 | `Fuel ` | `fuel` | string | — | none | `C12H26` or a dodecane/iso-dodecane blend. Trailing space in the header is preserved. |

**Limitations:** this is a test-condition log, not a processed droplet-combustion result table.

#### 4.14.5 PSI-47 DAFT/DAFT-2 — session log

**Source:** `PSI-47_Experimental table_DAFT.csv`
**Rows:** 2; **columns:** 5.
**Checksum:** `d9d1a436c6e7bbc410b433e04575fe7dedaff763b5237d688089929b7393b5c0`
**Access:** public `experimentalTable`; the record also has 32 `added` files.

| # | Raw field | Canonical field | Type | Unit | Missing / sentinel | Description |
|---:|---|---|---|---|---|---|
| 0 | `Session Name` | `session_name` | string | — | none | `D1`, `D2`. |
| 1 | `Actual Day` | `actual_day` | string | — | none | `GMT 54 (2005)`, `GMT 63 (2005)`. |
| 2 | `Hardware Description` | `hardware_description` | string | — | none | P-Trak or DustTrak hardware description. |
| 3 | `Sample Material` | `sample_material` | string | — | none | Arizona Road Dust aerosol description. |
| 4 | `Sampled Location` | `sampled_location` | string | — | none | ISS location description. |

**Limitations:** instrument-feasibility context, not a combustion measurement table.

#### 4.14.6 PSI-68 FLEX-2 — condition-range table

**Source:** `PSI-68_Experimental table_Flex2.csv`
**Rows:** 8; **columns:** 7.
**Checksum:** `cc57ad1bd9977aa13e7ac6c3aa618303012686e232b36c052c6a9f1a74e5f528`
**Access:** `experimental_table_only`; zero `added` files.

| # | Raw field | Canonical field | Type | Unit | Missing / sentinel | Description |
|---:|---|---|---|---|---|---|
| 0 | `Sample (Fuel Type)` | `fuel` | string | — | none | Eight pure or blended fuels. |
| 1 | `Initial Droplet Diameter (mm)` | `initial_droplet_diameter_mm_text` | string | mm (range) | none | `1.5 - 5` for all rows. This is a range, not a measurement. |
| 2 | `Ambient Gas Mixture ` | `ambient_gas_mixture` | category | — | none | `O2/N2 or O2/He`. Trailing space in the header is preserved. |
| 3 | `Oxygen Mole Fraction` | `oxygen_mole_fraction_text` | string | mole fraction (list) | none | `0.17; 0.21;0.25; 0.3`. This is a condition list, not a single value. |
| 4 | `Ambient Pressure (atm)` | `ambient_pressure_atm_text` | string | atm (list) | none | `0.5; 1.0; 1.5; 2.0; or 3.0`. This is a condition list. |
| 5 | ` Ambient Temperature (C)` | `ambient_temperature_c` | integer | °C | none | `25` for all rows. Leading space in the header is preserved. |
| 6 | `Flow Velocity (cm/s)` | `flow_velocity_cm_s_text` | string | cm/s (range) | none | `0.1 - 5`. This is a range. |

**Limitations:** ranges and lists are not measurements. Do not compute means or plot them as individual test points.

#### 4.14.7 PSI-69 FLEX — droplet-combustion summary

**Source:** `PSI-69_Experimental table_FLEX.csv`
**Rows:** 274; **columns:** 15.
**Checksum:** `37c88ce8ae9391b7544ff630a45ce87543d04d317cdbfbed104fe7d5c27e1b96`
**Access:** `experimental_table_only`; zero `added` files.

| # | Raw field | Canonical field | Type | Unit | Missing / sentinel | Description |
|---:|---|---|---|---|---|---|
| 0 | `FLEX Test #` | `flex_test_number` | string | — | none | Source test number. |
| 1 | `FLEX Identifier` | `flex_identifier` | string | — | none | Source identifier; one duplicate (`193F001`). |
| 2 | `Test Date` | `test_date` | string | — | none | `M/D/YYYY` or `M/D/YY` variants. |
| 3 | `Test GMT` | `test_gmt_time` | string | — | blank (1) | `HH:MM:SS`. |
| 4 | `Fuel` | `fuel` | category | — | none | `Heptane`, `Methanol`. |
| 5 | `Ambient pressure; mmHg` | `ambient_pressure_mmhg` | float | mmHg | none | Do not merge with atm/bar/psi axes without conversion. |
| 6 | `O initial ambient composition; mole fraction` | `oxygen_mole_fraction` | float | mole fraction | none | Initial ambient O2. |
| 7 | `N initial ambient composition; mole fraction` | `nitrogen_mole_fraction` | float | mole fraction | none | Initial ambient N2. |
| 8 | `CO initial ambient composition; mole fraction` | `co_mole_fraction` | float | mole fraction | none | Initial ambient CO as labeled. Do not assume CO2. |
| 9 | `He initial ambient composition; mole fraction` | `helium_mole_fraction` | float | mole fraction | none | Initial ambient He. |
| 10 | `Droplet initial diameter; mm` | `initial_droplet_diameter_mm` | float | mm | blank (6), `�` (6) | The replacement character indicates a non-UTF-8 source byte; it is not a measurement. |
| 11 | `Visible flame extinction diameter; mm` | `visible_flame_extinction_diameter_mm` | float | mm | blank (49), `�` (28) | Visible flame extinction diameter. |
| 12 | `Burning rate; mm` | `burning_rate_mm_as_labeled` | float | mm (as labeled) | blank (16) | The header states mm, not mm/s. Do not relabel it as a rate unit without source confirmation. |
| 13 | `Burn time; s` | `burn_time_s` | float | s | blank (6), `~6` (1), `~9` (1) | Approximate text values must be flagged, not silently parsed. |
| 14 | `Test end` | `test_end` | category | — | none | `Completion`, `Disruption`, `Extinction`. |

**Limitations:** droplet combustion, not flame spread. The `Burning rate; mm` unit is ambiguous and must be preserved exactly as labeled.

#### 4.14.8 PSI-98 SAFFIRE-I — sample summary

**Source:** `PSI-98_Experimental table_SAFFIRE-1.csv`
**Rows:** 4; **columns:** 13.
**Checksum:** `c01f29c62455f0a3b512290ab85e5687ecded326733189f002f580368402308d`
**Access:** public `experimentalTable`; the record also has 74 `added` files.

| # | Raw field | Canonical field | Type | Unit | Missing / sentinel | Description |
|---:|---|---|---|---|---|---|
| 0 | `Sample Number ` | `sample_number` | string | — | none | `S1`, `S2`, `F1C1/F1C2`, `F2C1/F2C2`. |
| 1 | `Material` | `material` | string | — | none | `SIBAL Fabric` or a pre-test flow-visualization description. |
| 2 | `Sample Thickness (cm)` | `sample_thickness_cm` | float | cm | blank (2) | Populated for the two sample rows only. |
| 3 | `Sample Length (cm)` | `sample_length_cm` | float | cm | blank (2) | Populated for the two sample rows only. |
| 4 | `Sample Width (cm)` | `sample_width_cm` | float | cm | blank (2) | Populated for the two sample rows only. |
| 5 | `Air Flow (cm/s)` | `air_flow_cm_s` | float | cm/s | blank (2) | Populated for the two sample rows only. |
| 6 | `Percent O2` | `oxygen_percent_text` | string | percent by volume (text) | blank (2) | `21.5 - 21.7`, `~ 21.5`. Ranges are not single values. |
| 7 | `Ignition Power (W)` | `ignition_power_w` | float | W | blank (2) | Populated for the two sample rows only. |
| 8 | `Ignition Time (s)` | `ignition_time_s` | float | s | blank (2) | Populated for the two sample rows only. |
| 9 | `Burn Time (s)` | `burn_time_s` | float | s | blank (2) | `420`, `70`. |
| 10 | `Flow Direction ` | `flow_direction` | category | — | blank (2) | `Concurrent`, `Opposed`. Trailing space in the header is preserved. |
| 11 | `Camera 1` | `camera_1` | string | — | blank (2) | Camera identifier. |
| 12 | `Camera 2` | `camera_2` | string | — | blank (2) | Camera identifier. |

**Limitations:** two rows are sample summaries and two are pre-test flow-visualization rows. Do not count all four as sample tests.

#### 4.14.9 PSI-99 SAFFIRE-II — sample summary

**Source:** `PSI-99_Experimental table_SAFFIRE-2.csv`
**Rows:** 15; **columns:** 17.
**Checksum:** `3c24390b9ef86f3d1ebaab911a1a3cc95a8759aebf42062371370e6d4b31b8ac`
**Access:** `experimental_table_only`; zero `added` files.

| # | Raw field | Canonical field | Type | Unit | Missing / sentinel | Description |
|---:|---|---|---|---|---|---|
| 0 | `Sample Number` | `sample_number` | string | — | none | Sample identifier or pre-test flow-visualization identifier. |
| 1 | `Material` | `material` | string | — | blank (6) | `Silicone`, `PMMA`, `PMMA & Nomex`, `Cotton-Fiberglass (SIBAL)`. |
| 2 | `Samle Thickness ` | `sample_thickness_text` | string | mixed (text) | blank (6) | Source typo `Samle` is preserved. Values include `0.27 mm`, `1 cm`, `037 mm`, `See Fig. 5`. |
| 3 | `Sample Length ` | `sample_length_text` | string | cm (text) | blank (6) | `29 cm`, `5 and 24 cm`. |
| 4 | `Sample Width (cm)` | `sample_width_cm_text` | string | cm (text) | blank (6) | `5 cm`. |
| 5 | `Air Flow (cm/s)` | `air_flow_cm_s_text` | string | cm/s (text) | blank (6) | `20 cm/s`. |
| 6 | `Percent O2 (Note 1)` | `oxygen_percent_text` | string | percent by volume (text) | blank (6) | `~ 21.5`, `~ 22.1`, `22.0 to 21.9`, `22.1 to 22.0`. |
| 7 | `Ignition Power (W)` | `ignition_power_w_text` | string | W (text) | blank (6) | `80 W`, `97 W`. |
| 8 | `Ignition Time (s)` | `ignition_time_s_text` | string | s (text) | blank (6) | `30 s`, `9.2 s`. |
| 9 | `Burn Time (s)` | `burn_time_s_text` | string | s (text) | blank (6) | `115 s`, `140 s`, `145 s`, `600 s`, `900 s`, `Insignificant`. |
| 10 | `Flow Direction` | `flow_direction` | category | — | blank (6) | `Concurrent`, `Opposed`. |
| 11 | `?-g Burn Length` | `microgravity_burn_length_text` | string | mixed (text) | blank (6) | The literal `?` is in the source header, likely a lost micro sign. Values include `29 cm`, `~ 0`, `~ 10 cm (note 3)`. |
| 12 | `?-g Spread Length` | `microgravity_spread_length_text` | string | mixed (text) | blank (6) | Values include `2.1 mm/s`, `2.6 mm/s`, `n/a`, `n/a (Nomex)`. The header says length but the values are rates; preserve the mismatch. |
| 13 | `1-g Burn Length` | `normal_gravity_burn_length_text` | string | mixed (text) | blank (6) | `7.6 cm`, `Complete`, `~ 0`, `~ 0 (Nomex)`. This is normal-gravity data. |
| 14 | `1-g Spread Rate` | `normal_gravity_spread_rate_text` | string | mixed (text) | blank (6) | `0.6 mm/s`, `1.2 mm/s`, `Acceleratory`, `n/a`, `n/a (Nomex)`. This is normal-gravity data, not microgravity. |
| 15 | `Camera 1` | `camera_1` | string | — | blank (7) | Camera identifier, including `n/a`. |
| 16 | `Camera 2` | `camera_2` | string | — | blank (6) | Camera identifier, including `n/a`. |

**Limitations:** the microgravity columns are incomplete or use non-numeric placeholders. The 1-g columns are normal-gravity comparisons and must not be presented as microgravity results.

#### 4.14.10 PSI-100 SAFFIRE-III — sample summary

**Source:** `PSI-100_Experimental table_SAFFIRE-3.csv`
**Rows:** 2; **columns:** 9.
**Checksum:** `4d3c717ec20dd0247db670b2784a9fd7d746788bc54a936f80693e48eb8cd117`
**Access:** public `experimentalTable`; the record also has 85 `added` files.

| # | Raw field | Canonical field | Type | Unit | Missing / sentinel | Description |
|---:|---|---|---|---|---|---|
| 0 | `Sample Number ` | `sample_number` | string | — | none | `S1`, `S2`. |
| 1 | `Material` | `material` | category | — | none | `SIBAL Fabric`. |
| 2 | `Sample Thickness` | `sample_thickness_text` | string | cm (text) | none | `.33 cm`. The unit is embedded in the value, not the header. |
| 3 | `Sample Length` | `sample_length_text` | string | cm (text) | none | `94 cm`. |
| 4 | `Sample Width` | `sample_width_text` | string | cm (text) | none | `40.6 cm`. |
| 5 | `Air Flow ` | `air_flow_text` | string | cm/s (text) | none | `30 cm/s`. Trailing space in the header is preserved. |
| 6 | `Direction` | `flow_direction` | category | — | none | `Concurrent`, `Opposed`. |
| 7 | `Camera 1` | `camera_1` | string | — | none | `S1C1`, `S2C1`. |
| 8 | `Camera 2` | `camera_2` | string | — | none | `S1C2`, `S2C2`. |

**Limitations:** this is a sample summary, not telemetry. The telemetry exports are described in §4.5.

#### 4.14.11 PSI-101 SAME-R — sample/test log

**Source:** `PSI-101_Experimental table_SAME-R.csv`
**Rows:** 109; **columns:** 10.
**Checksum:** `87164b7dc9168a4273c159f7a9f23699afbd06ad97b77974377e79b9bf8a3bef`
**Access:** public `experimentalTable`; the record also has 342 `added` files.

| # | Raw field | Canonical field | Type | Unit | Missing / sentinel | Description |
|---:|---|---|---|---|---|---|
| 0 | `Sample Type` | `sample_type` | category | — | none | `Kapton`, `Lampwick`, `Pyrell`, `Silicone`, `Teflon`. |
| 1 | `SAME Test #` | `same_test_number` | string | — | none | Source test number; some values have an `a` suffix. |
| 2 | `Description` | `description` | string | — | none | Free-text test description, e.g. `Baseline Aging`. |
| 3 | `Date` | `test_date_text` | string | — | none | `D-Mon`, e.g. `21-Jul`. The year is not stated in the table. |
| 4 | `Inlet velocity (cm/s)` | `inlet_velocity_cm_s` | float | cm/s | none | `0`, `1`, `2`, `8`, `8.1`. |
| 5 | `Rt/R0` | `rt_over_r0` | float | dimensionless | none | Ratio as labeled. |
| 6 | `Duration (sec)` | `duration_s` | float | s | blank (41) | `60`, `120`. |
| 7 | `Primary aging time (sec)` | `primary_aging_time_s` | float | s | blank (42) | `1`, `11`, `720`. |
| 8 | `Primary mixing time (sec)` | `primary_mixing_time_s` | float | s | blank (42) | `8`. |
| 9 | `Net aging time (sec)` | `net_aging_time_s` | float | s | `n/a` (5) | Net aging time; `n/a` is not zero. |

**Limitations:** this is a sample/test log, not the 98-channel HKP telemetry. The year is not in the table.

#### 4.14.12 PSI-102 SAME — sample summary

**Source:** `PSI-102_Experimental table_SAME.csv`
**Rows:** 8; **columns:** 5.
**Checksum:** `268d1e121d2f211b124407dd32b9475617bd269ede2c2d1749441da3e949a2af`
**Access:** public `experimentalTable`; the record also has 104 `added` files.

| # | Raw field | Canonical field | Type | Unit | Missing / sentinel | Description |
|---:|---|---|---|---|---|---|
| 0 | `Sample #` | `sample_number` | string | — | none | `1`–`8`. |
| 1 | `Sample Material  ` | `sample_material` | string | — | none | Material name; rows 5–8 say `same conditions as 1-4`. Trailing spaces in the header are preserved. |
| 2 | `Air Flow (cm/s)` | `air_flow_cm_s` | float | cm/s | blank (4) | Populated for rows 1–4. |
| 3 | `Weight loss rate (mg/min)` | `weight_loss_rate_mg_min` | float | mg/min | blank (4) | Populated for rows 1–4. |
| 4 | `Aging Duration (minutes)` | `aging_duration_min` | float | min | blank (4) | Populated for rows 1–4. |

**Limitations:** the blank numeric cells in rows 5–8 mean "same conditions as 1–4", not zero. Do not fill them without a documented inheritance rule.

#### 4.14.13 PSI-107 SPICE — flame-length and airflow table

**Source:** `PSI-107_Experimental table_Spice.csv`
**Rows:** 469; **columns:** 9.
**Checksum:** `fb0d7e60cf5367afb429089e9901d27288f78038efd26c8de1db4fbe04117136`
**Access:** public `experimentalTable`; the record also has 186 `added` files.

| # | Raw field | Canonical field | Type | Unit | Missing / sentinel | Description |
|---:|---|---|---|---|---|---|
| 0 | `GMT date` | `gmt_day` | string | day-of-year | none | `45`, `48`, `52`, `55`, `58`, `119`, `136`, `167`, `168`, `173`, `174`. |
| 1 | `GMT ignition` | `gmt_ignition_time_text` | string | — | none | `HH:MM:SS`, with some `HH.MM.SS` variants. |
| 2 | `GMT  Flame Off ` | `gmt_flame_off_time_text` | string | — | blank (11) | `HH:MM:SS` or `HH.MM.SS`. Double space in the header is preserved. |
| 3 | `Fuel` | `fuel` | category | — | none | `Ethylene`, `Methane`, `Propane`, `Propylene`, and percentage blends. |
| 4 | `Nozzle (mm)` | `nozzle_mm` | float | mm | none | `0.4064`, `0.762`, `1.6002`. |
| 5 | `Fuel Rate (sccm)` | `fuel_rate_sccm` | float | sccm | blank (12) | Fuel volumetric flow. |
| 6 | `Fuel Rate (mg/s)` | `fuel_rate_mg_s` | float | mg/s | blank (12) | Fuel mass flow. |
| 7 | `HC Fuel Rate (mg/s)` | `hc_fuel_rate_mg_s` | float | mg/s | none | Hydrocarbon fuel mass flow. |
| 8 | `Air Rate (cm/s)` | `air_rate_cm_s` | float | cm/s | blank (25) | Air flow rate. |

**Limitations:** this is a flame-length/airflow table, not a processed smoke-point result table. The raw XLS/XLSX files need a format audit.

---

## 5. Missingness summary

| Dataset / table | Physical rows | Valid rows | Main missingness / sentinels |
|---|---:|---:|---|
| PSI-10 normal | 207 | 207 | 20 blank final XO2/pfinal/pmean; 60 rows with `RAMP`/`RAMPED` |
| PSI-10 inverse | 120 | 120 | 11 rows with `RAMP`/`LOW O2`; no blank cells |
| PSI-159 normal | 179 | 179 | `Cool flame?` blank 171; Comments blank 135; burn time blank 4; `#DIV/0!` 2; `-` 46 in peak burner T |
| PSI-159 inverse | 1,015 | 154 | 861 all-blank rows; `#VALUE!` 2; `-` sentinels in peak burner T and color; Comments blank 115 among valid |
| PSI-100 raw CSV | 3,972 | 3,966 | 6 negative/sentinel `RelativeSeconds` rows |
| PSI-100 cleaned CSV | 11,450 | 11,449 | 1 sentinel `RelativeSeconds` row |
| PSI-100 XLSX `RawData` | 73,462 | 11,449 | 62,013 empty formatting rows |
| PSI-101 HKP gmt250_1 | 558 | 558 | No blank cells; `-999` in P-Trak; `DustTrakA` all zero |
| PSI-25 BASS-II matrices | 129 | 129 | `none`, `OR`, `-1`, free-text sequences |
| PSI-26 BASS experimental | 122 | 122 | 1 row missing As Run/Test/Sample identifiers |
| PSI-26 BASS as-run | 131 (as-run sheet after header) | 130 non-empty | `n/a`, `tbd`, `-`, free text in numeric-looking columns |
| PSI-20 BRE | 18 | 18 | Notes blank 16; oxygen text anomalies `3400%`, `2100%` |
| PSI-21 CLD | 32 | 32 | Notes blank 31; MFC units not stated |
| PSI-22 E-FIELD | 32 | 32 | 11 continuation rows with blank test identity; Notes blank 28 |
| PSI-23 s-Flame | 18 | 18 | Notes blank 15 |
| PSI-25 BASS-II combined | 129 | 129 | Fan display blank 13; Air display blank 4; Final CO2 blank 1; Final CO blank 1; `none`, `OR`, `>500`, `over`, `-1` |
| PSI-39 CFI | 87 | 87 | Fiber blank 9; pressure is text with units |
| PSI-47 DAFT | 2 | 2 | No missing values |
| PSI-68 FLEX-2 | 8 | 8 | No blanks; all condition ranges/lists |
| PSI-69 FLEX | 274 | 274 | `�` 6 in initial diameter, 28 in extinction diameter; blanks 6/49/16/6; `~6`, `~9` |
| PSI-98 SAFFIRE-I | 4 | 2 sample + 2 pre-test | Sample fields blank in the two pre-test rows |
| PSI-99 SAFFIRE-II | 15 | 9 sample + 6 note/pre-test | Sample fields blank 6; `n/a`, `~ 0`, `Insignificant`, `Complete`, `Acceleratory` |
| PSI-100 sample | 2 | 2 | No missing values |
| PSI-101 SAME-R sample | 109 | 109 | Duration blank 41; aging-time blanks 42; `n/a` 5 |
| PSI-102 SAME | 8 | 8 | Numeric blanks 4; rows 5–8 inherit conditions from rows 1–4 |
| PSI-106 SLICE | 12 | 12 | No measured variables |
| PSI-107 SPICE | 469 | 469 | Flame Off blank 11; Fuel Rate blank 12; Air Rate blank 25 |
| PSI-142 index | 8 | 8 | Index only |

Row counts are from the inspected files on 2026-11-08. The PSI-26 as-run count is for the `as run matrix` sheet; the `2012` and `2013` sheets are year-specific subsets and must not be added to it without deduplication.

---

## 6. Cross-dataset field mapping

This mapping is intentionally conservative. "Equivalent" means the source definitions are compatible enough for a labeled comparison. "Not equivalent" means the fields must not share an axis or a ranking.

| Concept | PSI-10 | PSI-159 | PSI-100 | PSI-101 | PSI-25 | PSI-26 |
|---|---|---|---|---|---|---|
| Fuel/material | `Fuel` (C2H4, C3H8) | `Fuel` (ethane, propane, butane blends) | SIBAL cloth (75% cotton / 25% fiberglass) | Synthetic smoke sources | PMMA, Nomex, SIBAL, candle, PMMA rods | SIBAL, PMMA, Nomex, Ultem, candle |
| Oxygen | `XO2 (init)`, `XO2 (final)` mole fraction | `XO2 before/after` mole fraction | No direct O2 channel | No direct O2 channel | Calibrated O2 % by volume | O2 % by volume |
| Pressure | `pinit`, `pfinal`, `pmean` atm | `approx p (bar)` | PCM EPS1/2/3 psi; psi/K composite | MFC/GN2/vacuum PSIA/PSIG | Not in matrix | `pressure, atm` |
| Flow | `mfuel`, `mN2`, `mtot` mg/s | `mHC`, `O2 flow rate` mg/s | Anemometers, fan tach, fan delta P Pa | LFE SCCM; MFC LPM | Air display cm/s; flow restrictor | Air display; flow restrictor |
| Temperature | `Tad` K computed | `Tad` K computed; peak burner C/K measured | PCM air temp °C; radiometers | Gas plume temp °C | No temperature column | No temperature column |
| Ignition | Implicit in test outcome | `Hot ignition`, `burn time` | 9 igniter V/I channels | Heater/sample resistance, test state | Igniter type | Igniter type |
| Flame behavior | Flame type, comments | Cool flame flag, color, comments | Radiometers, smoke detectors, images | Smoke detector/aerosol response | Video only | Video only |
| Spread rate | Not in summary table | Not in summary table | Not in telemetry table | Not applicable | Not published as a table | Not published as a table |
| Suppression outcome | Not in summary table | `Self-ext or flow term` | Burn-to-completion telemetry; no suppression table | Not applicable | Extinguish flag in as-run matrix | Extinguish flag in as-run matrix |

**Rules:**

1. `XO2` mole fraction and O2 % by volume are convertible, but the conversion must be explicit and reversible.
2. `Tad` is computed; peak burner temperature is measured; PCM air temperature is an engineering sensor reading. They are different variables.
3. `TFP` is a categorical flag, not a temperature.
4. `mfuel`/`mHC` (mg/s) and air display (cm/s) are not convertible without geometry and calibration.
5. BASS/BASS-II have no published spread-rate table. Do not draw a spread-rate chart from the test matrices.
6. SAME/SAME-R measure smoke and detector response, not flame spread.
7. SAFFIRE telemetry measures the spacecraft fire environment; image-derived spread rates are a separate derived product.

---

## 7. Open questions

These are unresolved source questions, not assumptions:

1. **PSI-100 timestamp reconciliation.** Which export is authoritative for each sensor? The raw CSV, cleaned CSV, and XLSX have different row counts and time spans.
2. **PSI-100 calibration.** The raw signal names and human-readable XLSX headers need a documented mapping and calibration source. Radiometer, anemometer, fan tach, smoke wire, and igniter units are not stated in the inspected headers.
3. **PSI-100 `Saffire Repeat?` and `Row to Row Delta T (ms)`.** Headers exist, but no values were populated in the inspected workbook. Confirm whether they are unused or lost.
4. **PSI-159 `TFP` meaning.** The field is a Yes/No flag; the source header does not expand the acronym. Confirm from the CFI-G readme or publication before analysis.
5. **PSI-159 `Xf` definition.** The source does not expand `Xf`. It is treated as the fuel mole fraction as labeled; confirm against the readme.
6. **PSI-101 run metadata.** The HKP CSV has test/sample/carousel numbers but not material names or aging conditions. The test logs and results workbook must be joined carefully.
7. **PSI-101 `-999` and `DustTrakA` all-zero.** Confirm the instrument sentinel and whether the channel was active. Do not treat `-999` as a concentration or all-zero as a measured zero.
8. **PSI-25 `-1` initial CO.** The source does not define the negative value. Confirm whether it is a below-detection or missing code.
9. **PSI-20 oxygen text anomalies.** `3400%` and `2100%` appear in a percent column. Preserve raw; confirm whether they are formatting errors for 34.00% and 21.00%.
10. **PSI-21 MFC units.** The `Fuel MFC` and `N2 MFC` headers do not state a unit. Confirm from the source documentation before conversion.
11. **SAFFIRE-I telemetry access.** The XLSX files are listed but return HTTP 404. Do not treat SAFFIRE-I telemetry as ingested.
12. **BASS/BASS-II spread rates.** No processed table was identified. Deriving spread rates requires validated computer vision, which is out of MVP scope.

---

## 8. Change control

Any change to this dictionary must:

1. cite the source file, page, or readme that justifies the change;
2. update `data/registry/annotations.json` if the change affects a curated limitation or table statistic;
3. regenerate `data/registry/psi_combustion_investigations.json` and `data/registry/psi_file_inventory.csv` if metadata changed;
4. add or update a parser test with a real fixture row;
5. record the change in the commit message and, for a semantic change, in `docs/decisions/`.

Do not add a unit, a field interpretation, or a cross-dataset equivalence without a source citation.
