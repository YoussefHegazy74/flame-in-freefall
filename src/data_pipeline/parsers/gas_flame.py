"""Parsers for the ACME Flame Design (PSI-10) and CFI-G (PSI-159) tables.

The source tables are wide per-test summaries. Every source field is mapped
explicitly; unknown headers fail closed. ``Tad`` and ``Zst`` are computed
source fields and are labeled as such in the canonical schema. ``TFP`` is a
categorical flag and is never treated as a temperature.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..provenance import SourceFile, observation_id, raw_row_json
from .base import (
    ParseResult,
    RowCountMismatchError,
    add_quality_flag,
    categorical,
    parse_number,
)
from .csv_reader import read_csv_table

PARSER_NAME = "gas_flame"
PARSER_VERSION = "1.0.0"

HEADERS: dict[str, list[str]] = {
    "PSI-10_normal": [
        "Flame Type",
        "Day",
        "Fuel",
        "Test",
        "Xfuel",
        "mfuel (mg/s)",
        "mN2 (mg/s)",
        "mtot (mg/s)",
        "XO2 (init)",
        "XO2 (final)",
        "pinit (atm)",
        "pfinal (atm)",
        "pmean (atm)",
        "mean Zst",
        "Tad (K)",
    ],
    "PSI-10_inverse": [
        "Flame Type",
        "Day",
        "Test",
        "XO2",
        "mO2 (mg/s)",
        "mN2 (mg/s)",
        "mtot (mg/s)",
        "XC2H4 initial",
        "XC2H4 final",
        "pinit (atm)",
        "pfinal (atm)",
        "pmean (atm)",
        "mean Zst",
        "Tad (K)",
    ],
    "PSI-159_normal": [
        "Flame Type",
        "Day",
        "Fuel",
        "Test",
        "Cool flame?",
        " XO2 before test",
        "XO2  after test",
        "approx p (bar)",
        "Xf",
        "mHC (mg/s)",
        "TFP",
        "Tad (K)",
        "Zst",
        "Hot ignition",
        "burn time (sec)",
        "Self-ext or flow term",
        "Peak burner T (C )",
        "Comments",
    ],
    "PSI-159_inverse": [
        "Flame Type",
        "Day",
        "Fuel",
        "Test",
        "Xf  before test",
        "Xf  after test",
        "approx p (bar)",
        "XO2",
        "HC burnrate (mg/s)",
        "O2 flow rate (mg/s)",
        "TFP",
        "Tad (K)",
        "Zst",
        "Hot ignition",
        "burn time (sec)",
        "Self -ext or flow term",
        "Peak burner Temp (C)",
        "Peak burner temp (K)",
        "Color",
        "Comments",
    ],
}

NUMERIC_FIELDS: dict[str, list[str]] = {
    "PSI-10_normal": [
        "fuel_mole_fraction",
        "fuel_mass_flow_mg_s",
        "diluent_mass_flow_mg_s",
        "total_mass_flow_mg_s",
        "oxygen_mole_fraction_initial",
        "oxygen_mole_fraction_final",
        "pressure_initial_atm",
        "pressure_final_atm",
        "pressure_mean_atm",
        "stoich_mixture_fraction",
        "adiabatic_flame_temp_k",
    ],
    "PSI-10_inverse": [
        "oxygen_mole_fraction",
        "oxidizer_mass_flow_mg_s",
        "diluent_mass_flow_mg_s",
        "total_mass_flow_mg_s",
        "fuel_mole_fraction_initial",
        "fuel_mole_fraction_final",
        "pressure_initial_atm",
        "pressure_final_atm",
        "pressure_mean_atm",
        "stoich_mixture_fraction",
        "adiabatic_flame_temp_k",
    ],
    "PSI-159_normal": [
        "oxygen_mole_fraction_before",
        "oxygen_mole_fraction_after",
        "pressure_approx_bar",
        "fuel_mole_fraction",
        "fuel_mass_flow_mg_s",
        "adiabatic_flame_temp_k",
        "stoich_mixture_fraction",
        "burn_time_s",
        "peak_burner_temp_c",
    ],
    "PSI-159_inverse": [
        "fuel_mole_fraction_before",
        "fuel_mole_fraction_after",
        "pressure_approx_bar",
        "oxygen_mole_fraction",
        "fuel_burn_rate_mg_s",
        "oxidizer_mass_flow_mg_s",
        "adiabatic_flame_temp_k",
        "stoich_mixture_fraction",
        "burn_time_s",
        "peak_burner_temp_c",
        "peak_burner_temp_k",
    ],
}

FIELD_MAP: dict[str, dict[str, str]] = {
    "PSI-10_normal": {
        "flame_type": "Flame Type",
        "day": "Day",
        "fuel": "Fuel",
        "test_code": "Test",
        "fuel_mole_fraction": "Xfuel",
        "fuel_mass_flow_mg_s": "mfuel (mg/s)",
        "diluent_mass_flow_mg_s": "mN2 (mg/s)",
        "total_mass_flow_mg_s": "mtot (mg/s)",
        "oxygen_mole_fraction_initial": "XO2 (init)",
        "oxygen_mole_fraction_final": "XO2 (final)",
        "pressure_initial_atm": "pinit (atm)",
        "pressure_final_atm": "pfinal (atm)",
        "pressure_mean_atm": "pmean (atm)",
        "stoich_mixture_fraction": "mean Zst",
        "adiabatic_flame_temp_k": "Tad (K)",
    },
    "PSI-10_inverse": {
        "flame_type": "Flame Type",
        "day": "Day",
        "test_code": "Test",
        "oxygen_mole_fraction": "XO2",
        "oxidizer_mass_flow_mg_s": "mO2 (mg/s)",
        "diluent_mass_flow_mg_s": "mN2 (mg/s)",
        "total_mass_flow_mg_s": "mtot (mg/s)",
        "fuel_mole_fraction_initial": "XC2H4 initial",
        "fuel_mole_fraction_final": "XC2H4 final",
        "pressure_initial_atm": "pinit (atm)",
        "pressure_final_atm": "pfinal (atm)",
        "pressure_mean_atm": "pmean (atm)",
        "stoich_mixture_fraction": "mean Zst",
        "adiabatic_flame_temp_k": "Tad (K)",
    },
    "PSI-159_normal": {
        "flame_type": "Flame Type",
        "day": "Day",
        "fuel": "Fuel",
        "test_code": "Test",
        "cool_flame_flag": "Cool flame?",
        "oxygen_mole_fraction_before": " XO2 before test",
        "oxygen_mole_fraction_after": "XO2  after test",
        "pressure_approx_bar": "approx p (bar)",
        "fuel_mole_fraction": "Xf",
        "fuel_mass_flow_mg_s": "mHC (mg/s)",
        "tfp_flag": "TFP",
        "adiabatic_flame_temp_k": "Tad (K)",
        "stoich_mixture_fraction": "Zst",
        "hot_ignition": "Hot ignition",
        "burn_time_s": "burn time (sec)",
        "extinction_mode": "Self-ext or flow term",
        "peak_burner_temp_c": "Peak burner T (C )",
        "comments": "Comments",
    },
    "PSI-159_inverse": {
        "flame_type": "Flame Type",
        "day": "Day",
        "fuel": "Fuel",
        "test_code": "Test",
        "fuel_mole_fraction_before": "Xf  before test",
        "fuel_mole_fraction_after": "Xf  after test",
        "pressure_approx_bar": "approx p (bar)",
        "oxygen_mole_fraction": "XO2",
        "fuel_burn_rate_mg_s": "HC burnrate (mg/s)",
        "oxidizer_mass_flow_mg_s": "O2 flow rate (mg/s)",
        "tfp_flag": "TFP",
        "adiabatic_flame_temp_k": "Tad (K)",
        "stoich_mixture_fraction": "Zst",
        "hot_ignition": "Hot ignition",
        "burn_time_s": "burn time (sec)",
        "extinction_mode": "Self -ext or flow term",
        "peak_burner_temp_c": "Peak burner Temp (C)",
        "peak_burner_temp_k": "Peak burner temp (K)",
        "color": "Color",
        "comments": "Comments",
    },
}

CATEGORICAL_FIELDS: dict[str, dict[str, tuple[str, ...]]] = {
    "PSI-10_normal": {
        "flame_type": ("",),
        "day": ("",),
        "fuel": ("",),
        "test_code": ("",),
    },
    "PSI-10_inverse": {
        "flame_type": ("",),
        "day": ("",),
        "test_code": ("",),
    },
    "PSI-159_normal": {
        "flame_type": ("",),
        "day": ("",),
        "fuel": ("",),
        "test_code": ("",),
        "cool_flame_flag": ("",),
        "tfp_flag": ("",),
        "hot_ignition": ("",),
        "extinction_mode": ("", "n/a", "none"),
        "comments": ("",),
    },
    "PSI-159_inverse": {
        "flame_type": ("",),
        "day": ("",),
        "fuel": ("",),
        "test_code": ("",),
        "tfp_flag": ("",),
        "hot_ignition": ("",),
        "extinction_mode": ("", "n/a", "none"),
        "color": ("", "n/a", "none"),
        "comments": ("",),
    },
}


@dataclass(frozen=True)
class GasFlameSpec:
    key: str
    accession: str
    file_name: str
    flame_type: str
    expected_physical_rows: int
    expected_data_rows: int


SPECS: dict[tuple[str, str], GasFlameSpec] = {
    ("PSI-10", "PSI-10_Experimental table_Flame Design_Normal Flame.csv"): GasFlameSpec(
        key="PSI-10_normal",
        accession="PSI-10",
        file_name="PSI-10_Experimental table_Flame Design_Normal Flame.csv",
        flame_type="Normal",
        expected_physical_rows=207,
        expected_data_rows=207,
    ),
    ("PSI-10", "PSI-10_Experimental table_Flame Design_Inverse Flame.csv"): GasFlameSpec(
        key="PSI-10_inverse",
        accession="PSI-10",
        file_name="PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
        flame_type="Inverse",
        expected_physical_rows=120,
        expected_data_rows=120,
    ),
    ("PSI-159", "PSI-159_Experimental table_CFI-G_Normal Flames.csv"): GasFlameSpec(
        key="PSI-159_normal",
        accession="PSI-159",
        file_name="PSI-159_Experimental table_CFI-G_Normal Flames.csv",
        flame_type="Normal",
        expected_physical_rows=179,
        expected_data_rows=179,
    ),
    ("PSI-159", "PSI-159_Experimental table_CFI-G_Inverse Flames.csv"): GasFlameSpec(
        key="PSI-159_inverse",
        accession="PSI-159",
        file_name="PSI-159_Experimental table_CFI-G_Inverse Flames.csv",
        flame_type="Inverse",
        expected_physical_rows=1015,
        expected_data_rows=154,
    ),
}


def spec_for(accession: str, file_name: str) -> GasFlameSpec:
    try:
        return SPECS[(accession, file_name)]
    except KeyError as exc:
        raise KeyError(f"no gas-flame parser for {accession} / {file_name}") from exc


def parse_gas_flame(source: SourceFile, spec: GasFlameSpec) -> ParseResult:
    table = read_csv_table(source.path, source, expected_header=HEADERS[spec.key])
    result = ParseResult(
        source=source,
        parser_name=PARSER_NAME,
        parser_version=PARSER_VERSION,
        table_name="gas_flame_test",
        physical_rows=table.physical_rows,
        data_rows=table.data_rows,
        issues=list(table.issues),
    )
    if (table.physical_rows, table.data_rows) != (
        spec.expected_physical_rows,
        spec.expected_data_rows,
    ):
        raise RowCountMismatchError(
            f"{source.file_name}: expected {spec.expected_physical_rows} physical / "
            f"{spec.expected_data_rows} valid rows, found {table.physical_rows} / {table.data_rows}"
        )

    index = {name: position for position, name in enumerate(table.header)}
    numeric_fields = NUMERIC_FIELDS[spec.key]
    categorical_fields = CATEGORICAL_FIELDS[spec.key]

    for source_row, row in table.iter_data_rows():
        flags: list[dict[str, Any]] = []
        record: dict[str, Any] = {
            "observation_id": observation_id(
                source.accession, source.file_name, source.sheet, source_row
            ),
            "accession": source.accession,
            "table_id": f"{source.accession}::{source.file_name}",
            "source_file": source.file_name,
            "source_sheet": source.sheet,
            "source_row": source_row,
            "source_url": source.source_url,
            "source_sha256": source.sha256,
            "retrieved_at": source.retrieved_at,
            "parser_version": PARSER_VERSION,
            "flame_type": spec.flame_type,
        }

        for canonical, raw_name in FIELD_MAP[spec.key].items():
            raw_value = row[index[raw_name]]
            if canonical in numeric_fields:
                parsed = parse_number(raw_value)
                record[canonical] = parsed.value
                add_quality_flag(flags, canonical, raw_name, raw_value, parsed.flag)
            else:
                missing_tokens = categorical_fields.get(canonical, ("",))
                value, flag = categorical(raw_value, missing_tokens=missing_tokens)
                record[canonical] = value
                if flag != "ok":
                    add_quality_flag(flags, canonical, raw_name, raw_value, flag)

        if any(flag["flag"] == "ramped_condition" for flag in flags):
            flags.append(
                {
                    "field": "__row__",
                    "raw_field": "__row__",
                    "token": None,
                    "flag": "has_ramped_condition",
                }
            )
        if any(flag["flag"] == "spreadsheet_error" for flag in flags):
            flags.append(
                {
                    "field": "__row__",
                    "raw_field": "__row__",
                    "token": None,
                    "flag": "has_spreadsheet_error",
                }
            )
        if any(
            flag["flag"] in {"missing", "sentinel_dash"}
            and flag["field"]
            in {
                "oxygen_mole_fraction_final",
                "pressure_final_atm",
                "pressure_mean_atm",
            }
            for flag in flags
        ):
            flags.append(
                {
                    "field": "__row__",
                    "raw_field": "__row__",
                    "token": None,
                    "flag": "has_missing_final_state",
                }
            )

        record["quality_flags"] = json.dumps(flags, ensure_ascii=False)
        record["raw_row_json"] = raw_row_json(table.header, row)
        result.records.append(record)

    result.metadata = {
        "table_key": spec.key,
        "flame_type": spec.flame_type,
        "column_count": len(table.header),
        "encoding": table.encoding,
        "encoding_fallback": table.encoding_fallback,
        "expected_physical_rows": spec.expected_physical_rows,
        "expected_data_rows": spec.expected_data_rows,
        "tfp_semantics": "categorical Yes/No flag; not a temperature",
        "tad_zst_semantics": "computed source fields; not measured",
    }
    return result
