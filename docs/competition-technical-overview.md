# Competition Technical Overview — Flame in Freefall

**Project:** Flame in Freefall
**Team:** AFAQ
**Challenge:** Flame in Freefall: SI-Powered Fire Safety Insights from Microgravity Combustion Data
**Event:** NASA Space Apps Challenge 2026, Shebeen El-Kom, Egypt
**Release:** Phase 7 final release
**Dataset version:** `2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb`

---

## 1. Problem addressed

Microgravity combustion research is distributed across NASA Physical Sciences
Informatics (PSI) investigations, heterogeneous summary tables, telemetry
exports, workbooks, publications, and source documentation. The data are
scientifically valuable but easy to misread: units differ by accession, blank
cells are not zeros, some fields are computed, some telemetry channels are
uncalibrated, and several listed files are unavailable.

Flame in Freefall makes the curated evidence reviewable and explainable. It
preserves source values, missingness, units, provenance, and limitations, and it
answers questions only from verified deterministic tools and citations.

It does **not** predict spacecraft fire safety, rank materials, or claim that a
curated subset represents the full NASA archive.

---

## 2. NASA PSI data sources

- 24 combustion investigations in the committed PSI metadata registry.
- A curated 72-file acquisition manifest (56,238,344 bytes).
- 13 canonical Parquet tables with 8,058,206 rows.
- Primary datasets: PSI-10 and PSI-159 gas-flame tables, PSI-100 SAFFIRE-III
  telemetry, PSI-101 SAME-R smoke/detector data.
- Supporting datasets: PSI-20, PSI-21, PSI-25, PSI-26, PSI-69, PSI-98, PSI-102.
- 299 deduplicated publication records; 235 with DOI, 64 without; year and venue
  unavailable in the registry.
- Two PSI-98 telemetry/sensor workbooks remain HTTP 404 and are marked
  unavailable.

Raw NASA files remain outside Git. The repository includes the manifest,
checksums, retrieval status, compact metadata, and authentic fixtures.

---

## 3. Data acquisition and validation

1. A standard-library collector snapshots the PSI investigation metadata.
2. A curated manifest selects 72 files with limits and documented 404s.
3. A resumable downloader verifies size and SHA-256 and records retrieval time.
4. Modular CSV/XLSX/XLS parsers preserve source headers, sentinel tokens, and
   missingness.
5. Canonical builders emit 13 Parquet tables with row-level provenance.
6. Acquisition and canonical validation run as explicit gates.
7. Quality reports record missingness, flags, channels, and provenance.
8. Registry generators reproduce the comparability and serving decisions.

Reproducibility commands include `manifest --check`, download-manifest check,
schema check, fixture check, catalog check, registry check, canonical validation,
retrieval-index check, and assistant evaluation.

---

## 4. Canonical data architecture

```text
NASA PSI metadata + curated raw files
  -> acquisition manifest + checksums
  -> interim parsed tables
  -> 13 canonical Parquet tables
  -> DuckDB read-only views
  -> FastAPI service envelopes
  -> Next.js frontend
  -> deterministic assistant tools + verified retrieval
```

Each canonical observation retains accession, source file, source row, source
URL, checksum, retrieval time, parser version, units, and quality flags where
available. Computed fields are labeled computed; raw channels are labeled raw;
missing values are null and flagged, not zero-filled.

---

## 5. Scientific comparability

Comparability is decided by a committed registry, not by matching field names.

- 93 measurement definitions.
- 60 pair-specific comparison rules.
- 9 curated dataset states and 93 measurement states across exploration,
  quantitative comparison, time series, and provenance.
- An unregistered pair defaults to `not_comparable`.
- A registered pair can still be conditional, blocked, or unavailable.
- Paired values are withheld unless a verified alignment method exists.
- The paired-alignment registry is deliberately empty.

The platform does not convert PSI-10 atm to PSI-159 bar, merge accession-specific
units, or infer an oxygen basis.

---

## 6. Backend architecture

- FastAPI `0.162.2`, Pydantic `2.14.3`, Uvicorn `0.54.0`.
- 37 read-only API paths under `/api/v1`.
- Shared success and error envelopes with request IDs.
- Strict query-parameter allowlisting.
- Bounded pagination and time-series limits.
- ETag/`304`, `Cache-Control`, rate limiting, request-size limits, security
  headers, readiness, and bounded metrics.
- DuckDB read-only views over canonical Parquet; no arbitrary SQL from clients.
- File and row citation registry with checksum and availability verification.

---

## 7. Frontend architecture

- Next.js 16 App Router, React 19, TypeScript, Tailwind CSS.
- 18 application routes, including `/assistant`.
- Centralized typed API client and TanStack Query hooks.
- Responsive scientific interface with loading, empty, error, blocked, and
  unavailable states.
- Citation drawer, file browser, field dictionary, limitations panel,
  publications, facets, comparison-integrity panel, and paired-value withholding.
- Exact serialized assistant numbers; no browser-side scientific rounding or
  unit conversion.
- Seven axe WCAG scans and keyboard-accessible navigation.

---

## 8. AI/RAG architecture

The assistant is deterministic by default and works with no LLM.

```text
Question
  -> bounded conversation context
  -> deterministic planner
  -> 22 allowlisted tools over Phase 1–6 data
  -> verified retrieval over committed docs/cards
  -> grounded draft
  -> citation validation
  -> claim/number/unit/scope validation
  -> optional provider rephrase (validated draft only)
  -> AssistantAnswer contract 1.0.0
```

The optional OpenAI-compatible provider:

- receives only the user question and validated deterministic draft;
- cannot select tools or see retrieved text as instructions;
- cannot add numbers, citations, accessions, dataset IDs, or URLs;
- is revalidated after rewriting;
- falls back to the deterministic answer on any failure.

There is no SQL, filesystem, URL-fetch, shell, or code-execution tool.

---

## 9. Citation and provenance

Every supported numerical answer links a claim to a current tool call and a
resolved Phase 4 citation. Citation validation checks kind, accession, dataset
scope, file, row locator, checksum, verification state, availability, and source
URL. Unknown or mismatched citations fail closed.

Repository documents and publication cards are context, not numerical evidence.
They are returned as evidence items with `citation_id=null` unless a Phase 4
citation resolves.

---

## 10. Scientific limitations

- NASA PSI data are curated observational data, not a controlled fire-safety
  experiment designed by this team.
- Missing values are not zero.
- PSI-10 atm and PSI-159 bar remain separate.
- PSI-159 `pressure_initial_atm` and PSI-10 `pressure_approx_bar` have zero
  canonical values.
- Paired comparisons remain unavailable while the alignment registry is empty.
- No BASS/BASS-II, SAME/SAME-R, or telemetry flame-spread rate is claimed.
- No fire-risk score, material ranking, causal conclusion from correlation, or
  spacecraft fire-safety guarantee is produced.
- The assistant retrieval method is lexical, not a neural embedding.
- A live language model was not evaluated; the deterministic and mock-provider
  checks are software checks.
- The platform analyzes the curated MVP, not the full 13.5 TB PSI archive.

---

## 11. Deployment architecture

- Independent FastAPI backend and Next.js frontend containers.
- Dockerfiles and Compose topology are implemented.
- Canonical Parquet and the retrieval index mount read-only.
- Committed metadata, reports, and documentation are baked into the backend image.
- Raw NASA files are excluded from images.
- Backend readiness checks dataset and index gates.
- Provider keys are server-side only.
- Native Uvicorn and Next.js standalone production startup were verified.
- Docker image build and hosted staging were not executed because the local
  Docker daemon and hosting credentials were unavailable.

---

## 12. Evaluation results

| Metric | Result |
|---|---|
| Backend tests | 496 passed (final Phase 7 run) |
| Frontend unit/component | 68 passed |
| Playwright | 27 passed |
| axe scans | 7 passed |
| Golden questions | 36 / 36 |
| Citation validity | 117 / 117 |
| Supported claims | 59 / 59 |
| Numerical exact match | 30 / 30 |
| Unit consistency | 30 / 30 |
| Tool-selection accuracy | 35 / 35 |
| Correct refusals | 12 / 12 |
| Retrieval precision@5 | 0.602381 |
| Retrieval recall@5 | 1.0 |
| Retrieval MRR | 1.0 |
| Clean-checkout data-free tests | 362 passed |
| Restore drill | Passed; 310 s pipeline recovery |
| Full npm audit | 0 vulnerabilities after Phase 7 upgrade |

A real-provider evaluation remains pending credentials. Deterministic and
mock-provider results are never merged with a real-model claim.

---

## 13. Implemented versus future

**Implemented:** verified acquisition and parsing, canonical tables, quality
gates, comparability and serving registries, read-only API, frontend exploration,
citation/provenance contracts, deterministic assistant, verified retrieval,
provider boundary, evaluation harness, containers, CI, readiness, metrics, and
operational documentation.

**Future research:** a verified paired-comparison executor, live-model
evaluation, validated material risk models, computer-vision-derived BASS spread
rates, full-archive ingestion, hosted staging, and external alerting.

Future work requires a separate scientific method and review. It is not implied
by the current release.
