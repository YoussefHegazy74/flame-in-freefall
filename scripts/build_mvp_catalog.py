#!/usr/bin/env python3
"""Build the curated MVP dataset catalog from the generated registry.

The catalog is a human-reviewed view of the machine-readable PSI snapshot. It
does not add measurements or access claims. Every count, size, checksum, and
archive status comes from ``psi_combustion_investigations.json``; the role and
use text comes from this file's curated table and must stay consistent with
``annotations.json``.

Usage
-----
    python scripts/build_mvp_catalog.py
    python scripts/build_mvp_catalog.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "registry" / "psi_combustion_investigations.json"
ANNOTATIONS = ROOT / "data" / "registry" / "annotations.json"
OUTPUT = ROOT / "data" / "registry" / "mvp_dataset_catalog.json"

ROLE_DESCRIPTIONS = {
    "primary": "Directly supports the MVP analysis and interface. Parsed first.",
    "supporting": "Provides material, flow, mission, droplet, or comparison context. Parsed after the primary datasets.",
    "future": "Scientifically relevant but requires a separate format or access audit before use.",
    "context": "Publications, modeling studies, indexes, or small campaign summaries. Not a per-test measurement table.",
}

ARCHIVE_STATUS_DESCRIPTIONS = {
    "available": "The PSI detail endpoint exposes one or more `added` archive files.",
    "experimental_table_only": "No `added` archive files are exposed, but a public experimental summary table is available.",
    "no_public_files": "Neither an `added` archive file nor an experimental summary table is exposed.",
}

CURATED: dict[str, dict[str, Any]] = {
    "PSI-10": {
        "mvp_use": "Primary gas-flame test table for comparing normal and inverse flames across fuel, oxidizer, pressure, stoichiometric mixture fraction, and computed adiabatic flame temperature.",
        "supports": [
            "Normal and inverse flame configurations",
            "C2H4 and C3H8 fuels",
            "Initial and final oxygen mole fraction",
            "Initial, final, and mean pressure in atm",
            "Computed mean stoichiometric mixture fraction and adiabatic flame temperature",
            "Flagged RAMP/RAMPED and LOW O2 qualifier rows",
        ],
        "does_not_support": [
            "Measured flame temperature (Tad is computed)",
            "Time-series telemetry",
            "Flame-spread rate",
            "Raw image or video analysis",
        ],
    },
    "PSI-20": {
        "mvp_use": "Supporting ACME BRE test-day summary for burner size, fuel bottle, oxygen concentration text, and number of flames ignited.",
        "supports": [
            "Burner size context (25 or 50 mm)",
            "Oxygen concentration ranges as published",
            "Flames ignited per test day",
        ],
        "does_not_support": [
            "Per-test flame measurements",
            "Chamber pressure (the notes state it varied but is not identified)",
            "Flame-spread rate",
        ],
    },
    "PSI-21": {
        "mvp_use": "Supporting ACME CLD test-day summary for test type, mass-flow-controller settings, fuel concentration range, and flames ignited.",
        "supports": [
            "Test-day context for methane and ethylene coflow tests",
            "Fuel concentration ranges as published",
            "Flames ignited per test day",
        ],
        "does_not_support": [
            "Per-test flame measurements",
            "Fuel MFC and N2 MFC units (not stated in the header)",
            "Flame-spread rate",
        ],
    },
    "PSI-22": {
        "mvp_use": "Context only. The `added` archive is empty, but PSI publishes a 32-row test-day summary table with test type, mesh polarity, fuel bottle, fuel concentration, flames ignited, and notes. Use it for electric-field test context; it contains no per-test flame measurements.",
        "supports": [
            "Test-day context for the ACME E-FIELD campaign",
            "Mesh polarity and fuel-bottle labels as published",
            "Flame counts per test day",
            "Notes field for anomalies",
        ],
        "does_not_support": [
            "Per-test flame measurements",
            "Time-series telemetry",
            "Flame-spread rate",
            "Any archive file not exposed by PSI",
        ],
    },
    "PSI-23": {
        "mvp_use": "Future. Large ACME s-Flame archive plus an 18-row test-day summary table. The summary supports campaign context; the archive needs a format audit before ingestion.",
        "supports": [
            "Test-day context from the 18-row summary",
            "Archive inventory for future soot and flame-structure work",
        ],
        "does_not_support": [
            "MVP analysis until the archive format is audited",
            "Processed flame-spread or soot measurements from the summary alone",
        ],
    },
    "PSI-25": {
        "mvp_use": "Supporting BASS-II test matrices for material, flow-restrictor, fan/air display, calibrated O2/CO2/CO, radiometer gain, and frame counts. The combined experimental table has 129 rows and 17 columns; the six-sheet workbook has 129 rows and 16 columns. Choose one as canonical, not both.",
        "supports": [
            "Material and sample context",
            "Flow-restrictor and display settings",
            "Calibrated initial and final O2 and CO2",
            "CO with OR over-range and -1 sentinel flags",
            "Video frame counts for archive indexing",
            "Combined 17-column experimental table",
        ],
        "does_not_support": [
            "Processed flame-spread rate",
            "Instantaneous air velocity (Air display is a slow-response display reading)",
            "Calibrated radiometer intensity (gain is uncalibrated)",
            "Treating the combined CSV and the workbook as independent samples",
            "Time-series analysis without the video archive",
        ],
    },
    "PSI-26": {
        "mvp_use": "Supporting BASS test log and as-run matrix for material, flow, oxygen, pressure, CO2, and operator observations. The experimental table is a 122-row, 6-column test log; the as-run matrix is a 130-row, 30-column workbook.",
        "supports": [
            "Material and sample context",
            "As-run O2 percent by volume, pressure in atm, and CO2 in mm Hg",
            "Flow-restrictor and display settings",
            "Operator observations and anomalies",
        ],
        "does_not_support": [
            "Processed flame-spread rate",
            "A clean numeric table without per-column parsing (free text and n/a appear in numeric-looking columns)",
            "Time-series analysis without the video archive",
        ],
    },
    "PSI-39": {
        "mvp_use": "Future. CFI droplet archive plus an 87-row test-condition table with flex number, date, pressure, oxygen, nitrogen, helium, fiber, and fuel. The table supports test-condition context; the raw archive still needs a parser and access audit.",
        "supports": [
            "Test-condition context from the 87-row table",
            "Archive inventory for future droplet analysis",
        ],
        "does_not_support": [
            "Processed droplet-combustion results from the summary alone",
            "MVP analysis until access and format are audited",
        ],
    },
    "PSI-47": {
        "mvp_use": "Context only. DAFT/DAFT-2 documents and a 2-row session table; not a flame-spread dataset.",
        "supports": [
            "Background on dust and aerosol measurement feasibility",
            "P-Trak instrument context for SAME/SAME-R",
        ],
        "does_not_support": [
            "Combustion flame-spread analysis",
            "Quantitative comparison with flame data",
        ],
    },
    "PSI-60": {
        "mvp_use": "Context only. Ground-based computational and experimental analysis of SPICE data sets; one metadata ZIP.",
        "supports": ["Background on SPICE modeling"],
        "does_not_support": ["Direct measurement analysis"],
    },
    "PSI-62": {
        "mvp_use": "Context only. Ground-based flame-spread modeling with flamelet generated manifolds and BASS comparison; one metadata ZIP.",
        "supports": ["Modeling context for BASS flame spread"],
        "does_not_support": ["A processed measurement table"],
    },
    "PSI-68": {
        "mvp_use": "Context only. The `added` archive is empty, but PSI publishes an 8-row test-condition range table listing fuel types, droplet diameters, ambient gas mixtures, oxygen mole fractions, pressures, temperatures, and flow velocities. Ranges are not measurements.",
        "supports": [
            "Experiment condition ranges as published",
            "Fuel and ambient-gas context for FLEX-2",
        ],
        "does_not_support": [
            "Per-test measurements",
            "Means or distributions computed from ranges",
            "Flame-spread rate",
        ],
    },
    "PSI-69": {
        "mvp_use": "Supporting. The `added` archive is empty, but PSI publishes a 274-row droplet-combustion summary table with fuel, ambient pressure and composition, initial droplet diameter, visible flame extinction diameter, burning rate, burn time, and test end. Supports droplet-combustion context; it is not a flame-spread dataset.",
        "supports": [
            "274-row droplet-combustion summary",
            "Fuel and ambient-condition context",
            "Burning rate, burn time, and extinction diameter as published",
            "Comparison context for droplet and gas-flame behavior",
        ],
        "does_not_support": [
            "Flame-spread rate",
            "Raw time series or video",
            "Relabeling `Burning rate; mm` as mm/s without source confirmation",
            "Merging mmHg pressure with atm pressure without conversion",
        ],
    },
    "PSI-98": {
        "mvp_use": "Supporting SAFFIRE-I record for spacecraft fire-safety context, a 4-row sample summary, and image-set documentation. The two telemetry XLSX files listed in the public inventory return HTTP 404.",
        "supports": [
            "Mission and experiment context",
            "4-row sample summary (S1, S2, F1, F2)",
            "Image sets for SAFFIRE-I, subject to archive access",
            "Readme and publications",
        ],
        "does_not_support": [
            "Telemetry analysis from the listed XLSX files (HTTP 404)",
            "Flame-spread rate without image processing",
        ],
    },
    "PSI-99": {
        "mvp_use": "Context only. The `added` archive is empty, but PSI publishes a 15-row sample summary table with material, thickness, flow, oxygen, ignition, burn time, flow direction, 1-g burn length, 1-g spread rate, and camera identifiers. The 1-g spread rate is normal gravity; microgravity columns are incomplete.",
        "supports": [
            "Sample and material context for SAFFIRE-II",
            "1-g comparison values as published",
            "Camera identifiers",
        ],
        "does_not_support": [
            "Microgravity spread rate from the incomplete columns",
            "Treating `1-g Spread Rate` as microgravity data",
            "Raw telemetry or video",
        ],
    },
    "PSI-100": {
        "mvp_use": "Primary SAFFIRE-III telemetry for time-series analysis of the spacecraft fire environment: radiometers, anemometers, igniters, air temperature, pressures, smoke detectors, fan differential pressure, body rates, and accelerations. A 2-row sample summary records the SIBAL fabric samples and camera identifiers.",
        "supports": [
            "1 Hz telemetry channels",
            "Smoke-detector obscuration and scatter voltages",
            "PCM pressure and temperature",
            "Igniter voltage and current",
            "Attitude and acceleration context",
            "Separate raw, cleaned, and XLSX exports",
            "2-row sample summary with SIBAL fabric and camera identifiers",
        ],
        "does_not_support": [
            "Processed flame-spread rate",
            "Calibrated physical concentrations from raw voltages without calibration documentation",
            "Concatenation of the three exports without timestamp reconciliation",
            "Causal claims about material flammability",
        ],
    },
    "PSI-101": {
        "mvp_use": "Primary SAME-R smoke and aerosol housekeeping data for detector response, particle counts, and test-state context, plus a 109-row sample/test table with material, inlet velocity, Rt/R0, duration, and aging times.",
        "supports": [
            "98-channel HKP telemetry for SAME-R runs",
            "P-Trak and DustTrak aerosol channels",
            "ISS and STS detector voltages",
            "Gas plume temperature and sample resistance",
            "Test, sample, and carousel identifiers",
            "109-row sample/test log",
        ],
        "does_not_support": [
            "Flame-spread rate",
            "Material identity from the HKP CSV alone (join test logs)",
            "P-Trak -999 as a concentration",
            "DustTrakA all-zero as a measured zero",
            "Detector voltage as obscuration percentage without calibration",
        ],
    },
    "PSI-102": {
        "mvp_use": "Supporting SAME record for earlier smoke and aerosol analyzed workbooks and test logs, plus an 8-row sample table with material, air flow, weight-loss rate, and aging duration.",
        "supports": [
            "Background and comparison context for SAME-R",
            "Analyzed workbooks and test logs in legacy .xls and .xlsx formats",
            "8-row sample summary",
        ],
        "does_not_support": [
            "Flame-spread rate",
            "A single standardized table across runs",
        ],
    },
    "PSI-106": {
        "mvp_use": "Future. SLICE exposes one 12-row, 2-column experimental table with test date and fuel type; no measured variables.",
        "supports": ["Test dates and fuel types as published"],
        "does_not_support": [
            "Quantitative analysis",
            "Flame liftoff measurements from the summary alone",
        ],
    },
    "PSI-107": {
        "mvp_use": "Future. SPICE provides a 469-row flame-length and airflow table plus raw flame-length, smoke-point, airflow-calibration, and fuel-flow files. The summary supports soot-point context; the raw files need a format audit.",
        "supports": [
            "469-row flame-length and airflow table",
            "Raw calibration and smoke-point files for future analysis",
        ],
        "does_not_support": [
            "MVP analysis until the XLS/XLSX files are audited",
            "A processed smoke-point result table",
        ],
    },
    "PSI-115": {
        "mvp_use": "Context only. Ground-based modeling and simulation of smoke generation using SAME data.",
        "supports": ["Background on SAME smoke modeling"],
        "does_not_support": ["Direct measurement analysis"],
    },
    "PSI-117": {
        "mvp_use": "Context only. Ground-based CFD analysis of cool-flame dynamics under thermo-convective perturbation.",
        "supports": ["Modeling context for cool-flame behavior"],
        "does_not_support": ["Direct measurement analysis"],
    },
    "PSI-142": {
        "mvp_use": "Context only. Eight-row data index linking figures to a reference publication; not a measurement table.",
        "supports": ["Bibliography and figure index"],
        "does_not_support": ["Measurement analysis"],
    },
    "PSI-159": {
        "mvp_use": "Primary gas-flame test table for cool flames, hot ignition, extinction mode, burn time, peak burner temperature, oxygen, pressure, and computed adiabatic flame temperature.",
        "supports": [
            "Normal and inverse flame configurations",
            "Ethane, propane, and butane blends",
            "Hot ignition outcomes",
            "Cool-flame flag with PCI stage text",
            "Extinction mode (SE or FT)",
            "Measured peak burner temperature in C and K",
            "Computed Tad and Zst",
            "TFP categorical flag",
        ],
        "does_not_support": [
            "TFP as a temperature",
            "Merging the C and K peak burner columns without a documented conversion",
            "Treating blank Cool flame? as no",
            "Flame-spread rate",
            "Time-series telemetry",
        ],
    },
}

SPECIAL_ARTIFACTS: dict[str, list[dict[str, Any]]] = {
    "PSI-25": [
        {
            "file_name": "PSI-25_Science Documents_BASS-II_ReadMe.docx",
            "role": "readme",
            "notes": "Defines flow-restrictor codes, fan display scale, air display units, radiometer gain, and calibrated O2/CO2/CO conventions.",
        }
    ],
    "PSI-98": [
        {
            "file_name": "PSI-98_Science Documents_SAFFIRE-I and SAFFIRE-III Readme.docx",
            "role": "readme",
            "notes": "Describes SAFFIRE-I and SAFFIRE-III objectives, SIBAL cloth, flow velocity, and image-set organization.",
        }
    ],
    "PSI-100": [
        {
            "file_name": "PSI-100_Science Documents_SAFFIRE-I and SAFFIRE-III Readme.docx",
            "role": "readme",
            "notes": "Describes SAFFIRE-I and SAFFIRE-III objectives, SIBAL cloth, flow velocity, and image-set organization.",
        }
    ],
    "PSI-101": [
        {
            "file_name": "PSI-101_Reports_SAME-R_Final Report.pdf",
            "role": "report",
            "notes": "SAME-R final report; not a processed table.",
        }
    ],
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def build_catalog(registry: dict[str, Any], annotations: dict[str, Any]) -> dict[str, Any]:
    datasets = []
    role_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}

    for inv in registry["investigations"]:
        accession = inv["accession"]
        curated = CURATED.get(accession)
        if curated is None:
            raise KeyError(f"No curated catalog text for {accession}.")
        annotation = annotations.get(accession, {})
        if annotation.get("mvp_role") != inv["mvp_role"]:
            raise ValueError(
                f"{accession}: registry role {inv['mvp_role']!r} does not match "
                f"annotation role {annotation.get('mvp_role')!r}."
            )

        documented = []
        for table in inv["tabular_files"]:
            if table["file_name"] in (annotation.get("table_stats") or {}):
                documented.append(dict(table))
        documented.extend(SPECIAL_ARTIFACTS.get(accession, []))

        role_counts[inv["mvp_role"]] = role_counts.get(inv["mvp_role"], 0) + 1
        status_counts[inv["archive_status"]] = (
            status_counts.get(inv["archive_status"], 0) + 1
        )

        datasets.append(
            {
                "accession": accession,
                "acronym": inv["acronym"],
                "title": inv["title"],
                "doi": inv["doi"],
                "role": inv["mvp_role"],
                "archive_status": inv["archive_status"],
                "file_count": inv["file_count"],
                "removed_file_count": inv["removed_file_count"],
                "experimental_table_count": inv["experimental_table_count"],
                "experimental_table_only_count": inv[
                    "experimental_table_only_count"
                ],
                "registered_total_bytes": inv["registered_total_bytes"],
                "registered_total_gb_decimal": inv[
                    "registered_total_gb_decimal"
                ],
                "mvp_use": curated["mvp_use"],
                "supports": curated["supports"],
                "does_not_support": curated["does_not_support"],
                "documented_artifacts": documented,
                "experimental_tables": inv["experimental_tables"],
                "limitations": inv["limitations"],
                "access_notes": inv["access_notes"],
            }
        )

    totals = registry["totals"]
    return {
        "schema_version": "1.1.0",
        "snapshot_date": registry["snapshot_date"],
        "source": {
            "registry": "data/registry/psi_combustion_investigations.json",
            "annotations": "data/registry/annotations.json",
            "nasa_psi": "https://psi.nasa.gov/physci/repo",
            "selection_decision": "docs/decisions/0001-mvp-dataset-selection.md",
        },
        "roles": ROLE_DESCRIPTIONS,
        "archive_status": ARCHIVE_STATUS_DESCRIPTIONS,
        "selection_rules": [
            "The record must be a NASA PSI Combustion Science investigation with a public detail endpoint.",
            "The record must expose at least one public artifact, either an `added` file or an `experimentalTable` entry.",
            "A primary dataset must contain a public tabular artifact that supports test-level or time-series analysis.",
            "A dataset is not promoted to primary if its public files are only video, images, documents, metadata, or a small campaign summary.",
            "Cross-dataset comparison is allowed only for semantically equivalent fields in the comparability matrix.",
            "No record is selected to fill a narrative gap; records with only a summary table are reported as `experimental_table_only`.",
        ],
        "totals": {
            "records": len(datasets),
            "role_counts": role_counts,
            "archive_status_counts": status_counts,
            "current_files": totals["file_count"],
            "experimental_table_count": totals["experimental_table_count"],
            "experimental_table_bytes": totals["experimental_table_bytes"],
            "experimental_table_only_count": totals[
                "experimental_table_only_count"
            ],
            "distinct_public_artifacts": totals["distinct_public_artifacts"],
            "registered_total_bytes": totals["registered_total_bytes"],
            "registered_total_gb_decimal": totals[
                "registered_total_gb_decimal"
            ],
        },
        "datasets": datasets,
    }


def check_catalog(catalog: dict[str, Any], path: Path) -> int:
    if not path.exists():
        print(f"No committed catalog at {path}.", file=sys.stderr)
        return 1
    committed = load_json(path)
    if committed != catalog:
        print(
            f"Committed catalog differs from the regenerated catalog at {path}.",
            file=sys.stderr,
        )
        return 1
    print("Committed catalog matches the regenerated catalog.", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare the committed catalog with a regenerated catalog; do not write.",
    )
    args = parser.parse_args()

    registry = load_json(REGISTRY)
    annotations = load_json(ANNOTATIONS)
    catalog = build_catalog(registry, annotations)
    if args.check:
        return check_catalog(catalog, OUTPUT)

    with OUTPUT.open("w", encoding="utf-8") as handle:
        json.dump(catalog, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(
        f"Wrote {OUTPUT} ({len(catalog['datasets'])} datasets, "
        f"{catalog['totals']['distinct_public_artifacts']} distinct public artifacts).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
