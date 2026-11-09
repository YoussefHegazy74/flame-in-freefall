"""HTTP contract tests for the read-only FastAPI application.

The service uses the synthetic canonical dataset from ``conftest`` and the
committed comparability/serving registries. No test asserts a scientific
measurement; comparisons assert the registry decision only.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app import API_PREFIX, create_app
from backend.models import Envelope
from src.analytics.db import AnalyticsDatabase
from src.analytics.registry import load_registries
from src.analytics.service import AnalyticsService

OXYGEN_LEFT = "psi-10-gas-flame.oxygen_mole_fraction"
OXYGEN_RIGHT = "psi-159-gas-flame.oxygen_mole_fraction"
OXYGEN_CONDITIONS = {
    "same_oxygen_basis": True,
    "flame_configuration_documented": True,
}


@pytest.fixture
def client(synthetic_analytics):
    service = AnalyticsService(
        database=synthetic_analytics["db"], bundle=load_registries()
    )
    return TestClient(
        create_app(service=service, cors_origins=["http://example.test"]),
        raise_server_exceptions=False,
    )


def assert_envelope(response, expected_status: int = 200) -> dict:
    assert response.status_code == expected_status, response.text
    payload = response.json()
    Envelope.model_validate(payload)
    assert set(payload) == {"data", "meta", "provenance", "quality"}
    assert payload["meta"]["request_id"]
    assert payload["meta"]["generated_at"]
    assert payload["quality"]["status"] in {
        "verified",
        "partial",
        "blocked",
        "experimental_table_only",
        "not_available",
    }
    return payload


def assert_error(response, expected_status: int, code: str) -> dict:
    assert response.status_code == expected_status, response.text
    payload = response.json()
    assert set(payload) == {"error"}
    assert payload["error"]["code"] == code
    assert payload["error"]["request_id"]
    assert isinstance(payload["error"]["details"], dict)
    return payload


# ----------------------------------------------------------------------
# Envelope, request IDs, and strict query parameters
# ----------------------------------------------------------------------
def test_health_returns_the_shared_envelope(client):
    payload = assert_envelope(client.get(f"{API_PREFIX}/health"))
    assert payload["data"]["status"] == "ok"
    assert payload["data"]["assistant"] == "disabled"
    bundle = load_registries()
    assert payload["data"]["dataset_version"] == bundle.dataset_version
    assert payload["meta"]["dataset_version"] == bundle.dataset_version


def test_health_reports_an_unavailable_dataset(tmp_path):
    processed = tmp_path / "processed"
    processed.mkdir()
    database = AnalyticsDatabase(
        processed_dir=processed, reports_dir=tmp_path, timeout_seconds=5
    )
    service = AnalyticsService(database=database, bundle=load_registries())
    client = TestClient(create_app(service=service), raise_server_exceptions=False)
    payload = assert_envelope(client.get(f"{API_PREFIX}/health"))
    assert payload["data"]["status"] == "unavailable"
    assert payload["data"]["database"] == "unavailable"
    assert payload["quality"]["status"] == "blocked"
    assert "dataset_unavailable" in payload["quality"]["flags"]


def test_request_id_is_echoed_and_generated(client):
    supplied = client.get(
        f"{API_PREFIX}/health", headers={"X-Request-ID": "req_test_abc"}
    )
    assert supplied.headers["X-Request-ID"] == "req_test_abc"
    assert supplied.json()["meta"]["request_id"] == "req_test_abc"

    generated = client.get(f"{API_PREFIX}/health")
    assert generated.headers["X-Request-ID"].startswith("req_")
    assert generated.json()["meta"]["request_id"] == generated.headers["X-Request-ID"]


def test_unknown_query_parameter_is_rejected(client):
    payload = assert_error(
        client.get(f"{API_PREFIX}/health?include_raw=true"), 400, "invalid_query"
    )
    assert payload["error"]["details"]["unknown"] == ["include_raw"]


def test_repeated_query_parameter_is_rejected(client):
    payload = assert_error(
        client.get(f"{API_PREFIX}/gas-flame/tests?limit=1&limit=2"),
        400,
        "invalid_query",
    )
    assert payload["error"]["details"]["repeated"] == ["limit"]


def test_invalid_parameter_types_return_validation_errors(client):
    assert_error(client.get(f"{API_PREFIX}/gas-flame/tests?limit=0"), 422, "validation_error")
    assert_error(
        client.get(f"{API_PREFIX}/gas-flame/tests?limit=201"), 422, "validation_error"
    )
    assert_error(
        client.get(f"{API_PREFIX}/telemetry/runs/run-a/series?channels=x&start_ms=0&end_ms=1&max_points=20001"),
        422,
        "validation_error",
    )
    assert_error(
        client.get(f"{API_PREFIX}/provenance?accession=PSI-10&file=gas.csv&row=0"),
        422,
        "validation_error",
    )


def test_unknown_route_and_method_return_error_envelopes(client):
    assert_error(client.get(f"{API_PREFIX}/not-a-route"), 404, "not_found")
    assert_error(client.post(f"{API_PREFIX}/health"), 405, "method_not_allowed")


# ----------------------------------------------------------------------
# Catalog
# ----------------------------------------------------------------------
def test_investigations_list_and_detail(client):
    payload = assert_envelope(client.get(f"{API_PREFIX}/investigations?limit=1"))
    assert payload["meta"]["page"]["total"] == 2
    assert payload["meta"]["page"]["has_more"] is True
    assert len(payload["data"]) == 1

    detail = assert_envelope(client.get(f"{API_PREFIX}/investigations/PSI-10"))
    assert detail["data"]["accession"] == "PSI-10"
    assert detail["data"]["limitations"] == ["Synthetic fixture only."]
    assert detail["data"]["curated_datasets"][0]["dataset_id"] == "psi-10-gas-flame"

    assert_error(client.get(f"{API_PREFIX}/investigations/PSI-999"), 404, "not_found")
    assert_error(
        client.get(f"{API_PREFIX}/investigations/not-an-accession"), 400, "invalid_query"
    )


def test_dataset_listing_and_use_specific_states(client):
    payload = assert_envelope(client.get(f"{API_PREFIX}/datasets?limit=20"))
    assert payload["meta"]["page"]["total"] == 9
    assert payload["quality"]["status"] == "partial"

    metadata = assert_envelope(
        client.get(f"{API_PREFIX}/datasets?state=metadata_only&use=exploration")
    )
    assert [item["dataset_id"] for item in metadata["data"]] == ["psi-98-metadata"]
    assert metadata["data"][0]["quality_status"] == "experimental_table_only"

    blocked = assert_envelope(
        client.get(f"{API_PREFIX}/datasets/psi-100-telemetry")
    )
    assert blocked["data"]["serving"]["quantitative_comparison"]["state"] == "blocked"

    assert_error(
        client.get(f"{API_PREFIX}/datasets?use=not_a_use"), 400, "invalid_query"
    )
    assert_error(client.get(f"{API_PREFIX}/datasets/not-a-dataset"), 404, "not_found")


def test_dataset_quality_endpoints(client):
    listing = assert_envelope(client.get(f"{API_PREFIX}/datasets/quality"))
    assert len(listing["data"]) == 9
    assert all("quality_status" in item for item in listing["data"])

    detail = assert_envelope(
        client.get(f"{API_PREFIX}/datasets/psi-10-gas-flame/quality")
    )
    assert detail["data"]["report"]["tables"][0]["table_name"] == "gas_flame_test"
    assert detail["data"]["report"]["issues"][0]["code"] == "sentinel_dash"
    assert "sentinel_dash" in detail["quality"]["flags"]


# ----------------------------------------------------------------------
# Measurements and comparability
# ----------------------------------------------------------------------
def test_measurement_listing_and_detail(client):
    listing = assert_envelope(
        client.get(f"{API_PREFIX}/measurements?dataset_id=psi-10-gas-flame&limit=3")
    )
    assert listing["meta"]["page"]["total"] > 3
    assert len(listing["data"]) == 3
    assert all(item["dataset_id"] == "psi-10-gas-flame" for item in listing["data"])

    detail = assert_envelope(
        client.get(f"{API_PREFIX}/measurements/{OXYGEN_LEFT}")
    )
    assert detail["data"]["measurement_id"] == OXYGEN_LEFT
    assert detail["data"]["unit"] == "mole fraction"
    assert detail["data"]["serving"]["state"] in {
        "available",
        "available_with_warnings",
        "restricted",
        "blocked",
        "metadata_only",
    }
    assert detail["data"]["rules"]

    assert_error(
        client.get(f"{API_PREFIX}/measurements/not-a-measurement"),
        404,
        "unknown_measurement",
    )


def test_comparability_summary_is_explicit(client):
    payload = assert_envelope(client.get(f"{API_PREFIX}/comparability"))
    assert payload["data"]["measurement_count"] == 93
    assert payload["data"]["rule_count"] == 60
    assert payload["data"]["concepts"]
    assert len(payload["provenance"]) == len(
        {
            (item.get("kind"), item.get("accession"), item.get("file_name"), item.get("path"), item.get("section"))
            for item in payload["provenance"]
        }
    )


def test_compare_returns_every_comparability_state_with_http_200(client):
    conditions = json.dumps(OXYGEN_CONDITIONS)
    comparable = assert_envelope(
        client.get(
            f"{API_PREFIX}/compare",
            params={"left": OXYGEN_LEFT, "right": OXYGEN_RIGHT, "conditions": conditions},
        )
    )
    assert comparable["data"]["status"] == "comparable"
    assert comparable["quality"]["status"] == "verified"

    conditional = assert_envelope(
        client.get(f"{API_PREFIX}/compare?left={OXYGEN_LEFT}&right={OXYGEN_RIGHT}")
    )
    assert conditional["data"]["status"] == "conditionally_comparable"
    assert conditional["quality"]["status"] == "partial"

    blocked = assert_envelope(
        client.get(
            f"{API_PREFIX}/compare?left=psi-159-gas-flame.peak_burner_temp_c"
            "&right=psi-10-gas-flame.adiabatic_flame_temp_k"
        )
    )
    assert blocked["data"]["status"] == "blocked"
    assert blocked["quality"]["status"] == "blocked"

    not_comparable = assert_envelope(
        client.get(
            f"{API_PREFIX}/compare?left=psi-10-gas-flame.oxygen_mole_fraction"
            "&right=psi-10-gas-flame.pressure_initial_atm"
        )
    )
    assert not_comparable["data"]["status"] == "not_comparable"
    assert not_comparable["quality"]["status"] == "blocked"

    insufficient = assert_envelope(
        client.get(
            f"{API_PREFIX}/compare?left=psi-10-gas-flame.adiabatic_flame_temp_k"
            "&right=psi-159-gas-flame.adiabatic_flame_temp_k"
        )
    )
    assert insufficient["data"]["status"] == "insufficient_metadata"
    assert insufficient["quality"]["status"] == "blocked"


def test_compare_rejects_unknown_measurements_and_bad_conditions(client):
    assert_error(
        client.get(f"{API_PREFIX}/compare?left=nope&right={OXYGEN_RIGHT}"),
        404,
        "unknown_measurement",
    )
    assert_error(
        client.get(
            f"{API_PREFIX}/compare",
            params={"left": OXYGEN_LEFT, "right": OXYGEN_RIGHT, "conditions": "{not json"},
        ),
        400,
        "invalid_query",
    )
    assert_error(
        client.get(
            f"{API_PREFIX}/compare",
            params={"left": OXYGEN_LEFT, "right": OXYGEN_RIGHT, "conditions": "[1, 2]"},
        ),
        400,
        "invalid_query",
    )


# ----------------------------------------------------------------------
# Observation tables
# ----------------------------------------------------------------------
def test_gas_flame_listing_filters_and_detail(client):
    default = assert_envelope(
        client.get(f"{API_PREFIX}/gas-flame/tests?accession=PSI-10")
    )
    assert default["meta"]["page"]["total"] == 1
    assert default["meta"]["page"]["excluded_qualified_rows"] == 1
    assert default["meta"]["page"]["pressure_unit"] == "atm"

    qualified = assert_envelope(
        client.get(
            f"{API_PREFIX}/gas-flame/tests?accession=PSI-10&include_qualified=true"
        )
    )
    assert qualified["meta"]["page"]["total"] == 2

    detail = assert_envelope(
        client.get(f"{API_PREFIX}/gas-flame/tests/g1")
    )
    assert detail["data"]["computed_fields"] == [
        "stoich_mixture_fraction",
        "adiabatic_flame_temp_k",
    ]
    assert "computed" in detail["quality"]["warnings"][0]

    assert_error(
        client.get(f"{API_PREFIX}/gas-flame/tests?pressure_min=0.5"),
        400,
        "invalid_query",
    )
    assert_error(
        client.get(f"{API_PREFIX}/gas-flame/tests?sort=raw_row_json"),
        400,
        "invalid_query",
    )
    assert_error(
        client.get(f"{API_PREFIX}/gas-flame/tests/missing"), 404, "not_found"
    )


def test_material_and_droplet_listings_carry_restrictions(client):
    material = assert_envelope(
        client.get(f"{API_PREFIX}/material/tests?accession=PSI-26")
    )
    assert material["meta"]["page"]["total"] == 1
    assert material["meta"]["page"]["spread_rate_available"] is False
    assert any("percent" in warning for warning in material["quality"]["warnings"])
    assert any("flame-spread rate" in warning for warning in material["quality"]["warnings"])

    droplet = assert_envelope(client.get(f"{API_PREFIX}/droplet/tests"))
    assert droplet["meta"]["page"]["total"] == 2
    assert any("labeled mm" in warning for warning in droplet["quality"]["warnings"])

    assert_error(
        client.get(f"{API_PREFIX}/material/tests?o2_min=0.2"), 400, "invalid_query"
    )


# ----------------------------------------------------------------------
# Telemetry and smoke
# ----------------------------------------------------------------------
def test_telemetry_runs_detail_and_series(client):
    runs = assert_envelope(client.get(f"{API_PREFIX}/telemetry/runs"))
    assert runs["meta"]["page"]["total"] == 2
    assert runs["provenance"][0]["sha256"] == "b" * 64

    run = assert_envelope(client.get(f"{API_PREFIX}/telemetry/runs/run-a"))
    channels = {
        channel["channel_name_canonical"]: channel for channel in run["data"]["channels"]
    }
    assert "uncalibrated" in channels["radiometer_1_raw"]["quality_flags"]

    series = assert_envelope(
        client.get(
            f"{API_PREFIX}/telemetry/runs/run-a/series",
            params={
                "channels": "pcm_air_temp_c,radiometer_1_raw",
                "start_ms": 0,
                "end_ms": 3000,
                "max_points": 100,
            },
        )
    )
    assert series["meta"]["returned_points"] == 3
    assert series["meta"]["excluded_sentinel_rows"] == 1
    assert series["provenance"][0]["row_range"] == [2, 5]
    assert series["quality"]["status"] == "partial"
    assert "ok" not in series["quality"]["flags"]

    assert_error(
        client.get(
            f"{API_PREFIX}/telemetry/runs/run-a/series",
            params={"channels": "pcm_air_temp_c", "start_ms": 0, "end_ms": 3000, "max_points": 2},
        ),
        413,
        "range_too_large",
    )
    assert_error(
        client.get(
            f"{API_PREFIX}/telemetry/runs/run-a/series",
            params={"channels": "missing", "start_ms": 0, "end_ms": 100},
        ),
        400,
        "invalid_query",
    )
    assert_error(
        client.get(f"{API_PREFIX}/telemetry/runs/missing"), 404, "not_found"
    )


def test_smoke_runs_detail_and_series(client):
    runs = assert_envelope(client.get(f"{API_PREFIX}/smoke/runs"))
    assert runs["meta"]["page"]["total"] == 1

    run = assert_envelope(client.get(f"{API_PREFIX}/smoke/runs/smoke-a"))
    channels = {
        channel["channel_name_canonical"]: channel for channel in run["data"]["channels"]
    }
    assert channels["detector_1_v"]["quality_flags"] == ["uncalibrated"]

    series = assert_envelope(
        client.get(
            f"{API_PREFIX}/smoke/runs/smoke-a/series",
            params={
                "channels": "gas_plume_temp_c,detector_1_v,ptrak_count",
                "start_s": 0,
                "end_s": 4,
                "max_points": 100,
            },
        )
    )
    assert series["meta"]["returned_points"] == 3
    assert series["meta"]["excluded_sentinel_rows"] == 1
    assert series["meta"]["excluded_invalid_rows"] == 1
    assert series["provenance"][0]["row_range"] == [2, 6]

    assert_error(
        client.get(
            f"{API_PREFIX}/smoke/runs/smoke-a/series",
            params={"channels": "gas_plume_temp_c", "start_s": 0, "end_s": 4, "max_points": 1},
        ),
        413,
        "range_too_large",
    )


# ----------------------------------------------------------------------
# Provenance
# ----------------------------------------------------------------------
def test_provenance_endpoint(client):
    payload = assert_envelope(
        client.get(
            f"{API_PREFIX}/provenance",
            params={"accession": "PSI-10", "file": "gas.csv", "row": 2},
        )
    )
    assert payload["data"]["origin"] == "experimental_table"
    assert payload["data"]["row_verified"] is True
    assert payload["provenance"][0]["sha256"] == "e" * 64

    missing_checksum = assert_envelope(
        client.get(
            f"{API_PREFIX}/provenance",
            params={"accession": "PSI-100", "file": "telemetry.csv"},
        )
    )
    assert missing_checksum["quality"]["status"] == "partial"
    assert "checksum_not_available" in missing_checksum["quality"]["flags"]

    assert_error(
        client.get(
            f"{API_PREFIX}/provenance",
            params={"accession": "PSI-10", "file": "../gas.csv"},
        ),
        400,
        "invalid_query",
    )
    assert_error(
        client.get(
            f"{API_PREFIX}/provenance",
            params={"accession": "PSI-10", "file": "absent.csv"},
        ),
        404,
        "not_found",
    )


# ----------------------------------------------------------------------
# CORS and OpenAPI
# ----------------------------------------------------------------------
def test_cors_preflight_allows_configured_origin(client):
    response = client.options(
        f"{API_PREFIX}/health",
        headers={
            "Origin": "http://example.test",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://example.test"


def test_cors_preflight_rejects_other_origins(client):
    response = client.options(
        f"{API_PREFIX}/health",
        headers={
            "Origin": "http://evil.test",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_openapi_lists_every_required_endpoint(client):
    schema = client.get(f"{API_PREFIX}/openapi.json").json()
    paths = schema["paths"]
    required = {
        "/health",
        "/meta",
        "/investigations",
        "/investigations/{accession}",
        "/datasets",
        "/datasets/quality",
        "/datasets/{dataset_id}",
        "/datasets/{dataset_id}/quality",
        "/datasets/{dataset_id}/files",
        "/datasets/{dataset_id}/fields",
        "/datasets/{dataset_id}/limitations",
        "/citations",
        "/citations/{citation_id}",
        "/publications",
        "/publications/{publication_id}",
        "/measurements",
        "/measurements/{measurement_id}",
        "/gas-flame/facets",
        "/gas-flame/tests",
        "/gas-flame/tests/{observation_id}",
        "/material/tests",
        "/droplet/tests",
        "/telemetry/runs",
        "/telemetry/runs/{run_id}",
        "/telemetry/runs/{run_id}/series",
        "/smoke/runs",
        "/smoke/runs/{run_id}",
        "/smoke/runs/{run_id}/series",
        "/comparability",
        "/compare",
        "/provenance",
    }
    assert {path.removeprefix(API_PREFIX) for path in paths} == required
    assert "413" in paths[f"{API_PREFIX}/telemetry/runs/{{run_id}}/series"]["get"]["responses"]
    assert "400" in paths[f"{API_PREFIX}/compare"]["get"]["responses"]
    assert client.get(f"{API_PREFIX}/docs").status_code == 200


def test_unhandled_errors_are_not_leaked(synthetic_analytics):
    class ExplodingService(AnalyticsService):
        def health(self, request_id=None):  # noqa: ARG002
            raise RuntimeError("secret path /etc/passwd")

    service = ExplodingService(
        database=synthetic_analytics["db"], bundle=load_registries()
    )
    client = TestClient(create_app(service=service), raise_server_exceptions=False)
    payload = assert_error(client.get(f"{API_PREFIX}/health"), 500, "internal_error")
    assert "secret" not in json.dumps(payload)
    assert "/etc/passwd" not in json.dumps(payload)
