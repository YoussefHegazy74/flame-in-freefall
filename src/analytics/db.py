"""Read-only DuckDB access to the canonical Parquet tables.

The database layer is intentionally narrow. It exposes named analytical
operations instead of arbitrary SQL: the API never receives a table name, a
file path, or a SQL fragment from a client. Every query is parameterized, every
list is bounded, and every series request has an explicit point cap.

DuckDB 2.0.0 does not implement ``statement_timeout`` and cannot bind a
parameter inside ``read_parquet``. Views are therefore created from literal
paths that come only from the canonical schema table names, and a
``threading.Timer`` calls ``Connection.interrupt()`` to enforce a wall-clock
budget.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import duckdb

from src.analytics.errors import (
    AnalyticsError,
    DatasetUnavailableError,
    InvalidQueryError,
    LimitExceededError,
    NotFoundError,
    QueryError,
    QueryTimeoutError,
)
from src.analytics.logging import get_logger
from src.analytics.registry import repo_root
from src.data_pipeline.schemas import TABLE_SCHEMAS

LOGGER = get_logger("flame.analytics.db")

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
DEFAULT_SERIES_POINTS = 5000
MAX_SERIES_POINTS = 20000
MAX_SERIES_CHANNELS = 8

GAS_FLAME_ACCESSIONS = ("PSI-10", "PSI-159")
MATERIAL_ACCESSIONS = ("PSI-25", "PSI-26")
DROPLET_ACCESSIONS = ("PSI-69",)
TELEMETRY_ACCESSIONS = ("PSI-100",)
SMOKE_ACCESSIONS = ("PSI-101",)

ACCESSION_PATTERN = re.compile(r"^PSI-\d+$")

AGGREGATE_TABLES = ("gas_flame_test", "material_test", "droplet_test")
MAX_AGGREGATE_FIELDS = 24

QUALIFIED_GAS_FLAME_SQL = (
    "COALESCE(quality_flags, '') LIKE '%ramped_condition%' "
    "OR COALESCE(quality_flags, '') LIKE '%low_oxygen_condition%'"
)

GAS_FLAME_STAT_FIELDS = (
    "pressure_initial_atm",
    "pressure_final_atm",
    "pressure_mean_atm",
    "pressure_approx_bar",
    "oxygen_mole_fraction",
    "oxygen_mole_fraction_initial",
    "oxygen_mole_fraction_final",
    "oxygen_mole_fraction_before",
    "oxygen_mole_fraction_after",
    "adiabatic_flame_temp_k",
    "peak_burner_temp_c",
    "peak_burner_temp_k",
    "stoich_mixture_fraction",
    "fuel_mole_fraction",
    "fuel_mass_flow_mg_s",
    "diluent_mass_flow_mg_s",
    "total_mass_flow_mg_s",
    "burn_time_s",
)

GAS_FLAME_OXYGEN_FIELDS = (
    "oxygen_mole_fraction",
    "oxygen_mole_fraction_initial",
    "oxygen_mole_fraction_before",
)

GAS_FLAME_COLUMNS = (
    "observation_id",
    "accession",
    "table_id",
    "source_file",
    "source_sheet",
    "source_row",
    "source_sha256",
    "retrieved_at",
    "source_url",
    "parser_version",
    "flame_type",
    "day",
    "fuel",
    "test_code",
    "fuel_mole_fraction",
    "fuel_mass_flow_mg_s",
    "diluent_mass_flow_mg_s",
    "total_mass_flow_mg_s",
    "oxygen_mole_fraction",
    "oxygen_mole_fraction_initial",
    "oxygen_mole_fraction_final",
    "oxygen_mole_fraction_before",
    "oxygen_mole_fraction_after",
    "pressure_initial_atm",
    "pressure_final_atm",
    "pressure_mean_atm",
    "pressure_approx_bar",
    "oxidizer_mass_flow_mg_s",
    "fuel_mole_fraction_initial",
    "fuel_mole_fraction_final",
    "fuel_mole_fraction_before",
    "fuel_mole_fraction_after",
    "fuel_burn_rate_mg_s",
    "stoich_mixture_fraction",
    "adiabatic_flame_temp_k",
    "cool_flame_flag",
    "tfp_flag",
    "hot_ignition",
    "burn_time_s",
    "extinction_mode",
    "peak_burner_temp_c",
    "peak_burner_temp_k",
    "color",
    "comments",
    "quality_flags",
)

MATERIAL_COLUMNS = (
    "observation_id",
    "accession",
    "table_id",
    "source_file",
    "source_sheet",
    "source_row",
    "source_sha256",
    "retrieved_at",
    "source_url",
    "parser_version",
    "record_type",
    "test_date",
    "gmt_day",
    "as_run_test_no",
    "test_no",
    "sample_no",
    "material",
    "flow_restrictor",
    "fan_display",
    "air_display",
    "radiometer_gain",
    "total_frames",
    "initial_o2_pct",
    "final_o2_pct",
    "o2_pct",
    "initial_co2_pct",
    "final_co2_pct",
    "initial_co_ppm",
    "final_co_ppm",
    "pressure_atm",
    "co2_mm_hg",
    "observations",
    "quality_flags",
)

DROPLET_COLUMNS = (
    "observation_id",
    "accession",
    "table_id",
    "source_file",
    "source_sheet",
    "source_row",
    "source_sha256",
    "retrieved_at",
    "source_url",
    "parser_version",
    "flex_test_number",
    "test_date",
    "flex_identifier",
    "test_gmt",
    "fuel",
    "ambient_pressure_mm_hg",
    "o2_initial_mole_fraction",
    "n2_initial_mole_fraction",
    "co_initial_mole_fraction",
    "he_initial_mole_fraction",
    "droplet_initial_diameter_mm",
    "visible_flame_extinction_diameter_mm",
    "burning_rate_mm_as_labeled",
    "burn_time_s",
    "test_end",
    "quality_flags",
)

RUN_COLUMNS = (
    "run_id",
    "accession",
    "source_file",
    "source_sheet",
    "export_kind",
    "physical_rows",
    "empty_rows",
    "invalid_time_rows",
    "sentinel_rows",
    "valid_rows",
    "time_min_ms",
    "time_max_ms",
    "column_count",
    "channel_count",
    "sha256",
    "retrieved_at",
    "source_url",
    "parser_version",
    "notes",
)

SMOKE_RUN_COLUMNS = (
    "run_id",
    "accession",
    "source_file",
    "test_number",
    "sample_number",
    "carousel_number",
    "test_numbers_json",
    "sample_numbers_json",
    "carousel_numbers_json",
    "run_mode_codes_json",
    "time_min_unix_s",
    "time_max_unix_s",
    "elapsed_test_time_min_s",
    "elapsed_test_time_max_s",
    "physical_rows",
    "empty_rows",
    "malformed_rows",
    "invalid_time_rows",
    "sentinel_time_rows",
    "valid_rows",
    "column_count",
    "channel_count",
    "issues_json",
    "sha256",
    "retrieved_at",
    "source_url",
    "parser_version",
    "notes",
)

COMPUTED_GAS_FIELDS = ("stoich_mixture_fraction", "adiabatic_flame_temp_k")

PROVENANCE_TABLES = (
    "gas_flame_test",
    "material_test",
    "droplet_test",
    "telemetry_point",
    "smoke_point",
    "smoke_test_log",
    "experimental_table_cell",
    "source_row",
)


@dataclass(frozen=True)
class PageResult:
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total

    def page(self) -> dict[str, Any]:
        return {
            "limit": self.limit,
            "offset": self.offset,
            "total": self.total,
            "has_more": self.has_more,
            **self.extra,
        }


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _placeholders(count: int) -> str:
    return ", ".join("?" for _ in range(count))


def _loads(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _json_list(value: Any) -> list[Any]:
    parsed = _loads(value, [])
    return parsed if isinstance(parsed, list) else []


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _validate_page(limit: int, offset: int) -> None:
    if limit < 1 or limit > MAX_PAGE_SIZE:
        raise LimitExceededError(
            f"limit must be between 1 and {MAX_PAGE_SIZE}",
            details={"limit": limit, "maximum": MAX_PAGE_SIZE},
        )
    if offset < 0:
        raise InvalidQueryError(
            "offset must be zero or greater",
            details={"offset": offset},
        )


def _validate_accession(accession: str, allowed: Sequence[str] | None = None) -> str:
    if not ACCESSION_PATTERN.match(accession or ""):
        raise InvalidQueryError(
            "accession must match PSI-<number>",
            details={"accession": accession},
        )
    if allowed is not None and accession not in allowed:
        raise InvalidQueryError(
            "accession is not available through this endpoint",
            details={"accession": accession, "allowed": list(allowed)},
        )
    return accession


def _validate_series_points(max_points: int) -> None:
    if max_points < 1 or max_points > MAX_SERIES_POINTS:
        raise LimitExceededError(
            f"max_points must be between 1 and {MAX_SERIES_POINTS}",
            details={"max_points": max_points, "maximum": MAX_SERIES_POINTS},
        )


def _parse_channels(channels: str | Sequence[str] | None) -> list[str]:
    if channels is None:
        raise InvalidQueryError("channels is required")
    if isinstance(channels, str):
        values = [part.strip() for part in channels.split(",")]
    else:
        values = [str(part).strip() for part in channels]
    values = [value for value in values if value]
    if not values:
        raise InvalidQueryError("at least one channel is required")
    if len(values) > MAX_SERIES_CHANNELS:
        raise LimitExceededError(
            f"at most {MAX_SERIES_CHANNELS} channels may be requested",
            details={"channels": len(values), "maximum": MAX_SERIES_CHANNELS},
        )
    return _dedupe(values)


def _parse_profile_flags(profile: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if profile.get("uncalibrated"):
        flags.append("uncalibrated")
    if profile.get("unit") == "not stated":
        flags.append("not_stated_unit")
    if profile.get("constant"):
        flags.append("constant")
    if profile.get("sentinel"):
        flags.append("sentinel")
    if not flags:
        flags.append("ok")
    return flags


def _channel_index(profiles: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        canonical = profile.get("canonical_name")
        if not canonical:
            continue
        index.setdefault(canonical, profile)
    return index


class AnalyticsDatabase:
    """Named, bounded queries over the canonical Parquet dataset."""

    def __init__(
        self,
        processed_dir: Path | str | None = None,
        reports_dir: Path | str | None = None,
        *,
        timeout_seconds: float | None = None,
    ):
        root = repo_root()
        self.processed_dir = Path(
            processed_dir
            or os.environ.get("FLAME_PROCESSED_DIR")
            or root / "data" / "processed"
        ).expanduser().resolve()
        self.reports_dir = Path(
            reports_dir
            or os.environ.get("FLAME_REPORTS_DIR")
            or root / "data" / "reports"
        ).expanduser().resolve()
        self.timeout_seconds = float(
            timeout_seconds
            if timeout_seconds is not None
            else os.environ.get("FLAME_QUERY_TIMEOUT_SECONDS", "10")
        )
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._available_tables = {
            name
            for name in TABLE_SCHEMAS
            if (self.processed_dir / f"{name}.parquet").exists()
        }
        self._quality_report: dict[str, Any] | None = None
        self._manifest: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Connection and execution
    # ------------------------------------------------------------------
    def _connect(self) -> duckdb.DuckDBPyConnection:
        connection = duckdb.connect(database=":memory:")
        for table_name in sorted(self._available_tables):
            path = self.processed_dir / f"{table_name}.parquet"
            connection.execute(
                f'CREATE VIEW "{table_name}" AS SELECT * FROM read_parquet({_sql_string(str(path))})'
            )
        return connection

    def _fetch(
        self,
        sql: str,
        params: Sequence[Any] = (),
        *,
        timeout_seconds: float | None = None,
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        connection = self._connect()
        budget = self.timeout_seconds if timeout_seconds is None else timeout_seconds

        def interrupt() -> None:
            try:
                connection.interrupt()
            except Exception:
                # The query may have completed and closed the connection just
                # before the watchdog fired. There is nothing to cancel.
                pass

        timer = threading.Timer(budget, interrupt)
        timer.daemon = True
        timer.start()
        try:
            cursor = connection.execute(sql, list(params))
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description or []]
            return columns, rows
        except duckdb.InterruptException as exc:
            raise QueryTimeoutError(
                "the query exceeded its time budget",
                details={"timeout_seconds": budget},
            ) from exc
        except duckdb.Error as exc:
            LOGGER.error("duckdb query failed", exc_info=True)
            raise QueryError(
                "the read-only query failed",
                details={"error_type": type(exc).__name__},
            ) from exc
        finally:
            timer.cancel()
            connection.close()

    def _rows(
        self,
        sql: str,
        params: Sequence[Any] = (),
        *,
        timeout_seconds: float | None = None,
    ) -> list[dict[str, Any]]:
        columns, rows = self._fetch(sql, params, timeout_seconds=timeout_seconds)
        return [dict(zip(columns, row)) for row in rows]

    def _one(
        self,
        sql: str,
        params: Sequence[Any] = (),
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any] | None:
        rows = self._rows(sql, params, timeout_seconds=timeout_seconds)
        return rows[0] if rows else None

    def _scalar(
        self,
        sql: str,
        params: Sequence[Any] = (),
        *,
        timeout_seconds: float | None = None,
    ) -> Any:
        _, rows = self._fetch(sql, params, timeout_seconds=timeout_seconds)
        return rows[0][0] if rows else None

    def _require_table(self, table_name: str) -> None:
        if table_name not in self._available_tables:
            raise DatasetUnavailableError(
                "the canonical dataset is not available",
                details={"table": table_name, "missing_tables": self.missing_tables},
            )

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    @property
    def available_tables(self) -> list[str]:
        return sorted(self._available_tables)

    @property
    def missing_tables(self) -> list[str]:
        return sorted(set(TABLE_SCHEMAS) - self._available_tables)

    def dataset_manifest(self) -> dict[str, Any]:
        if self._manifest is None:
            path = self.processed_dir / "dataset_manifest.json"
            if not path.exists():
                return {}
            try:
                self._manifest = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise AnalyticsError(
                    "the dataset manifest could not be read",
                    details={"error_type": type(exc).__name__},
                ) from exc
        return self._manifest

    def dataset_version(self) -> str | None:
        return self.dataset_manifest().get("dataset_version")

    def quality_report(self) -> dict[str, Any]:
        if self._quality_report is None:
            path = self.reports_dir / "dataset_quality_report.json"
            if not path.exists():
                raise AnalyticsError(
                    "the dataset quality report is not available",
                    details={"report": path.name},
                )
            try:
                self._quality_report = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise AnalyticsError(
                    "the dataset quality report could not be read",
                    details={"error_type": type(exc).__name__},
                ) from exc
        return self._quality_report

    def health(self) -> dict[str, Any]:
        try:
            self._scalar("SELECT 1")
            query_ok = True
        except AnalyticsError:
            query_ok = False
        if not query_ok or not self._available_tables:
            database = "unavailable"
        elif self.missing_tables:
            database = "degraded"
        else:
            database = "ok"
        return {
            "database": database,
            "dataset_version": self.dataset_version(),
            "available_tables": len(self._available_tables),
            "missing_tables": self.missing_tables,
        }

    def table_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for table_name in sorted(self._available_tables):
            counts[table_name] = int(
                self._scalar(f'SELECT COUNT(*) FROM "{table_name}"') or 0
            )
        return counts

    # ------------------------------------------------------------------
    # PSI investigations
    # ------------------------------------------------------------------
    def list_investigations(
        self,
        *,
        role: str | None = None,
        query: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> PageResult:
        self._require_table("psi_investigation")
        _validate_page(limit, offset)
        clauses: list[str] = []
        params: list[Any] = []
        if role:
            clauses.append("mvp_role = ?")
            params.append(role)
        if query:
            pattern = _like_pattern(query)
            clauses.append(
                "(accession ILIKE ? ESCAPE '\\' OR acronym ILIKE ? ESCAPE '\\' OR title ILIKE ? ESCAPE '\\')"
            )
            params.extend([pattern, pattern, pattern])
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        total = int(
            self._scalar(f"SELECT COUNT(*) FROM psi_investigation{where}", params) or 0
        )
        rows = self._rows(
            f"SELECT * FROM psi_investigation{where} ORDER BY accession LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        for row in rows:
            row["limitations"] = _json_list(row.pop("limitations_json", None))
        return PageResult(items=rows, total=total, limit=limit, offset=offset)

    def get_investigation(self, accession: str) -> dict[str, Any]:
        self._require_table("psi_investigation")
        _validate_accession(accession)
        row = self._one(
            "SELECT * FROM psi_investigation WHERE accession = ?",
            [accession],
        )
        if row is None:
            raise NotFoundError(
                "investigation is not present in the canonical catalog",
                details={"accession": accession},
            )
        row["limitations"] = _json_list(row.pop("limitations_json", None))
        return row

    # ------------------------------------------------------------------
    # Gas-flame tests
    # ------------------------------------------------------------------
    def _gas_flame_pressure_column(self, accession: str | None) -> tuple[str | None, str | None]:
        if accession == "PSI-10":
            return "pressure_initial_atm", "atm"
        if accession == "PSI-159":
            return "pressure_approx_bar", "bar"
        return None, None

    def list_gas_flame_tests(
        self,
        *,
        accession: str | None = None,
        flame_type: str | None = None,
        fuel: str | None = None,
        oxygen_min: float | None = None,
        oxygen_max: float | None = None,
        pressure_min: float | None = None,
        pressure_max: float | None = None,
        hot_ignition: str | None = None,
        extinction_mode: str | None = None,
        tfp: str | None = None,
        include_qualified: bool = False,
        sort: str = "source_row",
        order: str = "asc",
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> PageResult:
        self._require_table("gas_flame_test")
        _validate_page(limit, offset)
        if accession is not None:
            _validate_accession(accession, GAS_FLAME_ACCESSIONS)
        pressure_column, pressure_unit = self._gas_flame_pressure_column(accession)
        if (pressure_min is not None or pressure_max is not None) and pressure_column is None:
            raise InvalidQueryError(
                "pressure filters require an explicit gas-flame accession because PSI-10 uses atm and PSI-159 uses bar",
                details={"allowed": list(GAS_FLAME_ACCESSIONS)},
            )
        if oxygen_min is not None and oxygen_max is not None and oxygen_min > oxygen_max:
            raise InvalidQueryError("oxygen_min must not exceed oxygen_max")
        if pressure_min is not None and pressure_max is not None and pressure_min > pressure_max:
            raise InvalidQueryError("pressure_min must not exceed pressure_max")
        if order not in {"asc", "desc"}:
            raise InvalidQueryError("order must be asc or desc", details={"order": order})

        sort_map = {
            "source_row": "source_row",
            "oxygen_mole_fraction": "oxygen_mole_fraction",
            "pressure": pressure_column or "pressure_initial_atm",
            "peak_burner_temp_c": "peak_burner_temp_c",
            "observation_id": "observation_id",
        }
        if sort not in sort_map:
            raise InvalidQueryError(
                "sort is not allowed for gas-flame tests",
                details={"sort": sort, "allowed": sorted(sort_map)},
            )

        clauses: list[str] = []
        params: list[Any] = []
        if accession:
            clauses.append("accession = ?")
            params.append(accession)
        else:
            clauses.append(f"accession IN ({_placeholders(len(GAS_FLAME_ACCESSIONS))})")
            params.extend(GAS_FLAME_ACCESSIONS)
        if flame_type:
            clauses.append("flame_type = ?")
            params.append(flame_type)
        if fuel:
            clauses.append("lower(fuel) = lower(?)")
            params.append(fuel)
        if oxygen_min is not None:
            clauses.append("oxygen_mole_fraction >= ?")
            params.append(oxygen_min)
        if oxygen_max is not None:
            clauses.append("oxygen_mole_fraction <= ?")
            params.append(oxygen_max)
        if pressure_column and pressure_min is not None:
            clauses.append(f'"{pressure_column}" >= ?')
            params.append(pressure_min)
        if pressure_column and pressure_max is not None:
            clauses.append(f'"{pressure_column}" <= ?')
            params.append(pressure_max)
        if hot_ignition:
            clauses.append("hot_ignition = ?")
            params.append(hot_ignition)
        if extinction_mode:
            clauses.append("extinction_mode = ?")
            params.append(extinction_mode)
        if tfp:
            clauses.append("tfp_flag = ?")
            params.append(tfp)

        qualified = QUALIFIED_GAS_FLAME_SQL
        base_where = " WHERE " + " AND ".join(clauses)
        if not include_qualified:
            clauses.append(f"NOT ({qualified})")
        where = " WHERE " + " AND ".join(clauses)
        total = int(self._scalar(f"SELECT COUNT(*) FROM gas_flame_test{where}", params) or 0)
        excluded_qualified = 0
        if not include_qualified:
            excluded_qualified = int(
                self._scalar(
                    f"SELECT COUNT(*) FROM gas_flame_test{base_where} AND ({qualified})",
                    params,
                )
                or 0
            )

        columns = ", ".join(f'"{column}"' for column in GAS_FLAME_COLUMNS)
        rows = self._rows(
            f"SELECT {columns} FROM gas_flame_test{where} "
            f'ORDER BY "{sort_map[sort]}" {order.upper()}, observation_id '
            "LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        for row in rows:
            row["quality_flags"] = _json_list(row.get("quality_flags"))
            row["computed_fields"] = list(COMPUTED_GAS_FIELDS)
        page = PageResult(
            items=rows,
            total=total,
            limit=limit,
            offset=offset,
            extra={
                "excluded_qualified_rows": excluded_qualified,
                "pressure_field": pressure_column,
                "pressure_unit": pressure_unit,
            },
        )
        return page

    def gas_flame_facet_rows(self, accession: str | None = None) -> list[dict[str, Any]]:
        """Return the bounded gas-flame columns needed to compute facets.

        The gas-flame table has only 660 real rows. Reading the facet columns
        without pagination is therefore safe and keeps facet counts consistent
        with the list endpoint. Qualification filtering is applied by the
        caller so excluded-row counts can be reported.
        """

        self._require_table("gas_flame_test")
        if accession is not None:
            _validate_accession(accession, GAS_FLAME_ACCESSIONS)
        columns = [
            "accession",
            "flame_type",
            "fuel",
            "oxygen_mole_fraction",
            "oxygen_mole_fraction_initial",
            "oxygen_mole_fraction_before",
            "pressure_initial_atm",
            "pressure_approx_bar",
            "hot_ignition",
            "extinction_mode",
            "tfp_flag",
            "quality_flags",
        ]
        selected = ", ".join(f'"{column}"' for column in columns)
        if accession:
            rows = self._rows(
                f"SELECT {selected} FROM gas_flame_test WHERE accession = ? "
                "ORDER BY source_row, observation_id",
                [accession],
            )
        else:
            rows = self._rows(
                f"SELECT {selected} FROM gas_flame_test "
                f"WHERE accession IN ({_placeholders(len(GAS_FLAME_ACCESSIONS))}) "
                "ORDER BY accession, source_row, observation_id",
                list(GAS_FLAME_ACCESSIONS),
            )
        for row in rows:
            row["quality_flags"] = _json_list(row.get("quality_flags"))
        return rows

    # ------------------------------------------------------------------
    # Deterministic field statistics
    # ------------------------------------------------------------------
    def field_statistics(
        self,
        table_name: str,
        accession: str,
        fields: Sequence[str] | None = None,
        *,
        include_qualified: bool = False,
    ) -> dict[str, Any]:
        """Aggregate allowlisted numeric fields for one canonical table.

        The table name comes from a fixed allowlist, the accession is bound as
        a parameter, and every field name is checked against the canonical
        schema. No SQL text, path, or free-form expression is accepted.
        """

        if table_name not in AGGREGATE_TABLES:
            raise InvalidQueryError(
                "table is not approved for field statistics",
                details={"table": table_name, "allowed": list(AGGREGATE_TABLES)},
            )
        self._require_table(table_name)
        _validate_accession(accession)
        schema = TABLE_SCHEMAS[table_name]
        numeric_fields = [
            field.name
            for field in schema
            if str(field.type).startswith(
                ("int", "uint", "float", "double", "decimal")
            )
        ]
        if fields is None:
            requested = list(numeric_fields)
        else:
            requested = list(dict.fromkeys(fields))
        if not requested:
            raise InvalidQueryError("at least one numeric field is required")
        if len(requested) > MAX_AGGREGATE_FIELDS:
            raise InvalidQueryError(
                "too many fields requested",
                details={"limit": MAX_AGGREGATE_FIELDS},
            )
        invalid = [field for field in requested if field not in numeric_fields]
        if invalid:
            raise InvalidQueryError(
                "field is not an approved numeric canonical field",
                details={
                    "fields": invalid,
                    "allowed": numeric_fields,
                    "table": table_name,
                },
            )

        canonical_rows = int(
            self._scalar(
                f"SELECT COUNT(*) FROM {table_name} WHERE accession = ?",
                [accession],
            )
            or 0
        )
        clauses = ["accession = ?"]
        params: list[Any] = [accession]
        if table_name == "gas_flame_test" and not include_qualified:
            clauses.append(f"NOT ({QUALIFIED_GAS_FLAME_SQL})")
        where = " WHERE " + " AND ".join(clauses)
        included_rows = int(
            self._scalar(f"SELECT COUNT(*) FROM {table_name}{where}", params) or 0
        )
        excluded_qualified = (
            canonical_rows - included_rows
            if table_name == "gas_flame_test" and not include_qualified
            else 0
        )

        select_parts = ['COUNT(*) AS "rows_in_scope"']
        for index, field in enumerate(requested):
            select_parts.extend(
                [
                    f'COUNT("{field}") AS "f{index}_count"',
                    f'MIN("{field}") AS "f{index}_min"',
                    f'MAX("{field}") AS "f{index}_max"',
                    f'AVG("{field}") AS "f{index}_mean"',
                    f'MEDIAN("{field}") AS "f{index}_median"',
                ]
            )
        row = self._one(
            f"SELECT {', '.join(select_parts)} FROM {table_name}{where}", params
        )
        if row is None:
            raise QueryError("field statistics query returned no row")

        fields_payload: dict[str, Any] = {}
        for index, field in enumerate(requested):
            non_null = int(row[f"f{index}_count"] or 0)
            fields_payload[field] = {
                "field": field,
                "status": "available" if non_null else "missing",
                "non_null_count": non_null,
                "missing_count": max(0, included_rows - non_null),
                "min": row[f"f{index}_min"] if non_null else None,
                "max": row[f"f{index}_max"] if non_null else None,
                "mean": row[f"f{index}_mean"] if non_null else None,
                "median": row[f"f{index}_median"] if non_null else None,
            }

        return {
            "table": table_name,
            "accession": accession,
            "canonical_rows": canonical_rows,
            "included_rows": included_rows,
            "excluded_qualified_rows": excluded_qualified,
            "include_qualified": include_qualified,
            "fields": fields_payload,
            "dataset_version": self.dataset_version(),
            "notes": [
                "Missing values are counted as missing, not zero.",
                "Each field is aggregated independently; fields are never merged.",
            ],
        }

    def gas_flame_statistics(
        self,
        accession: str,
        *,
        include_qualified: bool = False,
    ) -> dict[str, Any]:
        """Deterministic counts and numeric summaries for one gas-flame accession."""

        _validate_accession(accession, GAS_FLAME_ACCESSIONS)
        stats = self.field_statistics(
            "gas_flame_test",
            accession,
            GAS_FLAME_STAT_FIELDS,
            include_qualified=include_qualified,
        )
        pressure_field, pressure_unit = self._gas_flame_pressure_column(accession)
        stats["pressure"] = {
            "field": pressure_field,
            "unit": pressure_unit,
            "stats": stats["fields"].get(pressure_field) if pressure_field else None,
        }
        stats["oxygen_fields"] = list(GAS_FLAME_OXYGEN_FIELDS)

        clauses = ["accession = ?"]
        params: list[Any] = [accession]
        if not include_qualified:
            clauses.append(f"NOT ({QUALIFIED_GAS_FLAME_SQL})")
        where = " WHERE " + " AND ".join(clauses)
        stats["flame_type"] = self._rows(
            f"SELECT flame_type AS value, COUNT(*) AS count FROM gas_flame_test"
            f"{where} GROUP BY flame_type ORDER BY count DESC, value",
            params,
        )
        stats["fuel"] = self._rows(
            f"SELECT fuel AS value, COUNT(*) AS count FROM gas_flame_test"
            f"{where} GROUP BY fuel ORDER BY count DESC, value",
            params,
        )
        return stats

    def get_gas_flame_test(self, observation_id: str) -> dict[str, Any]:
        self._require_table("gas_flame_test")
        columns = ", ".join(f'"{column}"' for column in GAS_FLAME_COLUMNS)
        row = self._one(
            f"SELECT {columns} FROM gas_flame_test WHERE observation_id = ?",
            [observation_id],
        )
        if row is None:
            raise NotFoundError(
                "gas-flame observation does not exist",
                details={"observation_id": observation_id},
            )
        row["quality_flags"] = _json_list(row.get("quality_flags"))
        row["computed_fields"] = list(COMPUTED_GAS_FIELDS)
        return row

    # ------------------------------------------------------------------
    # Material tests
    # ------------------------------------------------------------------
    def list_material_tests(
        self,
        *,
        accession: str | None = None,
        material: str | None = None,
        flow_restrictor: str | None = None,
        o2_min: float | None = None,
        o2_max: float | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> PageResult:
        self._require_table("material_test")
        _validate_page(limit, offset)
        if accession is not None:
            _validate_accession(accession, MATERIAL_ACCESSIONS)
        if (o2_min is not None or o2_max is not None) and accession is None:
            raise InvalidQueryError(
                "o2 filters require an explicit accession because PSI-25 and PSI-26 use different oxygen columns and units",
                details={"allowed": list(MATERIAL_ACCESSIONS)},
            )
        if o2_min is not None and o2_max is not None and o2_min > o2_max:
            raise InvalidQueryError("o2_min must not exceed o2_max")

        clauses: list[str] = []
        params: list[Any] = []
        if accession:
            clauses.append("accession = ?")
            params.append(accession)
        else:
            clauses.append(f"accession IN ({_placeholders(len(MATERIAL_ACCESSIONS))})")
            params.extend(MATERIAL_ACCESSIONS)
        if material:
            clauses.append("material ILIKE ? ESCAPE '\\'")
            params.append(_like_pattern(material))
        if flow_restrictor:
            clauses.append("flow_restrictor = ?")
            params.append(flow_restrictor)

        o2_column = None
        if accession == "PSI-25":
            o2_column = "initial_o2_pct"
        elif accession == "PSI-26":
            o2_column = "o2_pct"
        if o2_column and o2_min is not None:
            clauses.append(f'"{o2_column}" >= ?')
            params.append(o2_min)
        if o2_column and o2_max is not None:
            clauses.append(f'"{o2_column}" <= ?')
            params.append(o2_max)

        where = " WHERE " + " AND ".join(clauses)
        total = int(self._scalar(f"SELECT COUNT(*) FROM material_test{where}", params) or 0)
        columns = ", ".join(f'"{column}"' for column in MATERIAL_COLUMNS)
        rows = self._rows(
            f"SELECT {columns} FROM material_test{where} "
            "ORDER BY accession, source_row LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        for row in rows:
            row["quality_flags"] = _json_list(row.get("quality_flags"))
        page = PageResult(
            items=rows,
            total=total,
            limit=limit,
            offset=offset,
            extra={
                "o2_field": o2_column,
                "o2_unit_note": (
                    "PSI-26 labels the oxygen column percent while observed values are fraction-like; the value is preserved as labeled."
                    if accession == "PSI-26"
                    else None
                ),
                "spread_rate_available": False,
            },
        )
        return page

    # ------------------------------------------------------------------
    # Droplet tests
    # ------------------------------------------------------------------
    def list_droplet_tests(
        self,
        *,
        accession: str = "PSI-69",
        fuel: str | None = None,
        pressure_min: float | None = None,
        pressure_max: float | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> PageResult:
        self._require_table("droplet_test")
        _validate_page(limit, offset)
        _validate_accession(accession, DROPLET_ACCESSIONS)
        if pressure_min is not None and pressure_max is not None and pressure_min > pressure_max:
            raise InvalidQueryError("pressure_min must not exceed pressure_max")
        clauses = ["accession = ?"]
        params: list[Any] = [accession]
        if fuel:
            clauses.append("lower(fuel) = lower(?)")
            params.append(fuel)
        if pressure_min is not None:
            clauses.append("ambient_pressure_mm_hg >= ?")
            params.append(pressure_min)
        if pressure_max is not None:
            clauses.append("ambient_pressure_mm_hg <= ?")
            params.append(pressure_max)
        where = " WHERE " + " AND ".join(clauses)
        total = int(self._scalar(f"SELECT COUNT(*) FROM droplet_test{where}", params) or 0)
        columns = ", ".join(f'"{column}"' for column in DROPLET_COLUMNS)
        rows = self._rows(
            f"SELECT {columns} FROM droplet_test{where} ORDER BY source_row LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        for row in rows:
            row["quality_flags"] = _json_list(row.get("quality_flags"))
        return PageResult(items=rows, total=total, limit=limit, offset=offset)

    # ------------------------------------------------------------------
    # Telemetry runs and series
    # ------------------------------------------------------------------
    def list_telemetry_runs(
        self,
        *,
        accession: str = "PSI-100",
        export_kind: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> PageResult:
        self._require_table("telemetry_run")
        _validate_page(limit, offset)
        _validate_accession(accession, TELEMETRY_ACCESSIONS)
        clauses = ["accession = ?"]
        params: list[Any] = [accession]
        if export_kind:
            clauses.append("export_kind = ?")
            params.append(export_kind)
        where = " WHERE " + " AND ".join(clauses)
        total = int(self._scalar(f"SELECT COUNT(*) FROM telemetry_run{where}", params) or 0)
        columns = ", ".join(f'"{column}"' for column in RUN_COLUMNS)
        rows = self._rows(
            f"SELECT {columns} FROM telemetry_run{where} ORDER BY run_id LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        for row in rows:
            row["time_unit"] = "ms"
        return PageResult(items=rows, total=total, limit=limit, offset=offset)

    def _telemetry_run_row(self, run_id: str) -> dict[str, Any]:
        row = self._one(
            "SELECT * FROM telemetry_run WHERE run_id = ?",
            [run_id],
        )
        if row is None:
            raise NotFoundError(
                "telemetry run does not exist",
                details={"run_id": run_id},
            )
        return row

    def get_telemetry_run(self, run_id: str) -> dict[str, Any]:
        self._require_table("telemetry_run")
        row = self._telemetry_run_row(run_id)
        profiles = _json_list(row.pop("channel_profiles_json", None))
        constant_channels = _json_list(row.pop("constant_channels_json", None))
        channels = []
        for profile in profiles:
            channels.append(
                {
                    "channel_name_raw": profile.get("raw_name"),
                    "channel_name_canonical": profile.get("canonical_name"),
                    "unit": profile.get("unit"),
                    "quality_flags": _parse_profile_flags(profile),
                    "point_count": profile.get("count"),
                    "missing_count": profile.get("missing"),
                    "sentinel_count": profile.get("sentinel"),
                    "min": profile.get("min"),
                    "max": profile.get("max"),
                    "constant": bool(profile.get("constant")),
                }
            )
        row["time_unit"] = "ms"
        row["channels"] = sorted(
            channels, key=lambda item: item["channel_name_canonical"] or ""
        )
        row["constant_channels"] = constant_channels
        row["limitations"] = [
            "Telemetry exports are separate runs and are never concatenated.",
            "RelativeSeconds is milliseconds despite the header name.",
            "Uncalibrated raw channels are not physical measurements.",
        ]
        return row

    def get_telemetry_series(
        self,
        run_id: str,
        channels: str | Sequence[str] | None,
        start_ms: float | None,
        end_ms: float | None,
        *,
        max_points: int = DEFAULT_SERIES_POINTS,
    ) -> dict[str, Any]:
        self._require_table("telemetry_run")
        self._require_table("telemetry_point")
        _validate_series_points(max_points)
        run = self._telemetry_run_row(run_id)
        if start_ms is None or end_ms is None:
            raise InvalidQueryError("start_ms and end_ms are required")
        if not math.isfinite(start_ms) or not math.isfinite(end_ms):
            raise InvalidQueryError("start_ms and end_ms must be finite")
        if start_ms >= end_ms:
            raise InvalidQueryError("start_ms must be less than end_ms")
        run_min = run.get("time_min_ms")
        run_max = run.get("time_max_ms")
        if run_min is not None and start_ms < run_min:
            raise InvalidQueryError(
                "start_ms is before the run's valid time range",
                details={"start_ms": start_ms, "run_min_ms": run_min},
            )
        if run_max is not None and end_ms > run_max:
            raise InvalidQueryError(
                "end_ms is after the run's valid time range",
                details={"end_ms": end_ms, "run_max_ms": run_max},
            )
        requested = _parse_channels(channels)
        profiles = _json_list(run.get("channel_profiles_json"))
        channel_index = _channel_index(profiles)
        unknown = [channel for channel in requested if channel not in channel_index]
        if unknown:
            raise InvalidQueryError(
                "one or more channels are not present in this run",
                details={"unknown_channels": unknown},
            )

        channel_placeholders = _placeholders(len(requested))
        base_params: list[Any] = [run_id, start_ms, end_ms, *requested]
        count_sql = (
            "SELECT COUNT(*) FROM ("
            "SELECT relative_time_ms FROM telemetry_point "
            "WHERE run_id = ? AND relative_time_ms >= ? AND relative_time_ms <= ? "
            "AND value IS NOT NULL "
            f"AND channel_name_canonical IN ({channel_placeholders}) "
            "GROUP BY relative_time_ms)"
        )
        point_count = int(self._scalar(count_sql, base_params) or 0)
        if point_count > max_points:
            span = end_ms - start_ms
            suggested = max(1.0, span * max_points / max(point_count, 1))
            raise LimitExceededError(
                "the requested range produces more points than max_points",
                details={
                    "actual_points": point_count,
                    "max_points": max_points,
                    "suggested_max_span_ms": math.floor(suggested),
                },
            )

        select_columns = ", ".join(
            f'MAX(CASE WHEN channel_name_canonical = ? THEN value END) AS "c{position}"'
            for position in range(len(requested))
        )
        sql = (
            f"SELECT relative_time_ms AS time_ms, {select_columns} "
            "FROM telemetry_point "
            "WHERE run_id = ? AND relative_time_ms >= ? AND relative_time_ms <= ? "
            "AND value IS NOT NULL "
            f"AND channel_name_canonical IN ({channel_placeholders}) "
            "GROUP BY relative_time_ms ORDER BY relative_time_ms LIMIT ?"
        )
        params = [*requested, *base_params, max_points + 1]
        rows = self._rows(sql, params)
        if len(rows) > max_points:
            raise LimitExceededError(
                "the requested range produces more points than max_points",
                details={"actual_points": len(rows), "max_points": max_points},
            )

        points = []
        for row in rows:
            point = {"time_ms": row["time_ms"]}
            for position, channel in enumerate(requested):
                point[channel] = row[f"c{position}"]
            points.append(point)

        sentinel_rows = int(
            self._scalar(
                "SELECT COUNT(*) FROM telemetry_point "
                "WHERE run_id = ? AND relative_time_ms >= ? AND relative_time_ms <= ? "
                f"AND channel_name_canonical IN ({channel_placeholders}) "
                "AND quality_flag = 'sentinel'",
                base_params,
            )
            or 0
        )
        source_row_range = self._one(
            "SELECT MIN(source_row) AS min_row, MAX(source_row) AS max_row "
            "FROM telemetry_point "
            "WHERE run_id = ? AND relative_time_ms >= ? AND relative_time_ms <= ? "
            f"AND channel_name_canonical IN ({channel_placeholders})",
            base_params,
        )

        return {
            "run_id": run_id,
            "time_unit": "ms",
            "channels": [
                {
                    "channel_name_raw": channel_index[channel].get("raw_name"),
                    "channel_name_canonical": channel,
                    "unit": channel_index[channel].get("unit"),
                    "quality_flags": _parse_profile_flags(channel_index[channel]),
                }
                for channel in requested
            ],
            "points": points,
            "returned_points": len(points),
            "excluded_sentinel_rows": sentinel_rows,
            "source_row_range": [
                source_row_range.get("min_row") if source_row_range else None,
                source_row_range.get("max_row") if source_row_range else None,
            ],
            "start_ms": start_ms,
            "end_ms": end_ms,
        }

    # ------------------------------------------------------------------
    # Smoke runs and series
    # ------------------------------------------------------------------
    def list_smoke_runs(
        self,
        *,
        accession: str = "PSI-101",
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> PageResult:
        self._require_table("smoke_run")
        _validate_page(limit, offset)
        _validate_accession(accession, SMOKE_ACCESSIONS)
        total = int(
            self._scalar(
                "SELECT COUNT(*) FROM smoke_run WHERE accession = ?",
                [accession],
            )
            or 0
        )
        columns = ", ".join(f'"{column}"' for column in SMOKE_RUN_COLUMNS)
        rows = self._rows(
            f"SELECT {columns} FROM smoke_run WHERE accession = ? "
            "ORDER BY run_id LIMIT ? OFFSET ?",
            [accession, limit, offset],
        )
        for row in rows:
            row["time_unit"] = "s"
        return PageResult(items=rows, total=total, limit=limit, offset=offset)

    def _smoke_run_row(self, run_id: str) -> dict[str, Any]:
        row = self._one("SELECT * FROM smoke_run WHERE run_id = ?", [run_id])
        if row is None:
            raise NotFoundError(
                "smoke run does not exist",
                details={"run_id": run_id},
            )
        return row

    def get_smoke_run(self, run_id: str) -> dict[str, Any]:
        self._require_table("smoke_run")
        row = self._smoke_run_row(run_id)
        profiles = _json_list(row.pop("channel_profiles_json", None))
        row.pop("constant_channels_json", None)
        row.pop("sentinel_channels_json", None)
        channels = []
        for profile in profiles:
            channels.append(
                {
                    "channel_name_raw": profile.get("raw_name"),
                    "channel_name_canonical": profile.get("canonical_name"),
                    "unit": profile.get("unit"),
                    "quality_flags": _parse_profile_flags(profile),
                    "point_count": profile.get("count"),
                    "missing_count": profile.get("missing"),
                    "sentinel_count": profile.get("sentinel"),
                    "min": profile.get("min"),
                    "max": profile.get("max"),
                    "constant": bool(profile.get("constant")),
                }
            )
        row["time_unit"] = "s"
        row["channels"] = sorted(
            channels, key=lambda item: item["channel_name_canonical"] or ""
        )
        row["limitations"] = [
            "Each HKP export is a separate run and is never concatenated.",
            "Detector voltages are uncalibrated and are not obscuration percentages.",
            "P-Trak -999 values are sentinels and are excluded from series.",
        ]
        return row

    def get_smoke_series(
        self,
        run_id: str,
        channels: str | Sequence[str] | None,
        start_s: float | None,
        end_s: float | None,
        *,
        max_points: int = DEFAULT_SERIES_POINTS,
    ) -> dict[str, Any]:
        self._require_table("smoke_run")
        self._require_table("smoke_point")
        _validate_series_points(max_points)
        run = self._smoke_run_row(run_id)
        if start_s is None or end_s is None:
            raise InvalidQueryError("start_s and end_s are required")
        if not math.isfinite(start_s) or not math.isfinite(end_s):
            raise InvalidQueryError("start_s and end_s must be finite")
        if start_s >= end_s:
            raise InvalidQueryError("start_s must be less than end_s")
        run_min = run.get("elapsed_test_time_min_s")
        run_max = run.get("elapsed_test_time_max_s")
        if run_min is not None and start_s < run_min:
            raise InvalidQueryError(
                "start_s is before the run's valid time range",
                details={"start_s": start_s, "run_min_s": run_min},
            )
        if run_max is not None and end_s > run_max:
            raise InvalidQueryError(
                "end_s is after the run's valid time range",
                details={"end_s": end_s, "run_max_s": run_max},
            )
        requested = _parse_channels(channels)
        profiles = _json_list(run.get("channel_profiles_json"))
        channel_index = _channel_index(profiles)
        unknown = [channel for channel in requested if channel not in channel_index]
        if unknown:
            raise InvalidQueryError(
                "one or more channels are not present in this run",
                details={"unknown_channels": unknown},
            )

        channel_placeholders = _placeholders(len(requested))
        base_params: list[Any] = [run_id, start_s, end_s, *requested]
        count_sql = (
            "SELECT COUNT(*) FROM ("
            "SELECT elapsed_test_time_s FROM smoke_point "
            "WHERE run_id = ? AND elapsed_test_time_s >= ? AND elapsed_test_time_s <= ? "
            "AND value IS NOT NULL "
            f"AND channel_name_canonical IN ({channel_placeholders}) "
            "GROUP BY elapsed_test_time_s)"
        )
        point_count = int(self._scalar(count_sql, base_params) or 0)
        if point_count > max_points:
            span = end_s - start_s
            suggested = max(1.0, span * max_points / max(point_count, 1))
            raise LimitExceededError(
                "the requested range produces more points than max_points",
                details={
                    "actual_points": point_count,
                    "max_points": max_points,
                    "suggested_max_span_s": math.floor(suggested),
                },
            )

        select_columns = ", ".join(
            f'MAX(CASE WHEN channel_name_canonical = ? THEN value END) AS "c{position}"'
            for position in range(len(requested))
        )
        sql = (
            f"SELECT elapsed_test_time_s AS time_s, {select_columns} "
            "FROM smoke_point "
            "WHERE run_id = ? AND elapsed_test_time_s >= ? AND elapsed_test_time_s <= ? "
            "AND value IS NOT NULL "
            f"AND channel_name_canonical IN ({channel_placeholders}) "
            "GROUP BY elapsed_test_time_s ORDER BY elapsed_test_time_s LIMIT ?"
        )
        rows = self._rows(sql, [*requested, *base_params, max_points + 1])
        if len(rows) > max_points:
            raise LimitExceededError(
                "the requested range produces more points than max_points",
                details={"actual_points": len(rows), "max_points": max_points},
            )

        points = []
        for row in rows:
            point = {"time_s": row["time_s"]}
            for position, channel in enumerate(requested):
                point[channel] = row[f"c{position}"]
            points.append(point)

        sentinel_rows = int(
            self._scalar(
                "SELECT COUNT(*) FROM smoke_point "
                "WHERE run_id = ? AND elapsed_test_time_s >= ? AND elapsed_test_time_s <= ? "
                f"AND channel_name_canonical IN ({channel_placeholders}) "
                "AND quality_flag = 'sentinel'",
                base_params,
            )
            or 0
        )
        invalid_rows = int(
            self._scalar(
                "SELECT COUNT(*) FROM smoke_point "
                "WHERE run_id = ? AND elapsed_test_time_s >= ? AND elapsed_test_time_s <= ? "
                f"AND channel_name_canonical IN ({channel_placeholders}) "
                "AND quality_flag = 'invalid_indefinite'",
                base_params,
            )
            or 0
        )
        source_row_range = self._one(
            "SELECT MIN(source_row) AS min_row, MAX(source_row) AS max_row "
            "FROM smoke_point "
            "WHERE run_id = ? AND elapsed_test_time_s >= ? AND elapsed_test_time_s <= ? "
            f"AND channel_name_canonical IN ({channel_placeholders})",
            base_params,
        )

        return {
            "run_id": run_id,
            "time_unit": "s",
            "channels": [
                {
                    "channel_name_raw": channel_index[channel].get("raw_name"),
                    "channel_name_canonical": channel,
                    "unit": channel_index[channel].get("unit"),
                    "quality_flags": _parse_profile_flags(channel_index[channel]),
                }
                for channel in requested
            ],
            "points": points,
            "returned_points": len(points),
            "excluded_sentinel_rows": sentinel_rows,
            "excluded_invalid_rows": invalid_rows,
            "source_row_range": [
                source_row_range.get("min_row") if source_row_range else None,
                source_row_range.get("max_row") if source_row_range else None,
            ],
            "start_s": start_s,
            "end_s": end_s,
        }

    # ------------------------------------------------------------------
    # Provenance
    # ------------------------------------------------------------------
    def resolve_provenance(
        self,
        accession: str,
        file_name: str,
        *,
        sheet: str | None = None,
        row: int | None = None,
    ) -> dict[str, Any]:
        _validate_accession(accession)
        if not file_name or any(token in file_name for token in ("/", "\\", "..")):
            raise InvalidQueryError(
                "file must be an exact source file name, not a path",
                details={"file": file_name},
            )
        if row is not None and row < 1:
            raise InvalidQueryError("row must be 1 or greater", details={"row": row})

        record: dict[str, Any] | None = None
        origin = None
        if "experimental_table" in self._available_tables:
            record = self._one(
                "SELECT 'experimental_table' AS origin, table_id, accession, file_name, "
                "file_size_bytes, sha256, retrieved_at, source_url "
                "FROM experimental_table WHERE accession = ? AND file_name = ?",
                [accession, file_name],
            )
            if record:
                origin = "experimental_table"
        if record is None and "psi_file" in self._available_tables:
            record = self._one(
                "SELECT 'psi_file' AS origin, file_id AS table_id, accession, file_name, "
                "file_size_bytes, sha256, retrieved_at, source_url, access_status "
                "FROM psi_file WHERE accession = ? AND file_name = ?",
                [accession, file_name],
            )
            if record:
                origin = "psi_file"
        if record is None:
            raise NotFoundError(
                "source file is not present in the canonical file metadata",
                details={"accession": accession, "file": file_name},
            )

        warnings: list[str] = []
        if not record.get("sha256"):
            warnings.append("checksum_not_available")
        row_tables: list[str] = []
        if row is not None:
            for table_name in PROVENANCE_TABLES:
                if table_name not in self._available_tables:
                    continue
                clauses = ["accession = ?", "source_file = ?", "source_row = ?"]
                params: list[Any] = [accession, file_name, row]
                if sheet and "source_sheet" in TABLE_SCHEMAS[table_name].names:
                    clauses.append("source_sheet = ?")
                    params.append(sheet)
                found = self._scalar(
                    f'SELECT 1 FROM "{table_name}" WHERE '
                    + " AND ".join(clauses)
                    + " LIMIT 1",
                    params,
                )
                if found:
                    row_tables.append(table_name)

        result = {
            "origin": origin,
            "accession": accession,
            "file": file_name,
            "sheet": sheet,
            "sha256": record.get("sha256"),
            "retrieved_at": record.get("retrieved_at"),
            "bytes": record.get("file_size_bytes"),
            "source_url": record.get("source_url"),
            "row": row,
            "row_verified": bool(row_tables) if row is not None else None,
            "row_tables": row_tables,
            "warnings": warnings,
        }
        if record.get("access_status"):
            result["access_status"] = record["access_status"]
        return result

    # ------------------------------------------------------------------
    # Dataset quality
    # ------------------------------------------------------------------
    def dataset_quality(
        self,
        table_names: Sequence[str],
        *,
        accession: str | None = None,
    ) -> dict[str, Any]:
        report = self.quality_report()
        selected = []
        for table_name in table_names:
            entry = report.get("tables", {}).get(table_name)
            if not entry:
                continue
            columns = []
            for column in entry.get("column_missingness", []):
                if (column.get("null_count") or 0) > 0 or (column.get("empty_string_count") or 0) > 0:
                    columns.append(column)
            selected.append(
                {
                    "table_name": entry["table_name"],
                    "rows": entry["rows"],
                    "columns": entry["columns"],
                    "primary_key": entry["primary_key"],
                    "columns_with_missingness": columns,
                }
            )
        point_tables = {
            name: report.get("point_tables", {}).get(name)
            for name in table_names
            if name in report.get("point_tables", {})
        }
        flag_tables = {
            name: report.get("flag_tables", {}).get(name)
            for name in table_names
            if name in report.get("flag_tables", {})
        }
        provenance = {
            name: report.get("provenance", {}).get(name)
            for name in table_names
            if name in report.get("provenance", {})
        }
        issues = []
        for issue in report.get("issues", []):
            details = issue.get("details") or {}
            issue_accession = details.get("accession")
            if accession and issue_accession and issue_accession != accession:
                continue
            issues.append(issue)
        return {
            "report_generated_at": report.get("generated_at"),
            "pipeline_version": report.get("pipeline_version"),
            "status": report.get("status"),
            "summary": report.get("summary"),
            "tables": selected,
            "point_tables": point_tables,
            "flag_tables": flag_tables,
            "provenance": provenance,
            "issues": issues,
        }
