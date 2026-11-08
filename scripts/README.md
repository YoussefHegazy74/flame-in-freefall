# Scripts

**Status:** Phase 1 complete (2026-11-09). The scripts cover metadata collection, the curated acquisition manifest, the checksum-verifying downloader, exact experimental-table schemas, authentic fixtures, and the parse/build/validate/report pipeline.

The metadata and manifest generators use the Python 3 standard library. Parquet, Excel, and test work requires the pinned dependencies in `requirements.txt`.

---

## Phase 1 pipeline CLI

The main entry point is the package module:

```bash
python -m src.data_pipeline --help
```

| Command | Purpose |
|---|---|
| `manifest` | Print the curated selection; `--check` compares it with the committed manifest. |
| `download` | Acquire selected files with size and SHA-256 verification. |
| `parse` | Build interim Parquet tables from `data/raw/`. |
| `build-canonical` | Build the 13 processed Parquet tables. |
| `validate` | Verify acquisition and canonical tables; write `validation_report.json`. |
| `report` | Regenerate the schema, validation, quality, and processing reports. |
| `all` | Run parse, build-canonical, validate, and report in order. |

### Manifest

```bash
# Print the committed selection.
python -m src.data_pipeline manifest

# Fail with exit 1 if the committed selection drifts from the registry.
python -m src.data_pipeline manifest --check
```

### Download

```bash
# Check the 72-file selection and its limits without network access.
python -m src.data_pipeline download --all --dry-run

# Download one investigation, or the whole curated selection.
python -m src.data_pipeline download --dataset PSI-10
python -m src.data_pipeline download --all

# Re-verify and replace an existing file.
python -m src.data_pipeline download --all --force
```

The downloader refuses selections above 100 files or 100,000,000 bytes unless `--allow-large` is passed. It never selects the full PSI archive. Every file is streamed into `data/raw/<accession>/`, checked against the expected size and SHA-256, and recorded in `data/manifests/download_manifest.csv` with HTTP status, bytes, retrieval time, attempts, and error text. Known 404s are re-verified and recorded as `listed_404`, not treated as successful downloads.

`scripts/download_psi_files.py` is a thin wrapper with the same options for direct script use.

### Parse and build

```bash
# Parse every selected source. Reuses unchanged interim outputs unless --force.
python -m src.data_pipeline parse
python -m src.data_pipeline parse --force

# Build the 13 canonical Parquet tables and the dataset manifest.
python -m src.data_pipeline build-canonical
```

Parsing writes interim Parquet tables and per-run point files under `data/interim/`, plus `data/interim/parse_report.json`. The canonical build writes `data/processed/*.parquet`, `data/processed/dataset_manifest.json`, and `data/reports/processing_report.json`.

### Validate and report

```bash
python -m src.data_pipeline validate
python -m src.data_pipeline report
```

`validate` fails with a non-zero exit code if a selected raw file is missing, a checksum or size differs, a canonical table is missing, or a row count or primary key check fails. `report` writes:

- `data/registry/canonical_schema.json`;
- `data/reports/validation_report.json`;
- `data/reports/dataset_quality_report.json`;
- `data/reports/processing_report.json`.

### Full run

```bash
python -m src.data_pipeline all --force
```

---

## `build_download_manifest.py`

Builds or checks `data/registry/download_manifest.json` and `data/manifests/download_manifest.csv` from the curated registry.

```bash
python scripts/build_download_manifest.py
python scripts/build_download_manifest.py --check
```

The selection contains 72 files and 56,238,344 expected bytes: all 22 experimental tables, the three published PSI-100 telemetry exports, all 44 PSI-101 HKP CSVs, the PSI-25 and PSI-26 workbooks, and one PSI-102 test log. `--check` is read-only and exits 1 on drift.

---

## `build_et_schemas.py`

Builds or checks `data/registry/experimental_table_schemas.json` from the authenticated experimental-table files.

```bash
python scripts/build_et_schemas.py
python scripts/build_et_schemas.py --check
```

The registry records the exact header, physical rows, non-empty data rows, column count, encoding, encoding-fallback state, checksum, restricted flag, and `in_added` state for all 22 tables. `--check` exits 1 if the committed schema drifts from the downloaded sources.

---

## `build_fixtures.py`

Builds or checks the seven committed fixtures under `data/fixtures/csv/`.

```bash
python scripts/build_fixtures.py
python scripts/build_fixtures.py --check
```

Each fixture is an exact excerpt from an authenticated NASA source: the source header is unchanged and the selected rows are copied without editing values. `data/fixtures/fixtures_manifest.json` records the source path and checksum, 1-based source data-row numbers, fixture checksum, byte size, encoding, column count, and purpose. The generator refuses to build if a source checksum does not match the acquisition manifest. `--check` verifies the manifest and fixture checksums and does not rewrite either file.

---

## `fetch_psi_metadata.py`

Collects a reproducible metadata snapshot of the NASA PSI Combustion Science investigations.

### What it does

1. Queries the public PSI search API and selects every investigation whose research area or sub-area matches combustion.
2. Fetches each investigation detail record.
3. Separates the two public file lists:
   - `added` — the archive inventory;
   - `experimentalTable` — curated summary tables, which may also appear in `added`.
4. Writes three files into `data/registry/`:
   - `psi_combustion_investigations.json`;
   - `psi_file_inventory.csv` (one row per `added` file);
   - `psi_experimental_tables.csv` (one row per experimental table).
5. Merges curated roles and limitations from `data/registry/annotations.json`.

It never downloads experimental data files and never writes credentials.

### Usage

```bash
# Fetch from the live API and write the registry.
python3 scripts/fetch_psi_metadata.py

# Compare the live API with the committed snapshot. Exit 1 on drift. Never writes.
python3 scripts/fetch_psi_metadata.py --check

# Reproduce from cached detail JSON without network access.
python3 scripts/fetch_psi_metadata.py --details-dir /tmp/psi_details

# Save full detail JSON outside the repository for inspection.
python3 scripts/fetch_psi_metadata.py --raw-dir /tmp/psi_details
```

### Options

| Option | Default | Meaning |
|---|---|---|
| `--out-dir` | `data/registry` | Output directory. |
| `--annotations` | `data/registry/annotations.json` | Curated role and limitation file. |
| `--details-dir` | none | Read cached `{PSI-ID}.json` files instead of the live API. |
| `--raw-dir` | none | Save each full detail JSON to this directory. |
| `--check` | off | Compare against the committed snapshot; do not write. |

### Drift detection

`--check` compares these fields for every accession:

- `version`
- `file_count`
- `registered_total_bytes`
- `experimental_table_count`
- `archive_status`
- experimental-table file names

It also reports new and removed accessions. It exits 0 only when no drift is found.

### API endpoints used

```text
GET https://psi.nasa.gov/geode-py/ws/repo/search?source=psi&type=investigation&size=200&from=0
GET https://psi.nasa.gov/geode-py/ws/repo/investigations/{PSI-ID}
```

The download endpoint used by the Phase 1 pipeline:

```text
GET https://psi.nasa.gov/geode-py/ws/studies/{PSI-ID}/download?file={url-encoded-filename}
```

---

## `build_mvp_catalog.py`

Builds the curated MVP catalog from the generated registry and annotations.

### What it does

1. Reads `data/registry/psi_combustion_investigations.json` and `data/registry/annotations.json`.
2. Checks that each registry role matches its annotation role.
3. Attaches curated `mvp_use`, `supports`, and `does_not_support` text from a table in the script.
4. Copies every count, size, checksum, and archive status from the registry.
5. Writes `data/registry/mvp_dataset_catalog.json`.

It does not add measurements or access claims.

### Usage

```bash
python3 scripts/build_mvp_catalog.py
python3 scripts/build_mvp_catalog.py --check
```

`--check` exits 1 if the committed catalog differs from a freshly generated one.

---

## Rules for new scripts

1. Keep the metadata collector and manifest generators standard-library only. Reproducibility with a bare Python 3 install is a feature.
2. Never write raw NASA files into Git. Use `data/raw/`, which is gitignored.
3. Stream large downloads; do not load a multi-gigabyte file into memory.
4. Compute SHA-256 for every downloaded file and record the retrieval timestamp.
5. Record HTTP status, date, and source URL for every retrieval.
6. Preserve raw values and units. Never coerce missingness to zero.
7. Add a `--check` mode to any generator whose output is committed.
8. Do not add a dependency without pinning it and documenting why.
9. Bump `PARSER_VERSION` when token, encoding, or parsing semantics change, then regenerate interim tables, canonical tables, and reports.
