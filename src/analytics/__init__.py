"""Phase 2 analytical layer for Flame in Freefall.

The package is deliberately split into four small pieces:

``catalog``
    Immutable Python definitions of datasets, measurements, and rules. The
    committed JSON registries are generated from this module.
``registry``
    Loaders and validators for the committed JSON registries.
``comparability`` / ``serving``
    Decision engines over the registries.
``db`` / ``service``
    Read-only DuckDB access to canonical Parquet and API-ready result shaping.

Phase 1 modules are not imported here and are never modified by this package.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "2.0.0"
