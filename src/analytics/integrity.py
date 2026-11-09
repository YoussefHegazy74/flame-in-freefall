"""Canonical data-presence checks for registry measurements.

The Phase 2 registries are authoritative for comparison policy. They are not a
substitute for checking that a named canonical field actually contains values.
This module adds a cheap, fail-closed presence check for the summary tables.
It never edits the registries and never invents a value: it reports a separate
integrity status that callers must not ignore.

The check exists because a registry entry can be internally consistent and
still name a canonical column that is empty for an accession. A concrete
example is PSI-159: the registry names ``pressure_initial_atm``, while the
canonical table has zero values there and reports ``pressure_approx_bar`` in
bar. Presenting the empty atm field as available, or approving a comparison
against it, would be misleading.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.analytics.db import AnalyticsDatabase
from src.analytics.errors import AnalyticsError
from src.analytics.registry import RegistryBundle

SUMMARY_TABLES: dict[str, tuple[str, str]] = {
    "psi-10-gas-flame": ("gas_flame_test", "PSI-10"),
    "psi-159-gas-flame": ("gas_flame_test", "PSI-159"),
    "psi-25-material": ("material_test", "PSI-25"),
    "psi-26-material": ("material_test", "PSI-26"),
    "psi-69-droplet": ("droplet_test", "PSI-69"),
    "psi-102-smoke-log": ("smoke_test_log", "PSI-102"),
}

# Verified source alternatives for a registry field that is empty. These are
# descriptive only; they are never substituted into a comparison.
KNOWN_ALTERNATIVES: dict[str, list[dict[str, Any]]] = {
    "psi-10-gas-flame.pressure_approx_bar": [
        {
            "canonical_field": "pressure_initial_atm",
            "unit": "atm",
            "description": (
                "PSI-10 reports initial pressure in atm. The canonical table has "
                "no values in pressure_approx_bar for PSI-10, so the atm field is "
                "the verified source quantity, not an approximate bar conversion."
            ),
            "evidence": {
                "kind": "document",
                "path": "DATA_DICTIONARY.md",
                "section": "4.1-4.2 PSI-10 ACME Flame Design",
            },
        }
    ],
    "psi-159-gas-flame.pressure_initial_atm": [
        {
            "canonical_field": "pressure_approx_bar",
            "unit": "bar",
            "description": (
                "PSI-159 reports approximate test pressure in bar. It is not an "
                "initial pressure in atm and is not interchangeable with one."
            ),
            "evidence": {
                "kind": "document",
                "path": "DATA_DICTIONARY.md",
                "section": "4.3-4.4 PSI-159 ACME CFI-G",
            },
        }
    ],
}


@dataclass(frozen=True)
class PresenceCheck:
    """The result of checking one registry measurement against canonical rows."""

    measurement_id: str
    checked: bool
    status: str
    reason: str | None
    table: str | None
    field: str | None
    accession: str | None
    total_rows: int | None
    non_null_count: int | None
    alternatives: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "measurement_id": self.measurement_id,
            "checked": self.checked,
            "status": self.status,
            "reason": self.reason,
            "table": self.table,
            "field": self.field,
            "accession": self.accession,
            "total_rows": self.total_rows,
            "non_null_count": self.non_null_count,
            "alternatives": [dict(item) for item in self.alternatives],
        }


def _not_checked(
    measurement_id: str,
    reason: str,
    *,
    table: str | None = None,
    field: str | None = None,
    accession: str | None = None,
) -> PresenceCheck:
    return PresenceCheck(
        measurement_id=measurement_id,
        checked=False,
        status="not_checked",
        reason=reason,
        table=table,
        field=field,
        accession=accession,
        total_rows=None,
        non_null_count=None,
        alternatives=tuple(KNOWN_ALTERNATIVES.get(measurement_id, ())),
    )


class MeasurementIntegrity:
    """Cached canonical data-presence checks for the summary tables."""

    def __init__(self, database: AnalyticsDatabase, bundle: RegistryBundle):
        self.db = database
        self.bundle = bundle
        self._columns: dict[str, set[str]] = {}
        self._checks: dict[str, PresenceCheck] = {}
        self._datasets_loaded: set[str] = set()

    def _table_columns(self, table: str) -> set[str]:
        if table in self._columns:
            return self._columns[table]
        if table not in self.db.available_tables:
            self._columns[table] = set()
            return self._columns[table]
        rows = self.db._rows(f'DESCRIBE SELECT * FROM "{table}"')
        self._columns[table] = {
            str(row["column_name"]) for row in rows if row.get("column_name")
        }
        return self._columns[table]

    def _load_dataset(self, dataset_id: str) -> None:
        if dataset_id in self._datasets_loaded:
            return
        self._datasets_loaded.add(dataset_id)
        measurements = [
            measurement
            for measurement in self.bundle.measurements.values()
            if measurement["dataset_id"] == dataset_id
        ]
        mapping = SUMMARY_TABLES.get(dataset_id)
        dataset = self.bundle.datasets.get(dataset_id) or {}
        if mapping is None and not dataset.get("canonical_tables"):
            for measurement in measurements:
                self._checks[measurement["measurement_id"]] = _not_checked(
                    measurement["measurement_id"],
                    "no_canonical_tables",
                )
            return
        if mapping is None:
            for measurement in measurements:
                self._checks[measurement["measurement_id"]] = _not_checked(
                    measurement["measurement_id"],
                    "presence_check_not_supported_for_large_point_table",
                )
            return
        table, accession = mapping
        if table not in self.db.available_tables:
            for measurement in measurements:
                self._checks[measurement["measurement_id"]] = _not_checked(
                    measurement["measurement_id"],
                    "canonical_table_unavailable",
                    table=table,
                    accession=accession,
                )
            return

        columns = self._table_columns(table)
        checked: list[tuple[dict[str, Any], str]] = []
        for measurement in measurements:
            measurement_id = measurement["measurement_id"]
            field = measurement.get("canonical_field") or measurement.get(
                "canonical_channel"
            )
            if not field:
                self._checks[measurement_id] = _not_checked(
                    measurement_id,
                    "no_canonical_field",
                    table=table,
                    accession=accession,
                )
                continue
            if field not in columns:
                self._checks[measurement_id] = PresenceCheck(
                    measurement_id=measurement_id,
                    checked=True,
                    status="missing",
                    reason="field_not_in_canonical_table",
                    table=table,
                    field=field,
                    accession=accession,
                    total_rows=None,
                    non_null_count=0,
                    alternatives=tuple(KNOWN_ALTERNATIVES.get(measurement_id, ())),
                )
                continue
            checked.append((measurement, field))

        if not checked:
            return

        aliases = []
        select_parts = ["count(*) AS total_rows"]
        for index, (measurement, field) in enumerate(checked):
            alias = f"f{index}"
            select_parts.append(f'count("{field}") AS {alias}')
            aliases.append((alias, measurement["measurement_id"]))
        sql = (
            "SELECT "
            + ", ".join(select_parts)
            + f' FROM "{table}" WHERE accession = ?'
        )
        try:
            row = self.db._one(sql, [accession]) or {}
        except AnalyticsError:
            for measurement, field in checked:
                measurement_id = measurement["measurement_id"]
                self._checks[measurement_id] = _not_checked(
                    measurement_id,
                    "presence_check_failed",
                    table=table,
                    field=field,
                    accession=accession,
                )
            return

        total_rows = int(row.get("total_rows") or 0)
        for alias, measurement_id in aliases:
            measurement = self.bundle.measurements[measurement_id]
            field = measurement.get("canonical_field") or measurement.get(
                "canonical_channel"
            )
            non_null = int(row.get(alias) or 0)
            status = "available" if non_null > 0 else "missing"
            self._checks[measurement_id] = PresenceCheck(
                measurement_id=measurement_id,
                checked=True,
                status=status,
                reason=None if status == "available" else "no_non_null_values",
                table=table,
                field=str(field),
                accession=accession,
                total_rows=total_rows,
                non_null_count=non_null,
                alternatives=tuple(KNOWN_ALTERNATIVES.get(measurement_id, ())),
            )

    def check(self, measurement_id: str) -> PresenceCheck:
        measurement = self.bundle.measurements.get(measurement_id)
        if measurement is None:
            return _not_checked(measurement_id, "unknown_measurement")
        self._load_dataset(measurement["dataset_id"])
        return self._checks.get(measurement_id) or _not_checked(
            measurement_id, "presence_check_not_available"
        )

    def check_decision(self, decision: Any) -> dict[str, Any]:
        checks = []
        for side in ("left", "right"):
            measurement = getattr(decision, side)
            measurement_id = measurement.get("measurement_id")
            if not measurement_id:
                continue
            checks.append(self.check(str(measurement_id)).to_dict())
        failures = [item for item in checks if item["status"] == "missing"]
        not_checked = [item for item in checks if item["status"] == "not_checked"]
        if failures:
            status = "failed"
        elif not_checked:
            status = "not_checked"
        else:
            status = "passed"
        messages = []
        for item in failures:
            message = (
                f"{item['measurement_id']} has no non-null values in "
                f"{item['table']}.{item['field']} for {item['accession']}."
            )
            for alternative in item.get("alternatives", []):
                message += (
                    f" The source reports {alternative['canonical_field']} in "
                    f"{alternative['unit']}; it is not this registry field."
                )
            messages.append(message)
        return {
            "status": status,
            "checks": checks,
            "failures": failures,
            "not_checked": not_checked,
            "messages": messages,
        }
