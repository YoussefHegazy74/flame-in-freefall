# Serving States

**Project:** Flame in Freefall
**Team:** AFAQ
**Artifact:** `data/metadata/serving_registry.json`
**Engine:** `src/analytics/serving.py`
**Registry version:** `1.0.0`

Serving state answers a narrower question than download status: **may this resource be exposed for this specific use, and with what warnings?** A dataset can be present on disk and still be blocked for quantitative comparison.

---

## 1. States

| State | Definition | Display rule |
|---|---|---|
| `available` | Present and usable for the requested use without a material scientific limitation. | Serve normally with provenance and dataset version. |
| `available_with_warnings` | Present and usable, but documented limitations must travel with every response. | Serve with visible warnings and limitations. |
| `restricted` | Present, but the requested use is limited by a scientific or quality constraint. | Serve only with an explicit restriction notice and approved scope. |
| `blocked` | The requested use is prohibited by a hard scientific or integrity constraint, even if bytes exist. | Do not serve for this use; explain why. |
| `metadata_only` | No measurement data are available; only metadata, provenance, or source references can be served. | Serve metadata only; never show a zero-valued data chart. |

Serving state is independent of `download_status` and `measurement_file_status`. A file can be downloaded and still be `blocked`.

---

## 2. Uses

Every dataset and measurement is evaluated for four uses:

| Use key | Question |
|---|---|
| `exploration` | May the resource be browsed and summarized with warnings? |
| `quantitative_comparison` | May the resource enter a numeric cross-dataset comparison? |
| `time_series` | May the resource be served as a time series? |
| `provenance` | May its source metadata and citations be served? |

The same dataset can be `available_with_warnings` for exploration, `restricted` for quantitative comparison, `blocked` for time series, and `available` for provenance. This is intentional.

---

## 3. Dataset states

The registry contains **9 curated datasets** and **93 measurement states**.

| Dataset | Exploration | Quantitative comparison | Time series | Provenance |
|---|---|---|---|---|
| `psi-10-gas-flame` | `available_with_warnings` | `restricted` | `blocked` | `available` |
| `psi-100-telemetry` | `available_with_warnings` | `blocked` | `available_with_warnings` | `available` |
| `psi-101-smoke` | `available_with_warnings` | `blocked` | `available_with_warnings` | `available` |
| `psi-102-smoke-log` | `available_with_warnings` | `blocked` | `blocked` | `available` |
| `psi-159-gas-flame` | `available_with_warnings` | `restricted` | `blocked` | `available` |
| `psi-25-material` | `available_with_warnings` | `blocked` | `blocked` | `available` |
| `psi-26-material` | `available_with_warnings` | `blocked` | `blocked` | `available` |
| `psi-69-droplet` | `available_with_warnings` | `restricted` | `blocked` | `available` |
| `psi-98-metadata` | `metadata_only` | `blocked` | `metadata_only` | `available` |

Every dataset is `available` for provenance. No dataset is served as `comparable` merely because it exists.

---

## 4. Measurement states

A dataset state is a default; a measurement can be stricter. At measurement level:

| Serving state | Count |
|---|---:|
| `available_with_warnings` | 68 |
| `restricted` | 22 |
| `available` | 1 |
| `blocked` | 1 |
| `metadata_only` | 1 |

Examples:

| Measurement | Exploration | Quantitative comparison | Why |
|---|---|---|---|
| `psi-100-telemetry.cygnus_timestamp_ms` | `available` | `restricted` | A timestamp is usable as a time axis but is not a physical comparison quantity. |
| `psi-10-gas-flame.oxygen_mole_fraction` | `available_with_warnings` | `restricted` | Summary-table measurement; quantitative use only through explicit comparability rules. |
| `psi-26-material.o2_pct` | `available_with_warnings` | `blocked` | Unit ambiguity: the header says percent while observed values are fraction-like. |
| `psi-25-material.pressure_atm` | `blocked` | `blocked` | The column is present but has no non-null values in the canonical table. |
| `psi-100-telemetry.radiometer_1_raw` | `available_with_warnings` | `blocked` | Raw, uncalibrated signal, not a physical measurement. |
| `psi-98-metadata.telemetry_sensor_data` | `metadata_only` | `blocked` | Metadata only; no measurement data were ingested. |

---

## 5. Reasons and restrictions

Every decision carries machine-readable reasons and human-readable restrictions. Examples of reason codes:

- `source_summary_table`
- `pair_specific_comparison`
- `ramped_condition_rows`
- `missing_final_state`
- `computed_tad_zst`
- `unit_ambiguity`
- `uncalibrated_channels`
- `pressure_missing`
- `no_spread_rate`
- `material_names_unvalidated`
- `metadata_only`

A reason has a stable `code` and a message. Restrictions are short imperative strings such as "Do not treat Tad or Zst as measured temperatures."

---

## 6. API quality mapping

The API maps serving states to the response `quality.status`:

| Serving state | API `quality.status` |
|---|---|
| `available` | `verified` |
| `available_with_warnings` | `partial` |
| `restricted` | `partial` |
| `blocked` | `blocked` |
| `metadata_only` | `experimental_table_only` if a public experimental table exists, otherwise `not_available` |

A metadata-only dataset with a public experimental table is labeled `experimental_table_only`. It is never presented as empty measurement data.

---

## 7. API surface

| Endpoint | Serving information |
|---|---|
| `GET /api/v1/datasets?use=...` | Each dataset's decision for the requested use. |
| `GET /api/v1/datasets/{dataset_id}` | Decisions for all four uses. |
| `GET /api/v1/datasets/{dataset_id}/quality` | Decisions plus the quality report slice. |
| `GET /api/v1/measurements?use=...&serving_state=...` | Measurement summaries filtered by serving state. |
| `GET /api/v1/measurements/{measurement_id}?use=...` | One measurement's decision for a use. |

An unknown `use` returns `400 invalid_query`.

---

## 8. Tests

`tests/test_serving.py` covers all five states at dataset and measurement level, use-specific state changes, metadata-only handling, and registry validation. `tests/test_api.py` covers the HTTP mapping, including `experimental_table_only` and blocked quantitative use.

The registry generator is `scripts/build_phase2_registries.py`. Run it with `--check` to verify the committed artifact.
