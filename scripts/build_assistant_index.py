#!/usr/bin/env python3
"""Build or validate the Phase 5 assistant retrieval index.

Usage::

    .venv/bin/python scripts/build_assistant_index.py
    .venv/bin/python scripts/build_assistant_index.py --check

The index is a reproducible local artifact built only from committed
documentation and verified metadata. It is gitignored. ``--check`` verifies the
existing artifact against current source hashes and a fresh in-memory build
without writing anything.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analytics.registry import load_registries  # noqa: E402
from src.analytics.service import AnalyticsService  # noqa: E402
from src.assistant.retrieval import (  # noqa: E402
    DEFAULT_INDEX_PATH,
    RetrievalError,
    RetrievalIndex,
    build_index,
)

DEFAULT_OUTPUT = ROOT / DEFAULT_INDEX_PATH


def _report_error(exc: RetrievalError) -> None:
    print(f"assistant index error: {exc}", file=sys.stderr)
    details = getattr(exc, "details", None)
    if details:
        print(f"  details: {details}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"index artifact path (default: {DEFAULT_INDEX_PATH})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the existing index without writing; exit 1 on drift.",
    )
    args = parser.parse_args(argv)

    try:
        service = AnalyticsService(bundle=load_registries())
        built = build_index(service)
    except RetrievalError as exc:
        _report_error(exc)
        return 1

    if args.check:
        if not args.output.exists():
            print(f"missing assistant index: {args.output}", file=sys.stderr)
            return 1
        try:
            existing = RetrievalIndex.load(
                args.output, root=ROOT, verify_sources=True
            )
        except RetrievalError as exc:
            _report_error(exc)
            return 1
        if existing.manifest.index_version != built.manifest.index_version:
            print(
                "assistant index version drift detected: "
                f"{existing.manifest.index_version} != {built.manifest.index_version}",
                file=sys.stderr,
            )
            return 1
        if existing.manifest.chunk_digest != built.manifest.chunk_digest:
            print(
                "assistant index chunk digest drift detected",
                file=sys.stderr,
            )
            return 1
        print(
            "Assistant index is current: "
            f"{existing.manifest.index_version}, "
            f"{existing.manifest.chunk_count} chunks, "
            f"{existing.manifest.document_count} documents, "
            f"{len(existing.manifest.sources)} verified sources."
        )
        return 0

    destination = built.write(args.output)
    print(
        f"Wrote {destination}\n"
        f"index_version: {built.manifest.index_version}\n"
        f"chunks: {built.manifest.chunk_count} "
        f"documents: {built.manifest.document_count} "
        f"sources: {len(built.manifest.sources)}\n"
        f"validate: {built.manifest.validation_command}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
