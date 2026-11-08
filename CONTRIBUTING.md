# Contributing

**Project:** Flame in Freefall
**Team:** AFAQ

This guide is for anyone changing the repository: team members, reviewers, and automated agents. The project handles scientific data, so the review bar is higher than a typical demo. A change that renders correctly but misstates a unit, hides missingness, or invents a comparison is not acceptable.

Read `AGENTS.md` first if you are an AI agent. It contains the same rules in a stricter form.

---

## 1. Before you start

1. Read `README.md` for scope and current status.
2. Read the relevant record card in `DATA_SOURCES.md`.
3. Read the field definitions in `DATA_DICTIONARY.md`.
4. Find the phase and gate in `DEVELOPMENT_ROADMAP.md`.
5. Check `docs/decisions/` for a decision that already covers the question.

If the task is not in the current phase, open an issue or discuss it before writing code. Scope creep into deferred datasets is a known risk.

---

## 2. Ways to contribute

| Contribution | Where |
|---|---|
| Fix a typo or clarify a limitation | Documentation |
| Add a source citation or verification step | `DATA_SOURCES.md`, `docs/research/source-verification-log.md` |
| Add a parser and fixtures | `scripts/`, `data/fixtures/`, tests |
| Add an API endpoint | `api/`, `API_DOCUMENTATION.md`, contract tests |
| Add a UI view | `web/`, accessibility and provenance tests |
| Improve the assistant evaluation | `insight/`, golden set |
| Report a data access problem | Issue with accession, file name, HTTP status, and date |
| Report a security issue | Private channel to the maintainers; do not open a public issue with secrets |

Do not add a dataset to the MVP without an update to `docs/decisions/0001-mvp-dataset-selection.md` and `data/registry/mvp_dataset_catalog.json`.

---

## 3. Development setup

### 3.1 Foundation tools

The metadata collector needs only Python 3.10 or newer and its standard library.

```bash
git clone https://github.com/YoussefHegazy74/flame-in-freefall.git
cd flame-in-freefall
python3 --version
python3 scripts/fetch_psi_metadata.py --check
```

### 3.2 Later phases

Parser and application dependencies will be pinned when those phases begin. Expected tools:

- Python 3.12
- `pytest`, `ruff`, `mypy`
- `polars`, `pyarrow`, `openpyxl`, `xlrd`
- FastAPI, Pydantic v2, SQLAlchemy 2, Alembic
- Node.js and pnpm for the Next.js frontend

Do not add a dependency without updating the lockfile and the relevant README.

### 3.3 Environment variables

Copy the example file and fill in local values:

```bash
cp .env.example .env
```

`.env` is gitignored. Never commit it. Never put a real credential in `.env.example`.

---

## 4. Branch and commit workflow

### 4.1 Branches

Use a short, descriptive branch name:

```text
docs/source-limitations
feat/psi-159-parser
fix/telemetry-time-range
data/regenerate-registry
```

Do not commit directly to `main` if a review is expected. For a solo foundation milestone, a direct commit is acceptable only after the checks pass.

### 4.2 Commits

Use Conventional Commits:

```text
<type>(<scope>): <summary>

<body: what changed, why, and what was verified>
```

Examples:

```text
docs(sources): record SAFFIRE-I telemetry 404 and fallback
data(registry): regenerate snapshot after sentinel annotation fix
feat(parser): add PSI-10 normal-flame parser with fixture tests
test(api): reject unbounded telemetry series requests
```

Keep commits focused. Do not mix a registry regeneration with an unrelated UI change. Never commit generated files and their source in separate commits if the generated file would be inconsistent in between.

### 4.3 Pull requests

A pull request should state:

1. the phase and roadmap item;
2. the source or issue it addresses;
3. what changed;
4. what was verified, with commands and output;
5. what is not covered;
6. any new limitation or open question.

Small pull requests are easier to review. A parser change and a frontend chart should be separate.

---

## 5. Data contribution rules

### 5.1 What may be committed

| Allowed | Not allowed |
|---|---|
| Metadata registry JSON/CSV | Raw NASA files |
| Curated annotations | Downloaded ZIP/MP4/PDF archives |
| Small fixtures with real headers and a few rows | Full telemetry CSV/XLSX |
| Checksums and retrieval timestamps | Credentials, tokens, presigned URLs |
| Documentation and code | `.env` or private keys |

A fixture must:

- use the exact source header, including spacing and unit text;
- contain 3–10 data rows;
- include the sentinel token it tests (`-`, `n/a`, `none`, `OR`, `RAMP`, `#DIV/0!`, `-999`, etc.);
- be small enough to review in a diff;
- record its provenance in the test file.

### 5.2 What must be verified

Before adding or changing a data claim:

1. Download the file from the public PSI endpoint.
2. Record the HTTP status and date.
3. Compute SHA-256.
4. Read the exact header.
5. Count physical and valid rows.
6. Identify missingness and sentinel tokens.
7. Record the unit or `not stated`.
8. Add the fact to `DATA_SOURCES.md` and `DATA_DICTIONARY.md`.
9. Add the table statistics to `data/registry/annotations.json`.
10. Regenerate the registry with `python3 scripts/fetch_psi_metadata.py`.
11. Regenerate the MVP catalog with `python3 scripts/build_mvp_catalog.py`.

**Experimental tables:** `added` and `experimentalTable` are separate lists. Count `file_count` only from `added`. Record an experimental table in `psi_experimental_tables.csv` with its `in_added` flag, row counts, column count, and SHA-256. A record with zero `added` files but a public experimental table is `experimental_table_only`, not `no_public_files`. A summary table is not raw telemetry; describe its limits in `DATA_DICTIONARY.md` before using it in a chart or answer.

Do not copy a number from a paper abstract into the registry without checking whether it describes the same table and the same version.

### 5.3 What must never be done

- Do not fill a blank with zero, a mean, or an interpolation.
- Do not convert a mole fraction to percent without an explicit, reversible conversion.
- Do not merge `atm`, `bar`, `psi`, `PSIA`, and `PSIG` on one axis.
- Do not concatenate PSI-100 exports.
- Do not treat `TFP` as a temperature.
- Do not derive a BASS/BASS-II spread rate without a validated computer-vision method.
- Do not create a risk score or material ranking.
- Do not add a team member name, role, or competition detail that is not verified.
- Do not add the `added` count and the experimental-table count into a single "file count" without subtracting overlap.
- Do not present an experimental summary table as raw telemetry or as a per-test measurement table when it is a test-day/sample/condition summary.
- Do not claim NASA endorsement.

---

## 6. Code style

### 6.1 Python

- Python 3.12 for application code; the collector remains standard-library compatible.
- Type hints on public functions.
- `ruff` for lint and format; `mypy` for types.
- Small modules with explicit names.
- No bare `except:`; catch specific exceptions.
- No silent fallbacks that hide a schema or checksum failure.
- Log structured context, not raw rows or secrets.

### 6.2 TypeScript

- Strict TypeScript.
- No `any` without a comment explaining why.
- Components are small and accessible.
- Server state goes through the API client; no ad hoc `fetch` in components.
- No scientific aggregation in the frontend beyond display formatting.

### 6.3 Documentation

- Use short paragraphs and tables.
- State the source and the verification date.
- Separate verified facts from open questions.
- Keep numbers consistent with the registry.
- Use decimal GB and say so.

---

## 7. Testing

### 7.1 Required by change type

| Change | Tests |
|---|---|
| Collector or registry | `--check`; JSON parse; inventory row count equals sum of `file_count`; total bytes equals sum of `registered_total_bytes` |
| Parser | Fixture with exact header; normal row; missing row; sentinel row; malformed header raises |
| Canonical table | Row count, checksum, time monotonicity, range, unit, and missingness assertions |
| API | Contract tests for success, empty, invalid, blocked, rate-limited |
| Chart | Axis unit, provenance, missingness, no dual axis |
| Assistant | Golden question with expected citation and evidence status |
| Docs | Numbers match the registry; links resolve |

### 7.2 Commands

```bash
# Metadata
python3 scripts/fetch_psi_metadata.py --check

# Python tests (once dependencies exist)
python3 -m pytest
python3 -m ruff check .
python3 -m mypy .

# Frontend (once it exists)
pnpm lint
pnpm typecheck
pnpm test
pnpm test:e2e
```

Paste the relevant output in the pull request. Do not claim a test passed if it was not run.

---

## 8. Review checklist

A reviewer should confirm:

- [ ] The change is in the current roadmap phase.
- [ ] Every new number has a source and a verification date.
- [ ] Every new field has a raw name, canonical name, type, and unit or `not stated`.
- [ ] Missingness and sentinel tokens are preserved and flagged.
- [ ] Computed values are labeled computed.
- [ ] Cross-dataset comparisons are in the comparability matrix.
- [ ] No risk score, ranking, or unsupported causation was added.
- [ ] No raw data, secret, or large binary was committed.
- [ ] Tests cover normal, missing, sentinel, and malformed cases.
- [ ] API responses include provenance and quality flags.
- [ ] Charts label axes, units, source, and limitations.
- [ ] The UI handles empty, blocked, `experimental_table_only`, `no_public_files`, and error states.
- [ ] Accessibility checks pass for the affected flow.
- [ ] Documentation and registry agree.
- [ ] The commit message explains what and why.

A reviewer may block a change that is technically correct but scientifically misleading.

---

## 9. Reporting data problems

Open an issue with:

- accession (`PSI-159`);
- exact file name;
- HTTP status and date;
- what changed (404, new version, different row count, different header, checksum mismatch);
- the command used;
- the expected and actual result.

Do not attach the raw file. Attach a small excerpt only if it is public and necessary.

If the problem affects a committed number, update the documentation and regenerate the registry in the same pull request.

---

## 10. Security

- Do not open a public issue for a credential leak. Contact the maintainers privately.
- Do not include secrets in logs, screenshots, or test fixtures.
- Do not add an endpoint that accepts arbitrary SQL, file paths, or URLs.
- Do not execute code or shell commands from dataset comments.
- Do not disable TLS verification or bypass access controls.
- Report a dependency vulnerability through the repository's private security channel.

---

## 11. Attribution and conduct

- Attribute NASA PSI and the originating investigators in any public output.
- Do not imply that NASA or the originating investigators endorse this project.
- Be precise when disagreeing about data. Cite the file and row.
- Do not publish a team member's name or role without consent.
- Keep discussion focused on the work.

No code of conduct policy has been formally adopted yet. Until it is, follow the standards above and raise concerns with the maintainers.

---

## 12. License

No license has been selected. By contributing, you agree that your contribution may be distributed under the license Team AFAQ chooses. Do not add a license file without a team decision.
