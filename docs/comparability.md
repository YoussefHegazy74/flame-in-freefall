# Comparability

**Project:** Flame in Freefall
**Team:** AFAQ
**Artifact:** `data/metadata/comparability_registry.json`
**Engine:** `src/analytics/comparability.py`
**Registry version:** `1.0.0`

This document explains how the platform decides whether two measurements may be compared. The decision is registry-driven and fail-closed. A name match, a similar column, or a shared axis label is never sufficient.

---

## 1. States

Every comparison returns exactly one of five states:

| State | Meaning | Engine behavior |
|---|---|---|
| `comparable` | Same physical quantity, compatible units and value kinds, no unresolved calibration or metadata restriction, and every required condition is verified. | Returned only when all conditions are `true`. |
| `conditionally_comparable` | The measurements can be compared only after explicit conditions are verified, such as a documented fuel mapping or a known normal/inverse configuration. | Returned when a rule exists but at least one condition is missing or `null`. |
| `not_comparable` | The measurements do not share a valid comparison basis. | Returned for explicit not-comparable rules and by default when no rule exists. |
| `blocked` | A hard integrity constraint prevents comparison: ambiguous units, an uncalibrated raw signal, a missing measurement, or measured-versus-computed conflict. | Returned for explicit blocked rules and when the engine detects a hard conflict. |
| `insufficient_metadata` | The metadata cannot establish whether the comparison is valid. | Returned for explicit insufficient-metadata rules and when required metadata is absent. |

There is no implicit `comparable` default.

---

## 2. Registry contents

The committed registry contains **93 measurement entries** and **60 comparison rules**.

Each measurement entry records:

| Field group | Fields |
|---|---|
| Identity | `measurement_id`, `dataset_id`, `accession`, `experiment_family`, `parameter` |
| Data binding | `canonical_field`, `canonical_channel` |
| Physical meaning | `physical_quantity`, `physical_meaning` |
| Units and kind | `unit`, `unit_status`, `value_kind`, `measurement_method` |
| Integrity | `calibration_status`, `availability`, `quality_restrictions` |
| Rationale | `scientific_justification`, `notes`, `source_file_keys`, `source_references` |
| Compatibility | `compatible_datasets`, `incompatible_datasets`, `comparison_status` |

Each rule records:

| Field | Purpose |
|---|---|
| `rule_id` | Stable identifier. |
| `left_measurement_id`, `right_measurement_id` | The exact pair covered by the rule. |
| `status` | Declared state before condition evaluation. |
| `required_conditions` | Named conditions with a human-readable description. |
| `policies` | Unit, value-kind, physical-quantity, and calibration policy. |
| `scientific_justification` | Why the comparison is or is not valid. |
| `source_references` | Dictionary sections or NASA files supporting the decision. |

Measurement IDs are stable strings of the form `<dataset_id>.<parameter>`, for example:

```text
psi-10-gas-flame.oxygen_mole_fraction
psi-159-gas-flame.oxygen_mole_fraction
psi-26-material.o2_pct
psi-100-telemetry.radiometer_1_raw
```

---

## 3. Decision order

The engine applies checks in this order:

1. **Resolve both measurements.** Unknown identifiers raise `unknown_measurement` (HTTP 404).
2. **Find an explicit rule.** Rules are pair-specific. A reversed pair is resolved to the same rule.
3. **Apply hard integrity checks.** Even an explicit rule is downgraded or blocked when:
   - units differ and no explicit conversion is declared;
   - `value_kind` differs (for example `measured` versus `computed`);
   - either side is uncalibrated for quantitative use;
   - either side is unavailable or metadata-only;
   - the physical quantity differs.
4. **Evaluate required conditions.** A supplied `false` produces `not_comparable`. A missing or `null` condition produces `conditionally_comparable`.
5. **Default.** If no rule exists, return `not_comparable`.

The API returns the decision in a normal `200` response. A blocked or not-comparable result is a scientific result, not a transport error.

---

## 4. Conditions

Conditions are named booleans. The caller supplies them explicitly:

```json
{
  "same_oxygen_basis": true,
  "flame_configuration_documented": true
}
```

Example with the PSI-10/PSI-159 oxygen rule:

| Conditions supplied | Result |
|---|---|
| both `true` | `comparable` |
| none | `conditionally_comparable` |
| `same_oxygen_basis: false` | `not_comparable` |

The response lists every required condition, whether it was satisfied, and why.

---

## 5. Examples from the registry

| Pair | Declared status | Reason |
|---|---|---|
| PSI-10 oxygen mole fraction ↔ PSI-159 oxygen mole fraction | `conditionally_comparable` | Same physical quantity, but the oxygen basis and flame configuration must be verified. |
| PSI-10 oxygen mole fraction ↔ PSI-10 pressure | `not_comparable` | Different physical quantities. |
| PSI-159 peak burner temperature (measured) ↔ PSI-10 Tad (computed) | `blocked` | Measured versus computed conflict. |
| PSI-25 `initial_o2_pct` ↔ PSI-26 `o2_pct` | `blocked` | PSI-26 labels the column percent while observed values are fraction-like. |
| PSI-100 radiometer 1 ↔ radiometer 2 | `blocked` | Both channels are uncalibrated raw signals; they are not comparable physical measurements. |
| PSI-10 Tad ↔ PSI-159 Tad | `insufficient_metadata` | The computation method and source metadata are not sufficient for a quantitative comparison. |
| Any unregistered pair | `not_comparable` | Default policy. |

These are registry decisions, not claims that either measurement is invalid on its own.

---

## 6. Hard restrictions

The engine must never:

- infer a flame-spread rate for BASS/BASS-II, SAME/SAME-R, or telemetry;
- convert an ambiguous unit silently;
- compare a raw, uncalibrated signal with a calibrated physical measurement;
- compare a measured value with a computed value without an explicit rule;
- treat categorical fields such as `TFP`, fuel labels, or extinction modes as numeric;
- map PSI-10 `C2H4`/`C3H8` to PSI-159 ethane/propane/butane blends without an explicit chemistry mapping.

---

## 7. API surface

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/comparability` | Full registry summary, concepts, measurements, and rules. |
| `GET /api/v1/compare?left=...&right=...` | One decision, including reasons, conditions, and provenance. |
| `GET /api/v1/measurements` | Measurement registry entries with serving states. |
| `GET /api/v1/measurements/{measurement_id}` | One measurement with its rules and serving decision. |

`conditions` is an optional JSON object encoded as a query parameter. Invalid JSON or a non-object shape returns `400 invalid_query`.

---

## 8. Tests

`tests/test_comparability.py` covers every state, condition handling, unknown measurements, reversed pairs, hard unit/value-kind/calibration checks, and the default not-comparable policy. `tests/test_api.py` covers the HTTP contract, including blocked comparisons returning `200`.

The registry generator is `scripts/build_phase2_registries.py`. Run it with `--check` to verify that the committed JSON matches the catalog definitions.
