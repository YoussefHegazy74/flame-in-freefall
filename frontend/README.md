# FLAREX — Frontend

Scientific data exploration interface for **FLAREX — Microgravity Combustion
Intelligence**. It is a read-only Next.js application over the Phase 5–6 FastAPI
service and the canonical NASA PSI data. It renders backend decisions; it does not reimplement
comparability, serving-state, calibration, or quality logic. Phase 6 adds a
standalone production build, container configuration, security headers, and
provider-usage transparency.

---

## Stack

| Layer | Choice | Version |
|---|---|---|
| Framework | Next.js App Router | 16.4.5 |
| UI | React | 19.3.1 |
| Language | TypeScript | 5.9.3 |
| Styling | Tailwind CSS | 4.3.5 |
| Server state | TanStack Query | 5.107.1 |
| Charts | Recharts | 3.10.1 |
| Icons | Lucide React | 1.70.0 |
| Unit/component tests | Vitest + React Testing Library | 4.1.12 |
| End-to-end tests | Playwright + axe-core | 1.65.0 / 4.14.0 |

All versions are pinned in `package.json`. `npm run dev` and `npm run build`
use the webpack builder explicitly.

## Brand

**FLAREX** is the product name. The official tagline is **Microgravity
Combustion Intelligence**. The custom orbit-and-flame mark is implemented in
`src/components/brand/flarex-mark.tsx`; public logo assets are in
`public/flarex-mark.svg` and `public/flarex-logo.svg`. The repository slug and
internal package identifiers remain `flame-in-freefall` for continuity and are
not user-facing.

## Design system

The visual system is documented in [`DESIGN_GUIDELINES.md`](DESIGN_GUIDELINES.md).
It defines the light/dark palette, semantic tokens, gradients, typography,
spacing, glass header behavior, reusable components, and accessibility rules.
New UI work should use the semantic tokens and primitives described there.

---

## Quick start

The backend and frontend run independently. From the repository root:

```bash
# Terminal 1 — backend
.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000

# Terminal 2 — frontend
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

| Service | URL |
|---|---|
| Frontend | <http://localhost:3000> |
| Backend API | <http://127.0.0.1:8000/api/v1> |
| Readiness | <http://127.0.0.1:8000/api/v1/ready> |
| Metrics | <http://127.0.0.1:8000/api/v1/metrics> |
| Swagger UI | <http://127.0.0.1:8000/api/v1/docs> |

The backend must include the frontend origin in `FLAME_CORS_ORIGINS`. The
default configuration allows `http://localhost:3000`.

### Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Yes | FastAPI base path, e.g. `http://localhost:8000/api/v1` |
| `NEXT_PUBLIC_SITE_URL` | No | Public site URL used in documentation links |

Only public values belong in `NEXT_PUBLIC_*` variables. The app sends no
credentials, cookies, or secrets. `.env.local` is gitignored.

---

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Development server on port 3000 |
| `npm run build` | Production webpack build |
| `npm start` | Serve the production build |
| `npm run lint` | ESLint |
| `npm run typecheck` | TypeScript without emit |
| `npm test` | Vitest unit and component suite |
| `npm run test:e2e` | Playwright against a real backend and frontend |

`npm run test:e2e` starts both servers automatically unless they are already
running. Set `PLAYWRIGHT_BASE_URL` to target a different frontend origin.

### Production build

```bash
npm ci
NEXT_PUBLIC_API_BASE_URL=https://api.example.org/api/v1 \
NEXT_PUBLIC_SITE_URL=https://example.org \
npm run build
npm start
```

The Docker image uses Next.js standalone output. `frontend/Dockerfile` creates a
non-root runtime and copies `.next/standalone` and `.next/static`. The public API
URL is a build-time value; it must not contain a secret.

---

## Routes

| Route | Purpose |
|---|---|
| `/` | Overview: live registry counts, serving-state distribution, quality summary, limitations |
| `/investigations` | Searchable, filterable, paginated investigation catalog |
| `/investigations/[accession]` | Investigation detail with datasets, measurements, warnings, and source references |
| `/datasets` | Curated dataset catalog with role, access, serving state, and quality |
| `/datasets/[datasetId]` | Dataset detail: measurements, files, field dictionary, limitations, publications, provenance |
| `/experiments/gas-flame` | PSI-10 / PSI-159 test explorer with dynamic facets and accession-bound filters |
| `/experiments/materials` | PSI-25 / PSI-26 material matrices with oxygen-ambiguity warning |
| `/experiments/droplets` | PSI-69 droplet summary with labeled burning-rate unit |
| `/telemetry` | PSI-100 SAFFIRE-III run and bounded time-series explorer |
| `/smoke` | PSI-101 SAME-R run and bounded time-series explorer |
| `/compare` | Backend-authoritative comparison studio with integrity and paired-value eligibility |
| `/quality` | Registry-wide and per-dataset quality, serving, and limitation center |
| `/provenance` | Exact source-file and row resolution with citation drawers |
| `/publications` | Verified publication list with accession and dataset filters |
| `/publications/[publicationId]` | Publication detail with source references and field status |
| `/about` | Methods, data processing, comparability, quality, and limitations |
| `/assistant` | Grounded research assistant with conversation, suggested questions, evidence panel, citation drawer, and provider/fallback status |

Filters that matter to reproducibility are synchronized to the URL. Browser
back/forward navigation restores them.

---

## Architecture

```text
src/
├── app/                 App Router pages, layout, loading/error/not-found
├── components/
│   ├── layout/          Sidebar, topbar, breadcrumbs, shell, footer
│   ├── scientific/      Domain components: badges, warnings, citations, files, fields, publications
│   ├── assistant/       Conversation, evidence panel, citation drawer, suggestions, status
│   ├── charts/          Lazy-loaded Recharts time-series and paired-scatter panels
│   └── ui/              Buttons, cards, filters, pagination, states, disclosure
└── lib/
    ├── api/             Client, endpoint functions, query keys, TanStack hooks, types
    ├── assistant.ts     Assistant labels, evidence tones, exact value serialization
    ├── format.ts        Number, unit, date, and missing-value formatting
    ├── series.ts        Chart-row and unit-group helpers
    ├── labels.ts        Human-readable domain labels
    ├── navigation.ts    Sidebar and breadcrumb metadata
    └── use-url-state.ts URL-synced filter state
```

- **One API client.** `src/lib/api/client.ts` owns the base URL, timeout,
  cancellation, query serialization, error normalization, and envelope
  handling. Components never call `fetch` directly.
- **Typed contracts.** `src/lib/api/types.ts` models the actual response
  envelopes (`data`, `meta`, `quality`, `provenance`) and domain records. The
  OpenAPI schema is generic, so domain types are maintained against observed
  responses.
- **TanStack Query.** `hooks.ts` provides cached, cancellable queries keyed by
  endpoint and parameters. Error objects retain HTTP status, API error code,
  request ID, and details.
- **URL state.** Filters use `use-url-state.ts`; URL parameters are the source
  of truth for shareable views.
- **Charts.** `lazy-time-series-chart.tsx` loads the time-series chart module on
  demand. `lazy-paired-scatter-chart.tsx` loads the paired chart only when the
  backend returns a complete verified contract. Recharts is used only for
  justified scientific panels.
- **Phase 4 panels.** Citation, file, field, limitation, publication, facet,
  comparison-integrity, and paired-value components live in
  `src/components/scientific/`; they render backend metadata and states rather
  than deriving them.
- **Assistant.** `src/components/assistant/` renders only validated backend
  answers: conversation, suggested questions, evidence and citation panels,
  supporting values, limitations, tool audit, validation status, and
  provider/fallback state. It never calls a model, resolves a citation, or
  computes a number. `src/lib/assistant.ts` owns labels and exact value
  serialization.

### API capabilities the frontend relies on

- `GET /meta`, `/investigations`, `/investigations/{accession}`
- `GET /datasets`, `/datasets/{dataset_id}`, `/datasets/quality`,
  `/datasets/{dataset_id}/quality`
- `GET /datasets/{dataset_id}/files`, `/fields`, `/limitations`
- `GET /measurements`, `/measurements/{measurement_id}`
- `GET /gas-flame/tests`, `/gas-flame/tests/{observation_id}`,
  `/gas-flame/facets`
- `GET /material/tests`, `/droplet/tests`
- `GET /telemetry/runs`, `/telemetry/runs/{run_id}`,
  `/telemetry/runs/{run_id}/series`
- `GET /smoke/runs`, `/smoke/runs/{run_id}`, `/smoke/runs/{run_id}/series`
- `GET /comparability`, `/compare`, `/provenance`
- `GET /citations`, `/citations/{citation_id}`
- `GET /publications`, `/publications/{publication_id}`
- `GET /assistant/status`, `/assistant/suggestions`, `/assistant/tools`
- `POST /assistant/query`

---

## Scientific safeguards

- Every value comes from the API. No measurement, citation, checksum, or
  dataset statistic is hardcoded.
- Missing values render as a dash or an explicit "not available" state. They
  are never replaced with zero.
- Raw and uncalibrated channels are visually distinguished from standard
  signals and labeled as such.
- Telemetry and smoke series preserve the backend time unit (`ms` or `s`) and
  run identity. Runs are never concatenated, downsampled, interpolated, or
  resampled in the browser.
- The series cap (20,000 points, 8 channels) is enforced by the backend. A
  `413 range_too_large` response is shown with its actual point count and the
  suggested maximum span; the client never retries silently.
- Pressure filters require an explicit accession because PSI-10 uses `atm` and
  PSI-159 uses `bar`. Oxygen filters require an explicit accession because
  PSI-25 and PSI-26 use different, partly ambiguous fields. Changing the
  accession clears incompatible filter values.
- Comparison status is whatever `/compare` returns. `comparable`,
  `conditionally_comparable`, `not_comparable`, `blocked`, and
  `insufficient_metadata` each render differently. Blocked comparisons render
  no chart.
- Comparison integrity checks are rendered from `data.integrity`; a registry
  field with no canonical values blocks a misleading comparison.
- Paired values render only when `paired_values.available`, `alignment.verified`,
  and numeric points all pass the client guard. When withheld, the panel shows
  `reason.code`, the required alignment keys, and exclusions. No series is
  derived from separate summaries.
- Conditions are sent as explicit `cond_<key>=true` URL state and a JSON
  `conditions` request parameter. The frontend never assumes a condition is
  satisfied.
- PSI-26 oxygen ambiguity, PSI-69 `Burning rate; mm`, uncalibrated PSI-100
  channels, and SAME-R `-999` sentinels remain visible in the relevant pages.
- Charts include title, y unit, x time unit, source dataset, limitations, and
  an accessible text description.
- Citation IDs are resolved through `/citations/{citation_id}`; the client does
  not parse or construct them. Unavailable files never render a download link.
- Field integrity statuses (`available`, `missing`, `not_checked`,
  `no_canonical_tables`) are shown explicitly. Missing registry fields are never
  rendered as zero.
- Publications show only source-provided fields. Missing year and venue display
  as "Not available in registry"; conflicting title and author variants are
  preserved.
- Gas-flame facets come from `/gas-flame/facets`, report excluded qualified rows,
  and keep PSI-10 atm and PSI-159 bar separate.
- Assistant answers render only the validated backend contract. Evidence status,
  answer type, claims, citations, supporting data, limitations, tools used, and
  validation results are displayed rather than inferred.
- Assistant numeric values use the backend's exact serialization. The UI does
  not round, convert, or reformat a scientific value for display.
- Documentary evidence is labeled as context, not as a numerical source.
  Citation IDs resolve through `/citations/{citation_id}` and unavailable files
  never show a download link.
- The assistant shows whether the answer came from the deterministic provider or
  an optional provider, and whether a fallback occurred. A provider failure is
  not hidden.
- When the backend reports provider token usage or estimated cost, the answer
  card displays it as optional metadata. The browser never computes or invents
  token or cost values.
- Production responses set `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, and `Permissions-Policy`; `poweredByHeader` is disabled.

### Deliberate omissions

- No paired chart is drawn unless the backend returns a complete verified
  alignment contract. The current API withholds values.
- No aggregate, rate, risk score, or ranking is computed in the browser.
- No material safety claim is made.
- No full public-file inventory is exposed; the file browser uses the curated
  manifest plus documented known-unavailable files.
- No language model is called by the frontend. The assistant is deterministic by
  default, and the optional provider is server-side only.
- No assistant answer is repaired, completed, or reworded in the browser. An
  invalid or unavailable answer is displayed with its actual status.

---

## Testing

```bash
npm test                 # 68 unit/component tests
npm run test:e2e         # 27 Playwright flows, including 7 axe scans
npm run typecheck
npm run lint
npm run build
```

The Playwright suite runs against the real backend and real canonical data. It
covers dashboard metrics, investigation search and role filtering, dataset
serving states and Phase 4 metadata panels, accession-bound gas-flame filters
and dynamic facets, telemetry run identity and units, `413` guidance, smoke run
identity and sentinels, conditional and blocked comparisons, paired-value
withholding, citation drawers, publication list/detail, provenance resolution
and 404 handling, assistant suggested questions and grounded answers, evidence
and citation panels, provider/fallback status, mobile viewport behavior, and
serious/critical WCAG A/AA axe scans.

---

## Known backend gaps

These are documented, not worked around with fabricated data:

- No verified paired-comparison executor. `/compare` returns eligibility and a
  withholding reason; observations and series are empty.
- No real language-model evaluation has been run. The assistant works
  deterministically, and the optional provider is exercised only through
  server-side boundary checks.
- The assistant retrieval method is lexical (BM25 plus deterministic hashed
  TF-IDF, with source-aware ranking), not a neural embedding. Documentary
  evidence is not a numerical source.
- The Docker image build was not executed locally because the Docker daemon was
  inaccessible. Native standalone startup was verified.
- The frontend dependency audit is clean after the Phase 7 Vitest upgrade and a
  tested `minimatch` override. No `npm audit fix --force` was used.
- Rate limiting and metrics are process-local and have no shared store.
- The API is public and read-only with no authentication.
- `/material/tests` is the implemented route; the broader target contract names
  `/materials/tests`.
- Embedded OpenAPI request/response examples are not present; examples live in
  the documentation.

See `../docs/frontend-readiness.md`, `../docs/phase4-contracts.md`,
`../docs/comparison-alignment.md`, `../docs/phase5-assistant-architecture.md`,
`../docs/assistant-answer-contract.md`, `../docs/phase6-deployment.md`,
`../docs/phase6-operations.md`, and `../DEVELOPMENT_ROADMAP.md`.
