"""Pydantic response models for the read-only API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PageMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    limit: int
    offset: int
    total: int
    has_more: bool


class ResponseMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str
    registry_snapshot: str | None = None
    dataset_version: str | None = None
    registry_version: str | None = None
    retrieved_at: str | None = None
    generated_at: str
    page: PageMeta | None = None


class Quality(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Literal[
        "verified",
        "partial",
        "blocked",
        "experimental_table_only",
        "not_available",
    ]
    flags: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Envelope(BaseModel):
    """The single success envelope used by every endpoint."""

    model_config = ConfigDict(extra="allow")

    data: Any
    meta: ResponseMeta
    provenance: list[dict[str, Any]] = Field(default_factory=list)
    quality: Quality


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorBody
