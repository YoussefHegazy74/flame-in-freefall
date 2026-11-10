#!/usr/bin/env bash
# Reproducibility checks shared by local development and CI.
#
# The default mode is data-free: it verifies committed metadata, schemas,
# fixtures, catalog, and registries without requiring the gitignored canonical
# Parquet or raw NASA files.
#
# Usage:
#   scripts/verify_reproducibility.sh
#   scripts/verify_reproducibility.sh --with-data
#
# --with-data additionally validates the canonical tables, the retrieval index,
# and the deterministic assistant evaluation. It requires data/processed,
# data/interim, data/raw as appropriate, and data/assistant.

set -euo pipefail

PYTHON="${PYTHON:-python}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== Committed manifest =="
"$PYTHON" -m src.data_pipeline manifest --check

echo "== Download manifest =="
"$PYTHON" scripts/build_download_manifest.py --check

echo "== MVP catalog =="
"$PYTHON" scripts/build_mvp_catalog.py --check

echo "== Committed JSON parse =="
"$PYTHON" - <<'PY'
import json
from pathlib import Path

paths = [
    *Path("data/registry").glob("*.json"),
    *Path("data/metadata").glob("*.json"),
    *Path("data/reports").glob("*.json"),
    *Path("data/fixtures").glob("*.json"),
]
for path in paths:
    json.loads(path.read_text(encoding="utf-8"))
print(f"Parsed {len(paths)} committed JSON artifacts.")
PY

if [[ "${1:-}" == "--with-data" ]]; then
  echo "== Experimental-table schemas =="
  "$PYTHON" scripts/build_et_schemas.py --check

  echo "== Authentic fixtures =="
  "$PYTHON" scripts/build_fixtures.py --check

  echo "== Phase 2 registries =="
  "$PYTHON" scripts/build_phase2_registries.py --check

  echo "== Canonical validation =="
  "$PYTHON" -m src.data_pipeline validate

  echo "== Retrieval index =="
  "$PYTHON" scripts/build_assistant_index.py --check

  echo "== Assistant evaluation =="
  "$PYTHON" scripts/evaluate_assistant.py --check
fi

echo "Reproducibility checks passed."
