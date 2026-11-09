"""Typed errors shared by the analytics and API layers."""

from __future__ import annotations

from typing import Any


class AnalyticsError(Exception):
    """Base class for expected analytics failures."""

    code = "analytics_error"
    http_status = 500

    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AnalyticsError):
    """A requested registry resource or data row does not exist."""

    code = "not_found"
    http_status = 404


class InvalidQueryError(AnalyticsError):
    """A query parameter combination is invalid or unsupported."""

    code = "invalid_query"
    http_status = 400


class LimitExceededError(AnalyticsError):
    """A caller requested more rows or points than the contract permits."""

    code = "range_too_large"
    http_status = 413


class QueryTimeoutError(AnalyticsError):
    """A bounded query exceeded its configured time budget."""

    code = "query_timeout"
    http_status = 503


class QueryError(AnalyticsError):
    """A bounded read-only query failed for an unexpected reason."""

    code = "query_error"
    http_status = 500


class DatasetUnavailableError(AnalyticsError):
    """A required canonical table is absent from the local dataset."""

    code = "service_unavailable"
    http_status = 503


class RegistryError(AnalyticsError):
    """A registry is missing, malformed, or internally inconsistent."""

    code = "registry_error"
    http_status = 500


class UnknownMeasurementError(NotFoundError):
    """A measurement identifier is not present in the comparability registry."""

    code = "unknown_measurement"
