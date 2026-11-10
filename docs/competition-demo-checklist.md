# Competition Demo Checklist

**Project:** Flame in Freefall
**Use:** 30 minutes before the live demonstration

---

## 1. Environment

- [ ] Repository is at the release commit; working tree is clean.
- [ ] `.venv` exists with pinned backend dependencies.
- [ ] `frontend/node_modules` is installed from the locked dependency set.
- [ ] `data/processed/` contains the canonical Parquet tables and dataset manifest.
- [ ] `data/assistant/index.json` is current or can be rebuilt.
- [ ] Backend starts on port 8000.
- [ ] Frontend starts on port 3000.
- [ ] `NEXT_PUBLIC_API_BASE_URL` points to the running API.
- [ ] `FLAME_CORS_ORIGINS` includes the frontend origin.
- [ ] No secret is visible in the browser, terminal, or logs.
- [ ] No raw NASA file is served by the frontend or API.

## 2. Health checks

```bash
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8000/api/v1/ready
curl -fsS http://127.0.0.1:8000/api/v1/metrics
```

- [ ] `/health` returns `status: ok` (or degraded with a known reason).
- [ ] `/ready` returns HTTP 200 and `status: ready`.
- [ ] Assistant index version is reported.
- [ ] Metrics endpoint returns bounded counters, no question text.

## 3. Critical URLs

- [ ] `/`
- [ ] `/investigations`
- [ ] `/investigations/PSI-159`
- [ ] `/experiments/gas-flame?accession=PSI-10`
- [ ] `/datasets/psi-10-gas-flame`
- [ ] `/telemetry`
- [ ] `/provenance?accession=PSI-10&file=PSI-10_Experimental%20table_Flame%20Design_Normal%20Flame.csv&row=2`
- [ ] `/compare?left=psi-10-gas-flame.oxygen_mole_fraction&right=psi-159-gas-flame.oxygen_mole_fraction`
- [ ] `/assistant`

## 4. Assistant checks

- [ ] Deterministic provider is active; fallback state is visible if applicable.
- [ ] "How many valid PSI-10 gas-flame records are available?" returns 256 included, 71 excluded, 327 total, with citations.
- [ ] "What is the fire-risk score for Nomex?" returns `insufficient_evidence` and refuses.
- [ ] "Is PSI-159 safer than PSI-10?" returns the safety-ranking refusal.
- [ ] Pressure unit trap returns `unavailable_data` or a conditional decision without conversion.
- [ ] Citation drawer resolves a claimed citation.
- [ ] No answer presents retrieval text as a measurement.

## 5. Scientific checks

- [ ] PSI-10 atm and PSI-159 bar are visibly separate.
- [ ] Missing values render as a dash or "not available".
- [ ] PSI-98's two unavailable workbooks have no download link.
- [ ] Paired comparison chart is absent when `paired_values.available=false`.
- [ ] No fire-risk score, material ranking, or spacecraft guarantee is displayed.
- [ ] No BASS/BASS-II flame-spread rate is displayed.
- [ ] Computed fields are labeled computed; raw channels are labeled raw.

## 6. Accessibility and layout

- [ ] Keyboard-only navigation reaches the main routes.
- [ ] Focus rings are visible.
- [ ] Axe scans pass or the known issue is documented.
- [ ] Mobile viewport is readable.
- [ ] Charts have accessible descriptions and units.
- [ ] Color is not the only state indicator.

## 7. Fallback readiness

- [ ] API fallback commands are copied in the demo notes.
- [ ] A deterministic-only run works with no provider credentials.
- [ ] A provider failure displays the fallback banner rather than a fabricated answer.
- [ ] If canonical data are unavailable, the demo will state that clearly and use the restore/validation evidence instead.
- [ ] Screenshots are labeled as recorded fallback, not live output.

## 8. Final pre-flight

- [ ] Browser tabs open at `/`, `/assistant`, `/compare`, and `/telemetry`.
- [ ] Terminal font size is readable.
- [ ] Notifications and auto-updates are disabled.
- [ ] Network dependency is understood.
- [ ] No local path, token, or `.env` content is visible.
- [ ] The demo script and FAQ are open in a second window.
- [ ] The presenter can explain one limitation without reading from the screen.
