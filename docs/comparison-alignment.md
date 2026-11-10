# Comparison Alignment Methodology

**Project:** Flame in Freefall
**Team:** AFAQ
**Status:** Implemented as an eligibility and withholding contract (2026-11-10)
**Scope:** How `/api/v1/compare` decides whether two measurements may be paired, what `paired_values` returns, and why no paired series is produced today.

This document defines the scientific rules behind paired comparison. It is intentionally conservative: a comparison that cannot be justified from committed metadata and real source records is withheld, not estimated.

---

## 1. Principles

1. **A comparability decision is not an alignment method.** A rule may say two measurements are comparable in principle. That does not identify which left row corresponds to which right row.
2. **Pairing requires exact keys.** A method must name the columns that identify a pair and the columns that carry the values.
3. **No row-number pairing.** Source row 1 in one file has no scientific relationship to source row 1 in another file.
4. **No interpolation.** The API never fills a missing left or right value to manufacture a pair.
5. **No silent normalization.** Labels are not lowercased, trimmed, or mapped unless a committed method documents the mapping.
6. **No ambiguous unit conversion.** Pressure in atm is not converted to bar without an explicit, verified conversion rule. PSI-10 and PSI-159 are kept separate.
7. **No measured/computed mixing.** A measured temperature and a source-computed adiabatic temperature are different quantities unless a rule explicitly defines the comparison.
8. **Every pair must be traceable.** A paired observation must identify the left and right source records, files, units, and provenance.
9. **Withholding is a valid result.** `available: false` with a reason is more useful than a chart built on an unverified join.

---

## 2. Eligibility pipeline

`/compare` evaluates the request in this order:

| Step | Check | Failure behavior |
|---|---|---|
| 1 | Both measurement IDs exist in the comparability registry. | `404 unknown_measurement`. |
| 2 | An explicit comparison rule exists. | `not_comparable` with `no_explicit_rule`. |
| 3 | The rule's status and required conditions are evaluated. | `conditionally_comparable`, `blocked`, `insufficient_metadata`, or `not_comparable`. |
| 4 | Canonical-data presence is checked for both measurements. | `integrity.status: "failed"`; paired values withheld with `measurement_unavailable`. |
| 5 | A verified alignment method is looked up for the rule. | `no_verified_alignment`. |
| 6 | Observations are produced from real source records. | Not implemented; the alignment registry is empty. |

A `comparable` decision is necessary but not sufficient for a paired series. Today, even a `comparable` decision returns `paired_values.available: false`.

---

## 3. Decision states

| Decision status | Meaning | Paired values |
|---|---|---|
| `comparable` | The measurements share a valid basis and all required conditions are verified. | Still withheld unless a verified alignment method exists. |
| `conditionally_comparable` | A rule exists, but at least one required condition is unverified. | Withheld with `conditions_not_verified`. |
| `not_comparable` | No valid comparison basis, or no explicit rule. | Withheld. |
| `blocked` | A hard unit, value-kind, calibration, availability, or quantity conflict exists. | Withheld. |
| `insufficient_metadata` | The metadata cannot support a decision. | Withheld. |

The frontend renders the decision and never overrides it.

---

## 4. Integrity checks

The `integrity` object reports whether each measurement has canonical values.

```json
{
  "status": "passed",
  "checks": [
    {
      "measurement_id": "psi-10-gas-flame.oxygen_mole_fraction",
      "checked": true,
      "status": "available",
      "reason": null,
      "table": "gas_flame_test",
      "field": "oxygen_mole_fraction",
      "accession": "PSI-10",
      "total_rows": 327,
      "non_null_count": 109,
      "alternatives": []
    },
    {
      "measurement_id": "psi-159-gas-flame.oxygen_mole_fraction",
      "checked": true,
      "status": "available",
      "reason": null,
      "table": "gas_flame_test",
      "field": "oxygen_mole_fraction",
      "accession": "PSI-159",
      "total_rows": 333,
      "non_null_count": 154,
      "alternatives": []
    }
  ],
  "failures": [],
  "not_checked": [],
  "messages": []
}
```

Integrity statuses:

| Status | Meaning |
|---|---|
| `available` | The field has canonical values. |
| `missing` | The registry marks the field available, but the canonical table has zero non-null values. |
| `not_checked` | The measurement is not a canonical table field. |
| `no_canonical_tables` | The dataset has no canonical tables. |

When integrity fails, `paired_values.reason.code` is `measurement_unavailable`, and the failing checks are included in `reason.failures`.

---

## 5. Alignment registry

The intended method registry is `data/metadata/paired_alignment_registry.json`. It is intentionally empty in Phase 4.

A method must provide:

| Field | Meaning |
|---|---|
| `method_id` | Stable method identifier. |
| `rule_id` | The comparison rule it applies to. |
| `left_measurement_id`, `right_measurement_id` | Exact registry IDs. |
| `keys` | Exact columns used to match records, such as a verified test code and configuration. |
| `value_fields.left`, `value_fields.right` | Exact canonical value fields. |
| `unit_policy` | `identical`, an explicit conversion with a documented factor, or a refusal. |
| `value_kind_policy` | Whether both sides are measured, both computed, or an explicit mixed rule. |
| `row_scope` | Which rows are eligible, including qualified-row handling. |
| `exclusions` | Documented reasons a candidate pair is dropped. |
| `scientific_justification` | Why the keys identify the same physical test. |
| `source_references` | Files, registry paths, and documents that support the method. |
| `verified` | Must be `true` only after review and tests. |

The current registry has no verified methods. The API therefore returns `no_verified_alignment` for approved comparisons.

---

## 6. Reason codes

| Code | When it appears | What the client shows |
|---|---|---|
| `conditions_not_verified` | The rule requires conditions that were not supplied or were not true. | The required condition keys and a request to verify them. No chart. |
| `no_verified_alignment` | The decision is approved, but no method names exact keys and value fields. | The rule ID, required alignment note, and a statement that no series is produced. |
| `comparison_not_approved` | The decision is not comparable or blocked. | The decision reasons. No chart. |
| `measurement_unavailable` | At least one measurement has no canonical values. | The failing integrity checks and any unit-specific alternatives. No chart. |

`paired_values.status` is `unavailable` for all four in the current implementation.

---

## 7. Worked examples

### 7.1 Conditions not verified

```text
GET /api/v1/compare?left=psi-10-gas-flame.oxygen_mole_fraction&right=psi-159-gas-flame.oxygen_mole_fraction
```

The decision is `conditionally_comparable`. The required conditions are `same_oxygen_basis` and `flame_configuration_documented`. Neither is supplied.

```json
{
  "available": false,
  "status": "unavailable",
  "alignment": {
    "method_id": null,
    "verified": false,
    "keys": [],
    "value_fields": {},
    "unit_policy": null
  },
  "conditions": {
    "supplied": {},
    "required": [
      {"key": "same_oxygen_basis", "satisfied": null},
      {"key": "flame_configuration_documented", "satisfied": null}
    ]
  },
  "observations": [],
  "series": [],
  "exclusions": [],
  "reason": {
    "code": "conditions_not_verified",
    "message": "Required comparison conditions are not verified, so no paired values are returned.",
    "missing_conditions": ["same_oxygen_basis", "flame_configuration_documented"]
  }
}
```

### 7.2 Approved but no alignment method

Supplying both conditions as `true` changes the decision to `comparable`. Integrity passes. Paired values are still withheld:

```json
{
  "available": false,
  "status": "unavailable",
  "alignment": {
    "method_id": null,
    "verified": false,
    "keys": [],
    "value_fields": {},
    "unit_policy": null
  },
  "conditions": {
    "supplied": {
      "same_oxygen_basis": true,
      "flame_configuration_documented": true
    },
    "required": [
      {"key": "same_oxygen_basis", "satisfied": true},
      {"key": "flame_configuration_documented", "satisfied": true}
    ]
  },
  "observations": [],
  "series": [],
  "exclusions": [],
  "reason": {
    "code": "no_verified_alignment",
    "message": "The comparison is approved, but no verified record-level alignment method is registered for this rule. The API does not pair by row number, interpolate, normalize silently, or convert ambiguous units.",
    "rule_id": "psi10-psi159-oxygen",
    "required_alignment": {
      "keys": [],
      "note": "A committed method must name exact alignment keys and value fields."
    }
  }
}
```

This is the key distinction: **approval is not pairing**.

### 7.3 Integrity failure with a unit-specific alternative

The pressure rule is approved when both conditions are supplied, but PSI-159 `pressure_initial_atm` has zero canonical values. The response is:

```json
{
  "available": false,
  "status": "unavailable",
  "reason": {
    "code": "measurement_unavailable",
    "message": "The registry approves this comparison, but at least one requested measurement has no values in the canonical data. No paired values are returned.",
    "decision_status": "comparable",
    "failures": [
      {
        "measurement_id": "psi-159-gas-flame.pressure_initial_atm",
        "checked": true,
        "status": "missing",
        "reason": "no_non_null_values",
        "table": "gas_flame_test",
        "field": "pressure_initial_atm",
        "accession": "PSI-159",
        "total_rows": 333,
        "non_null_count": 0,
        "alternatives": [
          {
            "canonical_field": "pressure_approx_bar",
            "unit": "bar",
            "description": "PSI-159 reports approximate test pressure in bar. It is not an initial pressure in atm and is not interchangeable with one.",
            "evidence": {
              "kind": "document",
              "path": "DATA_DICTIONARY.md",
              "section": "4.3-4.4 PSI-159 ACME CFI-G"
            }
          }
        ]
      }
    ]
  }
}
```

The API does not replace `pressure_initial_atm` with `pressure_approx_bar`, because bar is not atm and the fields are not interchangeable.

### 7.4 Unit mismatch

PSI-10 pressure is reported in atm; PSI-159 pressure is reported in bar. The facets and fields endpoints keep the units separate. A future alignment method must state a unit policy explicitly. Until then, no paired series is produced.

---

## 8. Response contract

```json
{
  "available": false,
  "status": "unavailable",
  "alignment": {
    "method_id": null,
    "verified": false,
    "keys": [],
    "value_fields": {},
    "unit_policy": null
  },
  "conditions": {
    "supplied": {},
    "required": []
  },
  "observations": [],
  "series": [],
  "exclusions": [],
  "dataset_version": "2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb",
  "provenance": [],
  "reason": {
    "code": "no_verified_alignment",
    "message": "...",
    "rule_id": "...",
    "required_alignment": {
      "keys": [],
      "note": "A committed method must name exact alignment keys and value fields."
    }
  }
}
```

When a verified method exists, the same object is expected to include:

- `alignment.method_id`, `alignment.verified: true`, exact `keys`, `value_fields`, and `unit_policy`;
- `observations` with left/right source records, values, units, and provenance;
- `series` only if the observations support a chart;
- `exclusions` for candidate pairs that were dropped and why.

No such method is registered today, so `observations` and `series` are empty.

---

## 9. Frontend guard

The chart renders only when all of the following are true:

1. `paired_values.available === true`;
2. `paired_values.alignment.verified === true`;
3. there is at least one numeric point in `observations` or `series`;
4. when points are derived from observations, the left and right units match exactly.

If the guard fails, the UI shows the reason, required conditions or alignment keys, and exclusions. It does not fall back to a row-number join, a separate-series overlay, or a client-side conversion.

---

## 10. How to add a method safely

1. Choose a rule with a defensible scientific basis.
2. Identify exact alignment keys that exist in both canonical tables and are verified for the same physical test.
3. Define value fields and units. If units differ, write an explicit conversion policy with a source reference; otherwise refuse.
4. Decide how qualified, missing, and sentinel rows are excluded.
5. Add the method to `data/metadata/paired_alignment_registry.json` with `verified: false` until reviewed.
6. Add tests for valid pairs, missing keys, duplicate keys, unit mismatches, excluded rows, and provenance.
7. Review the method against the source files and `DATA_DICTIONARY.md`.
8. Set `verified: true` only after the tests and review pass.
9. Update this document and `docs/phase4-contracts.md` with a real example.

Do not add a method that pairs by row number, interpolates, normalizes labels without a documented mapping, or converts ambiguous units.

---

## 11. Tests and references

Automated coverage:

- `tests/test_phase4_api.py`: comparison integrity, paired-value withholding, reason codes, provenance, and invalid pairing.
- `tests/test_operations.py`: cache, ETag, rate limiting, and request IDs.
- `frontend/tests/components/phase4-panels.test.tsx`: chart guard and blocked states.
- `frontend/e2e/app.spec.ts`: real-backend withholding and citation flows.

Related documents:

- `docs/comparability.md`
- `docs/phase4-contracts.md`
- `docs/serving-states.md`
- `DATA_DICTIONARY.md` §10.7
- `data/metadata/comparability_registry.json`
- `data/metadata/paired_alignment_registry.json`
