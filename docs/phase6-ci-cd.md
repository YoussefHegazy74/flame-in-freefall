# Phase 6 — CI/CD and Quality Gates

**Project:** Flame in Freefall
**Team:** AFAQ
**Status date:** 2026-11-10
**Workflows:** `.github/workflows/ci.yml`, `.github/workflows/full-data.yml`

The repository has two workflows with different evidence claims. The default CI
workflow is honest about running without the gitignored canonical Parquet data.
The full-data workflow is manual and runs only on a runner that has the curated
data and retrieval index.

---

## 1. Default CI workflow

`.github/workflows/ci.yml` runs on pushes to `main`, pull requests, and manual
dispatch.

### Backend job

| Step | Purpose |
|---|---|
| Checkout | Read-only repository access |
| Python 3.12 + pip cache | Reproducible runtime |
| `pip install -r requirements.txt` | Pin the tested dependency set |
| `python -m compileall -q backend src scripts` | Syntax check |
| `pytest -m "not integration"` | Unit, contract, and synthetic-data tests |
| `pip-audit -r requirements.txt` | Known Python vulnerability check |
| `scripts/verify_reproducibility.sh` | Committed manifest, download manifest, MVP catalog, and JSON parse checks |

The data-free test gate was verified from a clean worktree at commit
`2b718eb`:

```text
362 passed, 131 deselected, 1 warning
```

The deselected tests are marked `integration` because they need raw files,
canonical Parquet, or built interim outputs. They are not silently run against
synthetic data.

### Frontend job

| Step | Purpose |
|---|---|
| Node 22 + npm cache | Pinned frontend toolchain |
| `npm ci` | Lockfile install |
| `npm run lint` | ESLint |
| `npm run typecheck` | TypeScript without emit |
| `npm test` | Vitest and React Testing Library |
| `npm audit --omit=dev --audit-level=high` | Production dependency audit |
| `npm run build` | Next.js production build with standalone output |

Verified locally: 68 unit/component tests, clean typecheck and lint, and a
passing production build containing `/assistant`.

### Release quality gate

The `quality-gate` job depends on both backend and frontend jobs. It fails when
either required job fails. It does not claim that full-data, Playwright, axe, or
live-model checks ran.

---

## 2. Full-data workflow

`.github/workflows/full-data.yml` is `workflow_dispatch` only and targets:

```text
runs-on: [self-hosted, linux, full-data]
```

It runs:

```bash
python -m pytest -q
bash scripts/verify_reproducibility.sh --with-data
npm ci
npx playwright install --with-deps chromium
npm run test:e2e
```

The `--with-data` mode additionally runs:

- experimental-table schema verification;
- authentic fixture verification;
- Phase 2 registry verification;
- canonical validation;
- retrieval index freshness;
- deterministic assistant evaluation.

Verified locally on the full data: 493 backend tests, 27 Playwright tests, 7 axe
scans, canonical validation pass, current retrieval index, and 36 / 36 golden
questions.

The runner must provide:

- `data/raw/` where integration tests need raw files;
- `data/interim/` parse outputs;
- `data/processed/` canonical Parquet and `dataset_manifest.json`;
- `data/reports/` committed plus regenerated reports;
- `data/assistant/index.json` or the ability to rebuild it.

The workflow does not download the 13.5 TB registered NASA archive. It uses the
curated 72-file scope only.

---

## 3. Why the split is necessary

A clean Git checkout does not contain:

- raw NASA files (`data/raw/`, gitignored);
- interim parses (`data/interim/`, gitignored);
- canonical Parquet (`data/processed/`, gitignored);
- the generated retrieval index (`data/assistant/`, gitignored).

Running the full suite in a data-free job would either fail or require silently
substituting synthetic data. Both are unacceptable. The default workflow runs
only checks that are valid in a data-free environment; the full-data workflow
makes the stronger claim explicitly.

Tests that were incorrectly classified were corrected in Milestone A. The
data-free gate now passes from a clean worktree.

---

## 4. Local equivalents

```bash
# Data-free backend gate.
.venv/bin/python -m pytest -m "not integration" -q
PYTHON=.venv/bin/python bash scripts/verify_reproducibility.sh

# Full backend gate.
.venv/bin/python -m pytest -q
PYTHON=.venv/bin/python bash scripts/verify_reproducibility.sh --with-data

# Frontend.
cd frontend
npm ci
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

---

## 5. Release gates

A release must fail if:

1. a backend unit, contract, or integration test fails;
2. an API contract test fails;
3. citation validation regresses;
4. numerical or unit consistency regresses;
5. a scientific registry drifts unexpectedly;
6. the retrieval index is stale without an approved rebuild;
7. the frontend production build fails;
8. lint or type checking fails;
9. a known production dependency vulnerability is reported;
10. Playwright, accessibility, or canonical validation fails in the full-data
    job.

---

## 6. Caching and secret handling

- Python dependencies use the `actions/setup-python` pip cache.
- Frontend dependencies use the `actions/setup-node` npm cache keyed by
  `frontend/package-lock.json`.
- CI uses `permissions: contents: read`.
- Provider credentials are never required for the default workflow.
- The full-data workflow does not print environment values.
- No secret is written to a report, log, or workflow artifact.
- Live-model evaluation is not part of hosted CI. It requires a separate runner
  with explicit credentials and is reported separately.

---

## 7. Known CI limitations

- Hosted CI cannot run the canonical-data integration suite or Playwright.
- The full-data workflow requires a self-hosted runner label and is not
  exercised by GitHub-hosted runners.
- A live provider is not tested in CI. The deterministic and mock-provider
  checks are software checks, not a model benchmark.
- Docker image building is not in the default workflow because the local
  Docker daemon was unavailable. A Docker-capable runner should add a build job
  before production release.
