#!/usr/bin/env python3
"""Build or check the committed Phase 1 download manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_pipeline.config import DOWNLOAD_MANIFEST_CSV, DOWNLOAD_MANIFEST_JSON
from src.data_pipeline.manifest import (
    ManifestError,
    build_manifest,
    validate_manifest,
    write_manifest_csv,
    write_manifest_json,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare the committed manifest with a fresh build; exit 1 on drift.",
    )
    args = parser.parse_args(argv)

    try:
        manifest = build_manifest()
    except ManifestError as exc:
        print(f"manifest build failed:\n{exc}", file=sys.stderr)
        return 1

    if args.check:
        if not DOWNLOAD_MANIFEST_JSON.exists():
            print(f"missing committed manifest: {DOWNLOAD_MANIFEST_JSON}", file=sys.stderr)
            return 1
        committed = DOWNLOAD_MANIFEST_JSON.read_text(encoding="utf-8")
        generated = (
            __import__("json").dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        )
        if committed != generated:
            print("manifest drift detected", file=sys.stderr)
            return 1
        print(
            "Committed manifest matches the regenerated manifest: "
            f"{manifest['totals']['selected_files']} files, "
            f"{manifest['totals']['selected_bytes']} bytes."
        )
        return 0

    write_manifest_json(manifest)
    write_manifest_csv(manifest, DOWNLOAD_MANIFEST_CSV, status="pending")
    print(
        f"Wrote {DOWNLOAD_MANIFEST_JSON} and {DOWNLOAD_MANIFEST_CSV}\n"
        f"{manifest['totals']['selected_files']} files, "
        f"{manifest['totals']['selected_bytes']} bytes, "
        f"{manifest['totals']['experimental_tables']} experimental tables."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
