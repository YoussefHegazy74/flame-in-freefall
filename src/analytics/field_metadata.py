"""Verified field metadata for canonical fields absent from the measurement registry.

The comparability registry is the primary source for units and value kinds.
A few canonical fields are documented in ``DATA_DICTIONARY.md`` but are not
registered as comparison measurements. They still need a unit and a value
kind when they are summarized for exploration. This module supplies only
those documented fallbacks; it never invents a unit or a value kind.

Registry metadata always takes precedence over this fallback.
"""

from __future__ import annotations

from typing import Any

FIELD_METADATA: dict[tuple[str, str], dict[str, Any]] = {
    ("PSI-10", "oxygen_mole_fraction_initial"): {
        "unit": "mole fraction",
        "value_kind": "measured",
        "source": {
            "kind": "document",
            "path": "DATA_DICTIONARY.md",
            "section": "4.1-4.2 PSI-10 ACME Flame Design",
        },
    },
    ("PSI-10", "oxygen_mole_fraction_final"): {
        "unit": "mole fraction",
        "value_kind": "measured",
        "source": {
            "kind": "document",
            "path": "DATA_DICTIONARY.md",
            "section": "4.1-4.2 PSI-10 ACME Flame Design",
        },
    },
    ("PSI-10", "fuel_mole_fraction_initial"): {
        "unit": "mole fraction",
        "value_kind": "measured",
        "source": {
            "kind": "document",
            "path": "DATA_DICTIONARY.md",
            "section": "4.2 PSI-10 ACME Flame Design - inverse flames",
        },
    },
    ("PSI-10", "fuel_mole_fraction_final"): {
        "unit": "mole fraction",
        "value_kind": "measured",
        "source": {
            "kind": "document",
            "path": "DATA_DICTIONARY.md",
            "section": "4.2 PSI-10 ACME Flame Design - inverse flames",
        },
    },
    ("PSI-10", "pressure_final_atm"): {
        "unit": "atm",
        "value_kind": "measured",
        "source": {
            "kind": "document",
            "path": "DATA_DICTIONARY.md",
            "section": "4.1-4.2 PSI-10 ACME Flame Design",
        },
    },
    ("PSI-159", "oxygen_mole_fraction_before"): {
        "unit": "mole fraction",
        "value_kind": "measured",
        "source": {
            "kind": "document",
            "path": "DATA_DICTIONARY.md",
            "section": "4.3 PSI-159 ACME CFI-G - normal flames",
        },
    },
    ("PSI-159", "oxygen_mole_fraction_after"): {
        "unit": "mole fraction",
        "value_kind": "measured",
        "source": {
            "kind": "document",
            "path": "DATA_DICTIONARY.md",
            "section": "4.3 PSI-159 ACME CFI-G - normal flames",
        },
    },
    ("PSI-159", "fuel_mole_fraction_before"): {
        "unit": "mole fraction",
        "value_kind": "measured",
        "source": {
            "kind": "document",
            "path": "DATA_DICTIONARY.md",
            "section": "4.4 PSI-159 ACME CFI-G - inverse flames",
        },
    },
    ("PSI-159", "fuel_mole_fraction_after"): {
        "unit": "mole fraction",
        "value_kind": "measured",
        "source": {
            "kind": "document",
            "path": "DATA_DICTIONARY.md",
            "section": "4.4 PSI-159 ACME CFI-G - inverse flames",
        },
    },
    ("PSI-159", "pressure_approx_bar"): {
        "unit": "bar",
        "value_kind": "measured",
        "source": {
            "kind": "document",
            "path": "DATA_DICTIONARY.md",
            "section": "4.3-4.4 PSI-159 ACME CFI-G",
        },
    },
    ("PSI-159", "pressure_final_atm"): {
        "unit": "atm",
        "value_kind": "measured",
        "source": {
            "kind": "document",
            "path": "DATA_DICTIONARY.md",
            "section": "4.3-4.4 PSI-159 ACME CFI-G",
        },
    },
}


def field_metadata(accession: str, field: str) -> dict[str, Any] | None:
    value = FIELD_METADATA.get((accession.upper(), field))
    return dict(value) if value else None
