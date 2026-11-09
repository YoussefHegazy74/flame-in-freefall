# Query Contract

**Project:** Flame in Freefall
**Team:** AFAQ
**Implementation:** `src/analytics/db.py`
**Database:** DuckDB `2.0.0` over canonical Parquet
**Dataset version:** `2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb`

This document defines the read-only analytical contract between the API and the canonical Parquet tables. The database layer exposes named operations. It does not accept SQL, table names, file paths, or filter expressions from a client.

---

## 1. Connection model

Each query opens an in-memory DuckDB connection and creates a view for every canonical table that exists in the processed directory:

```sql
CREATE VIEW "gas_flame_test"
AS SELECT * FROM read_parquet('/absolute/path/data/processed/gas_flame_test.parquet')
```

Rules:

- Table names come only from `src.data_pipeline.schemas.TABLE_SCHEMAS`.
- The path comes only from the configured processed directory.
- `read_parquet` is not parameterizable in DuckDB 2.0.0, so the literal path is built from a validated local configuration value, never from a request.
- The connection is closed after each operation.
- No `INSERT`, `UPDATE`, `DELETE`, `COPY`, `ATTACH`, or extension loading is exposed.
- The API never returns a filesystem path.

Configuration:

| Variable | Default | Purpose |
|---|---|---|
| `FLAME_PROCESSED_DIR` | `data/processed` | Canonical Parquet directory. |
| `FLAME_REPORTS_DIR` | `data/reports` | Quality report directory. |
| `FLAME_QUERY_TIMEOUT_SECONDS` | `10` | Wall-clock query budget. |

---

## 2. Bounds

| Bound | Default | Maximum | Error |
|---|---:|---:|---|
| Page size (`limit`) | 50 | 200 | `413 range_too_large` |
| Page offset (`offset`) | 0 | unbounded | `400 invalid_query` if negative |
| Series points (`max_points`) | 5,000 | 20,000 | `413 range_too_large` |
| Series channels | — | 8 | `413 range_too_large` |
| Time range | required | within run's valid range | `400 invalid_query` |

A page response includes `limit`, `offset`, `total`, and `has_more`.

A series request that exceeds `max_points` is rejected with the actual count and a suggested narrower span. The API never silently downsamples.

---

## 3. Named operations

### 3.1 Catalog

| Operation | Filters |
|---|---|
| `list_investigations` | `role`, text `query`, pagination |
| `get_investigation` | exact accession |
| `table_counts` | none |
| `health` | none |

### 3.2 Gas-flame tests

`list_gas_flame_tests` supports:

- `accession` (PSI-10 or PSI-159)
- `flame_type`
- `fuel` (case-insensitive exact label)
- `oxygen_min`, `oxygen_max` on `oxygen_mole_fraction`
- `pressure_min`, `pressure_max`
- `hot_ignition`
- `extinction_mode`
- `tfp`
- `include_qualified` (default `false`)
- `sort` from an allowlist
- `order` (`asc` or `desc`)
- pagination

Pressure filtering requires an explicit accession because PSI-10 uses `pressure_initial_atm` (atm) and PSI-159 uses `pressure_approx_bar` (bar). The response reports `pressure_field` and `pressure_unit`.

By default, rows whose `quality_flags` contain `ramped_condition` or `low_oxygen_condition` are excluded. The response reports `excluded_qualified_rows`. They are not deleted; `include_qualified=true` returns them.

`computed_fields` is always `["stoich_mixture_fraction", "adiabatic_flame_temp_k"]` for gas-flame rows.

### 3.3 Material tests

`list_material_tests` supports `accession` (PSI-25 or PSI-26), `material`, `flow_restrictor`, `o2_min`, `o2_max`, and pagination.

Oxygen filtering requires an explicit accession because PSI-25 uses `initial_o2_pct` and PSI-26 uses `o2_pct`. For PSI-26, the response includes a unit note: the source header says percent while observed values are fraction-like. Values are preserved as labeled.

The response reports `spread_rate_available: false`. No spread-rate column is synthesized.

### 3.4 Droplet tests

`list_droplet_tests` supports accession PSI-69, `fuel`, `ambient_pressure_mm_hg` range, and pagination. The `burning_rate_mm_as_labeled` column is preserved under its source label. It is not converted to mm/s.

### 3.5 Telemetry

| Operation | Behavior |
|---|---|
| `list_telemetry_runs` | Lists PSI-100 exports as separate runs. Never concatenates. |
| `get_telemetry_run` | Returns run metadata and a channel profile list with units and quality flags. |
| `get_telemetry_series` | Returns a bounded, wide series for up to 8 canonical channels. |

Series rules:

- `start_ms` and `end_ms` are required and must lie within the run's valid range.
- `start_ms < end_ms`.
- Channels must exist in the run's channel profiles.
- Rows with `value IS NULL` are excluded.
- Sentinel rows are counted in `excluded_sentinel_rows`.
- The result is grouped by `relative_time_ms`; if multiple rows share a timestamp for a channel, `MAX(value)` is used.
- A selected channel can be `null` at a timestamp where another selected channel has a value. The API does not interpolate across that gap.
- `source_row_range` reports the minimum and maximum source row for the returned query window. The service moves it into provenance `row_range`.

### 3.6 Smoke

`list_smoke_runs`, `get_smoke_run`, and `get_smoke_series` follow the telemetry pattern with `start_s` and `end_s`. Sentinel (`-999`) and `invalid_indefinite` rows are counted separately. Each HKP export is a separate run.

### 3.7 Provenance

`resolve_provenance(accession, file_name, sheet, row)`:

1. Rejects path separators and `..` in the file name.
2. Looks up the exact source file in `experimental_table`, then `psi_file`.
3. Returns checksum, bytes, retrieval time, source URL, and access status when available.
4. If `row` is supplied, checks the row across provenance-bearing tables and returns `row_verified` plus the matching table names.
5. Adds `checksum_not_available` when the source record has no checksum.

A missing file returns `404 not_found`. A path-like file name returns `400 invalid_query`.

### 3.8 Dataset quality

`dataset_quality(table_names, accession)` slices the committed quality report:

- table row and column counts;
- columns with non-zero missingness;
- point-table and flag-table summaries;
- provenance summary;
- issues that are global or match the accession.

---

## 4. Timeout watchdog

DuckDB 2.0.0 does not implement `statement_timeout`. The layer therefore uses:

```python
timer = threading.Timer(budget, connection.interrupt)
timer.start()
try:
    cursor = connection.execute(sql, params)
    ...
finally:
    timer.cancel()
    connection.close()
```

`Connection.interrupt()` cancels a running query and leaves the process usable. An interrupted query raises `503 query_timeout` with the configured budget. Unexpected DuckDB errors are wrapped as `500 query_error` without exposing SQL or paths.

---

## 5. Error mapping

| Condition | Error | HTTP |
|---|---|---:|
| Unknown or repeated query parameter | `invalid_query` | 400 |
| Invalid accession, sort, range, or channel | `invalid_query` | 400 |
| Missing row, run, file, dataset, or measurement | `not_found` / `unknown_measurement` | 404 |
| Page or series limit exceeded | `range_too_large` | 413 |
| Missing canonical table | `service_unavailable` | 503 |
| Query timeout | `query_timeout` | 503 |
| Unexpected query failure | `query_error` | 500 |

---

## 6. Read-only guarantees

- No endpoint accepts `sql`, `table`, `path`, `file_path`, or a free-form filter expression.
- `file` in the provenance endpoint must be an exact source file name; separators and `..` are rejected.
- Accessions must match `PSI-<number>` and, where relevant, an allowlist.
- Sort fields and channels are allowlisted.
- The database connection is opened per operation and closed afterward.
- No query writes to the canonical Parquet files.

---

## 7. Tests

`tests/test_db.py` uses a synthetic canonical dataset to cover filtering, pagination, qualified-row exclusion, unit-specific pressure/O2 filters, series caps, sentinel handling, provenance, quality slicing, and the watchdog.

`tests/test_analytics_integration.py` runs the same contract against the real canonical Parquet tables, including 8,058,206 rows, 1,762,436 telemetry points, 6,251,427 smoke points, and real provenance checksums.
