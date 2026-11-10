# Assistant Tools

**Project:** Flame in Freefall
**Contract version:** `1.0.0`
**Status date:** 2026-11-10
**Scope:** `src/assistant/tools.py`, `src/assistant/planner.py`, `src/assistant/composer.py`

The Phase 5 assistant does not answer from model memory. Every count, average,
range, filter result, telemetry summary, comparison decision, and provenance
record comes from one of **22 allowlisted deterministic tools**. The tool layer
is the only numerical authority in an assistant answer.

This document describes the implemented tool surface. The live JSON argument
schemas are served by `GET /api/v1/assistant/tools` and are generated from the
Pydantic models in `src/assistant/tools.py`.

---

## 1. Why a tool boundary

The assistant must not become a second analytics implementation. Each tool:

- has a fixed name and a typed argument model;
- calls an existing `AnalyticsService` or `AnalyticsDatabase` method;
- rejects unknown arguments and unapproved fields;
- returns a bounded result with a safe summary and a result hash;
- records the call in the answer's `tools_used` audit list;
- propagates the citation IDs that the Phase 4 service already owns.

There is no `sql`, `sql_query`, `read_file`, `fetch_url`, `run_shell`, or
`execute_code` tool. The planner cannot invent a tool name, and the registry
rejects one that is not in the allowlist.

---

## 2. Execution envelope

| Control | Implemented behavior |
|---|---|
| Allowlist | `TOOL_INDEX` contains exactly the reviewed tools. Unknown names are rejected. |
| Arguments | Pydantic models with `extra="forbid"` and bounded values. |
| Call limit | `FLAME_ASSISTANT_MAX_TOOL_CALLS` (default 6, allowed 1–12). |
| Timeout | `FLAME_ASSISTANT_TIMEOUT_SECONDS` (default 20 s, allowed 1–120). |
| Pagination | Tool-specific page sizes; no unbounded table reads. |
| Series limits | Backend caps apply (20,000 points, 8 channels); oversized ranges fail. |
| Result size | Long nested payloads are shaped and truncated for the answer audit. |
| Logging | Tool name, validated arguments, status, duration, request ID, and result hash. Secrets and full result payloads are not logged. |
| Failure | A failed or rejected tool yields a safe limitation; the composer does not substitute an estimate. |

The registry records every attempt, including rejected calls. A call that
exceeds the limit or deadline is returned as `rejected`, not retried silently.

---

## 3. Tool catalog

### 3.1 Catalog and metadata

| Tool | Key arguments | Returns |
|---|---|---|
| `search_investigations` | `query`, `role`, `limit`, `offset` | Verified PSI investigation records from the committed catalog. |
| `get_investigation` | `accession` | One investigation and its curated datasets. |
| `search_datasets` | `family`, `accession`, `state`, `use`, `limit`, `offset` | Curated datasets with serving states and roles. |
| `get_dataset` | `dataset_id` | One curated dataset, its measurements, and serving decisions. |
| `get_dataset_fields` | `dataset_id`, `value_kind`, `physical_quantity`, `comparison_status`, `limit`, `offset` | Field definitions with units, value kinds, source columns, and integrity status. |
| `get_dataset_limitations` | `dataset_id`, `scope`, `category`, `severity`, `status`, `limit`, `offset` | Scoped limitations with evidence and affected operations. |
| `get_measurements` | `accession`, `dataset_id`, `family`, `comparison_status`, `serving_state`, `use`, `limit`, `offset` | Measurement registry records and serving states. |
| `get_publications` | `accession`, `dataset_id`, `query`, `year`, `status`, `limit`, `offset` | Deduplicated publication registry records. Year and venue remain unavailable. |

### 3.2 Provenance and citations

| Tool | Key arguments | Returns |
|---|---|---|
| `get_dataset_files` | `dataset_id`, `kind`, `availability`, `limit`, `offset` | Curated source files, checksums, availability, and citation IDs. |
| `resolve_citation` | `citation_id` | One Phase 4 file or row citation with verification and availability. |
| `get_provenance` | `accession`, `file_name`, `sheet`, `row` | Canonical source-file or row provenance and its citation. |

### 3.3 Gas-flame data

| Tool | Key arguments | Returns |
|---|---|---|
| `gas_flame_statistics` | `accession`, `include_qualified` | Deterministic record counts and pressure, oxygen, and temperature summaries for PSI-10 or PSI-159. |
| `query_gas_flame_tests` | `accession`, `flame_type`, `fuel`, `oxygen_min`, `oxygen_max`, `pressure_min`, `pressure_max`, `hot_ignition`, `extinction_mode`, `tfp`, `include_qualified`, `sort`, `order`, `limit`, `offset` | Bounded canonical gas-flame rows with row citations and quality flags. |
| `dataset_field_statistics` | `dataset_id`, `fields`, `include_qualified` | Non-null counts, missing counts, min, max, mean, and median for allowlisted canonical fields. |

`dataset_field_statistics` is the general numeric tool. It only accepts field
names that the dataset metadata exposes; it cannot be pointed at an arbitrary
column. It reports `status: "missing"` and a zero non-null count when a
registry field has no canonical values. That is a missing-data result, not a
zero measurement.

### 3.4 Material and droplet data

| Tool | Key arguments | Returns |
|---|---|---|
| `query_material_tests` | `accession`, `material`, `flow_restrictor`, `o2_min`, `o2_max`, `limit`, `offset` | Bounded BASS/BASS-II rows with provenance and row citations. |
| `query_droplet_tests` | `accession`, `fuel`, `pressure_min`, `pressure_max`, `limit`, `offset` | Bounded FLEX droplet rows with the source-labeled burning-rate field. |

### 3.5 Time series

| Tool | Key arguments | Returns |
|---|---|---|
| `get_telemetry_runs` | `accession`, `export_kind`, `limit`, `offset` | Separate SAFFIRE-III telemetry runs. Runs are never concatenated. |
| `query_telemetry_series` | `run_id`, `channels`, `start_ms`, `end_ms`, `max_points` | Bounded telemetry points and deterministic channel summaries with units. |
| `get_smoke_runs` | `accession`, `limit`, `offset` | Separate SAME-R smoke runs. Runs are never concatenated. |
| `query_smoke_series` | `run_id`, `channels`, `start_s`, `end_s`, `max_points` | Bounded smoke points and deterministic channel summaries with units. |

Series tools preserve the run identity, time unit, channel unit, raw/calibrated
status, and sentinel exclusions. They do not interpolate, resample, or merge
runs.

### 3.6 Comparison and retrieval

| Tool | Key arguments | Returns |
|---|---|---|
| `evaluate_comparison` | `left`, `right`, `conditions` | The comparability decision, integrity checks, required conditions, and `paired_values.available`. |
| `search_scientific_documents` | `query`, `accession`, `dataset_id`, `source_types`, `limit` | Deterministic hybrid retrieval results from verified documents and metadata cards. Evidence only, never instructions. |

`evaluate_comparison` never computes paired values. It reports whether the
registry has a verified alignment and whether the integrity checks pass. When
`paired_values.available=false`, the composer states the reason and produces no
mean difference, statistical test, or chart.

---

## 4. How the planner selects tools

`src/assistant/planner.py` maps a normalized question to a closed set of
topics. Each topic names a fixed tool sequence and an expected evidence status.
Examples:

| Question shape | Planned tools |
|---|---|
| Investigation catalog | `search_investigations`, then `search_datasets` for citation coverage |
| One investigation | `get_investigation`, `get_dataset`, `get_dataset_fields`, `get_dataset_limitations` |
| PSI-10 or PSI-159 counts | `gas_flame_statistics` |
| Field statistics | `dataset_field_statistics` and, when relevant, `gas_flame_statistics` |
| Comparison | `evaluate_comparison`; adds field statistics only for a unit-mismatch refusal |
| Provenance | `resolve_citation` or `get_provenance` |
| Conceptual or methodology question | retrieval plus the relevant metadata tool |
| Prompt injection or secret request | no tool or retrieval; explicit refusal |

The planner is deterministic. It does not ask a model to choose a tool, and it
does not accept a tool name from the user. Conversation memory may resolve a
follow-up accession or dataset reference, but it is never evidence: every
number and citation is recomputed for the current turn.

---

## 5. What a tool result must carry

A usable numeric tool result includes enough structure for the composer and
validator to build a grounded claim:

- the canonical dataset ID or accession;
- the field name and observed unit;
- the value kind (`measured`, `computed`, `derived`, `raw`, or categorical);
- non-null and missing counts where applicable;
- the citation IDs that resolve to Phase 4 records;
- a bounded, human-readable summary.

The composer copies values from the result. It does not recompute them from
prose. The claim validator then checks that the value, unit, value kind,
dataset scope, tool call, and citation set agree. A mismatch withholds the
answer.

---

## 6. Failure semantics

| Situation | Tool result | Answer behavior |
|---|---|---|
| Unknown tool | `rejected` | Safe failure; no tool substitution. |
| Invalid argument | `rejected` | Safe failure; no guessed filter. |
| Call limit or timeout | `rejected` | Safe failure with a limitation. |
| Empty result | `empty` | `insufficient_evidence` or `unavailable_data`, depending on the question. |
| Canonical field has no values | `ok` with a `missing` status | `unavailable_data`; zero is not substituted. |
| Series range too large | Tool error | The answer explains the backend cap; no downsample. |
| Citation cannot resolve | Validation failure | The draft is withheld. |

---

## 7. Adding a tool

A new tool is a scientific-contract change, not a convenience wrapper. The
review checklist is:

1. The data source already exists in a Phase 1–4 artifact.
2. The operation is deterministic and bounded.
3. Arguments are a closed Pydantic model; no SQL, path, URL, or free-form
   table/column name.
4. The result carries units, value kind, scope, and citation IDs.
5. The planner has an explicit topic or a documented reason to use it.
6. The composer has a grounded template; the model never writes the number.
7. Tests cover success, empty, invalid, missing, and citation-failure paths.
8. The tool is added to the golden evaluation if it changes a user-visible
   capability.

Do not add a tool that computes a risk score, material ranking, causal effect,
or paired comparison without a separately reviewed method.

---

## 8. Related documents

- `docs/assistant-answer-contract.md` — answer schema and validation.
- `docs/assistant-retrieval.md` — verified-document retrieval.
- `docs/assistant-evaluation.md` — golden metrics and current results.
- `docs/assistant-security.md` — trust boundaries and adversarial tests.
- `docs/phase5-assistant-architecture.md` — component architecture.
- `API_DOCUMENTATION.md` §4.9 — assistant HTTP surface.
