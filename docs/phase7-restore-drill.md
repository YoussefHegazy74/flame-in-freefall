# Restore Drill — Phase 7

**Project:** Flame in Freefall
**Drill date:** 2026-11-10
**Source dataset version:** `2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb`
**Isolation:** `/tmp/opencode/flame-restore-drill` (separate copy; original repository data untouched)
**Result:** Pass after correcting the metadata-registry environment path.

---

## 1. What was tested

The drill restored an isolated copy containing committed code, registry,
metadata, reports, fixtures, download manifests, and raw NASA files. It excluded
the canonical Parquet, interim parses, and generated retrieval index so those
had to be rebuilt.

The original `/mnt/data/flame-in-freefall/data` tree was not modified.

---

## 2. Exact commands

```bash
DRILL=/tmp/opencode/flame-restore-drill
rm -rf "$DRILL"
mkdir -p "$DRILL"
rsync -a \
  --exclude '.git' --exclude '.venv' --exclude '__pycache__' \
  --exclude '.pytest_cache' --exclude 'frontend/node_modules' \
  --exclude 'frontend/.next' --exclude 'frontend/test-results' \
  --exclude 'frontend/playwright-report' \
  --exclude 'data/processed' --exclude 'data/interim' \
  --exclude 'data/assistant' \
  /mnt/data/flame-in-freefall/ "$DRILL"/

cd "$DRILL"
/mnt/data/flame-in-freefall/.venv/bin/python -m src.data_pipeline parse
/mnt/data/flame-in-freefall/.venv/bin/python -m src.data_pipeline build-canonical
/mnt/data/flame-in-freefall/.venv/bin/python -m src.data_pipeline validate
/mnt/data/flame-in-freefall/.venv/bin/python -m src.data_pipeline report
/mnt/data/flame-in-freefall/.venv/bin/python scripts/build_phase2_registries.py --check
/mnt/data/flame-in-freefall/.venv/bin/python scripts/build_assistant_index.py
```

API startup:

```bash
cd "$DRILL"
FLAME_PROCESSED_DIR="$DRILL/data/processed" \
FLAME_REPORTS_DIR="$DRILL/data/reports" \
FLAME_REGISTRY_DIR="$DRILL/data/metadata" \
FLAME_RATE_LIMIT_REQUESTS=100000 \
FLAME_LOG_LEVEL=WARNING \
/mnt/data/flame-in-freefall/.venv/bin/python -m uvicorn backend.app:app \
  --host 127.0.0.1 --port 8010
```

---

## 3. Results

| Step | Result | Duration |
|---|---|---:|
| Copy isolated workspace | 71 MB copied, raw data present | not separately timed |
| Parse raw sources | 79 sources, interim outputs built | 292 s |
| Build canonical tables | 13 tables, 8,058,206 rows | 12 s |
| Validate | Acquisition pass 72/72; canonical 13/13 | 3 s |
| Regenerate reports | Validation pass; quality pass (13 tables, 6 issues) | 3 s |
| Total pipeline | Complete | **310 s** |
| Registry check | 93 measurements, 60 rules, 9 datasets, 93 states match | < 5 s |
| Retrieval index rebuild | 1,398 chunks, 944 documents, 18 sources | < 5 s |
| API readiness | HTTP 200 `ready` | startup + first index load |
| Citation resolution | `cit_f_21df4ec92db1eca0` verified/available | < 1 s |
| Assistant deterministic answer | `fully_supported`, 2 citations, validation passed | < 1 s |
| Assistant fallback with incomplete provider | deterministic, `fallback_mode=true`, validation passed | < 1 s |

Restored dataset version matched the source exactly:
`2a19f9f2e7dda7bb41d6d83c3c1a4b3b616c1d91849f7edb2e749f89708934cb`.

The rebuilt index version was `assistant-index-v1-d2ea8860c5da`, not the
repository index version. This is expected: the drill regenerated reports with
new timestamps, and the retrieval manifest hashes those report files. It does
not indicate a data or schema mismatch.

---

## 4. Failure found and fixed

The first API startup in the drill failed with:

```text
src.analytics.errors.RegistryError: registry file is missing
```

Cause: the startup command set `FLAME_REGISTRY_DIR` to `data/registry`. The
loader uses that variable for the **metadata registry directory** containing
`comparability_registry.json` and `serving_registry.json`, which lives in
`data/metadata`.

Resolution:

- use `FLAME_REGISTRY_DIR=<copy>/data/metadata`;
- correct `.env.example` and `docs/api-implementation.md`;
- document the distinction in the restore procedure.

No data was lost or overwritten.

---

## 5. Recovery limitations

- The drill used locally retained raw NASA files. It did not re-download them
  from NASA.
- Acquisition report and fixtures were copied from Git rather than regenerated
  from the live PSI API.
- The restored index version changes when report timestamps change. For exact
  index-version recovery, restore `data/assistant` from backup instead of
  rebuilding.
- No destructive production restore or point-in-time database restore was
  performed; the system has no production database.
- The drill did not test multi-host failover or object-storage recovery.

---

## 6. Recovery duration

The measured pipeline recovery was **310 seconds** on the local host. API
startup and readiness added a small additional period for index loading. This is
an implementation-specific observation, not a service-level guarantee.
