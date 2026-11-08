"""Command-line interface for the Flame in Freefall data pipeline.

Commands:
    download          acquire the curated NASA PSI selection
    validate          verify raw files and processed tables
    parse             build interim Parquet tables
    build-canonical   build processed canonical tables
    report            write schema, validation, and quality reports
    manifest          build or check the committed selection manifest
    all               run download, parse, build-canonical, validate, report
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .canonical import CanonicalBuildError, build_canonical
from .config import (
    CANONICAL_SCHEMA_JSON,
    DEFAULT_BACKOFF_SECONDS,
    DEFAULT_MAX_FILES,
    DEFAULT_MAX_SINGLE_FILE_BYTES,
    DEFAULT_MAX_TOTAL_BYTES,
    DEFAULT_RATE_LIMIT_SECONDS,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT_SECONDS,
    DOWNLOAD_MANIFEST_CSV,
    DOWNLOAD_MANIFEST_JSON,
    PROCESSED_DIR,
    ensure_directories,
)
from .downloader import DownloadError, download_all
from .manifest import (
    ManifestError,
    build_manifest,
    read_manifest,
    write_manifest_csv,
    write_manifest_json,
)
from .pipeline import PipelineError, parse_all
from .quality import build_quality_report
from .schemas import write_schema_report
from .validation import write_validation_report


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def _cmd_manifest(args: argparse.Namespace) -> int:
    try:
        manifest = build_manifest()
    except ManifestError as exc:
        print(f"manifest build failed:\n{exc}", file=sys.stderr)
        return 1
    if args.check:
        if not DOWNLOAD_MANIFEST_JSON.exists():
            print(f"missing committed manifest: {DOWNLOAD_MANIFEST_JSON}", file=sys.stderr)
            return 1
        generated = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        if DOWNLOAD_MANIFEST_JSON.read_text(encoding="utf-8") != generated:
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


def _cmd_download(args: argparse.Namespace) -> int:
    if not DOWNLOAD_MANIFEST_JSON.exists():
        print("manifest is missing; building it first")
        code = _cmd_manifest(argparse.Namespace(check=False))
        if code != 0:
            return code
    datasets = ["all"] if args.all else args.dataset
    if not datasets:
        print("select at least one --dataset or use --all", file=sys.stderr)
        return 2
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
    except (DownloadError, ManifestError) as exc:
        print(f"download failed: {exc}", file=sys.stderr)
        return 1
    summary = report.summary()
    print("\nAcquisition summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    return 0 if summary["failed"] == 0 else 1


def _cmd_parse(args: argparse.Namespace) -> int:
    try:
        report = parse_all(force=args.force)
    except (PipelineError, ManifestError, FileNotFoundError, KeyError, ValueError) as exc:
        print(f"parse failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Parsed {report['source_count']} sources into "
        f"{len(report['outputs'])} interim outputs in "
        f"{report['duration_seconds']} seconds; "
        f"{report['reused_count']} reused; {report['issue_count']} issues."
    )
    for name, output in report["outputs"].items():
        print(f"  {name}: {output['rows']} rows, {output['bytes']} bytes")
    return 0


def _cmd_build_canonical(args: argparse.Namespace) -> int:
    try:
        report = build_canonical()
    except (CanonicalBuildError, ManifestError, FileNotFoundError, ValueError) as exc:
        print(f"canonical build failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Built {report['table_count']} canonical tables, "
        f"{report['total_rows']} rows, {report['total_bytes']} bytes, "
        f"dataset_version={report['dataset_version']}."
    )
    for name, table in report["tables"].items():
        print(f"  {name}: {table['rows']} rows, {table['bytes']} bytes")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    report = write_validation_report()
    acquisition = report["acquisition"]
    canonical = report["canonical"]
    print(
        f"Acquisition: {acquisition['status']} "
        f"({acquisition['summary']['verified']}/{acquisition['summary']['selected_files']} verified, "
        f"{acquisition['summary']['failed']} failed)"
    )
    print(
        f"Canonical: {canonical['status']} "
        f"({canonical['summary'].get('tables', 0)} checks, "
        f"{canonical['summary'].get('failed', 0)} failed)"
    )
    return 0 if report["status"] == "pass" else 1


def _cmd_report(args: argparse.Namespace) -> int:
    ensure_directories()
    write_schema_report(CANONICAL_SCHEMA_JSON)
    if not PROCESSED_DIR.exists() or not any(PROCESSED_DIR.glob("*.parquet")):
        print(
            "processed tables are missing; run build-canonical before report",
            file=sys.stderr,
        )
        write_validation_report()
        return 1
    quality = build_quality_report()
    validation = write_validation_report()
    print(
        f"Wrote {CANONICAL_SCHEMA_JSON}, "
        "data/reports/validation_report.json, and data/reports/dataset_quality_report.json."
    )
    print(
        f"Validation: {validation['status']}; "
        f"quality: {quality['status']} "
        f"({quality['summary']['tables']} tables, "
        f"{quality['summary']['issues']} issues)"
    )
    return 0 if validation["status"] == "pass" and quality["status"] == "pass" else 1


def _cmd_all(args: argparse.Namespace) -> int:
    download_args = argparse.Namespace(
        dataset=[],
        all=True,
        dry_run=False,
        force=False,
        timeout=DEFAULT_TIMEOUT_SECONDS,
        retries=DEFAULT_RETRIES,
        backoff=DEFAULT_BACKOFF_SECONDS,
        delay=DEFAULT_RATE_LIMIT_SECONDS,
        max_bytes=DEFAULT_MAX_SINGLE_FILE_BYTES,
        max_total_bytes=DEFAULT_MAX_TOTAL_BYTES,
        max_files=DEFAULT_MAX_FILES,
        allow_large=False,
        no_verify_unavailable=False,
    )
    for name, function, arguments in (
        ("download", _cmd_download, download_args),
        ("parse", _cmd_parse, argparse.Namespace(force=args.force)),
        ("build-canonical", _cmd_build_canonical, argparse.Namespace()),
        ("report", _cmd_report, argparse.Namespace()),
    ):
        print(f"\n=== {name} ===")
        code = function(arguments)
        if code != 0:
            print(f"{name} failed", file=sys.stderr)
            return code
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.data_pipeline",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("manifest", help="build or check the selection manifest")
    manifest_parser.add_argument("--check", action="store_true", help="compare against the committed manifest")
    manifest_parser.set_defaults(func=_cmd_manifest)

    download_parser = subparsers.add_parser("download", help="download the curated NASA PSI selection")
    download_parser.add_argument("--dataset", action="append", default=[], help="PSI accession, repeatable")
    download_parser.add_argument("--all", action="store_true", help="select every manifest file")
    download_parser.add_argument("--dry-run", action="store_true", help="check selection and limits only")
    download_parser.add_argument("--force", action="store_true", help="replace an existing file after verification")
    download_parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    download_parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    download_parser.add_argument("--backoff", type=float, default=DEFAULT_BACKOFF_SECONDS)
    download_parser.add_argument("--delay", type=float, default=DEFAULT_RATE_LIMIT_SECONDS)
    download_parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_SINGLE_FILE_BYTES)
    download_parser.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    download_parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    download_parser.add_argument("--allow-large", action="store_true")
    download_parser.add_argument("--no-verify-unavailable", action="store_true")
    download_parser.set_defaults(func=_cmd_download)

    parse_parser = subparsers.add_parser("parse", help="parse selected sources into interim Parquet")
    parse_parser.add_argument("--force", action="store_true", help="rebuild every interim table")
    parse_parser.set_defaults(func=_cmd_parse)

    canonical_parser = subparsers.add_parser("build-canonical", help="build processed canonical Parquet")
    canonical_parser.set_defaults(func=_cmd_build_canonical)

    validate_parser = subparsers.add_parser("validate", help="validate acquisition and canonical tables")
    validate_parser.set_defaults(func=_cmd_validate)

    report_parser = subparsers.add_parser("report", help="write schema, validation, and quality reports")
    report_parser.set_defaults(func=_cmd_report)

    all_parser = subparsers.add_parser("all", help="run the full acquisition and processing pipeline")
    all_parser.add_argument("--force", action="store_true", help="rebuild interim tables")
    all_parser.set_defaults(func=_cmd_all)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
