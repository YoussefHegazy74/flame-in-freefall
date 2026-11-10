# Final Release Checklist — Flame in Freefall

**Release:** Phase 7 final release
**Starting SHA:** `be777e7ae8ce01af7630ff145231b08ab6ac1f15`
**Release date:** 2026-11-11
**Result:** Release-ready for demonstration, with external-environment items explicitly pending.

---

## 1. Repository and release

- [x] Branch is `main`.
- [x] Starting SHA verified as `be777e7`.
- [x] Working tree reviewed before changes.
- [x] Phase 1–6 implementation preserved.
- [x] No raw NASA files committed.
- [x] No secrets committed.
- [x] No virtual environments or `node_modules` committed.
- [x] Meaningful milestone commits used.
- [ ] Final local/remote SHA verification and clean tree recorded after push.
- [ ] Docker image build and scan on a Docker-capable host.
- [ ] Hosted staging deployment.
- [ ] Live-provider evaluation with real credentials.

## 2. Science and data

- [x] Canonical dataset version verified: `2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb`.
- [x] 13 canonical tables, 8,058,206 rows.
- [x] Acquisition validation: 72/72 verified, 0 failed.
- [x] Canonical validation: 13 checks, 0 failed.
- [x] Phase 2 registries match: 93 measurements, 60 rules, 9 datasets, 93 states.
- [x] Retrieval index is current and reproducible.
- [x] Missing values are not treated as zero.
- [x] PSI-10 atm and PSI-159 bar are kept separate.
- [x] PSI-98 unavailable workbooks remain unavailable and non-downloadable.
- [x] Paired values remain withheld with `no_verified_alignment`.
- [x] No BASS/BASS-II flame-spread rate is claimed.
- [x] No fire-risk score, material ranking, causal conclusion, or spacecraft
      fire-safety guarantee is produced.
- [x] Safety-ranking questions now use the refusal path.
- [x] Scientific integrity audit completed.

## 3. Assistant

- [x] 36 / 36 golden questions pass.
- [x] 117 / 117 citation references valid.
- [x] 59 / 59 supported claims link to a current tool call.
- [x] 30 / 30 numerical exact-match checks.
- [x] 30 / 30 unit-consistency checks.
- [x] 35 / 35 tool-selection checks.
- [x] 12 / 12 correct refusals.
- [x] Deterministic fallback verified.
- [x] Prompt-injection and adversarial tests pass.
- [x] Retrieval precision@5 `0.602381`, recall@5 `1.0`, MRR `1.0`.
- [x] Real-model evaluation remains pending; no result fabricated.

## 4. Backend

- [x] Backend unit and integration suite: **496 passed, 1 warning**.
- [x] API contract tests pass.
- [x] Readiness and metrics endpoints covered.
- [x] Security headers and request-size limit covered.
- [x] Provider retry, timeout, usage, and cost tests pass.
- [x] No known Python dependency vulnerabilities (`pip-audit`).
- [ ] Image-level vulnerability scan pending.

## 5. Frontend

- [x] 68 unit/component tests pass.
- [x] TypeScript passes.
- [x] ESLint passes.
- [x] Production build passes with `/assistant`.
- [x] 27 Playwright tests pass.
- [x] 7 axe scans pass.
- [x] Full `npm audit` reports 0 vulnerabilities.
- [x] Vitest `4.1.12`; tested `minimatch@11.0.1` override.
- [x] No `npm audit fix --force` used.
- [x] Mobile viewport covered by Playwright.
- [x] Assistant fallback and citation drawer covered.

## 6. Deployment and recovery

- [x] Backend and frontend Dockerfiles implemented.
- [x] Compose topology implemented.
- [x] Non-root container users defined.
- [x] Read-only canonical data and index mounts.
- [x] No raw NASA files in images.
- [x] Provider credentials server-side only.
- [x] Readiness checks dataset and index.
- [x] Structured logs and metrics documented.
- [x] Backup and recovery procedure documented.
- [x] Isolated restore drill passed; original data untouched.
- [x] Restore pipeline duration recorded: 310 s.
- [x] `FLAME_REGISTRY_DIR` metadata path corrected.
- [ ] Docker image build, scan, and Compose smoke test.
- [ ] Hosted staging HTTPS/CORS/readiness verification.

## 7. UX review

Reviewed the landing page, dashboard, investigation navigation, dataset detail,
gas-flame explorer, telemetry, comparison studio, provenance, publications,
quality, assistant, error states, mobile layout, and accessibility.

Findings:

- The purpose and scientific limits are stated on the landing and about pages.
- Missing values are visually distinct from zero.
- Units and source accessions are visible on scientific views.
- Comparison withholding and paired-value absence are explicit.
- Citation and provenance drawers are reachable and keyboard accessible.
- Assistant evidence, validation, provider, and fallback states are visible.
- Error and empty states explain what is missing.
- No unsupported promise or risk score was found.

No UI redesign was justified. The only product-behavior fix was the
safety-ranking refusal.

## 8. Competition package

- [x] `docs/competition-technical-overview.md`
- [x] `docs/competition-demo-script.md`
- [x] `docs/competition-demo-checklist.md`
- [x] `docs/competition-faq.md`
- [x] `docs/scientific-integrity-audit.md`
- [x] `docs/phase7-restore-drill.md`
- [x] `docs/final-release-checklist.md`
- [x] README and roadmap updated.
- [x] Deterministic-only fallback demo plan documented.
- [x] No staged answer is presented as a real measurement.

## 9. Release decision

**Recommendation:** proceed with the live demonstration using the deterministic
assistant and local production build. Do not claim Docker image verification,
hosted staging, or live-model evaluation until those external-environment checks
are actually completed.
