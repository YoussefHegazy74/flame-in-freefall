# Known Scientific Limitations

**Project:** Flame in Freefall
**Team:** AFAQ
**Status date:** 2026-11-09
**Canonical dataset version:** `2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb`

This page consolidates the limitations that affect comparisons and serving. It does not replace `DATA_SOURCES.md` or `DATA_DICTIONARY.md`; it points to the decisions those documents require.

The API encodes these limits as comparability states, serving states, quality flags, warnings, and restrictions. A limitation is never removed by a frontend label or a client-side conversion.

---

## 1. Dataset-level limitations

| Dataset | Limitation | Effect on use |
|---|---|---|
| PSI-98 SAFFIRE-I | The telemetry and sensor XLSX files return HTTP 404. | `metadata_only`; no SAFFIRE-I telemetry series or quantitative comparison. |
| PSI-159 CFI-G | `TFP` and `Xf` are not expanded by the source. | `TFP` is categorical; `Xf` is not given a derived physical meaning. |
| PSI-26 BASS | The oxygen header says percent while observed values are fraction-like (`o2_pct` ≈ 0.221). | Unit status `ambiguous`; blocked for quantitative comparison until resolved. |
| PSI-69 FLEX | The burning-rate column is labeled `mm`, not a rate. | Preserved as `burning_rate_mm_as_labeled`; never converted to mm/s. |
| PSI-100 SAFFIRE-III | Some channels are raw and uncalibrated; timestamp reconciliation is unresolved. | Raw channels are not physical measurements; runs are never concatenated. |
| PSI-101 SAME-R | `-999` sentinels exist; `DustTrakA` inactivity and material/aging joins are unresolved. | Sentinels are null with quality flags; no flame-spread rate or validated material join. |
| PSI-25 BASS-II | `pressure_atm` is present but has no non-null values; the initial CO `-1` meaning is undefined. | Pressure is blocked; `-1` is preserved and flagged, not treated as a measurement. |
| PSI-20 ACME BRE | Oxygen text anomalies include `3400%` and `2100%`. | Preserved raw; not interpreted as 34% or 21% without confirmation. |
| PSI-21 ACME CLD Flame | MFC headers do not state a unit. | `not stated`; no conversion. |
| PSI-25 / PSI-26 BASS / BASS-II | No published flame-spread-rate table was identified. | No spread-rate measurement, chart, or comparison. |

---

## 2. Comparison limitations

1. **An unregistered pair is `not_comparable`.** The comparability registry is an allowlist, not a name-matching heuristic.
2. **Measured and computed values are distinct.** `Tad` and `Zst` are computed by the source. `peak_burner_temp_c` is measured. They are not interchangeable.
3. **Raw and calibrated values are distinct.** Radiometer, anemometer, and detector voltages are raw signals unless the source documents calibration. They do not become physical measurements through a client-side scale factor.
4. **Ambiguous units stay ambiguous.** PSI-26 oxygen and PSI-69 burning rate are the current examples. A conversion requires an explicit rule and a documented basis.
5. **Fuel labels are not cross-mapped.** PSI-10 `C2H4`/`C3H8` are not silently equated to PSI-159 ethane/propane/butane labels.
6. **Categorical flags are not numeric.** `TFP`, cool-flame flags, hot ignition, extinction mode, fuel, and material labels are categorical.
7. **Conditions must be supplied.** A `conditionally_comparable` decision becomes `comparable` only when every required condition is explicitly verified.
8. **A blocked comparison is a scientific result.** `GET /api/v1/compare` returns it with HTTP `200` and a reason; it is not a transport error.

The full decision order is in `docs/comparability.md`. The registry is `data/metadata/comparability_registry.json`.

---

## 3. Serving limitations

| State | What it means here |
|---|---|
| `available_with_warnings` | The data are usable, but the warnings must travel with the response. Most exploration views are in this state. |
| `restricted` | The data are present but limited for the requested use. PSI-10, PSI-159, and PSI-69 quantitative comparison are restricted rather than fully available. |
| `blocked` | The use is prohibited by a hard constraint. PSI-26 quantitative comparison, PSI-25 pressure, and raw telemetry comparisons are blocked. |
| `metadata_only` | Only metadata and source references are available. PSI-98 is in this state. |

The full matrix is in `docs/serving-states.md`. The registry is `data/metadata/serving_registry.json`.

---

## 4. Time-series limitations

1. **Runs are separate.** PSI-100 has five telemetry exports; PSI-101 has 44 HKP exports. They are never concatenated into one series.
2. **Bounded ranges are required.** `start_ms`/`end_ms` and `start_s`/`end_s` must lie inside the run's valid range.
3. **Oversized ranges are rejected.** The API returns `413 range_too_large` with the actual point count and a suggested narrower span. It does not downsample.
4. **Sentinels are excluded and counted.** `-999` values become null and are reported in `excluded_sentinel_rows`.
5. **Missing points are gaps.** A selected channel can be null at a timestamp where another channel has a value. The API does not interpolate.
6. **Units come from channel profiles.** The run detail response lists the unit and quality flags for every channel. Raw channels are labeled.

The query contract is in `docs/query-contract.md`.

---

## 5. Units in observation rows

Observation row endpoints return canonical field names. Numeric names encode the unit (`pressure_initial_atm`, `adiabatic_flame_temp_k`, `fuel_mass_flow_mg_s`, `burning_rate_mm_as_labeled`) or are documented in `DATA_DICTIONARY.md`.

For registry-level `unit` and `unit_status`, use `/api/v1/measurements` or `/api/v1/measurements/{measurement_id}`. If no unit is documented, display `not stated`. Do not infer a unit from a bare field name that does not encode one.

---

## 6. API limitations in Phase 2

Not implemented yet:

- citation records and `/citations/{citation_id}`;
- dataset file, field, limitation, and publication endpoints;
- gas-flame facets;
- ETag/cache headers, rate limiting, and authentication;
- embedded OpenAPI request/response examples;
- assistant endpoints and any LLM/RAG layer;
- frontend assets.

The implemented material route is `/material/tests`; the target contract uses `/materials/tests`. The investigation catalog is `/investigations`; `/datasets` means curated datasets. These differences are recorded in `API_DOCUMENTATION.md` §1.1 and `docs/api-implementation.md`.

---

## 7. What must not be claimed

- No flame-spread rate for BASS/BASS-II, SAME/SAME-R, or telemetry.
- No causal relationship from a correlation.
- No fire-risk score, material ranking, or prediction without a validated method.
- No NASA endorsement of the team's interpretations.
- No measurement, unit, comparison, or citation that is absent from the source and the committed registries.

If a question needs a value that is not in the canonical tables, the correct result is `blocked`, `insufficient_metadata`, `not_comparable`, or an explicit "not available" — never an estimate presented as data.

---

## 8. Related documents

- `DATA_SOURCES.md` — verified source inventory and per-record limitations.
- `DATA_DICTIONARY.md` — exact headers, units, sentinels, and canonical fields.
- `docs/comparability.md` — comparison states, decision order, restrictions.
- `docs/serving-states.md` — dataset and measurement states by use.
- `docs/query-contract.md` — DuckDB operations, bounds, and provenance.
- `docs/api-implementation.md` — implemented API surface and gaps.
- `docs/frontend-readiness.md` — what the frontend may rely on and must not infer.
