# Scientific Integrity Audit — Phase 7

**Project:** Flame in Freefall
**Team:** AFAQ
**Audit date:** 2026-11-10
**Dataset version:** `2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb`
**Result:** Pass with documented limitations. One verification gap was closed by adding an explicit safety-ranking refusal.

This audit covers the visible product, API contracts, assistant answers, and
documentation. It does not claim that the underlying NASA experiments prove a
fire-safety conclusion.

---

## 1. Method

1. Inspected dashboard, dataset, experiment, comparison, provenance, publication,
   and assistant copy in `frontend/src`.
2. Checked APIs and assistant responses against the committed registries and
   canonical tables.
3. Re-ran the assistant adversarial and golden evaluations.
4. Verified the known unit, missingness, availability, and paired-value traps.
5. Checked deployment and test documentation for claims that exceeded the
   evidence.

---

## 2. Verified scientific invariants

### 2.1 Missing values are not zero

Direct tool results on the canonical dataset:

| Dataset | Field | Status | Non-null | Missing | Unit |
|---|---|---|---:|---:|---|
| PSI-159 | `pressure_initial_atm` | missing | 0 | 333 | atm |
| PSI-10 | `pressure_approx_bar` | missing | 0 | 256 | bar |
| PSI-159 | `pressure_approx_bar` | available | 333 | 0 | bar |
| PSI-10 | `pressure_initial_atm` | available | 256 | 0 | atm |

The assistant and UI report missing values as missing, never as zero. The field
integrity state is `missing`, and the tool notes explicitly say missing values
are counted as missing.

### 2.2 PSI-10 atm and PSI-159 bar are not merged

The gas-flame table keeps separate columns and separate accession labels:

- PSI-10 pressure is displayed as `pressure_initial_atm` / `atm`.
- PSI-159 pressure is displayed as `pressure_approx_bar` / `bar`.
- Pressure filters require an explicit accession.
- The comparison engine refuses an unapproved cross-accession pressure
  comparison or reports `unavailable_data` when one side has zero values.

### 2.3 PSI-98 unavailable files remain unavailable

Verified file states for `psi-98-metadata`:

| File | Availability | Downloadable |
|---|---|---|
| `PSI-98_Experimental table_SAFFIRE-1.csv` | available | yes |
| `PSI-98_Raw Data_Saffire-I Sample 1 Sensor Data Complete TM graphs.xlsx` | unavailable | no |
| `PSI-98_Raw Data_Saffire-I Telemetry Data Good Process Version.xlsx` | unavailable | no |

The citation drawer and file browser never show a download link for an
unavailable file.

### 2.4 Paired comparisons remain withheld

For the registered PSI-10/PSI-159 oxygen comparison, with both required
conditions set to true:

- decision: `comparable`;
- `paired_values.available`: `false`;
- reason: `no_verified_alignment`.

No paired difference, statistical test, or shared chart is computed. The UI
renders the withholding reason and required alignment keys.

### 2.5 No BASS/BASS-II flame-spread rate

The material pages state that no BASS flame-spread rate is published in the
selected tables and none is calculated. No spread-rate measurement exists in
the canonical tables or measurement registry. The word "rate" in the droplet
page refers only to the source-labeled burning rate and is explicitly not a
spread rate.

### 2.6 No fire-risk score, ranking, or spacecraft guarantee

The assistant refuses requests for fire-risk scores, material rankings, and
spacecraft fire-safety guarantees. A Phase 7 review found that the phrase
"Is PSI-159 safer than PSI-10?" could reach generic retrieval instead of the
refusal path. The planner now treats explicit safety-ranking phrases as a
refusal and returns `insufficient_evidence` with the existing
`no_fire_risk_model` limitation.

Tests added:

- "Is PSI-159 safer than PSI-10?"
- "Which material is safest for a spacecraft cabin?"
- "Is Nomex safe for spacecraft?"

All return `insufficient_evidence`, `methodology`, low confidence, and the
fire-risk refusal text.

### 2.7 Measured, computed, raw, and derived values stay distinct

- `Tad` / `adiabatic_flame_temp_k` is labeled computed.
- `Zst` / stoichiometric mixture fraction is labeled computed.
- Peak burner temperature is labeled measured.
- Uncalibrated telemetry channels are labeled raw/uncalibrated.
- Categorical fields such as `TFP` are not treated as temperatures.
- Missingness and value-kind filters are visible in the field dictionary.

### 2.8 Publications

Publications are deduplicated by DOI or normalized title. Missing year and venue
are returned as unavailable, not inferred. Conflicting title and author
variants are preserved. No abstract text or finding is fabricated.

### 2.9 Provenance and citations

Every displayed citation resolves through `/api/v1/citations/{citation_id}`.
File and row citations include accession, file, locator, checksum where
available, verification state, and availability. Unavailable sources are not
downloadable. The assistant validation rejects unresolved or mismatched
citations.

---

## 3. Findings and resolutions

| Finding | Severity | Resolution |
|---|---|---|
| Explicit "safer than" wording could reach generic retrieval | Medium | Added safety-ranking markers to the fire-risk refusal path; added three adversarial tests. |
| `FLAME_REGISTRY_DIR` was documented as `data/registry` but actually points at `data/metadata` | Medium | Corrected `.env.example` and API implementation documentation; restore drill confirmed the correct path. |
| Development-only npm audit findings | Low | Upgraded Vitest to a secure release and added a tested `minimatch` override; full audit is now clean. |
| Docker image build and scan not executed | Verification gap | Documented as pending; native startup verified. |
| Live-model evaluation not executed | Verification gap | Documented as pending credentials. |

No unsupported measured value, missing-as-zero substitution, unit conversion,
paired-value invention, publication fabrication, or risk score was found.

---

## 4. Limitations that remain visible

- NASA PSI data are observational and curated; they do not establish causal
  spacecraft fire-safety outcomes.
- The paired-alignment registry is empty, so paired values remain unavailable.
- The retrieval method is lexical, not neural semantic search.
- The assistant is deterministic by default; a live provider was not evaluated.
- Docker image and hosted staging verification remain pending.
- The canonical archive is much larger than the curated MVP; the platform does
  not claim to have analyzed the full PSI archive.

---

## 5. Conclusion

The product presents curated, cited NASA PSI observations with explicit
uncertainty and limitations. It does not claim to predict or guarantee spacecraft
fire safety. The audit passes for the implemented scope, with the verification
gaps listed above.
