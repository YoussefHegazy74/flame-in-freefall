"""Facets computed from the actual gas-flame rows.

Facet counts use the same default qualification exclusion as the gas-flame
list endpoint. Pressure is always grouped by accession because PSI-10 reports
atm and PSI-159 reports bar; the two are never combined or converted.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from src.analytics.errors import InvalidQueryError

QUALIFIED_FLAGS = {"ramped_condition", "low_oxygen_condition"}
PRESSURE_FIELDS = {
    "PSI-10": ("pressure_initial_atm", "atm"),
    "PSI-159": ("pressure_approx_bar", "bar"),
}
OXYGEN_INITIAL_FIELDS = {
    "PSI-10": ("oxygen_mole_fraction_initial", "mole fraction"),
    "PSI-159": ("oxygen_mole_fraction_before", "mole fraction"),
}


def _is_qualified(row: dict[str, Any]) -> bool:
    flags = row.get("quality_flags") or []
    if not isinstance(flags, list):
        return False
    return any(
        isinstance(item, dict) and item.get("flag") in QUALIFIED_FLAGS
        for item in flags
    )


def _numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _histogram(values: list[float], bins: int = 8) -> list[dict[str, Any]]:
    if not values:
        return []
    low = min(values)
    high = max(values)
    if low == high:
        return [{"min": low, "max": high, "count": len(values)}]
    width = (high - low) / bins
    counts = [0] * bins
    for value in values:
        index = min(int((value - low) / width), bins - 1)
        counts[index] += 1
    return [
        {
            "min": round(low + index * width, 12),
            "max": round(low + (index + 1) * width, 12),
            "count": count,
        }
        for index, count in enumerate(counts)
    ]


def _numeric_summary(
    rows: Iterable[dict[str, Any]],
    field: str,
    unit: str,
    *,
    accession: str,
) -> dict[str, Any]:
    values = [value for row in rows if (value := _numeric(row.get(field))) is not None]
    return {
        "accession": accession,
        "field": field,
        "unit": unit,
        "count": len(values),
        "missing_count": sum(1 for row in rows if row.get(field) is None),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "histogram": _histogram(values),
    }


def _categorical_facet(
    rows: list[dict[str, Any]], field: str
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    by_accession: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        value = row.get(field)
        if value is None or str(value).strip() == "":
            continue
        label = str(value)
        counts[label] += 1
        by_accession[label][row["accession"]] += 1
    return [
        {
            "value": value,
            "count": count,
            "by_accession": dict(sorted(by_accession[value].items())),
        }
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def build_gas_flame_facets(
    rows: list[dict[str, Any]],
    *,
    include_qualified: bool = False,
) -> dict[str, Any]:
    if not isinstance(rows, list):
        raise InvalidQueryError("gas-flame facet rows must be a list")

    all_rows = rows
    included = [row for row in all_rows if include_qualified or not _is_qualified(row)]
    included_ids = {id(row) for row in included}
    excluded = [row for row in all_rows if id(row) not in included_ids]

    accessions = sorted({row["accession"] for row in all_rows})
    accession_summary = []
    for accession in accessions:
        accession_rows = [row for row in all_rows if row["accession"] == accession]
        included_rows = [row for row in included if row["accession"] == accession]
        accession_summary.append(
            {
                "accession": accession,
                "total_rows": len(accession_rows),
                "included_rows": len(included_rows),
                "excluded_qualified_rows": len(accession_rows) - len(included_rows),
            }
        )

    pressure_by_accession = []
    oxygen_by_accession = []
    oxygen_initial_by_accession = []
    for accession in accessions:
        accession_rows = [row for row in included if row["accession"] == accession]
        pressure_field, pressure_unit = PRESSURE_FIELDS.get(
            accession, (None, None)
        )
        if pressure_field:
            pressure_by_accession.append(
                _numeric_summary(
                    accession_rows,
                    pressure_field,
                    pressure_unit,
                    accession=accession,
                )
            )
        oxygen_by_accession.append(
            _numeric_summary(
                accession_rows,
                "oxygen_mole_fraction",
                "mole fraction",
                accession=accession,
            )
        )
        initial_field, initial_unit = OXYGEN_INITIAL_FIELDS.get(
            accession, (None, None)
        )
        if initial_field:
            oxygen_initial_by_accession.append(
                _numeric_summary(
                    accession_rows,
                    initial_field,
                    initial_unit,
                    accession=accession,
                )
            )

    notes = [
        "Facet counts are computed from the canonical gas-flame rows.",
        "Pressure is reported per accession and is never combined: PSI-10 uses atm and PSI-159 uses bar.",
        "Case variants are preserved exactly as published.",
        "Blank and sentinel values are missing, not zero.",
    ]
    if not include_qualified:
        notes.append(
            "Rows carrying ramped-condition or low-oxygen qualifiers are excluded by default, matching the list endpoint."
        )
    if any(item["excluded_qualified_rows"] for item in accession_summary):
        notes.append(
            "Excluded qualified-row counts are reported per accession in the accessions facet."
        )
    notes.append(
        "The oxygen facet uses oxygen_mole_fraction. PSI-10 normal rows and PSI-159 normal rows carry their oxygen in initial/before columns; those are reported separately."
    )

    return {
        "accessions": accession_summary,
        "flame_type": _categorical_facet(included, "flame_type"),
        "fuel": _categorical_facet(included, "fuel"),
        "hot_ignition": _categorical_facet(included, "hot_ignition"),
        "extinction_mode": _categorical_facet(included, "extinction_mode"),
        "tfp": _categorical_facet(included, "tfp_flag"),
        "pressure": {
            "by_accession": pressure_by_accession,
            "note": (
                "PSI-10 pressure_initial_atm is in atm; PSI-159 pressure_approx_bar is in bar. "
                "The values are not converted or merged."
            ),
        },
        "oxygen": {
            "field": "oxygen_mole_fraction",
            "unit": "mole fraction",
            "by_accession": oxygen_by_accession,
        },
        "oxygen_initial": {
            "by_accession": oxygen_initial_by_accession,
            "note": (
                "PSI-10 uses oxygen_mole_fraction_initial; PSI-159 uses oxygen_mole_fraction_before. "
                "These are not the same field and are not merged."
            ),
        },
        "include_qualified": include_qualified,
        "excluded_qualified_rows": len(excluded),
        "notes": notes,
    }
