"""Read-only FastAPI application for Flame in Freefall Phase 2.

The app exposes named queries only. It does not accept table names, file paths,
SQL, or arbitrary filter expressions. Every request is bounded, and every
successful response uses the shared envelope from ``API_DOCUMENTATION.md``.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from typing import Annotated, Any

from fastapi import APIRouter, FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import TypeAdapter, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.models import Envelope, ErrorEnvelope
from src.analytics.db import (
    DEFAULT_PAGE_SIZE,
    DEFAULT_SERIES_POINTS,
    MAX_PAGE_SIZE,
    MAX_SERIES_CHANNELS,
    MAX_SERIES_POINTS,
)
from src.analytics.errors import AnalyticsError, InvalidQueryError
from src.analytics.logging import get_logger
from src.analytics.service import AnalyticsService

LOGGER = get_logger("flame.api")

API_PREFIX = "/api/v1"
CONDITION_ADAPTER = TypeAdapter(dict[str, bool | None])

Limit = Annotated[
    int,
    Query(ge=1, le=MAX_PAGE_SIZE, description=f"Page size (maximum {MAX_PAGE_SIZE})."),
]
Offset = Annotated[int, Query(ge=0, description="Zero-based result offset.")]
Use = Annotated[
    str,
    Query(description="Serving use: exploration, quantitative_comparison, time_series, or provenance."),
]

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorEnvelope, "description": "Invalid query."},
    404: {"model": ErrorEnvelope, "description": "Resource not found."},
    413: {"model": ErrorEnvelope, "description": "Requested range or page is too large."},
    422: {"model": ErrorEnvelope, "description": "Request validation failed."},
    500: {"model": ErrorEnvelope, "description": "Internal error."},
    503: {"model": ErrorEnvelope, "description": "Query timeout or unavailable dependency."},
}


class StrictQueryRoute(APIRoute):
    """Reject query parameters that the endpoint did not declare."""

    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            allowed = {parameter.alias for parameter in self.dependant.query_params}
            repeated = [
                key
                for key in request.query_params.keys()
                if len(request.query_params.getlist(key)) > 1
            ]
            unknown = sorted(set(request.query_params.keys()) - allowed)
            if repeated or unknown:
                raise InvalidQueryError(
                    "unknown or repeated query parameters are not allowed",
                    details={
                        "unknown": unknown,
                        "repeated": sorted(repeated),
                        "allowed": sorted(allowed),
                    },
                )
            return await original(request)

        return handler


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req_" + secrets.token_hex(12))


def _cors_origins() -> list[str]:
    raw = os.environ.get("FLAME_CORS_ORIGINS")
    if raw is None:
        return ["http://localhost:3000", "http://localhost:5173"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _parse_conditions(value: str | None) -> dict[str, bool | None] | None:
    if value is None or value == "":
        return None
    try:
        parsed = CONDITION_ADAPTER.validate_json(value)
    except ValidationError as exc:
        raise InvalidQueryError(
            "conditions must be a JSON object mapping condition keys to true, false, or null",
            details={"errors": exc.errors(include_url=False)},
        ) from exc
    return parsed


def create_app(
    service: AnalyticsService | None = None,
    *,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """Build the API. Passing a service is useful for isolated contract tests."""

    application = FastAPI(
        title="Flame in Freefall API",
        version="2.0.0",
        description=(
            "Read-only access to the curated NASA PSI combustion datasets, "
            "serving states, quality warnings, and comparability decisions."
        ),
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    application.state.service = service or AnalyticsService()

    origins = _cors_origins() if cors_origins is None else cors_origins
    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "HEAD", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
            max_age=600,
        )

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID") or (
            "req_" + secrets.token_hex(12)
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @application.exception_handler(AnalyticsError)
    async def analytics_error_handler(request: Request, exc: AnalyticsError):
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": _request_id(request),
                }
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        details = []
        for error in exc.errors():
            details.append(
                {
                    "location": list(error.get("loc", [])),
                    "message": error.get("msg", "invalid value"),
                    "type": error.get("type", "validation_error"),
                }
            )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "request validation failed",
                    "details": {"errors": details},
                    "request_id": _request_id(request),
                }
            },
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        codes = {
            404: "not_found",
            405: "method_not_allowed",
            400: "invalid_query",
            413: "range_too_large",
        }
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": codes.get(exc.status_code, "http_error"),
                    "message": str(exc.detail),
                    "details": {},
                    "request_id": _request_id(request),
                }
            },
        )

    @application.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        LOGGER.error("unhandled API error", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "an unexpected server error occurred",
                    "details": {},
                    "request_id": _request_id(request),
                }
            },
        )

    router = APIRouter(
        prefix=API_PREFIX,
        route_class=StrictQueryRoute,
        responses=ERROR_RESPONSES,
    )

    def svc(request: Request) -> AnalyticsService:
        return request.app.state.service

    @router.get("/health", response_model=Envelope, tags=["health"])
    def health(request: Request) -> dict[str, Any]:
        return svc(request).health(request_id=_request_id(request))

    @router.get("/meta", response_model=Envelope, tags=["health"])
    def meta(request: Request) -> dict[str, Any]:
        return svc(request).meta(request_id=_request_id(request))

    @router.get("/investigations", response_model=Envelope, tags=["catalog"])
    def list_investigations(
        request: Request,
        role: str | None = Query(default=None, description="Curated MVP role."),
        q: str | None = Query(default=None, description="Search accession, acronym, or title."),
        limit: Limit = DEFAULT_PAGE_SIZE,
        offset: Offset = 0,
    ) -> dict[str, Any]:
        return svc(request).list_investigations(
            role=role,
            query=q,
            limit=limit,
            offset=offset,
            request_id=_request_id(request),
        )

    @router.get("/investigations/{accession}", response_model=Envelope, tags=["catalog"])
    def get_investigation(
        request: Request,
        accession: str = Path(description="NASA PSI accession such as PSI-159."),
    ) -> dict[str, Any]:
        return svc(request).get_investigation(
            accession, request_id=_request_id(request)
        )

    @router.get("/datasets/quality", response_model=Envelope, tags=["quality"])
    def list_dataset_quality(request: Request) -> dict[str, Any]:
        return svc(request).list_dataset_quality(request_id=_request_id(request))

    @router.get("/datasets", response_model=Envelope, tags=["catalog"])
    def list_datasets(
        request: Request,
        family: str | None = Query(default=None, description="Experiment family."),
        accession: str | None = Query(default=None, description="NASA PSI accession."),
        state: str | None = Query(default=None, description="Serving state filter."),
        use: Use = "exploration",
        limit: Limit = DEFAULT_PAGE_SIZE,
        offset: Offset = 0,
    ) -> dict[str, Any]:
        return svc(request).list_datasets(
            family=family,
            accession=accession,
            state=state,
            use=use,
            limit=limit,
            offset=offset,
            request_id=_request_id(request),
        )

    @router.get("/datasets/{dataset_id}", response_model=Envelope, tags=["catalog"])
    def get_dataset(
        request: Request,
        dataset_id: str = Path(description="Curated dataset identifier."),
    ) -> dict[str, Any]:
        return svc(request).get_dataset(dataset_id, request_id=_request_id(request))

    @router.get("/datasets/{dataset_id}/quality", response_model=Envelope, tags=["quality"])
    def get_dataset_quality(request: Request, dataset_id: str) -> dict[str, Any]:
        return svc(request).get_dataset_quality(
            dataset_id, request_id=_request_id(request)
        )

    @router.get("/measurements", response_model=Envelope, tags=["measurements"])
    def list_measurements(
        request: Request,
        accession: str | None = Query(default=None),
        family: str | None = Query(default=None),
        dataset_id: str | None = Query(default=None),
        comparison_status: str | None = Query(default=None),
        serving_state: str | None = Query(default=None),
        use: Use = "exploration",
        limit: Limit = DEFAULT_PAGE_SIZE,
        offset: Offset = 0,
    ) -> dict[str, Any]:
        return svc(request).list_measurements(
            accession=accession,
            family=family,
            dataset_id=dataset_id,
            comparison_status=comparison_status,
            serving_state=serving_state,
            use=use,
            limit=limit,
            offset=offset,
            request_id=_request_id(request),
        )

    @router.get("/measurements/{measurement_id}", response_model=Envelope, tags=["measurements"])
    def get_measurement(
        request: Request,
        measurement_id: str,
        use: Use = "exploration",
    ) -> dict[str, Any]:
        return svc(request).get_measurement(
            measurement_id, use=use, request_id=_request_id(request)
        )

    @router.get("/gas-flame/tests", response_model=Envelope, tags=["gas-flame"])
    def list_gas_flame_tests(
        request: Request,
        accession: str | None = Query(default=None),
        flame_type: str | None = Query(default=None),
        fuel: str | None = Query(default=None),
        oxygen_min: float | None = Query(default=None),
        oxygen_max: float | None = Query(default=None),
        pressure_min: float | None = Query(default=None),
        pressure_max: float | None = Query(default=None),
        hot_ignition: str | None = Query(default=None),
        extinction_mode: str | None = Query(default=None),
        tfp: str | None = Query(default=None),
        include_qualified: bool = Query(default=False),
        sort: str = Query(default="source_row"),
        order: str = Query(default="asc", pattern="^(asc|desc)$"),
        limit: Limit = DEFAULT_PAGE_SIZE,
        offset: Offset = 0,
    ) -> dict[str, Any]:
        return svc(request).list_gas_flame_tests(
            accession=accession,
            flame_type=flame_type,
            fuel=fuel,
            oxygen_min=oxygen_min,
            oxygen_max=oxygen_max,
            pressure_min=pressure_min,
            pressure_max=pressure_max,
            hot_ignition=hot_ignition,
            extinction_mode=extinction_mode,
            tfp=tfp,
            include_qualified=include_qualified,
            sort=sort,
            order=order,
            limit=limit,
            offset=offset,
            request_id=_request_id(request),
        )

    @router.get("/gas-flame/tests/{observation_id}", response_model=Envelope, tags=["gas-flame"])
    def get_gas_flame_test(request: Request, observation_id: str) -> dict[str, Any]:
        return svc(request).get_gas_flame_test(
            observation_id, request_id=_request_id(request)
        )

    @router.get("/material/tests", response_model=Envelope, tags=["material"])
    def list_material_tests(
        request: Request,
        accession: str | None = Query(default=None),
        material: str | None = Query(default=None),
        flow_restrictor: str | None = Query(default=None),
        o2_min: float | None = Query(default=None),
        o2_max: float | None = Query(default=None),
        limit: Limit = DEFAULT_PAGE_SIZE,
        offset: Offset = 0,
    ) -> dict[str, Any]:
        return svc(request).list_material_tests(
            accession=accession,
            material=material,
            flow_restrictor=flow_restrictor,
            o2_min=o2_min,
            o2_max=o2_max,
            limit=limit,
            offset=offset,
            request_id=_request_id(request),
        )

    @router.get("/droplet/tests", response_model=Envelope, tags=["droplet"])
    def list_droplet_tests(
        request: Request,
        accession: str = Query(default="PSI-69"),
        fuel: str | None = Query(default=None),
        pressure_min: float | None = Query(default=None),
        pressure_max: float | None = Query(default=None),
        limit: Limit = DEFAULT_PAGE_SIZE,
        offset: Offset = 0,
    ) -> dict[str, Any]:
        return svc(request).list_droplet_tests(
            accession=accession,
            fuel=fuel,
            pressure_min=pressure_min,
            pressure_max=pressure_max,
            limit=limit,
            offset=offset,
            request_id=_request_id(request),
        )

    @router.get("/telemetry/runs", response_model=Envelope, tags=["telemetry"])
    def list_telemetry_runs(
        request: Request,
        accession: str = Query(default="PSI-100"),
        export_kind: str | None = Query(default=None),
        limit: Limit = DEFAULT_PAGE_SIZE,
        offset: Offset = 0,
    ) -> dict[str, Any]:
        return svc(request).list_telemetry_runs(
            accession=accession,
            export_kind=export_kind,
            limit=limit,
            offset=offset,
            request_id=_request_id(request),
        )

    @router.get("/telemetry/runs/{run_id}", response_model=Envelope, tags=["telemetry"])
    def get_telemetry_run(request: Request, run_id: str) -> dict[str, Any]:
        return svc(request).get_telemetry_run(
            run_id, request_id=_request_id(request)
        )

    @router.get("/telemetry/runs/{run_id}/series", response_model=Envelope, tags=["telemetry"])
    def get_telemetry_series(
        request: Request,
        run_id: str,
        channels: str = Query(description="Comma-separated canonical channel names."),
        start_ms: float = Query(description="Inclusive start in milliseconds."),
        end_ms: float = Query(description="Inclusive end in milliseconds."),
        max_points: int = Query(default=DEFAULT_SERIES_POINTS, ge=1, le=MAX_SERIES_POINTS),
    ) -> dict[str, Any]:
        return svc(request).get_telemetry_series(
            run_id,
            channels,
            start_ms,
            end_ms,
            max_points=max_points,
            request_id=_request_id(request),
        )

    @router.get("/smoke/runs", response_model=Envelope, tags=["smoke"])
    def list_smoke_runs(
        request: Request,
        accession: str = Query(default="PSI-101"),
        limit: Limit = DEFAULT_PAGE_SIZE,
        offset: Offset = 0,
    ) -> dict[str, Any]:
        return svc(request).list_smoke_runs(
            accession=accession,
            limit=limit,
            offset=offset,
            request_id=_request_id(request),
        )

    @router.get("/smoke/runs/{run_id}", response_model=Envelope, tags=["smoke"])
    def get_smoke_run(request: Request, run_id: str) -> dict[str, Any]:
        return svc(request).get_smoke_run(run_id, request_id=_request_id(request))

    @router.get("/smoke/runs/{run_id}/series", response_model=Envelope, tags=["smoke"])
    def get_smoke_series(
        request: Request,
        run_id: str,
        channels: str = Query(description="Comma-separated canonical channel names."),
        start_s: float = Query(description="Inclusive start in elapsed seconds."),
        end_s: float = Query(description="Inclusive end in elapsed seconds."),
        max_points: int = Query(default=DEFAULT_SERIES_POINTS, ge=1, le=MAX_SERIES_POINTS),
    ) -> dict[str, Any]:
        return svc(request).get_smoke_series(
            run_id,
            channels,
            start_s,
            end_s,
            max_points=max_points,
            request_id=_request_id(request),
        )

    @router.get("/comparability", response_model=Envelope, tags=["comparability"])
    def comparability(request: Request) -> dict[str, Any]:
        return svc(request).comparability_summary(request_id=_request_id(request))

    @router.get("/compare", response_model=Envelope, tags=["comparability"])
    def compare(
        request: Request,
        left: str = Query(description="Left measurement identifier."),
        right: str = Query(description="Right measurement identifier."),
        conditions: str | None = Query(
            default=None,
            description="Optional JSON object mapping condition keys to true, false, or null.",
        ),
    ) -> dict[str, Any]:
        return svc(request).compare(
            left,
            right,
            conditions=_parse_conditions(conditions),
            request_id=_request_id(request),
        )

    @router.get("/provenance", response_model=Envelope, tags=["provenance"])
    def provenance(
        request: Request,
        accession: str = Query(description="NASA PSI accession."),
        file: str = Query(description="Exact source file name, not a path."),
        sheet: str | None = Query(default=None),
        row: int | None = Query(default=None, ge=1),
    ) -> dict[str, Any]:
        return svc(request).resolve_provenance(
            accession,
            file,
            sheet=sheet,
            row=row,
            request_id=_request_id(request),
        )

    application.include_router(router)
    return application


app = create_app()
