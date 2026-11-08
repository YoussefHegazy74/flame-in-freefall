#!/usr/bin/env python3
"""Collect a reproducible metadata snapshot of NASA PSI combustion investigations.

The script uses only the Python standard library. It reads the public NASA
Physical Sciences Informatics (PSI) repository API, selects every investigation
whose research area is "Combustion Science", and writes:

  data/registry/psi_combustion_investigations.json
  data/registry/psi_file_inventory.csv
  data/registry/psi_experimental_tables.csv

It does not download experimental data files. File names, sizes, formats, and
categories are metadata; they are sufficient to audit coverage without copying
terabytes of NASA raw data into Git.

The PSI detail endpoint exposes two different file lists:

* ``added`` — the archive inventory (telemetry, video, images, documents).
* ``experimentalTable`` — small curated summary tables. These may also appear
  in ``added``, or they may be the only public artifact for a record.

``file_count`` always counts ``added`` entries. Experimental tables are counted
separately so the archive inventory and the summary-table inventory stay
distinct. A record with no ``added`` entries but a public experimental table is
reported as ``experimental_table_only``, not as inaccessible.

Usage
-----
    python scripts/fetch_psi_metadata.py
    python scripts/fetch_psi_metadata.py --check
    python scripts/fetch_psi_metadata.py --details-dir /tmp/psi_details
    python scripts/fetch_psi_metadata.py --raw-dir /tmp/psi_raw

``--check`` compares the live API against the committed snapshot and exits with
status 1 if file counts, versions, registered sizes, or experimental-table
inventories have drifted. It never rewrites the snapshot in check mode.

The companion file ``data/registry/annotations.json`` contains human-reviewed
MVP roles, limitations, and table statistics. Mechanical fields always come
from the live API; annotations never override file counts or sizes.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

PSI_API_BASE = "https://psi.nasa.gov/geode-py/ws"
SEARCH_PATH = "/repo/search"
DETAIL_PATH = "/repo/investigations/{accession}"
DOWNLOAD_PATH = "/studies/{accession}/download"
USER_AGENT = "flame-in-freefall-metadata-collector/0.2 (NASA Space Apps 2026)"
PAGE_SIZE = 200
COMBUSTION_AREA = "combustion science"


def http_json(url: str, *, timeout: int = 90, retries: int = 4) -> Any:
    """Fetch JSON with bounded exponential backoff and no credential handling."""
    last_error: Exception | None = None
    for attempt in range(retries):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == retries - 1:
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"Unable to fetch {url}: {last_error}") from last_error


def search_investigations() -> list[dict[str, Any]]:
    """Return every PSI investigation record, following pagination."""
    records: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = urllib.parse.urlencode(
            {
                "source": "psi",
                "type": "investigation",
                "size": PAGE_SIZE,
                "from": offset,
            }
        )
        payload = http_json(f"{PSI_API_BASE}{SEARCH_PATH}?{query}")
        hits = payload.get("hits", {})
        page = hits.get("hits", [])
        records.extend(hit["_source"] for hit in page if "_source" in hit)
        total = int(hits.get("total", 0))
        offset += len(page)
        if not page or offset >= total:
            break
    return records


def is_combustion(source: dict[str, Any]) -> bool:
    area = str(source.get("Research Area", "")).lower()
    subarea = str(source.get("SubResearch Area", "")).lower()
    return COMBUSTION_AREA in area or "combust" in subarea


def load_annotations(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return suffix if suffix else "(none)"


def table_stat_fields(stats: dict[str, Any]) -> dict[str, Any]:
    """Return annotation statistics without the identity fields."""
    return {
        key: value
        for key, value in stats.items()
        if key not in {"file_name", "bytes"}
    }


def archive_status(file_count: int, experimental_table_count: int) -> str:
    """Classify the public artifact state without conflating the two lists."""
    if file_count > 0:
        return "available"
    if experimental_table_count > 0:
        return "experimental_table_only"
    return "no_public_files"


def summarize(
    detail: dict[str, Any],
    annotations: dict[str, Any],
) -> dict[str, Any]:
    accession = detail.get("accession", "")
    files = detail.get("added") or []
    removed = detail.get("removed") or []
    et_items = detail.get("experimentalTable") or []
    annotation = annotations.get(accession, {})
    table_stats = annotation.get("table_stats", {})

    formats = Counter(extension(str(item.get("file_name", ""))) for item in files)
    added_names = {str(item.get("file_name", "")) for item in files}
    experimental_tables = []
    tabular_files = []
    metadata_packages = []

    for item in files:
        name = str(item.get("file_name", ""))
        lower = name.lower()
        suffix = extension(name)
        if suffix in {".csv", ".xlsx", ".xls", ".tsv"}:
            stats = table_stats.get(name, {})
            table_entry = {
                "file_name": name,
                "bytes": item.get("file_size"),
                "in_added": True,
            }
            table_entry.update(table_stat_fields(stats))
            tabular_files.append(table_entry)
        if "metadata" in lower and lower.endswith(".zip"):
            metadata_packages.append(
                {"file_name": name, "bytes": item.get("file_size")}
            )

    for item in et_items:
        name = str(item.get("file_name", ""))
        stats = table_stats.get(name, {})
        table_entry = {
            "file_name": name,
            "bytes": item.get("file_size"),
            "in_added": name in added_names,
            "restricted": item.get("restricted", ""),
        }
        table_entry.update(table_stat_fields(stats))
        experimental_tables.append(table_entry)
        if name not in added_names:
            tabular_files.append(dict(table_entry))

    publications = []
    for publication in detail.get("publications") or []:
        status = publication.get("status") or {}
        publications.append(
            {
                "title": publication.get("title"),
                "doi": publication.get("doi"),
                "author_list": publication.get("authorList"),
                "status": status.get("annotationValue") if isinstance(status, dict) else None,
            }
        )

    contacts = []
    for contact in detail.get("contacts") or []:
        orcid = ""
        for comment in contact.get("comments") or []:
            if comment.get("name") == "orcidIdentifier":
                orcid = comment.get("value", "")
        contacts.append(
            {
                "name": " ".join(
                    part
                    for part in [
                        contact.get("firstName", ""),
                        contact.get("midInitials", ""),
                        contact.get("lastName", ""),
                    ]
                    if part
                ).strip(),
                "affiliation": contact.get("affiliation", ""),
                "roles": [
                    role.get("annotationValue", "")
                    for role in contact.get("roles") or []
                ],
                "orcid": orcid,
            }
        )

    total_bytes = detail.get("totalFileSize") or 0
    experimental_table_bytes = sum(
        int(item.get("file_size") or 0) for item in et_items
    )
    et_only_count = sum(
        1 for item in experimental_tables if not item.get("in_added")
    )
    return {
        "accession": accession,
        "acronym": detail.get("investigationAcronym", ""),
        "title": detail.get("title", ""),
        "doi": detail.get("doi", ""),
        "research_area": detail.get("researchArea", ""),
        "sub_research_area": detail.get("subResearchArea", ""),
        "project_type": detail.get("projectType", ""),
        "start_date": detail.get("investigationStartDate", ""),
        "end_date": detail.get("investigationEndDate", ""),
        "submission_date": detail.get("submissionDate", ""),
        "release_date": detail.get("releaseDate", ""),
        "version": detail.get("version"),
        "public": detail.get("public"),
        "restricted": detail.get("restricted"),
        "file_count": len(files),
        "removed_file_count": len(removed),
        "registered_total_bytes": total_bytes,
        "registered_total_gb_decimal": round(total_bytes / 1_000_000_000, 2),
        "experimental_table_count": len(experimental_tables),
        "experimental_table_bytes": experimental_table_bytes,
        "experimental_table_only_count": et_only_count,
        "archive_status": archive_status(len(files), len(experimental_tables)),
        "file_formats": dict(formats.most_common()),
        "experimental_tables": experimental_tables,
        "tabular_files": tabular_files,
        "metadata_packages": metadata_packages,
        "publication_count": len(publications),
        "publications": publications,
        "contacts": contacts,
        "description": detail.get("description", ""),
        "objective": detail.get("objective", ""),
        "hypothesis": detail.get("hypothesis", ""),
        "approach": detail.get("approach", ""),
        "research_impacts": detail.get("researchImpacts", ""),
        "project_title": detail.get("projectTitle", ""),
        "proposal_title": detail.get("proposalTitle", ""),
        "mvp_role": annotation.get("mvp_role", "unreviewed"),
        "mvp_rationale": annotation.get("rationale", ""),
        "limitations": annotation.get("limitations", []),
        "access_notes": annotation.get("access_notes", ""),
    }


def detail_from_cache(details_dir: Path, accession: str) -> dict[str, Any]:
    path = details_dir / f"{accession}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Cached detail for {accession} not found at {path}. "
            "Remove --details-dir to fetch from the live API."
        )
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def build_snapshot(
    details_dir: Path | None,
    annotations: dict[str, Any],
    raw_dir: Path | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    sources = search_investigations()
    combustion = sorted(
        (source for source in sources if is_combustion(source)),
        key=lambda source: int(str(source.get("Accession", "PSI-0")).split("-")[-1]),
    )
    if not combustion:
        raise RuntimeError("The PSI search returned no combustion investigations.")

    investigations = []
    inventory_rows = []
    experimental_table_rows = []
    for source in combustion:
        accession = str(source["Accession"])
        if details_dir is not None:
            detail = detail_from_cache(details_dir, accession)
        else:
            detail = http_json(
                f"{PSI_API_BASE}{DETAIL_PATH.format(accession=accession)}"
            )
        if raw_dir is not None:
            raw_dir.mkdir(parents=True, exist_ok=True)
            with (raw_dir / f"{accession}.json").open("w", encoding="utf-8") as handle:
                json.dump(detail, handle, indent=2, ensure_ascii=False)
        summary = summarize(detail, annotations)
        investigations.append(summary)
        for item in detail.get("added") or []:
            inventory_rows.append(
                {
                    "accession": accession,
                    "file_name": item.get("file_name", ""),
                    "file_size_bytes": item.get("file_size", ""),
                    "format": extension(str(item.get("file_name", ""))),
                    "category": item.get("subcategory") or "",
                    "restricted": item.get("restricted", ""),
                    "visible": item.get("visible", ""),
                    "version": item.get("version", ""),
                }
            )
        for table in summary["experimental_tables"]:
            experimental_table_rows.append(
                {
                    "accession": accession,
                    "file_name": table.get("file_name", ""),
                    "file_size_bytes": table.get("bytes", ""),
                    "in_added": table.get("in_added", ""),
                    "sha256": table.get("sha256", ""),
                    "data_rows": table.get("data_rows", ""),
                    "physical_rows": table.get("physical_rows", ""),
                    "columns": table.get("columns", ""),
                    "notes": table.get("notes", ""),
                }
            )
        print(
            f"  {accession:8} {summary['acronym'][:32]:32} "
            f"{summary['file_count']:5} files  "
            f"{summary['experimental_table_count']:2} tables  "
            f"{summary['registered_total_gb_decimal']:9.2f} GB  "
            f"{summary['archive_status']}",
            file=sys.stderr,
        )

    status_counts = Counter(item["archive_status"] for item in investigations)
    et_only_total = sum(
        item["experimental_table_only_count"] for item in investigations
    )
    snapshot = {
        "snapshot_date": dt.date.today().isoformat(),
        "source": {
            "name": "NASA Physical Sciences Informatics (PSI)",
            "landing_page": "https://science.nasa.gov/physical-sciences-informatics-psi/",
            "repository_ui": "https://psi.nasa.gov/physci/repo",
            "api_base": PSI_API_BASE,
            "search_endpoint": f"{PSI_API_BASE}{SEARCH_PATH}",
            "detail_endpoint_template": f"{PSI_API_BASE}{DETAIL_PATH}",
            "download_endpoint_template": f"{PSI_API_BASE}{DOWNLOAD_PATH}?file={{filename}}",
            "notes": (
                "File inventories reflect the public 'added' list returned by the "
                "detail endpoint. 'removed_file_count' counts prior-version files "
                "listed in the API's removed array; they are not part of the "
                "current public inventory. 'experimentalTable' is a separate "
                "curated summary-table list; an entry may also appear in 'added' "
                "or may be the record's only public artifact."
            ),
        },
        "selection": {
            "filter": "Research Area contains 'Combustion Science' or SubResearch Area contains 'combust'",
            "total_psi_investigations": len(sources),
            "combustion_investigations": len(combustion),
        },
        "totals": {
            "file_count": sum(item["file_count"] for item in investigations),
            "experimental_table_count": sum(
                item["experimental_table_count"] for item in investigations
            ),
            "experimental_table_bytes": sum(
                item["experimental_table_bytes"] for item in investigations
            ),
            "experimental_table_only_count": et_only_total,
            "distinct_public_artifacts": sum(
                item["file_count"] for item in investigations
            )
            + et_only_total,
            "archive_status_counts": dict(status_counts),
            "registered_total_bytes": sum(
                item["registered_total_bytes"] for item in investigations
            ),
            "registered_total_gb_decimal": round(
                sum(item["registered_total_bytes"] for item in investigations)
                / 1_000_000_000,
                2,
            ),
        },
        "investigations": investigations,
    }
    return snapshot, inventory_rows, experimental_table_rows


def write_snapshot(
    snapshot: dict[str, Any],
    inventory_rows: list[dict[str, Any]],
    experimental_table_rows: list[dict[str, Any]],
    out_dir: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = out_dir / "psi_combustion_investigations.json"
    inventory_path = out_dir / "psi_file_inventory.csv"
    tables_path = out_dir / "psi_experimental_tables.csv"
    with snapshot_path.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    with inventory_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "accession",
                "file_name",
                "file_size_bytes",
                "format",
                "category",
                "restricted",
                "visible",
                "version",
            ],
        )
        writer.writeheader()
        writer.writerows(inventory_rows)
    with tables_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "accession",
                "file_name",
                "file_size_bytes",
                "in_added",
                "sha256",
                "data_rows",
                "physical_rows",
                "columns",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(experimental_table_rows)
    print(
        f"Wrote {snapshot_path}, {inventory_path} "
        f"({len(inventory_rows)} archive rows), and {tables_path} "
        f"({len(experimental_table_rows)} experimental-table rows).",
        file=sys.stderr,
    )


def check_snapshot(snapshot: dict[str, Any], out_dir: Path) -> int:
    path = out_dir / "psi_combustion_investigations.json"
    if not path.exists():
        print(f"No committed snapshot at {path}.", file=sys.stderr)
        return 1
    with path.open(encoding="utf-8") as handle:
        committed = json.load(handle)
    previous = {
        item["accession"]: item for item in committed.get("investigations", [])
    }
    drift = 0
    for item in snapshot["investigations"]:
        accession = item["accession"]
        old = previous.get(accession)
        if old is None:
            print(f"NEW     {accession} is not in the committed snapshot.")
            drift += 1
            continue
        for field in (
            "version",
            "file_count",
            "registered_total_bytes",
            "experimental_table_count",
            "archive_status",
        ):
            if old.get(field) != item.get(field):
                print(
                    f"CHANGED {accession} {field}: "
                    f"{old.get(field)!r} -> {item.get(field)!r}"
                )
                drift += 1
        old_tables = {
            table.get("file_name") for table in old.get("experimental_tables", [])
        }
        new_tables = {
            table.get("file_name") for table in item.get("experimental_tables", [])
        }
        if old_tables != new_tables:
            print(
                f"CHANGED {accession} experimental table names: "
                f"{sorted(old_tables)} -> {sorted(new_tables)}"
            )
            drift += 1
    for accession in sorted(
        set(previous) - {item["accession"] for item in snapshot["investigations"]}
    ):
        print(f"REMOVED {accession} is no longer returned by the API.")
        drift += 1
    if drift:
        print(f"Detected {drift} drift(s).", file=sys.stderr)
        return 1
    print("No metadata drift detected.", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "registry",
        help="Directory for the generated snapshot and inventories.",
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "data"
        / "registry"
        / "annotations.json",
        help="Human-reviewed MVP annotations.",
    )
    parser.add_argument(
        "--details-dir",
        type=Path,
        default=None,
        help="Read cached investigation detail JSON files instead of the live API.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=None,
        help="Optionally save full detail JSON files outside the repository.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare live metadata with the committed snapshot; do not write.",
    )
    args = parser.parse_args()

    annotations = load_annotations(args.annotations)
    snapshot, inventory_rows, experimental_table_rows = build_snapshot(
        args.details_dir, annotations, args.raw_dir
    )
    if args.check:
        return check_snapshot(snapshot, args.out_dir)
    write_snapshot(snapshot, inventory_rows, experimental_table_rows, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
