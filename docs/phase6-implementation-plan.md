# Phase 6 — Production Readiness Implementation Plan

**Project:** Flame in Freefall
**Team:** AFAQ
**Baseline SHA:** `f777185e16636325f73a78b05139fd48309e9b4a`
**Audit date:** 2026-11-10
**Status:** Phase 6 complete (2026-11-10). Milestones A–H were implemented; the live-provider evaluation remains pending credentials.

This plan is based on the repository as it exists at the Phase 5 release. It
does not assume a deployment system that is not present, and it does not
replace Phase 1–5 safeguards.

---

## 1. Audit findings

### 1.1 Verified baseline

| Item | Result |
|---|---|
| Branch | `main` |
| Local HEAD | `f777185e16636325f73a78b05139fd48309e9b4a` |
| Remote `origin/main` | `f777185e16636325f73a78b05139fd48309e9b4a` |
| Working tree | Clean |
| Backend tests | 483 passed, 1 warning |
| Frontend unit/component | 68 passed |
| Playwright | 27 passed, including 7 axe scans |
| Retrieval index | `assistant-index-v1-537b6ec9903d`, 1,391 chunks, 944 documents, 18 sources |
| Evaluation report | 36 / 36 golden questions; 117 / 117 citations valid |
| Canonical dataset | 13 tables, 8,058,206 rows, version `2a19f9f2...` |

These are the audit baseline values. Final Phase 6 test counts, index version, and
performance results are recorded in the Phase 6 documents and generated reports.

### 1.2 Existing capabilities

- A read-only FastAPI service with 35 paths, shared envelopes, request IDs,
  CORS, ETag/`304`, rate limiting, and structured request logs.
- A deterministic grounded assistant with 22 allowlisted tools, verified
  retrieval, citation and claim validation, an optional OpenAI-compatible
  rephrase boundary, and a golden evaluation harness.
- A Next.js App Router frontend with 18 routes, a centralized API client,
  loading/error/empty states, citation and evidence panels, and axe scans.
- Committed registries, reports, fixtures, and metadata; canonical Parquet and
  raw NASA files remain outside Git.
- Reproducibility commands for the manifest, schemas, fixtures, catalog,
  registries, retrieval index, and assistant evaluation.

### 1.3 Production blockers

| Blocker | Evidence | Planned treatment |
|---|---|---|
| No Docker or Compose configuration | No Dockerfile, `.dockerignore`, or Compose file at baseline | Add production Dockerfiles and Compose; verify local production startup outside Docker when the daemon is unavailable |
| No CI/CD | `.github/` absent | Add GitHub Actions quality gates with data-free and full-data jobs |
| No readiness endpoint | Only `/health`; it reports data state but is not a deployment gate | Add `/api/v1/ready` with explicit 200/503 semantics |
| No operational metrics | Structured logs only | Add a bounded in-process metrics registry and read-only metrics endpoint |
| Provider lacks retry, rate-limit, token, and cost handling | `providers.py` performs one HTTP request and returns text only | Add bounded retries, `Retry-After`, request IDs, usage parsing, cost estimation, and safe logs |
| No live-model evaluation | No credentials available | Complete and test the real HTTP/provider path; record live evaluation as pending, not passed |
| Retrieval precision is moderate | precision@5 `0.602381` | Measure source-aware ranking improvements before adopting them |
| Data-free checkout has 5 test failures | `pytest -m "not integration"` in a clean worktree | Correct integration classification and test setup so CI is honest |
| Production frontend build is not container-oriented | No Next.js standalone output | Add `output: "standalone"` and a multi-stage frontend image |
| Canonical data is not in Git | Expected and correct | Mount read-only canonical data and index into the backend container; never bake raw files |

### 1.4 Non-blockers

- No authentication is required for the public read-only scientific experience.
  Authentication will not be added merely for appearance.
- No Kubernetes or external vector database is justified. The current workload
  is small and Compose is sufficient.
- No telemetry processing of the 13.5 TB registered archive is needed. CI uses
  the curated 72-file scope and data-free checks.

---

## 2. Deployment architecture

```text
Browser
  |
  v
Next.js frontend container (port 3000)
  |  NEXT_PUBLIC_API_BASE_URL baked at build time
  v
FastAPI backend container (port 8000)
  |-- committed registries, metadata, reports, fixtures (image)
  |-- read-only canonical Parquet mount (/app/data/processed)
  |-- read-only retrieval index mount (/app/data/assistant)
  |-- optional external OpenAI-compatible provider
```

- Frontend and backend remain independently deployable.
- Only public `NEXT_PUBLIC_*` values are available to the browser. Provider keys
  remain server-side.
- Raw NASA files are not copied into either image.
- The backend can start without an assistant index; retrieval-dependent
  answers fail closed and readiness reports the index state.
- `docker compose` is the reference local production topology. The same
  containers can be deployed independently by a platform that supplies the
  environment and read-only data mounts.

---

## 3. Milestones

### Milestone A — Audit and CI baseline

- Record the audit and plan.
- Correct data-dependent test classification so `pytest -m "not integration"`
  passes in a clean checkout.
- Preserve all Phase 1–5 tests and scientific checks.

### Milestone B — Deployment and readiness

- Add backend and frontend Dockerfiles.
- Add `.dockerignore` and `docker-compose.yml`.
- Add Next.js standalone output.
- Add `/api/v1/ready` with canonical-data and optional-index gates.
- Verify `uvicorn` and `next start` production startup locally.
- Document persistent storage and backup requirements.

### Milestone C — CI/CD

- Add a GitHub Actions workflow for backend, data-free reproducibility,
  frontend, build, and accessibility checks.
- Add an opt-in full-data/Playwright job for runners with canonical data.
- Cache Python and npm dependencies.
- Keep secrets out of logs.
- Add a local reproducibility script used by CI.

### Milestone D — Real-provider integration

- Add bounded retry, timeout, `Retry-After`, request-ID, token-usage, and
  optional cost-estimation support.
- Extend the answer contract with optional provider usage metadata.
- Test the HTTP provider path with local mock transports and a local
  OpenAI-compatible test server; never present mock output as a real model.
- Run the golden set against a real provider only if credentials exist.
- Otherwise generate an explicit pending report and document the limitation.

### Milestone E — Retrieval optimization

- Record before metrics: precision@5, recall@5, MRR.
- Add source-aware ranking only where it can be measured.
- Re-run all seven labelled cases and the full golden evaluation.
- Reject changes that reduce recall without a documented reason.
- Rebuild the index and record the new manifest.

### Milestone F — Monitoring and security

- Add a bounded metrics registry for requests, status codes, latency, rate
  limits, assistant provider/fallback/refusal counts, tool failures, and token
  usage.
- Add a read-only metrics endpoint and document log fields.
- Review CORS, proxy trust, request size limits, headers, dependency posture,
  error messages, and tool permissions.
- Add tests for readiness, metrics, security headers, and request-size limits.

### Milestone G — Performance

- Add a reproducible benchmark script against a running local server.
- Measure investigation listing, dataset metadata, gas-flame queries,
  telemetry series, citation resolution, provenance, deterministic assistant
  fallback, and retrieval.
- Record environment, dataset version, concurrency, mean, p95, error rate, and
  resource observations.
- Optimize only demonstrated bottlenecks.

### Milestone H — Release

- Complete the six Phase 6 documents.
- Update README, roadmap, architecture, API documentation, frontend README, and
  assistant documentation.
- Run full regression, Playwright, axe, reproducibility, and startup checks.
- Commit by milestone, push without force, and verify local/remote SHAs.

---

## 4. CI matrix

| Job | Requires canonical data | Checks |
|---|---|---|
| Backend unit and contract | No | `pytest -m "not integration"`, compile check |
| Data-free reproducibility | No | Manifest, schemas, fixtures, catalog, registries, index build/check, deterministic evaluation where possible |
| Frontend | No | `npm ci`, lint, typecheck, unit/component tests, production build |
| Full-data integration | Yes, supplied by a self-hosted runner or data artifact | `pytest -m integration`, canonical validation |
| Playwright and axe | Yes, real backend and canonical data | 27 Playwright tests and 7 axe scans |

The default hosted workflow must not pretend that full-data or live-model
checks ran. Those jobs are explicit and opt-in.

---

## 5. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Missing canonical data in CI | False green or failed build | Separate data-free and full-data jobs; skip integration tests explicitly |
| Provider outage or rate limit | Assistant unavailable or slow | Bounded retries, timeout, deterministic fallback, visible reason |
| Secret leakage | Credential compromise | Server-only env, no browser exposure, redacted logs, tests |
| Stale retrieval index | Wrong or unavailable evidence | Source-hash validation, readiness warning, rebuild instructions |
| Container lacks data | API starts but cannot serve | Readiness gate on canonical tables; documented mounts |
| Public metrics leak user content | Privacy risk | Aggregate counters only; no question text |
| Performance regression | Poor user experience | Reproducible benchmark and documented baseline |
| Retrieval change reduces recall | Lost evidence | Golden set plus labelled retrieval before/after gate |
| Docker daemon unavailable locally | Unverified image build | Validate Dockerfiles structurally, verify native production startup, document the environment limit |
