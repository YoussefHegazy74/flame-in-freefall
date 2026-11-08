#!/usr/bin/env python3
"""Download the curated NASA PSI selection.

Examples:
    python scripts/download_psi_files.py --dataset PSI-10
    python scripts/download_psi_files.py --all --dry-run
    python scripts/download_psi_files.py --all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_pipeline.config import (
    DEFAULT_BACKOFF_SECONDS,
    DEFAULT_MAX_FILES,
    DEFAULT_MAX_SINGLE_FILE_BYTES,
    DEFAULT_MAX_TOTAL_BYTES,
    DEFAULT_RATE_LIMIT_SECONDS,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT_SECONDS,
)
from src.data_pipeline.downloader import DownloadError, download_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", action="append", default=[], help="PSI accession, repeatable")
    parser.add_argument("--all", action="store_true", help="Select every file in the manifest")
    parser.add_argument("--dry-run", action="store_true", help="Check selection and limits without downloading")
    parser.add_argument("--force", action="store_true", help="Replace an existing file after verification")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--backoff", type=float, default=DEFAULT_BACKOFF_SECONDS)
    parser.add_argument("--delay", type=float, default=DEFAULT_RATE_LIMIT_SECONDS)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_SINGLE_FILE_BYTES)
    parser.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument(
        "--allow-large",
        action="store_true",
        help="Explicitly approve a single file above --max-bytes after reviewing it",
    )
    parser.add_argument(
        "--no-verify-unavailable",
        action="store_true",
        help="Skip the documented-404 verification requests",
    )
    args = parser.parse_args(argv)

    datasets = ["all"] if args.all else args.dataset
    if not datasets:
        parser.error("select at least one --dataset or use --all")

    try:
        report = download_all(
            datasets=datasets,
            timeout=args.timeout,
            retries=args.retries,
            backoff=args.backoff,
            rate_limit=args.delay,
            max_single_file_bytes=args.max_bytes,
            max_total_bytes=args.max_total_bytes,
            max_files=args.max_files,
            allow_large=args.allow_large,
            force=args.force,
            dry_run=args.dry_run,
            verify_unavailable=not args.no_verify_unavailable,
        )
    except DownloadError as exc:
        print(f"download failed: {exc}", file=sys.stderr)
        return 1

    summary = report.summary()
    print("\nAcquisition summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    return 0 if summary["failed"] == 0 and summary["approval_required"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
