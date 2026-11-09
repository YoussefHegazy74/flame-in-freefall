"""Phase 4 API contract tests over the real canonical dataset.

These tests exercise citations, dataset files, fields, limitations,
publications, gas-flame facets, and the paired-values contract against the
built canonical Parquet tables. They skip when those tables are absent.

Synthetic data is never used here: every count and record below comes from the
committed metadata and the canonical dataset.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app import API_PREFIX, create_app
from backend.models import Envelope
from backend.operations import CacheSettings, RateLimitSettings
from src.analytics.db import AnalyticsDatabase
from src.analytics.registry import load_registries
from src.analytics.service import AnalyticsService
from src.data_pipeline.config import PROCESSED_DIR, REPORTS_DIR

pytestmark = pytest.mark.integration

OXYGEN_LEFT = "psi-10-gas-flame.oxygen_mole_fraction"
OXYGEN_RIGHT = "psi-159-gas-flame.oxygen_mole_fraction"
OXYGEN_CONDITIONS = {
    "same_oxygen_basis": True,
    "flame_configuration_documented": True,
}


def require_canonical_data() -> None:
    required = (
        PROCESSED_DIR / "gas_flame_test.parquet",
        PROCESSED_DIR / "telemetry_point.parquet",
        PROCESSED_DIR / "smoke_point.parquet",
        PROCESSED_DIR / "dataset_manifest.json",
        REPORTS_DIR / "dataset_quality_report.json",
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        pytest.skip("canonical data is not present: " + ", ".join(missing))


@pytest.fixture(scope="module")
def db():
    require_canonical_data()
    return AnalyticsDatabase(timeout_seconds=60)


@pytest.fixture(scope="module")
def service(db):
    return AnalyticsService(database=db, bundle=load_registries())


@pytest.fixture(scope="module")
def client(service):
    return TestClient(
        create_app(
            service=service,
            cache_settings=CacheSettings(max_age_seconds=30),
            rate_limit_settings=RateLimitSettings(enabled=False),
        ),
        raise_server_exceptions=False,
    )


def assert_envelope(response, expected_status: int = 200) -> dict:
    assert response.status_code == expected_status, response.text
    payload = response.json()
    Envelope.model_validate(payload)
    assert set(payload) == {"data", "meta", "provenance", "quality"}
    assert payload["meta"]["request_id"]
    assert payload["meta"]["generated_at"]
    return payload


def assert_no_filesystem_path(payload: dict) -> None:
    serialized = json.dumps(payload)
    assert "/mnt/" not in serialized
    assert "/home/" not in serialized
    assert "data/raw" not in serialized
    assert ".venv" not in serialized
    assert "node_modules" not in serialized


def assert_error(response, expected_status: int, code: str) -> dict:
    assert response.status_code == expected_status, response.text
    payload = response.json()
    assert set(payload) == {"error"}
    assert payload["error"]["code"] == code
    assert payload["error"]["request_id"]
    return payload


# ----------------------------------------------------------------------
# Citations
# ----------------------------------------------------------------------
def test_citation_list_and_detail_are_stable_and_path_free(client):
    listing = assert_envelope(
        client.get(f"{API_PREFIX}/citations?dataset_id=psi-10-gas-flame&limit=200")
    )
    citations = listing["data"]
    assert len(citations) == 2
    assert {item["file"]["name"] for item in citations} == {
        "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
        "PSI-10_Experimental table_Flame Design_Normal Flame.csv",
    }
    for citation in citations:
        assert citation["citation_id"].startswith("cit_f_")
        assert citation["kind"] == "file"
        assert citation["accession"] == "PSI-10"
        assert citation["dataset_ids"] == ["psi-10-gas-flame"]
        assert citation["source"]["source_url"].startswith("https://psi.nasa.gov/")
        assert citation["source"]["sha256"]
        assert citation["verification"]["status"] == "verified"
        assert citation["availability"]["downloadable"] is True
        assert citation["locator"] == {"type": "file", "sheet": None, "row": None}
    assert_no_filesystem_path(listing)

    first = citations[0]
    detail = assert_envelope(
        client.get(f"{API_PREFIX}/citations/{first['citation_id']}")
    )
    assert detail["data"]["citation_id"] == first["citation_id"]
    assert detail["data"]["source"] == first["source"]
    assert detail["data"]["retrieval"] == first["retrieval"]
    assert detail["quality"]["status"] == "verified"
    assert detail["provenance"][0]["file_name"] == first["file"]["name"]

    repeated = assert_envelope(
        client.get(f"{API_PREFIX}/citations/{first['citation_id']}")
    )
    assert repeated["data"] == detail["data"]
    assert repeated["meta"]["request_id"] != detail["meta"]["request_id"]


def test_row_citation_round_trips_from_a_real_row(client):
    rows = assert_envelope(
        client.get(f"{API_PREFIX}/gas-flame/tests?accession=PSI-10&limit=1")
    )["data"]
    row = rows[0]
    assert row["citation_id"].startswith("cit_r_")

    detail = assert_envelope(
        client.get(f"{API_PREFIX}/citations/{row['citation_id']}")
    )["data"]
    assert detail["kind"] == "row"
    assert detail["accession"] == "PSI-10"
    assert detail["file"]["name"] == row["source_file"]
    assert detail["locator"]["type"] == "row"
    assert detail["locator"]["row"] == row["source_row"]
    assert detail["locator"]["row_range"] == [row["source_row"], row["source_row"]]
    assert detail["row_verification"]["row_verified"] is True
    assert detail["dataset_ids"] == ["psi-10-gas-flame"]
    assert detail["verification"]["status"] == "verified"

    provenance = assert_envelope(
        client.get(
            f"{API_PREFIX}/provenance",
            params={
                "accession": row["accession"],
                "file": row["source_file"],
                "row": row["source_row"],
            },
        )
    )
    assert provenance["data"]["citation_id"] == row["citation_id"]
    assert provenance["provenance"][0]["citation_id"] == row["citation_id"]
    assert provenance["provenance"][0]["row_citation_ids"] == [row["citation_id"]]
    assert provenance["provenance"][0]["file_citation_id"].startswith("cit_f_")


def test_unknown_and_malformed_citations_are_rejected(client):
    assert_error(
        client.get(f"{API_PREFIX}/citations/cit_f_deadbeefdeadbeef"),
        404,
        "not_found",
    )
    assert_error(
        client.get(f"{API_PREFIX}/citations/not-a-citation"), 404, "not_found"
    )


# ----------------------------------------------------------------------
# Dataset files
# ----------------------------------------------------------------------
def test_psi98_unavailable_files_are_not_downloadable(client):
    payload = assert_envelope(
        client.get(f"{API_PREFIX}/datasets/psi-98-metadata/files?limit=200")
    )
    data = payload["data"]
    assert data["summary"] == {
        "curated_files": 3,
        "available_files": 1,
        "unavailable_files": 2,
        "downloadable_files": 1,
        "known_unavailable_files": 2,
        "experimental_tables": 1,
    }
    assert data["inventory"]["public_inventory_file_count"] == 74
    assert data["inventory"]["curated_file_count"] == 3
    assert data["inventory"]["not_selected_file_count"] == 71
    assert data["inventory"]["public_experimental_table_count"] == 1

    unavailable = [item for item in data["files"] if not item["downloadable"]]
    assert len(unavailable) == 2
    for item in unavailable:
        assert item["availability"] == "unavailable"
        assert item["availability_reason"]
        assert "404" in item["availability_reason"]
        assert item["download"]["status"] == "known_unavailable"
        assert item["download"]["http_status"] == 404
        assert item["download"]["sha256"] is None
        assert item["verification"]["status"] == "unavailable"
        assert item["source_url"].startswith("https://psi.nasa.gov/")
    assert {item["file_name"] for item in unavailable} == {
        "PSI-98_Raw Data_Saffire-I Sample 1 Sensor Data Complete TM graphs.xlsx",
        "PSI-98_Raw Data_Saffire-I Telemetry Data Good Process Version.xlsx",
    }
    assert "known_unavailable_http_404" in payload["quality"]["flags"]
    assert_no_filesystem_path(payload)

    filtered = assert_envelope(
        client.get(
            f"{API_PREFIX}/datasets/psi-98-metadata/files?availability=unavailable&limit=200"
        )
    )
    assert len(filtered["data"]["files"]) == 2


def test_available_files_carry_verified_checksums(client):
    payload = assert_envelope(
        client.get(f"{API_PREFIX}/datasets/psi-10-gas-flame/files?limit=200")
    )
    files = payload["data"]["files"]
    assert len(files) == 2
    for item in files:
        assert item["availability"] == "available"
        assert item["downloadable"] is True
        assert item["download"]["checksum_match"] is True
        assert item["download"]["sha256"]
        assert item["verification"]["status"] == "verified"
        assert item["download"]["status"] in {"downloaded", "already_present"}


# ----------------------------------------------------------------------
# Dataset fields
# ----------------------------------------------------------------------
def test_fields_carry_verified_source_columns_and_units(client):
    payload = assert_envelope(
        client.get(f"{API_PREFIX}/datasets/psi-10-gas-flame/fields?limit=200")
    )
    fields = {item["canonical_name"]: item for item in payload["data"]["fields"]}
    oxygen = fields["oxygen_mole_fraction"]
    assert oxygen["unit"] == "mole fraction"
    assert oxygen["value_kind"] == "measured"
    assert oxygen["physical_quantity"] == "oxygen_mole_fraction"
    assert oxygen["calibration"]["status"] == "not_applicable"
    assert oxygen["source_columns"] == [
        {
            "raw_column": "XO2",
            "source_file": "PSI-10_Experimental table_Flame Design_Inverse Flame.csv",
            "applies_to": "Inverse flame rows",
        }
    ]
    assert oxygen["integrity"]["status"] == "available"
    assert oxygen["integrity"]["non_null_count"] > 0

    pressure = fields["pressure_initial_atm"]
    assert pressure["unit"] == "atm"
    assert pressure["source_columns"]
    assert {item["raw_column"] for item in pressure["source_columns"]} == {
        "pinit (atm)"
    }
    assert_no_filesystem_path(payload)


def test_empty_registry_field_is_reported_as_missing_not_available(client):
    payload = assert_envelope(
        client.get(f"{API_PREFIX}/datasets/psi-159-gas-flame/fields?limit=200")
    )
    summary = payload["data"]["summary"]
    assert summary["field_count"] == 14
    assert summary["without_canonical_values"] == 1

    field = next(
        item
        for item in payload["data"]["fields"]
        if item["measurement_id"] == "psi-159-gas-flame.pressure_initial_atm"
    )
    assert field["unit"] == "atm"
    assert field["integrity"] == {
        "measurement_id": "psi-159-gas-flame.pressure_initial_atm",
        "checked": True,
        "status": "missing",
        "reason": "no_non_null_values",
        "table": "gas_flame_test",
        "field": "pressure_initial_atm",
        "accession": "PSI-159",
        "total_rows": 333,
        "non_null_count": 0,
        "alternatives": [
            {
                "canonical_field": "pressure_approx_bar",
                "unit": "bar",
                "description": (
                    "PSI-159 reports approximate test pressure in bar. It is not "
                    "an initial pressure in atm and is not interchangeable with one."
                ),
                "evidence": {
                    "kind": "document",
                    "path": "DATA_DICTIONARY.md",
                    "section": "4.3-4.4 PSI-159 ACME CFI-G",
                },
            }
        ],
    }
    assert field["missingness"]["availability"] == "available"
    assert "measurement_has_no_canonical_values" in field["flags"]
    assert field["alternatives"][0]["canonical_field"] == "pressure_approx_bar"
    assert field["alternatives"][0]["unit"] == "bar"


def test_psi98_has_only_a_metadata_measurement(client):
    payload = assert_envelope(
        client.get(f"{API_PREFIX}/datasets/psi-98-metadata/fields?limit=200")
    )
    fields = payload["data"]["fields"]
    assert len(fields) == 1
    field = fields[0]
    assert field["measurement_id"] == "psi-98-metadata.telemetry_sensor_data"
    assert field["value_kind"] == "raw"
    assert field["missingness"]["availability"] == "metadata_only"
    assert field["integrity"]["status"] == "not_checked"
    assert field["integrity"]["reason"] == "no_canonical_tables"
    assert field["comparability"]["status"] == "not_comparable"
    assert field["source_columns"] == []


# ----------------------------------------------------------------------
# Limitations
# ----------------------------------------------------------------------
def test_limitations_cover_required_scientific_issues(client):
    psi26 = assert_envelope(
        client.get(f"{API_PREFIX}/datasets/psi-26-material/limitations?limit=200")
    )["data"]
    assert any(
        item["code"] == "o2_unit_ambiguity"
        and item["category"] == "units"
        and item["scope"] == "dataset"
        for item in psi26["limitations"]
    )

    psi69 = assert_envelope(
        client.get(f"{API_PREFIX}/datasets/psi-69-droplet/limitations?limit=200")
    )["data"]
    assert any(
        item["code"] == "burning_rate_unit_ambiguity"
        and item["category"] == "units"
        for item in psi69["limitations"]
    )

    psi100 = assert_envelope(
        client.get(f"{API_PREFIX}/datasets/psi-100-telemetry/limitations?limit=200")
    )["data"]
    assert any(
        item["code"] == "uncalibrated_channels"
        and item["category"] == "calibration"
        for item in psi100["limitations"]
    )

    psi101 = assert_envelope(
        client.get(f"{API_PREFIX}/datasets/psi-101-smoke/limitations?limit=200")
    )["data"]
    codes = {item["code"] for item in psi101["limitations"]}
    assert {"sentinel_ptrak", "material_join_unresolved"} <= codes

    psi98 = assert_envelope(
        client.get(f"{API_PREFIX}/datasets/psi-98-metadata/limitations?limit=200")
    )["data"]
    unavailable = [
        item
        for item in psi98["limitations"]
        if item["code"] == "known_unavailable_http_404"
    ]
    assert len(unavailable) == 2
    for item in unavailable:
        assert item["scope"] == "file"
        assert item["severity"] == "error"
        assert item["resolution_status"] == "accepted"
        assert item["affected_operations"] == [
            "exploration",
            "quantitative_comparison",
            "time_series",
            "provenance",
        ]
        assert item["evidence"][0]["kind"] == "acquisition_report"


def test_measurement_integrity_limitations_are_explicit(client):
    psi159 = assert_envelope(
        client.get(f"{API_PREFIX}/datasets/psi-159-gas-flame/limitations?limit=200")
    )["data"]
    integrity = [
        item
        for item in psi159["limitations"]
        if item["code"] == "measurement_has_no_canonical_values"
    ]
    assert len(integrity) == 1
    item = integrity[0]
    assert item["scope"] == "measurement"
    assert item["scope_id"] == "psi-159-gas-flame.pressure_initial_atm"
    assert item["severity"] == "error"
    assert item["resolution_status"] == "open"
    assert "0 non-null values" in item["explanation"]
    assert "pressure_approx_bar" in item["explanation"]
    assert item["evidence"][0]["kind"] == "canonical_data"
    assert item["evidence"][0]["non_null_count"] == 0
    assert item["evidence"][0]["total_rows"] == 333

    psi10 = assert_envelope(
        client.get(f"{API_PREFIX}/datasets/psi-10-gas-flame/limitations?limit=200")
    )["data"]
    psi10_integrity = [
        item
        for item in psi10["limitations"]
        if item["code"] == "measurement_has_no_canonical_values"
    ]
    assert len(psi10_integrity) == 1
    assert psi10_integrity[0]["scope_id"] == "psi-10-gas-flame.pressure_approx_bar"


def test_limitation_ids_are_stable_and_filters_are_strict(client):
    first = assert_envelope(
        client.get(f"{API_PREFIX}/datasets/psi-10-gas-flame/limitations?limit=200")
    )["data"]
    second = assert_envelope(
        client.get(f"{API_PREFIX}/datasets/psi-10-gas-flame/limitations?limit=200")
    )["data"]
    assert [item["limitation_id"] for item in first["limitations"]] == [
        item["limitation_id"] for item in second["limitations"]
    ]
    ids = [item["limitation_id"] for item in first["limitations"]]
    assert len(ids) == len(set(ids))

    dataset_scope = assert_envelope(
        client.get(
            f"{API_PREFIX}/datasets/psi-10-gas-flame/limitations?scope=dataset&limit=200"
        )
    )["data"]
    assert dataset_scope["limitations"]
    assert {item["scope"] for item in dataset_scope["limitations"]} == {"dataset"}

    error = client.get(
        f"{API_PREFIX}/datasets/psi-10-gas-flame/limitations?scope=unknown"
    )
    assert error.status_code == 400
    assert error.json()["error"]["code"] == "invalid_query"
    assert error.json()["error"]["details"]["allowed"] == [
        "comparison",
        "dataset",
        "file",
        "measurement",
    ]


# ----------------------------------------------------------------------
# Publications
# ----------------------------------------------------------------------
def test_publications_are_verified_and_do_not_invent_bibliographic_data(client):
    payload = assert_envelope(
        client.get(f"{API_PREFIX}/publications?limit=200")
    )
    data = payload["data"]
    assert data["summary"]["publication_count"] == 299
    assert data["summary"]["with_doi"] == 235
    assert data["summary"]["without_doi"] == 64
    assert data["summary"]["year_available"] is False
    assert data["summary"]["venue_available"] is False
    assert len(data["publications"]) == 200
    assert data["page"]["has_more"] is True

    for publication in data["publications"]:
        assert publication["title"]
        assert publication["year"] is None
        assert publication["venue"] is None
        assert publication["field_status"]["year"] == "not_available_in_registry"
        assert publication["field_status"]["venue"] == "not_available_in_registry"
        assert publication["verification"]["status"] == "registry_verified"
        assert publication["verification"]["unavailable_fields"] == ["year", "venue"]
        assert publication["related_investigations"]
        if publication["doi"]:
            assert publication["doi_url"] == f"https://doi.org/{publication['doi']}"
        else:
            assert publication["doi_url"] is None
    assert "year_not_available" in payload["quality"]["flags"]
    assert "venue_not_available" in payload["quality"]["flags"]


def test_publication_detail_and_investigation_filter(client):
    listing = assert_envelope(
        client.get(f"{API_PREFIX}/publications?accession=PSI-10&limit=200")
    )["data"]
    assert listing["summary"]["publication_count"] > 0
    for publication in listing["publications"]:
        assert any(
            related["accession"] == "PSI-10"
            for related in publication["related_investigations"]
        )

    publication = listing["publications"][0]
    detail = assert_envelope(
        client.get(f"{API_PREFIX}/publications/{publication['publication_id']}")
    )
    assert detail["data"]["publication_id"] == publication["publication_id"]
    assert detail["data"]["title"] == publication["title"]
    assert detail["data"]["year"] is None
    assert detail["data"]["venue"] is None

    by_dataset = assert_envelope(
        client.get(
            f"{API_PREFIX}/publications?dataset_id=psi-10-gas-flame&limit=200"
        )
    )["data"]
    assert by_dataset["summary"]["publication_count"] == listing["summary"][
        "publication_count"
    ]

    assert_error(
        client.get(f"{API_PREFIX}/publications/pub_0000000000000000"),
        404,
        "not_found",
    )
    year_filter = client.get(f"{API_PREFIX}/publications?year=2020")
    assert year_filter.status_code == 400
    assert year_filter.json()["error"]["code"] == "invalid_query"
    assert year_filter.json()["error"]["details"]["reason"] == "not_available_in_registry"


# ----------------------------------------------------------------------
# Facets
# ----------------------------------------------------------------------
def test_gas_flame_facets_preserve_accession_units(client):
    payload = assert_envelope(client.get(f"{API_PREFIX}/gas-flame/facets"))
    data = payload["data"]
    assert data["include_qualified"] is False
    assert data["excluded_qualified_rows"] == 71
    assert data["accessions"] == [
        {
            "accession": "PSI-10",
            "total_rows": 327,
            "included_rows": 256,
            "excluded_qualified_rows": 71,
        },
        {
            "accession": "PSI-159",
            "total_rows": 333,
            "included_rows": 333,
            "excluded_qualified_rows": 0,
        },
    ]

    pressure = {item["accession"]: item for item in data["pressure"]["by_accession"]}
    assert pressure["PSI-10"]["field"] == "pressure_initial_atm"
    assert pressure["PSI-10"]["unit"] == "atm"
    assert pressure["PSI-10"]["count"] == 256
    assert pressure["PSI-159"]["field"] == "pressure_approx_bar"
    assert pressure["PSI-159"]["unit"] == "bar"
    assert pressure["PSI-159"]["count"] == 333
    assert "never combined" in " ".join(data["notes"]).lower()
    assert "not converted or merged" in data["pressure"]["note"].lower()

    oxygen = {item["accession"]: item for item in data["oxygen"]["by_accession"]}
    assert oxygen["PSI-10"]["count"] == 109
    assert oxygen["PSI-159"]["count"] == 154
    initial = {
        item["accession"]: item for item in data["oxygen_initial"]["by_accession"]
    }
    assert initial["PSI-10"]["field"] == "oxygen_mole_fraction_initial"
    assert initial["PSI-159"]["field"] == "oxygen_mole_fraction_before"

    flame_types = {item["value"]: item for item in data["flame_type"]}
    assert flame_types["Normal"]["count"] == 326
    assert flame_types["inverse"]["count"] == 90
    assert flame_types["inverse"]["by_accession"] == {"PSI-159": 90}
    assert all(
        item["count"] == sum(item["by_accession"].values())
        for item in data["fuel"]
    )
    assert_no_filesystem_path(payload)


def test_facets_include_qualified_rows_on_request_and_filter_accession(client):
    payload = assert_envelope(
        client.get(f"{API_PREFIX}/gas-flame/facets?include_qualified=true")
    )["data"]
    assert payload["include_qualified"] is True
    assert payload["excluded_qualified_rows"] == 0
    assert [item["included_rows"] for item in payload["accessions"]] == [327, 333]
    assert any("excluded" in note.lower() for note in payload["notes"]) is False

    psi10 = assert_envelope(
        client.get(f"{API_PREFIX}/gas-flame/facets?accession=PSI-10")
    )["data"]
    assert [item["accession"] for item in psi10["accessions"]] == ["PSI-10"]
    assert [item["accession"] for item in psi10["pressure"]["by_accession"]] == [
        "PSI-10"
    ]


# ----------------------------------------------------------------------
# Paired comparison values
# ----------------------------------------------------------------------
def test_comparable_rule_withholds_values_without_verified_alignment(client):
    payload = assert_envelope(
        client.get(
            f"{API_PREFIX}/compare",
            params={
                "left": OXYGEN_LEFT,
                "right": OXYGEN_RIGHT,
                "conditions": json.dumps(OXYGEN_CONDITIONS),
            },
        )
    )
    data = payload["data"]
    assert data["status"] == "comparable"
    assert data["rule_id"] == "psi10-psi159-oxygen"
    assert data["integrity"]["status"] == "passed"
    paired = data["paired_values"]
    assert paired["available"] is False
    assert paired["status"] == "unavailable"
    assert paired["reason"]["code"] == "no_verified_alignment"
    assert paired["reason"]["rule_id"] == "psi10-psi159-oxygen"
    assert paired["observations"] == []
    assert paired["series"] == []
    assert paired["exclusions"] == []
    assert paired["alignment"]["verified"] is False
    assert paired["dataset_version"] == data["dataset_version"]
    assert paired["provenance"] == data["source_references"]
    assert payload["meta"]["paired_values_available"] is False
    assert payload["meta"]["integrity_status"] == "passed"
    assert payload["quality"]["status"] == "verified"


def test_conditional_rule_without_conditions_returns_no_values(client):
    payload = assert_envelope(
        client.get(
            f"{API_PREFIX}/compare",
            params={"left": OXYGEN_LEFT, "right": OXYGEN_RIGHT},
        )
    )
    data = payload["data"]
    assert data["status"] == "conditionally_comparable"
    paired = data["paired_values"]
    assert paired["available"] is False
    assert paired["reason"]["code"] == "conditions_not_verified"
    assert paired["reason"]["missing_conditions"] == [
        "same_oxygen_basis",
        "flame_configuration_documented",
    ]
    assert paired["observations"] == []
    assert paired["series"] == []


def test_unapproved_comparison_returns_no_values(client):
    payload = assert_envelope(
        client.get(
            f"{API_PREFIX}/compare",
            params={
                "left": "psi-10-gas-flame.oxygen_mole_fraction",
                "right": "psi-25-material.pressure_atm",
            },
        )
    )
    data = payload["data"]
    assert data["status"] in {"not_comparable", "blocked", "insufficient_metadata"}
    assert data["paired_values"]["available"] is False
    assert data["paired_values"]["reason"]["code"] == "comparison_not_approved"
    assert data["paired_values"]["observations"] == []
    assert data["paired_values"]["series"] == []


def test_integrity_failure_blocks_a_registry_approved_comparison(client):
    payload = assert_envelope(
        client.get(
            f"{API_PREFIX}/compare",
            params={
                "left": "psi-10-gas-flame.pressure_initial_atm",
                "right": "psi-159-gas-flame.pressure_initial_atm",
                "conditions": json.dumps(
                    {
                        "same_pressure_basis": True,
                        "flame_configuration_documented": True,
                    }
                ),
            },
        )
    )
    data = payload["data"]
    assert data["status"] == "comparable"
    assert data["integrity"]["status"] == "failed"
    assert data["integrity"]["failures"][0]["measurement_id"] == (
        "psi-159-gas-flame.pressure_initial_atm"
    )
    assert data["paired_values"]["available"] is False
    assert data["paired_values"]["reason"]["code"] == "measurement_unavailable"
    assert data["paired_values"]["observations"] == []
    assert data["paired_values"]["series"] == []
    assert payload["quality"]["status"] == "blocked"
    assert "measurement_unavailable" in payload["quality"]["flags"]
    assert payload["meta"]["paired_values_available"] is False
    assert payload["meta"]["integrity_status"] == "failed"
    assert any(
        "no non-null values" in warning for warning in payload["quality"]["warnings"]
    )


# ----------------------------------------------------------------------
# Response contracts and versioning
# ----------------------------------------------------------------------
def test_phase4_responses_share_version_and_provenance(client, service):
    bundle = load_registries()
    paths = [
        f"{API_PREFIX}/citations?limit=2",
        f"{API_PREFIX}/datasets/psi-10-gas-flame/files?limit=2",
        f"{API_PREFIX}/datasets/psi-10-gas-flame/fields?limit=2",
        f"{API_PREFIX}/datasets/psi-10-gas-flame/limitations?limit=2",
        f"{API_PREFIX}/publications?limit=2",
        f"{API_PREFIX}/gas-flame/facets",
    ]
    for path in paths:
        payload = assert_envelope(client.get(path))
        assert payload["meta"]["dataset_version"] == bundle.dataset_version
        assert payload["provenance"]
        assert payload["meta"]["request_id"].startswith("req_")
