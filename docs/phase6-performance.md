# Phase 6 — Performance Baseline

**Project:** Flame in Freefall
**Status date:** 2026-11-10
**Dataset version:** `2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb`
**Retrieval index:** `assistant-index-v1-796b45cda220`
**Report:** `data/reports/phase6_performance.json`

This is a local indicative baseline, not a production service-level objective.
It measures the existing API without changing scientific query semantics.

---

## 1. Environment

| Item | Value |
|---|---|
| Host | Local Linux development environment |
| Python | 3.14.4 |
| API server | Single Uvicorn process |
| Backend storage | Read-only DuckDB views over canonical Parquet |
| Iterations per scenario | 30 |
| Concurrency | 8 |
| Warmup | One request per scenario |
| Rate limiting | Relaxed on the benchmark server to avoid self-throttling; production default remains 600 requests / 60 seconds |
| Raw data | Not downloaded or loaded for the benchmark |

The benchmark script is `scripts/benchmark_api.py`. It discovers telemetry run
and citation identifiers from the API rather than hardcoding scientific values.

```bash
.venv/bin/python scripts/benchmark_api.py \
  --iterations 30 \
  --concurrency 8 \
  --server-pid <uvicorn-pid>
```

---

## 2. Results

| Scenario | Mean (ms) | p95 (ms) | Errors |
|---|---:|---:|---:|
| `health` | 111.335 | 140.640 | 0 / 30 |
| `investigations` | 184.820 | 227.459 | 0 / 30 |
| `datasets` | 18.537 | 27.109 | 0 / 30 |
| `dataset_metadata` | 12.932 | 16.986 | 0 / 30 |
| `gas_flame_tests` | 349.397 | 596.429 | 0 / 30 |
| `assistant_status` | 13.287 | 17.290 | 0 / 30 |
| `telemetry_series` | 527.218 | 604.966 | 0 / 30 |
| `citation_resolution` | 10.260 | 13.552 | 0 / 30 |
| `provenance` | 86.379 | 101.138 | 0 / 30 |
| `assistant_query_deterministic` | 232.058 | 273.357 | 0 / 30 |

All scenarios returned HTTP 200 for every measured request. The error rate was
0.0 in the committed report.

### Server resource observations

| Measurement | Before | After |
|---|---:|---:|
| Resident set size | 178,576 KB | 212,904 KB |
| Threads | 3 | 10 |

The RSS increase includes the warmed DuckDB/Parquet path, the in-memory
retrieval index, and the benchmark connection pool. It is a single-run
observation, not a memory-leak conclusion.

---

## 3. Interpretation

- Metadata routes (`/datasets`, dataset detail, citations, assistant status) are
  fast and stable.
- Investigation listing is the slowest metadata route because it reads the
  canonical investigation table and builds the page envelope.
- Gas-flame row queries and telemetry series are the dominant costs. They are
  bounded DuckDB/Parquet queries; the benchmark did not change their semantics.
- The deterministic assistant query is in the same order of magnitude as a
  gas-flame page query because it invokes deterministic tools over the same
  data.
- No pathological latency or error-rate regression was observed under 8-way
  concurrency with existing caps.

No scientific query was reimplemented, downsampled, or cached in a way that
changes its meaning.

---

## 4. Optimization decisions

The only performance-related change in Phase 6 was the measured retrieval
ranking improvement, documented in `docs/assistant-retrieval.md`. No API query
optimization was applied because the benchmark did not show a failure or a
release-blocking regression.

If production traffic grows, the evidence-based next steps are:

1. Run multiple backend workers and add a shared rate-limit store.
2. Precompute bounded telemetry summaries if the product requires repeated
   wide-range views.
3. Add an external cache or reverse-proxy cache for stable GET responses, while
   preserving `ETag`/`304` and `no-store` rules.
4. Re-run this benchmark after any change and compare the same scenarios.

---

## 5. Limitations

- Single host, single API process, local network; not a production load test.
- The benchmark server used a relaxed rate limit to avoid self-throttling.
- Python 3.14 was used locally; the container targets Python 3.12.
- DuckDB and Parquet caching behavior depends on warm caches and filesystem.
- The benchmark does not exercise a live LLM provider. Provider latency, tokens,
  and cost are reported by the separate real-model evaluation when available.
- Resource usage was sampled through `/proc`, not a continuous profiler.
- No conclusion about maximum sustainable throughput is drawn from 30 requests
  per scenario.
