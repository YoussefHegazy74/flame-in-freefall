# Phase 6 — Security Review

**Project:** Flame in Freefall
**Status date:** 2026-11-10
**Scope:** public API, frontend, assistant provider boundary, dependencies, deployment

This review records what was checked, what changed, what remains, and what was
not verified. It does not turn the public read-only API into an authenticated
application, and it does not weaken any Phase 1–5 scientific safeguard.

---

## 1. Method

1. Reviewed CORS, proxy trust, rate limiting, request limits, input validation,
   error handling, headers, secret handling, frontend environment variables,
   assistant tools, and prompt-injection defenses.
2. Ran the existing Phase 1–5 security and adversarial tests.
3. Added Phase 6 tests for readiness, metrics, security headers, and oversized
   requests.
4. Audited pinned Python and frontend dependencies.
5. Reviewed production Docker and Compose configuration.

---

## 2. Findings and changes

| Area | Finding | Treatment |
|---|---|---|
| CORS | Browser origins were already environment-driven | Kept `FLAME_CORS_ORIGINS`; no wildcard default |
| Trusted proxy | `X-Forwarded-For` was already ignored unless trusted | Kept `FLAME_TRUST_PROXY=false` default; documented reverse-proxy requirement |
| Rate limiting | Fixed-window, process-local | Kept; added metrics for 429 events; documented multi-replica limitation |
| Request size | No explicit body limit before Phase 6 | Added `FLAME_MAX_REQUEST_BYTES` (default 1 MiB) based on `Content-Length`; returns `413 request_too_large` |
| Security headers | Backend and frontend lacked a consistent set | Added `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy` to API and Next.js responses |
| Error handling | Safe envelopes already avoided stack traces and secrets | Kept; added tests for new error paths |
| Secrets | Provider key was server-only and hidden from repr/status | Kept; provider retry logs exclude prompts, keys, and headers |
| Frontend env | Only `NEXT_PUBLIC_*` values are exposed | Kept; documented that provider credentials must never use `NEXT_PUBLIC_*` |
| Assistant tools | Closed allowlist already existed | Kept; no SQL, path, URL, shell, or code-execution tool added |
| Prompt injection | Retrieved text was already untrusted evidence | Kept; no provider access to retrieved instructions |
| Dependencies | Python and frontend dependencies were untested in CI | Added `pip-audit` and full `npm audit` CI steps; Phase 7 removed the remaining dev-only findings with a tested Vitest upgrade and `minimatch` override |
| Authentication | Public read-only experience needs no account | No authentication added; rate limiting is not authorization |
| Docker | Root user by default in a naive image | Added non-root users, `init`, health checks, and `no-new-privileges` |

---

## 3. Dependency audit results

Run on 2026-11-10:

```bash
.venv/bin/python -m pip_audit -r requirements.txt
# No known vulnerabilities found

cd frontend
npm audit --audit-level=high
# found 0 vulnerabilities
```

Phase 7 upgraded Vitest from `3.2.7` to `4.1.12` after verifying the test suite,
lint, typecheck, and production build. This removed the critical Tinypool and
Vitest mocker advisories. A tested `minimatch@11.0.1` override cleared the
remaining transitive lint-tool advisories. The full audit now reports zero
vulnerabilities. No `npm audit fix --force` was used.

---

## 4. Assistant-specific review

- The planner selects from a closed set of 22 tools.
- No tool accepts SQL, a filesystem path, an arbitrary URL, a table name, or
  shell code.
- Tool arguments are validated by Pydantic models with `extra="forbid"`.
- Retrieved documents are labeled untrusted evidence and cannot become
  instructions.
- The optional provider sees the user question and the validated deterministic
  draft, not retrieved source text as instructions.
- Provider output is revalidated for numbers, citations, accessions, dataset
  IDs, URLs, secrets, control characters, unsafe expansion, self-reference, and
  causal/ranking/fire-risk assertions.
- A provider failure or rejected rephrase falls back to the deterministic draft.
- Token usage and cost metadata contain no prompt or answer text.
- Every citation still resolves through the Phase 4 citation registry.

No Phase 5 trust boundary was weakened.

---

## 5. Deployment review

- Backend and frontend containers run as non-root users.
- Compose uses `init: true` and `no-new-privileges:true`.
- Canonical data and the retrieval index are mounted read-only.
- Raw NASA files are excluded from images.
- The backend health check uses `/api/v1/ready`.
- Frontend provider credentials do not exist; only public build-time values are
  exposed.
- Logs are bounded by the Compose `json-file` driver (`10m`, 3 files).

The Docker image build was **not** executed because the local Docker daemon was
inaccessible. This is a verification gap, not evidence that the image works.

---

## 6. Residual risks

1. **No authentication.** The API is public and read-only. Rate limiting is an
   abuse control, not authorization.
2. **Process-local rate limiting and metrics.** A multi-replica deployment needs
   a shared store before those controls are global.
3. **Request-size check is based on `Content-Length`.** A chunked request
   without that header is not bounded by the middleware. The JSON schemas and
   question-length limits provide an additional bound, but a robust edge proxy
   should enforce a body limit.
4. **Development dependency vulnerabilities.** The full npm audit is clean after
   the Phase 7 Vitest upgrade and tested minimatch override.
5. **No live provider test.** The provider boundary is tested with deterministic
   stubs and mock transports; a real credential and provider were unavailable.
6. **No external secret manager.** Deployment secrets are supplied through the
   environment or platform secret store. `.env` remains gitignored.
7. **No container scan.** The image could not be built locally, so an image
   scanner result is not available.

---

## 7. Security release checklist

- [x] No secrets in Git, logs, status, health, or metrics.
- [x] CORS is environment-driven with no wildcard default.
- [x] Proxy trust is opt-in.
- [x] Rate limiting is enabled by default and configurable.
- [x] Request body limit is configurable.
- [x] Security headers are applied by the API and frontend.
- [x] Error envelopes are safe and include request IDs.
- [x] Assistant tools remain allowlisted.
- [x] Citation and claim validation remain mandatory.
- [x] Python runtime dependencies have no known vulnerabilities.
- [x] Frontend dependencies have no known vulnerabilities.
- [x] Full development dependency audit is clean.
- [ ] Docker image build and scan on a Docker-capable host.
- [ ] Live-provider security review with real credentials.
