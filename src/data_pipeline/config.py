"""Filesystem and pipeline constants.

All paths are resolved from the repository root so that the CLI behaves the
same whether it is invoked from the repository root or from another working
directory.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
REGISTRY_DIR = DATA_DIR / "registry"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = DATA_DIR / "reports"
MANIFESTS_DIR = DATA_DIR / "manifests"
FIXTURES_DIR = DATA_DIR / "fixtures"

REGISTRY_JSON = REGISTRY_DIR / "psi_combustion_investigations.json"
ANNOTATIONS_JSON = REGISTRY_DIR / "annotations.json"
ET_CSV = REGISTRY_DIR / "psi_experimental_tables.csv"
FILE_INVENTORY_CSV = REGISTRY_DIR / "psi_file_inventory.csv"
DOWNLOAD_MANIFEST_JSON = REGISTRY_DIR / "download_manifest.json"
DOWNLOAD_MANIFEST_CSV = MANIFESTS_DIR / "download_manifest.csv"
ET_SCHEMAS_JSON = REGISTRY_DIR / "experimental_table_schemas.json"
CHANNEL_MAPPING_JSON = REGISTRY_DIR / "channel_mapping.json"
CANONICAL_SCHEMA_JSON = REGISTRY_DIR / "canonical_schema.json"

ACQUISITION_REPORT_JSON = REPORTS_DIR / "acquisition_report.json"
VALIDATION_REPORT_JSON = REPORTS_DIR / "validation_report.json"
QUALITY_REPORT_JSON = REPORTS_DIR / "dataset_quality_report.json"
PROCESSING_REPORT_JSON = REPORTS_DIR / "processing_report.json"

PSI_DOWNLOAD_BASE = "https://psi.nasa.gov/geode-py/ws/studies"
PSI_DETAIL_BASE = "https://psi.nasa.gov/geode-py/ws/repo/investigations"

PARSER_VERSION = "1.0.1"
CANONICAL_SCHEMA_VERSION = "1.0.0"
MANIFEST_SCHEMA_VERSION = "1.0.0"
SOURCE_ROW_SCHEMA_VERSION = "1.0.0"

DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_RETRIES = 4
DEFAULT_BACKOFF_SECONDS = 2.0
DEFAULT_RATE_LIMIT_SECONDS = 0.20
DEFAULT_MAX_SINGLE_FILE_BYTES = 50_000_000
DEFAULT_MAX_TOTAL_BYTES = 100_000_000
DEFAULT_MAX_FILES = 100
MIN_FREE_DISK_MULTIPLIER = 1.20


def ensure_directories() -> None:
    """Create the non-committed working directories when needed."""

    for path in (
        RAW_DIR,
        INTERIM_DIR,
        PROCESSED_DIR,
        REPORTS_DIR,
        MANIFESTS_DIR,
        FIXTURES_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
