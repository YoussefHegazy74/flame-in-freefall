# Competition FAQ — Flame in Freefall

**Project:** Flame in Freefall
**Team:** AFAQ

---

## 1. What problem does this solve?

NASA PSI microgravity combustion data are distributed across investigations,
summary tables, telemetry, workbooks, publications, and source documentation.
The platform makes a curated subset reviewable and explainable with preserved
units, missingness, provenance, citations, and explicit scientific limits.

## 2. Is this a fire-risk prediction system?

No. It does not produce a fire-risk score, material ranking, causal conclusion,
or spacecraft fire-safety guarantee. No validated risk model exists in the
verified artifacts.

## 3. Is the assistant a general chatbot?

No. It is a grounded research assistant over curated NASA PSI evidence. It
selects from 22 allowlisted deterministic tools and verified retrieval. It
refuses questions the evidence cannot support.

## 4. Does it require an LLM?

No. The deterministic provider is the default and the fallback. An optional
OpenAI-compatible provider may only rephrase an already validated draft.

## 5. How do you prevent hallucinated numbers?

Every numerical claim comes from a deterministic tool result. The claim
validator checks the number, unit, value kind, dataset scope, and citation
against that tool call. A failed validation withholds the draft.

## 6. How do citations work?

Phase 4 citations use stable file and row IDs. The application resolves every
citation through the citation registry and checks accession, file, locator,
checksum where available, verification state, and availability. A retrieved
document is not a citation unless a Phase 4 citation ID resolves.

## 7. Why are some values missing?

NASA source tables use blanks, dashes, `n/a`, `-999`, and other sentinels. The
pipeline preserves them as missing or flagged values. Missing is never converted
to zero.

## 8. Why do PSI-10 and PSI-159 pressures use different units?

PSI-10 reports pressure in atm and PSI-159 reports pressure in bar. The platform
keeps accession-specific units separate and does not convert or merge them
without an explicit approved rule.

## 9. Why are paired comparisons withheld?

The paired-alignment registry is empty. A comparison decision is not a paired
dataset. Without a committed method that names matching keys, value fields, and
units, the platform returns `paired_values.available=false` with a reason.

## 10. Why is there no BASS/BASS-II flame-spread rate?

The selected BASS/BASS-II materials are test matrices and video, not a processed
spread-rate table. Deriving one would require a separate validated computer-vision
method. The platform does not infer it.

## 11. Why is there no PSI-98 telemetry series?

The two SAFFIRE-I telemetry/sensor workbooks return HTTP 404. The one available
summary table is shown with its documented limits. The missing workbooks are
never presented as downloadable.

## 12. Is the telemetry calibrated?

Some channels are raw/uncalibrated engineering signals. The platform labels them
raw and does not present them as calibrated physical concentrations. Missing
values are gaps, not zeros.

## 13. Is the retrieval semantic?

No. It is deterministic BM25 plus hashed TF-IDF with source-aware ranking. It is
lexical, not a neural semantic embedding. The documentation says so.

## 14. Was a real model evaluated?

Not yet. The provider integration, retries, token usage, cost reporting, safe
fallback, and mock-transport tests are implemented. No provider credentials were
available for a live evaluation, so no real-model result is claimed.

## 15. How reproducible is the project?

The repository includes pinned dependencies, committed manifests/registries,
reproducibility `--check` commands, a canonical dataset version, a golden
assistant evaluation, a labelled retrieval evaluation, CI gates, and a successful
restore drill.

## 16. Is Docker production deployment verified?

The Dockerfiles and Compose topology are implemented, but the local Docker
daemon was inaccessible during Phase 7. Native production startup was verified.
Image build, scan, and hosted staging remain pending a Docker-capable host.

## 17. Does the project imply NASA endorsement?

No. NASA data are used under their published terms. Interpretations and the
platform are the responsibility of Team AFAQ, not NASA.

## 18. What is the strongest scientific value of the project?

It preserves the chain from source file and row to canonical value, unit,
quality flag, citation, and assistant claim. It also makes refusal and
withholding first-class outcomes instead of hiding unsupported conclusions.

## 19. What is the biggest limitation?

The MVP is a curated subset, not the full PSI archive, and it is not a validated
fire-safety model. It is an evidence and exploration platform.

## 20. What comes next?

A live-model evaluation when credentials exist, a verified paired-comparison
executor, a Docker build/scan and hosted staging, and any future material-risk
method only after a published formula, validated inputs, uncertainty analysis,
and review.
