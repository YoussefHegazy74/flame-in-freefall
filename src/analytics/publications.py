"""Verified publication records from the NASA PSI investigation registry.

The registry provides a title, DOI, author list, and publication status. It
does not provide a publication year or venue. Those fields are returned as
null with an explicit ``not_available`` field status; they are never inferred
from a DOI, a title, or the current date.

Records are merged by DOI when present, otherwise by normalized title. Merge
conflicts are preserved as source variants rather than silently resolved.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from src.analytics.errors import AnalyticsError, InvalidQueryError, NotFoundError
from src.analytics.registry import repo_root

PUBLICATION_SCHEMA_VERSION = "1.0.0"


def _load_registry(root: Path) -> dict[str, Any]:
    path = root / "data" / "registry" / "psi_combustion_investigations.json"
    if not path.exists():
        raise AnalyticsError(
            "publication registry is not available",
            details={"path": path.name},
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AnalyticsError(
            "publication registry could not be read",
            details={"error_type": type(exc).__name__},
        ) from exc
    if not isinstance(payload, dict):
        raise AnalyticsError("publication registry must be a JSON object")
    return payload


def _normalized_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _publication_key(doi: str | None, title: str) -> str:
    if doi:
        return "doi:" + doi.strip().lower()
    return "title:" + _normalized_title(title)


def publication_id(key: str) -> str:
    return "pub_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _parse_authors(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = re.split(r",\s*|\s+and\s+", raw.strip())
    authors = []
    for part in parts:
        name = part.strip().strip(".").strip()
        if name and name.lower() != "and":
            authors.append(name)
    return authors


def _source_reference(accession: str) -> dict[str, Any]:
    return {
        "kind": "psi_investigation_registry",
        "path": "data/registry/psi_combustion_investigations.json",
        "accession": accession,
        "field": "publications",
    }


class PublicationRegistry:
    """Deduplicated publications with source-level verification metadata."""

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root).expanduser().resolve() if root else repo_root()
        payload = _load_registry(self.root)
        self.snapshot_date = payload.get("snapshot_date")
        self._publications: dict[str, dict[str, Any]] = {}
        self._build(payload)

    def _build(self, payload: dict[str, Any]) -> None:
        groups: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        investigation_meta: dict[str, dict[str, Any]] = {}
        for investigation in payload.get("investigations", []):
            if not isinstance(investigation, dict):
                continue
            accession = investigation.get("accession")
            if not accession:
                continue
            investigation_meta[accession] = investigation
            for record in investigation.get("publications") or []:
                if not isinstance(record, dict):
                    continue
                title = str(record.get("title") or "").strip()
                if not title:
                    continue
                doi = str(record.get("doi") or "").strip() or None
                key = _publication_key(doi, title)
                groups.setdefault(key, []).append((accession, record))

        for key, records in groups.items():
            titles: list[str] = []
            authors_variants: list[str] = []
            dois: list[str] = []
            statuses: list[str] = []
            accessions: list[str] = []
            for accession, record in records:
                title = str(record.get("title") or "").strip()
                authors = str(record.get("author_list") or "").strip()
                doi = str(record.get("doi") or "").strip()
                status = str(record.get("status") or "").strip()
                if title and title not in titles:
                    titles.append(title)
                if authors and authors not in authors_variants:
                    authors_variants.append(authors)
                if doi and doi.lower() not in {value.lower() for value in dois}:
                    dois.append(doi)
                if status and status not in statuses:
                    statuses.append(status)
                if accession not in accessions:
                    accessions.append(accession)

            # The source order is preserved. A conflict is exposed, not resolved.
            title = titles[0]
            authors_raw = authors_variants[0] if authors_variants else None
            doi = dois[0] if dois else None
            status = statuses[0] if statuses else None
            related = []
            for accession in sorted(accessions):
                meta = investigation_meta.get(accession, {})
                related.append(
                    {
                        "accession": accession,
                        "title": meta.get("title"),
                        "doi": meta.get("doi"),
                        "acronym": meta.get("acronym"),
                    }
                )
            self._publications[publication_id(key)] = {
                "publication_id": publication_id(key),
                "title": title,
                "title_variants": titles if len(titles) > 1 else [],
                "authors": _parse_authors(authors_raw),
                "authors_raw": authors_raw,
                "authors_raw_variants": (
                    authors_variants if len(authors_variants) > 1 else []
                ),
                "author_parse": "source_comma_or_and_delimited",
                "doi": doi,
                "doi_url": f"https://doi.org/{doi}" if doi else None,
                "year": None,
                "venue": None,
                "status": status,
                "related_investigations": related,
                "source_references": [
                    _source_reference(accession) for accession in sorted(accessions)
                ],
                "verification": {
                    "status": "registry_verified",
                    "source": "data/registry/psi_combustion_investigations.json",
                    "snapshot_date": self.snapshot_date,
                    "verified_fields": [
                        field
                        for field, value in (
                            ("title", title),
                            ("authors", authors_raw),
                            ("doi", doi),
                            ("status", status),
                        )
                        if value
                    ],
                    "unavailable_fields": ["year", "venue"],
                    "conflicts": {
                        "title_variants": titles if len(titles) > 1 else [],
                        "authors_raw_variants": (
                            authors_variants if len(authors_variants) > 1 else []
                        ),
                    },
                },
                "field_status": {
                    "title": "source_provided",
                    "authors": "source_provided",
                    "doi": "source_provided" if doi else "not_provided",
                    "year": "not_available_in_registry",
                    "venue": "not_available_in_registry",
                    "status": "source_provided" if status else "not_provided",
                },
            }

    @property
    def publications(self) -> dict[str, dict[str, Any]]:
        return self._publications

    def get(self, publication_id_value: str) -> dict[str, Any]:
        publication = self._publications.get(publication_id_value)
        if publication is None:
            raise NotFoundError(
                "publication is not present in the verified registry",
                details={"publication_id": publication_id_value},
            )
        return publication

    def list(
        self,
        *,
        accession: str | None = None,
        query: str | None = None,
        year: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        if year is not None:
            raise InvalidQueryError(
                "publication year is not available in the source registry",
                details={"field": "year", "reason": "not_available_in_registry"},
            )
        items = list(self._publications.values())
        if accession:
            items = [
                item
                for item in items
                if any(
                    related["accession"] == accession
                    for related in item["related_investigations"]
                )
            ]
        if status:
            items = [item for item in items if item["status"] == status]
        if query:
            needle = query.lower()
            items = [
                item
                for item in items
                if needle in item["title"].lower()
                or needle in (item["authors_raw"] or "").lower()
                or needle in (item["doi"] or "").lower()
            ]
        items.sort(key=lambda item: (item["title"].lower(), item["publication_id"]))
        total = len(items)
        page_items = items[offset : offset + limit]
        return {
            "publications": page_items,
            "page": {
                "limit": limit,
                "offset": offset,
                "total": total,
                "has_more": offset + len(page_items) < total,
            },
            "summary": {
                "publication_count": total,
                "with_doi": sum(1 for item in items if item["doi"]),
                "without_doi": sum(1 for item in items if not item["doi"]),
                "year_available": False,
                "venue_available": False,
                "note": (
                    "Year and venue are not present in the NASA PSI registry and "
                    "are returned as unavailable."
                ),
            },
        }
