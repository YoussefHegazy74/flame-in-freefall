# Scripts

**Status:** Foundation scripts only. Parsers and downloaders arrive in Phase 1.

Both scripts use the Python 3 standard library. No virtual environment, network client, or third-party package is required.

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

The download endpoint is documented but not used by this script:

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

1. Keep the metadata collector standard-library only. Reproducibility with a bare Python 3 install is a feature.
2. Never write raw NASA files into Git. Use `data/raw/`, which is gitignored.
3. Stream large downloads; do not load a multi-gigabyte file into memory.
4. Compute SHA-256 for every downloaded file and record the retrieval timestamp.
5. Record HTTP status, date, and source URL for every retrieval.
6. Preserve raw values and units. Never coerce missingness to zero.
7. Add a `--check` mode to any generator whose output is committed.
8. Do not add a dependency without pinning it and documenting why.

---

## Planned scripts

These do not exist yet:

- `download_psi_files.py` — stream the MVP files into `data/raw/` and write a checksum manifest.
- `parse_*.py` — one parser per source format, with fixture tests.
- `validate_*.py` — schema, row-count, unit, and time-monotonicity gates.
- `build_canonical.py` — write versioned Parquet tables.

See `DEVELOPMENT_ROADMAP.md` Phase 1–2 for the gates.
