# Competition Demo Script — Flame in Freefall

**Duration:** 8–10 minutes
**Audience:** NASA Space Apps judges and general technical reviewers
**Demo type:** Live local production build with deterministic assistant
**External LLM required:** No

This script tells a scientific evidence story. Every number shown comes from the
running API. Do not replace a failed live call with a screenshot of a different
result unless the screen is labeled as a recorded fallback.

---

## 1. Opening — the problem (45 seconds)

Say:

> Microgravity combustion data are spread across NASA PSI investigations,
> summary tables, telemetry exports, workbooks, and publications. The hard part
> is not only finding a number; it is knowing its source, unit, missingness, and
> whether a comparison is scientifically allowed.

Show: `http://localhost:3000/`

Point out:

- 24 verified PSI combustion investigations.
- 9 curated datasets.
- 8,058,206 canonical rows.
- Explicit warning that no BASS spread rate or fire-risk score is produced.

---

## 2. Dashboard and investigations (60 seconds)

1. Open `/`.
2. Show the live registry counts and dataset serving states.
3. Open `/investigations`.
4. Search `PSI-159`.
5. Open the PSI-159 investigation.
6. Point out the source references, curated datasets, and limitations.

Say:

> The catalog is metadata, not a substitute for the experiment. The platform
> shows what NASA published and what the MVP curated.

---

## 3. Verified gas-flame experiment (90 seconds)

Open:

```text
http://localhost:3000/experiments/gas-flame?accession=PSI-10
```

Show:

- Pressure filters are labeled `atm` and require an explicit PSI-10 accession.
- Oxygen is labeled as a mole fraction.
- Rows marked RAMP/RAMPED/LOW O2 are excluded by default and counted separately.
- A missing value renders as a dash, not zero.

Say:

> PSI-10 pressure is in atm. PSI-159 pressure is in bar. The platform does not
> silently convert or merge them.

Optional contrast: switch to PSI-159 and show `bar`.

---

## 4. Measured versus computed variables (60 seconds)

Open a PSI-10 dataset detail page or the field dictionary:

```text
http://localhost:3000/datasets/psi-10-gas-flame
```

Show:

- `adiabatic_flame_temp_k` is labeled computed.
- `peak_burner_temp_c` is labeled measured.
- `pressure_initial_atm` is measured.
- Missing fields are labeled `missing`.

Say:

> A computed flame temperature is not a measured thermocouple reading. The
> interface keeps value kinds distinct because mixing them changes the science.

---

## 5. Telemetry and raw channels (60 seconds)

Open:

```text
http://localhost:3000/telemetry
```

Show:

- Separate SAFFIRE-III runs; runs are never concatenated.
- Time unit is `ms`.
- Uncalibrated channels are labeled raw.
- Missing points are gaps, not zero.
- The series cap and `413` guidance are visible if a range is too large.

Say:

> Telemetry is engineering sensor data. A raw radiometer voltage is not a
> calibrated physical concentration.

---

## 6. Provenance and citation resolution (60 seconds)

Open a known provenance example:

```text
http://localhost:3000/provenance?accession=PSI-10&file=PSI-10_Experimental%20table_Flame%20Design_Normal%20Flame.csv&row=2
```

Show:

- Accession, file, row, checksum, retrieval date, source URL.
- Citation drawer resolves through `/api/v1/citations/{citation_id}`.
- An unavailable file never has a download link.

Say:

> A citation is not a bibliography label. It resolves to a source file and row.

---

## 7. Comparison withholding (60 seconds)

Open:

```text
http://localhost:3000/compare?left=psi-10-gas-flame.oxygen_mole_fraction&right=psi-159-gas-flame.oxygen_mole_fraction
```

Show:

- Default decision and required conditions.
- The conditions can be checked explicitly.
- Even when the decision becomes `comparable`, `paired_values.available` is
  `false` with `no_verified_alignment`.

Say:

> A comparison decision is not a paired dataset. Without a committed alignment
> method, the platform withholds paired values and renders no shared chart.

---

## 8. AI research assistant — grounded numerical answer (90 seconds)

Open `/assistant`.

Ask the suggested or typed question:

> How many valid PSI-10 gas-flame records are available?

Expected response:

- 256 valid included records.
- 71 qualified rows excluded by default.
- 327 canonical rows in total.
- Deterministic provider.
- Citations resolve to the PSI-10 source table.
- Supporting values and validation result are visible.

Say:

> The number came from a deterministic tool, not from a language model. The
> assistant cites the source and shows the validation state.

---

## 9. Assistant refusal — unsupported fire-risk question (60 seconds)

Ask:

> What is the fire-risk score for Nomex?

Expected response:

- `insufficient_evidence`.
- Low confidence.
- Explicit refusal to calculate a fire-risk score, rank materials, or claim a
  spacecraft fire-safety guarantee.
- Statement that no validated risk model exists in the verified artifacts.

Say:

> A fluent answer is not a scientific answer. The assistant refuses when the
> evidence cannot support the claim.

Optional follow-up:

> Is PSI-159 safer than PSI-10?

Expected: the same refusal path after the Phase 7 safety-ranking update.

---

## 10. Assistant refusal — unit trap (45 seconds)

Ask:

> Can I compare PSI-10 atm pressure directly with PSI-159 bar pressure?

Expected:

- The registry decision and required conditions are stated.
- The answer reports that PSI-159 `pressure_initial_atm` has zero values.
- No converted or paired value is produced.
- `unavailable_data` or a conditional decision is shown honestly.

Say:

> The assistant does not invent a conversion or a pairing to satisfy the
> question.

---

## 11. Close — scientific value and limits (45 seconds)

Say:

> Flame in Freefall turns a fragmented NASA archive into a reviewable evidence
> system: canonical data, explicit units and missingness, citations that resolve,
> comparisons that can be withheld, and an assistant that refuses unsupported
> claims.

> It does not predict spacecraft fire safety, rank materials, or claim that a
> curated subset is the full archive. Those are future research directions that
> require separate validation.

---

## 12. Fallback plan

### If the frontend is unavailable

Use the API directly:

```bash
curl http://127.0.0.1:8000/api/v1/ready
curl http://127.0.0.1:8000/api/v1/citations/cit_f_21df4ec92db1eca0
curl -X POST http://127.0.0.1:8000/api/v1/assistant/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"How many valid PSI-10 gas-flame records are available?"}'
```

### If an external provider is configured but failing

The assistant returns the validated deterministic draft with
`fallback_mode=true` and a safe reason. Continue the demo; do not hide the
fallback banner.

### If the canonical data are unavailable

Do not fabricate a demo. Show the committed validation report, the restore
drill record, and the deployment checklist, and state that the live data mount
is unavailable.

### If the network is unavailable

Run the local static production build and the local API. The deterministic path
does not require an external LLM or internet access.

---

## 13. Demo guardrails

- Do not call a number a measurement unless the API labels it measured.
- Do not compare PSI-10 atm with PSI-159 bar.
- Do not show a paired chart when `paired_values.available=false`.
- Do not claim a fire-risk score, material ranking, or spacecraft guarantee.
- Do not describe retrieved documentation as numerical evidence.
- Do not use a screenshot as a substitute for a failed live result unless it is
  explicitly labeled as a recorded fallback.
