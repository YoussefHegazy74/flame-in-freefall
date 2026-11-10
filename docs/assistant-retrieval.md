# Assistant Retrieval

**Project:** Flame in Freefall
**Status date:** 2026-11-10
**Scope:** `src/assistant/retrieval.py`, `scripts/build_assistant_index.py`, `data/assistant/`

The assistant uses retrieval for concepts, objectives, dataset structure,
publications, limitations, and methodology. It does **not** use retrieval for
counts, averages, ranges, filters, telemetry, quality statistics, comparison
eligibility, or paired observations. Those come from deterministic tools.

The index is built only from committed, verified artifacts. Raw NASA files are
never indexed, and the generated index is never committed.

---

## 1. Design constraints

1. **Verified sources only.** A source must be a committed repository document
   or a metadata card generated from a Phase 1–4 registry.
2. **No numerical authority.** Dataset, investigation, publication, field,
   limitation, and file cards deliberately omit count-bearing prose. A
   numeric question must use a deterministic tool.
3. **Reproducibility.** The manifest records source hashes, chunking, ranking
   configuration, dataset and registry versions, index version, build time,
   build command, and validation command.
4. **Fail closed.** A stale, missing, or invalid index is rebuilt in memory from
   the same sources. If that also fails, retrieval-dependent answers fail with
   a safe limitation rather than falling back to model memory.
5. **Untrusted text.** Retrieved chunks are evidence, never instructions.
   They cannot select tools, add numbers, create citations, or reveal secrets.
6. **Citation honesty.** Repository documents and publication cards have no
   Phase 4 citation ID. They are returned as `EvidenceItem` records with
   `citation_id=null`, not as fabricated citations.

---

## 2. Indexed sources

### 2.1 Repository documents

- `DATA_DICTIONARY.md`
- `DATA_SOURCES.md`
- `PROJECT_ARCHITECTURE.md`
- `API_DOCUMENTATION.md`
- `docs/known-limitations.md`
- `docs/phase4-contracts.md`
- `docs/comparison-alignment.md`
- `docs/comparability.md`
- `docs/serving-states.md`
- `docs/query-contract.md`

### 2.2 Registry and report sources

- `data/metadata/comparability_registry.json`
- `data/metadata/serving_registry.json`
- `data/metadata/paired_alignment_registry.json`
- `data/registry/psi_combustion_investigations.json`
- `data/registry/mvp_dataset_catalog.json`
- `data/registry/download_manifest.json`
- `data/reports/acquisition_report.json`
- `data/reports/dataset_quality_report.json`

### 2.3 Metadata cards

The builder also generates cards from the verified Phase 4 service:

| Card type | Source | Citation behavior |
|---|---|---|
| Dataset cards | Nine curated datasets, serving states, roles, and limitations | May carry resolved file citation IDs. |
| Investigation cards | 24 verified PSI records | May carry a resolved file citation ID. |
| Publication cards | Deduplicated publication registry | No abstract, findings, year, or venue; no citation ID. |
| Limitation cards | Dataset, file, measurement, and comparison limitations | May carry evidence citation IDs. |
| Field cards | 93 measurement-derived field definitions | May carry a citation ID when the field maps to a curated source file. |
| File cards | Curated manifest entries, including unavailable files | Carry the Phase 4 file citation ID when one exists. |

Cards contain identifiers, descriptions, units, value kinds, integrity states,
and limitations. They do not contain row counts, means, ranges, or other
computed statistics.

---

## 3. Chunking

| Setting | Value |
|---|---|
| Strategy | `markdown_heading_paragraph` |
| Maximum characters | 1,600 |
| Overlap | 200 characters |
| Minimum characters | 40 |

Markdown headings are preserved in the chunk section path. Paragraphs are
packed up to the maximum size; oversized paragraphs are split with overlap.
Each chunk stores:

- `document_id`, `chunk_id`, and `content_hash`;
- `source_type` and `source_reference`;
- `section` and `title`;
- `accession`, `accessions`, and `dataset_ids`;
- resolvable `citation_ids` when the source type supports them;
- `index_version`.

Duplicate content hashes are removed at search time, and at most two chunks
from the same document are returned by default.

---

## 4. Ranking

Ranking is deterministic and dependency-free:

| Component | Weight / setting |
|---|---|
| BM25 | `k1=1.5`, `b=0.75`, weight `0.65` |
| Hashed TF-IDF cosine | 256 dimensions, weight `0.35` |
| Exact phrase match | `+0.05` |
| Max chunks per document | 2 |
| Method label | `bm25+tfidf-hash-v1` |

The vector component is **lexical hashed TF-IDF**, not a neural semantic
embedding. The manifest, every search result, and the documentation carry that
label. No external embedding API is required to build or query the shipped
index. The optional `FLAME_EMBEDDING_PROVIDER` setting is validated for future
work, but the current index builder does not make an external embedding call.

The query is normalized with Unicode NFKC, lowercasing, scientific-token
preservation, and a stopword list. Search results are sorted by hybrid score,
then by stable document and chunk IDs, so equal scores do not depend on
dictionary order.

---

## 5. Filtering and scope

`search_scientific_documents` and `RetrievalIndex.search()` support:

| Filter | Behavior |
|---|---|
| `query` | Required; trimmed to a bounded length; empty or term-free queries return no results with a warning. |
| `accession` | Case-normalized; matches the chunk accession or an accession list. |
| `dataset_id` | Case-normalized; matches dataset IDs directly, with a controlled accession fallback for documentary chunks. |
| `source_types` | Allowlist of `document`, `dataset`, `investigation`, `publication`, `limitation`, `field`, `file`. |
| `limit` | 1–20 results. |

The assistant's retrieval tool uses a limit of four results in composed
answers. A result outside the requested accession or dataset scope is not
returned.

---

## 6. Manifest and index version

The generated manifest includes:

- `index_version` (`assistant-index-v1-<digest>`);
- `schema_version`, `dataset_version`, and `registry_version`;
- `generated_at`, `build_command`, and `validation_command`;
- `chunking`, `embedding`, and `retrieval` configuration;
- source paths, byte sizes, and SHA-256 values;
- source, chunk, and config digests;
- chunk count, document count, and manifest notes.

The index version changes when the source digest or configuration changes.
A load verifies:

- the index schema version;
- the dataset and registry versions;
- the source hashes and manifest;
- the chunk and config digests;
- the required manifest fields.

A mismatch raises `RetrievalError`. `get_default_index()` then rebuilds the
index in memory from the current committed sources. It does not serve a stale
index silently.

---

## 7. Build and validation

```bash
# Build data/assistant/index.json from committed sources.
.venv/bin/python scripts/build_assistant_index.py

# Validate the artifact against the current sources and configuration.
.venv/bin/python scripts/build_assistant_index.py --check
```

`data/assistant/` is gitignored because the artifact is generated and can be
large. A clean checkout can rebuild it. The runtime does not require the
artifact to exist: it rebuilds in memory when needed.

The check command exits non-zero when sources changed, a hash is missing, a
required field is absent, the schema or dataset version differs, or the chunk
digest does not match. Rebuild after documentation or registry changes, then
rerun the evaluation report so its recorded index version stays current.

---

## 8. Retrieval evaluation

`tests/assistant/retrieval_golden.json` contains seven conservative labelled
cases. The labels are minimal: they identify a verified document or card that
directly answers the query or states the limitation. They are not exhaustive
relevance judgments.

The current deterministic run reports:

| Metric | Result |
|---|---:|
| Usable cases | 7 / 7 |
| Label errors | 0 |
| Mean precision@5 | 0.602381 |
| Mean recall@5 | 1.0 |
| Mean reciprocal rank | 0.761905 |

Precision is a lower bound because unlabelled results may also be relevant.
The set is too small to support a general retrieval claim. The full results,
including per-case retrieved IDs, are in
`data/reports/assistant_evaluation.json`.

---

## 9. Security and prompt injection

- Retrieved text is wrapped as untrusted evidence and marked
  `trusted_as_instruction=false`.
- Instructions in a retrieved chunk cannot call tools or change the planner.
- A retrieved chunk is never promoted to a citation unless a Phase 4 citation
  ID resolves.
- The optional provider never receives retrieved source text as instructions.
  It sees only the user question and the validated deterministic draft.
- The index builder ignores uncommitted or unverified files; it does not crawl
  the web or the raw data directory.
- Index manifests and search results are checked for source drift so an
  attacker cannot substitute a modified document without detection.

See `docs/assistant-security.md` for the threat model and adversarial tests.

---

## 10. Known limitations

1. The retrieval method is lexical. It does not understand synonyms or
   paraphrase as a neural embedding might.
2. The labelled evaluation set is small and domain-specific.
3. Repository documents are not Phase 4 citations. An answer that relies on a
   document must state that the evidence is documentary context.
4. Publication cards contain registry metadata only. The registry has no year,
   venue, abstracts, or findings.
5. The index covers the curated MVP documentation, not the full NASA archive.
6. Retrieval is not a numerical source. If no deterministic tool covers a
   numeric question, the correct result is `insufficient_evidence` or
   `unavailable_data`.

---

## 11. Related documents

- `docs/assistant-tools.md` — deterministic tool catalog.
- `docs/assistant-answer-contract.md` — evidence and citation contract.
- `docs/assistant-evaluation.md` — retrieval and answer metrics.
- `docs/assistant-security.md` — untrusted-source and provider boundaries.
- `docs/phase5-assistant-architecture.md` — component architecture.
