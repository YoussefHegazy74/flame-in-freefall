# Phase 6 — Production Deployment

**Project:** Flame in Freefall
**Team:** AFAQ
**Status date:** 2026-11-10
**Scope:** FastAPI backend, Next.js frontend, canonical data, retrieval index, optional provider

This document describes the implemented deployment configuration and the
verified local production startup. It distinguishes what was actually tested
from what is provided for a Docker-capable host.

---

## 1. Deployment shape

```text
Browser
  |
  v
Next.js frontend (port 3000)
  |  NEXT_PUBLIC_API_BASE_URL is baked at build time
  v
FastAPI backend (port 8000)
  |-- committed registries, metadata, reports, fixtures (image)
  |-- read-only canonical Parquet mount: /app/data/processed
  |-- read-only retrieval index mount: /app/data/assistant
  |-- optional external OpenAI-compatible provider
```

The frontend and backend are independently deployable. The backend is
stateless apart from process-local rate-limit counters, metrics, and bounded
conversation memory. No user question or answer is written to disk.

Raw NASA files under `data/raw/` are **not** copied into either image. The
canonical Parquet tables and the retrieval index are mounted read-only.

---

## 2. Prerequisites

The API needs the gitignored canonical dataset:

```bash
data/processed/*.parquet
data/processed/dataset_manifest.json
```

The assistant index is optional at process start. If it is mounted, the backend
validates it against current source hashes. If it is absent, the backend
rebuilds it in memory from committed documentation and metadata; retrieval
answers fail closed if that rebuild is impossible.

Build or validate both artifacts before starting production:

```bash
.venv/bin/python scripts/build_assistant_index.py
.venv/bin/python scripts/build_assistant_index.py --check
.venv/bin/python -m src.data_pipeline validate
```

Committed registries, reports, fixtures, and documentation are baked into the
backend image. They are not mounted from the host.

---

## 3. Native production startup

### Backend

```bash
cd /path/to/flame-in-freefall
.venv/bin/python -m uvicorn backend.app:app \
  --host 0.0.0.0 \
  --port 8000
```

For production, place it behind a reverse proxy that terminates TLS and forwards
to port 8000. Set `FLAME_TRUST_PROXY=true` only when that proxy is trusted and
overwrites `X-Forwarded-For`.

### Frontend

```bash
cd frontend
npm ci
NEXT_PUBLIC_API_BASE_URL=https://api.example.org/api/v1 \
NEXT_PUBLIC_SITE_URL=https://example.org \
npm run build
npm start
```

`npm start` uses the Next.js production server. The Docker image uses the
standalone output (`output: "standalone"`), which was also verified locally by
running `node .next/standalone/server.js` after copying `.next/static` into the
standalone directory.

### Verified local startup

On 2026-11-10, the following were verified on the local host:

- `uvicorn backend.app:app` started successfully;
- `/api/v1/ready` returned HTTP 200 with `dataset.ready=true` and the verified
  index version;
- the standalone frontend server returned HTTP 200 for `/` and `/assistant`;
- production responses carried the security headers and the API envelope.

The Docker image build itself could not be executed in this environment because
the Docker daemon at `/var/run/docker.sock` was not accessible. The Dockerfiles
and Compose file are provided, but their build must be verified on a
Docker-capable host before claiming an image-level deployment test.

---

## 4. Docker and Compose

Files:

| File | Purpose |
|---|---|
| `Dockerfile` | Multi-layer Python 3.12 runtime for FastAPI |
| `frontend/Dockerfile` | Multi-stage Node 22 build and Next.js standalone runtime |
| `docker-compose.yml` | Backend + frontend local production topology |
| `.dockerignore`, `frontend/.dockerignore` | Keep Git, raw data, virtual environments, and build caches out of images |

Start:

```bash
docker compose up --build -d
docker compose ps
curl http://127.0.0.1:8000/api/v1/ready
```

Stop:

```bash
docker compose down
```

The backend container runs as a non-root user, uses `init: true`, and declares a
health check against `/api/v1/ready`. The frontend container runs as a non-root
user and checks `/` with Node's built-in `fetch`.

Compose mounts:

```yaml
volumes:
  - "./data/processed:/app/data/processed:ro"
  - "./data/assistant:/app/data/assistant:ro"
```

If `data/assistant` is absent, Docker creates an empty directory. The backend
can still rebuild the index in memory. `/ready` will report the index state.

---

## 5. Environment configuration

The complete template is `.env.example`. Deployment-relevant variables:

| Variable | Default | Purpose |
|---|---|---|
| `FLAME_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated browser origins |
| `FLAME_TRUST_PROXY` | `false` | Trust `X-Forwarded-For` from a known proxy |
| `FLAME_RATE_LIMIT_ENABLED` | `true` | Enable process-local fixed-window limits |
| `FLAME_RATE_LIMIT_REQUESTS` | `600` | Requests per window per client |
| `FLAME_RATE_LIMIT_WINDOW_SECONDS` | `60` | Window length |
| `FLAME_MAX_REQUEST_BYTES` | `1048576` | Declared request-body limit |
| `FLAME_METRICS_ENABLED` | `true` | Expose aggregate operational counters |
| `FLAME_READINESS_REQUIRE_FULL_DATASET` | `true` | Require every canonical table |
| `FLAME_READINESS_REQUIRE_ASSISTANT_INDEX` | `true` | Require a usable retrieval index |
| `FLAME_ASSISTANT_ENABLED` | `true` | Enable grounded assistant queries |
| `FLAME_RETRIEVAL_ENABLED` | `true` | Enable verified retrieval |
| `FLAME_LLM_PROVIDER` | `deterministic` | `deterministic` or `openai_compatible` |
| `FLAME_LLM_BASE_URL` | unset | Provider base URL, server-side only |
| `FLAME_LLM_MODEL` | unset | Provider model |
| `FLAME_LLM_API_KEY` | unset | Provider key, never exposed to the browser |
| `FLAME_LLM_MAX_RETRIES` | `2` | Bounded retry count |
| `FLAME_LLM_RETRY_BACKOFF_SECONDS` | `0.5` | Initial exponential backoff |
| `FLAME_LLM_INPUT_COST_PER_MILLION` | unset | Optional input-token pricing |
| `FLAME_LLM_OUTPUT_COST_PER_MILLION` | unset | Optional output-token pricing |

`NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_SITE_URL` are public and baked into
the browser bundle. Never put a secret in a `NEXT_PUBLIC_*` variable.

### Provider configuration

The default is deterministic and needs no credentials. A provider failure falls
back to the validated deterministic answer and reports the fallback reason.
Invalid optional provider configuration degrades to deterministic mode without
stopping the API.

---

## 6. Health and readiness

| Endpoint | Meaning |
|---|---|
| `GET /api/v1/health` | Liveness and dataset/assistant summary. Always returns an envelope. |
| `GET /api/v1/ready` | Deployment readiness. HTTP 200 only when required checks pass; HTTP 503 otherwise. |
| `GET /api/v1/metrics` | Aggregate request, latency, rate-limit, assistant, tool, and token counters. |

Readiness checks:

- canonical dataset database state is `ok` when full-dataset readiness is
  required;
- dataset version is present;
- a usable retrieval index is available when assistant retrieval is enabled and
  the index gate is required.

The response includes `checks.dataset` and `checks.assistant` so an operator can
see which gate failed without reading logs.

---

## 7. Persistent storage and backups

| Artifact | In Git | Backup needed | Rebuild command |
|---|---|---|---|
| Canonical Parquet tables | No | Yes, or rebuild from raw | `python -m src.data_pipeline build-canonical` |
| Dataset manifest | No | Yes, or rebuild | `python -m src.data_pipeline build-canonical` |
| Raw NASA files | No | Optional; re-downloadable | `python -m src.data_pipeline download --all` |
| Retrieval index | No | No; reproducible | `python scripts/build_assistant_index.py` |
| Committed registries | Yes | Git history | `scripts/build_phase2_registries.py` |
| Committed reports | Yes | Git history | `python -m src.data_pipeline report` |
| Provider credentials | No | Secret manager | Never in Git |
| `.env` | No | Secure secret store | Never in Git |

Recommended backup set: canonical Parquet, `dataset_manifest.json`, raw files if
retention is practical, and the deployment environment/secret configuration.
The retrieval index can always be regenerated from Git plus canonical metadata.

Recovery order:

1. Restore or rebuild raw data.
2. Rebuild canonical tables and validate.
3. Start the backend.
4. Rebuild or mount the retrieval index.
5. Verify `/api/v1/ready`.
6. Verify citations and the deterministic assistant evaluation.
7. Point the frontend at the backend and run a smoke test.

---

## 8. Restart and scaling behavior

- The API process is stateless for scientific data. Restarts do not change
  canonical values or citations.
- Rate-limit windows and metrics reset on restart. They are process-local.
- The retrieval index is loaded lazily and cached in memory. A missing or stale
  artifact triggers a validated rebuild when the source files are available.
- Conversation memory is bounded and non-authoritative; it is never evidence.
- Multiple backend replicas require a shared rate-limit store and a shared
  metrics backend before rate limits and counters can be treated as global.
  The current deployment is intentionally a single process.
- The frontend can be deployed independently as long as
  `NEXT_PUBLIC_API_BASE_URL` points at the backend and CORS allows its origin.

---

## 9. Deployment limitations

1. The Docker image build was not executed because the local Docker daemon was
   inaccessible. Native production startup was verified instead.
2. Docker Compose is the reference topology, not a Kubernetes deployment. The
   workload does not justify Kubernetes.
3. No authentication is provided for the public read-only API. If private
   administrative operations are added, they need a separate authenticated
   surface.
4. There is no shared rate-limit or metrics store for multi-replica deployment.
5. A real language-model deployment is optional and currently unverified
   against a live provider.
