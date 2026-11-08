import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES = ROOT / "data" / "fixtures" / "csv"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def fixtures_manifest() -> dict:
    return json.loads((ROOT / "data" / "fixtures" / "fixtures_manifest.json").read_text())


@pytest.fixture
def source_factory():
    """Build a SourceFile from a fixture without inventing provenance."""

    from src.data_pipeline.provenance import source_from_path

    def _make(
        path: Path,
        accession: str = "TEST",
        file_name: str | None = None,
        sheet: str | None = None,
    ):
        return source_from_path(
            accession,
            file_name or path.name,
            path,
            source_url=f"https://psi.nasa.gov/example/{accession}/{path.name}",
            retrieved_at="2026-11-09T00:00:00Z",
            sheet=sheet,
        )

    return _make
