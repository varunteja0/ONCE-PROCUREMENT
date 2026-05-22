"""Shared cross-cutting Pydantic schemas.

Defines:

* :class:`Problem` — RFC 9457 Problem Details envelope (the canonical shape
  the API uses for **all** 4xx/5xx error responses).
* :class:`ErrorResponse` — alias of :class:`Problem` exported under the more
  conventional name so route handlers can reference it from OpenAPI
  ``responses`` blocks without leaking the RFC noun.
* :class:`ValidationErrorItem` — one entry in the optional ``errors`` array
  on :class:`Problem` (matches the pydantic-v2 error record loosely).
* :class:`Page[T]` — generic pagination envelope supporting **both** offset
  and cursor modes, used by every list endpoint that adopts the contract.
* :class:`Cursor` — opaque cursor structure (encoded/decoded by
  :mod:`app.utils.pagination`; the public wire format is a single base64
  string).

These types are deliberately additive — existing route schemas continue to
ship their bespoke list responses. New routes (and B1's incoming additions)
should adopt :class:`Page` per ``docs/API.md``.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


__all__ = [
    "Problem",
    "ErrorResponse",
    "ValidationErrorItem",
    "Page",
    "Cursor",
    "PROBLEM_BASE_URL",
]


PROBLEM_BASE_URL: str = "https://docs.getonce.com/errors"
"""Base URL for Problem ``type`` URIs.

Overridable per-deployment via ``settings`` but kept module-level so the
schema layer never imports from the runtime config (which would break
pure-schema consumers like the OpenAPI generator).
"""


class ValidationErrorItem(BaseModel):
    """One pydantic-style validation error, surfaced in :attr:`Problem.errors`."""

    model_config = ConfigDict(extra="allow")

    loc: list[Any] = Field(
        default_factory=list,
        description="Path of the offending field (e.g. ``['body', 'email']``).",
    )
    msg: str = Field(default="", description="Human-readable error message.")
    code: str | None = Field(
        default=None,
        description=(
            "Machine-readable error code (e.g. ``value_error.email``). "
            "Pydantic v2 surfaces this as ``type`` on the raw error record."
        ),
    )


class Problem(BaseModel):
    """RFC 9457 Problem Details envelope.

    Every 4xx/5xx response uses this shape. The ``detail`` field is duplicated
    from ``title`` at the top level for backward compatibility with FastAPI's
    default ``{"detail": "..."}`` envelope; clients should migrate to reading
    ``type`` + ``title`` + ``status``.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": f"{PROBLEM_BASE_URL}/supplier-not-found",
                "title": "Supplier not found",
                "status": 404,
                "detail": "No supplier with id 'sup_01HXY' is accessible to your tenant.",
                "instance": "/v1/suppliers/sup_01HXY",
                "trace_id": "01HXYABCDEF01234567890",
            }
        }
    )

    type: str = Field(
        default=f"{PROBLEM_BASE_URL}/about:blank",
        description="URI identifying the error class.",
    )
    title: str = Field(
        ..., description="Short, human-readable summary of the problem type."
    )
    status: int = Field(..., ge=100, le=599, description="HTTP status code.")
    detail: Any = Field(
        default=None,
        description=(
            "Human-readable detail. For backward compatibility this is also "
            "the field FastAPI legacy clients read; new clients should use "
            "``title`` + ``errors`` instead."
        ),
    )
    instance: str | None = Field(
        default=None,
        description="URI reference for this specific occurrence (usually the request path).",
    )
    trace_id: str | None = Field(
        default=None,
        description="Correlates this response with server logs / Sentry events.",
    )
    errors: list[ValidationErrorItem] | None = Field(
        default=None,
        description="Validation error breakdown (populated on 422 responses).",
    )


# Conventional alias — route handlers and OpenAPI ``responses`` blocks read
# better with ``ErrorResponse`` than ``Problem``.
ErrorResponse = Problem


class Page(BaseModel, Generic[T]):  # noqa: UP046
    """Generic pagination envelope.

    Two modes are supported (see ``docs/API.md`` § Pagination):

    * **Offset mode** — ``offset`` + ``total`` are populated, cursors are
      ``None``. Suitable for admin UIs and bounded result sets.
    * **Cursor mode** — ``next_cursor`` / ``prev_cursor`` are populated,
      ``total`` is ``None`` (counting is intentionally skipped to keep
      latency bounded under load). Cursors are opaque base64 strings;
      clients MUST NOT decode them.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[T] = Field(default_factory=list, description="Page contents.")
    total: int | None = Field(
        default=None,
        description=(
            "Total matching rows. Populated only in offset mode; ``None`` in "
            "cursor mode because counting is intentionally skipped for "
            "high-throughput integrations."
        ),
    )
    limit: int = Field(
        ..., ge=1, le=1000, description="Page size that was applied server-side."
    )
    offset: int | None = Field(
        default=None,
        ge=0,
        description="Offset that was applied (offset mode only).",
    )
    next_cursor: str | None = Field(
        default=None,
        description="Opaque cursor for the next page (cursor mode); ``None`` at end of stream.",
    )
    prev_cursor: str | None = Field(
        default=None,
        description="Opaque cursor for the previous page (cursor mode).",
    )


class Cursor(BaseModel):
    """In-memory representation of a pagination cursor.

    Encoded to a base64-urlsafe string for transport. Clients receive the
    encoded form only — this model exists for server-side ergonomics.
    """

    created_at: str = Field(
        ..., description="ISO-8601 UTC timestamp of the boundary row."
    )
    id: str = Field(..., description="ID of the boundary row (tie-breaker).")
    direction: str = Field(
        default="next",
        pattern="^(next|prev)$",
        description="Cursor direction relative to the boundary row.",
    )
