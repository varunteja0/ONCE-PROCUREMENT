"""Custom OpenAPI generator for the Once API.

Wraps :func:`fastapi.openapi.utils.get_openapi` to inject:

* the canonical RFC-9457 :class:`~app.schemas.common.Problem` schema as a
  reusable response component (``#/components/responses/Problem``);
* the :class:`~app.schemas.common.Page` envelope as a reusable schema;
* security schemes — ``BearerAuth`` (JWT) and ``CsrfTokenHeader``;
* global parameters — ``Idempotency-Key``, ``If-Match``, ``If-None-Match``;
* rich tag metadata from :data:`app.schemas.openapi_tags.OPENAPI_TAGS`;
* ``servers`` listing (dev + production placeholder);
* ``x-rate-limit`` extension on every operation describing the default
  rate-limit policy (overridable per-route);
* a top-level ``info.contact`` block.

The generator is monkey-patched onto the app via
:func:`customize_openapi`, which is idempotent (subsequent calls reuse the
cached document, just like FastAPI's default).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.schemas.common import Page, Problem
from app.schemas.openapi_tags import OPENAPI_TAGS

__all__ = ["customize_openapi", "build_openapi"]


_SERVERS: list[dict[str, Any]] = [
    {"url": "http://localhost:8000", "description": "Local development"},
    {
        "url": "https://api.getonce.com",
        "description": "Production (placeholder until launch)",
    },
]


_DEFAULT_RATE_LIMIT: dict[str, Any] = {
    "policy": "120/minute per client IP",
    "burst": 30,
    "scope": "ip",
    "headers": {
        "limit": "X-RateLimit-Limit",
        "remaining": "X-RateLimit-Remaining",
        "reset": "X-RateLimit-Reset",
    },
}


_GLOBAL_PARAMETERS: list[dict[str, Any]] = [
    {
        "name": "Idempotency-Key",
        "in": "header",
        "required": False,
        "schema": {"type": "string", "format": "uuid"},
        "description": (
            "Optional client-supplied UUID/ULID. When provided on a mutating "
            "request the server caches the response for 24h; replays with the "
            "same key + identical body return the cached response with header "
            "`Idempotency-Replayed: true`."
        ),
    },
    {
        "name": "If-Match",
        "in": "header",
        "required": False,
        "schema": {"type": "string"},
        "description": (
            "Optimistic concurrency control on mutating requests. Server "
            "returns `412 Precondition Failed` if the resource's current "
            "ETag doesn't match."
        ),
    },
    {
        "name": "If-None-Match",
        "in": "header",
        "required": False,
        "schema": {"type": "string"},
        "description": (
            "Cache validator on GET. Server returns `304 Not Modified` if "
            "the response body's ETag matches."
        ),
    },
    {
        "name": "X-Request-ID",
        "in": "header",
        "required": False,
        "schema": {"type": "string"},
        "description": (
            "Optional client-supplied correlation id. Echoed back on every "
            "response and used for log/Sentry correlation."
        ),
    },
]


def _security_schemes() -> dict[str, Any]:
    return {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "JWT access token issued by `POST /v1/auth/login`. "
                "15-minute lifetime; refresh via `POST /v1/auth/refresh`."
            ),
        },
        "CsrfTokenHeader": {
            "type": "apiKey",
            "in": "header",
            "name": "X-CSRF-Token",
            "description": (
                "Double-submit-cookie CSRF token for browser/cookie clients. "
                "Bypassed for Bearer-authenticated requests."
            ),
        },
    }


def _problem_response_component() -> dict[str, Any]:
    return {
        "description": "RFC 9457 Problem Details error response.",
        "content": {
            "application/problem+json": {
                "schema": {"$ref": "#/components/schemas/Problem"},
            },
            "application/json": {
                "schema": {"$ref": "#/components/schemas/Problem"},
            },
        },
    }


def build_openapi(app: FastAPI) -> dict[str, Any]:
    """Build the customized OpenAPI document for ``app``."""

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description
        or (
            "Once — supplier-portal autopilot for US specialty insurance MGAs. "
            "**Submit once. Prove it forever.**"
        ),
        routes=app.routes,
        tags=OPENAPI_TAGS,
        servers=_SERVERS,
    )
    schema.setdefault("info", {})
    schema["info"].setdefault("contact", {"name": "Once support", "email": "support@getonce.com"})
    schema["info"].setdefault(
        "license", {"name": "Proprietary", "url": "https://getonce.com/terms"}
    )

    components = schema.setdefault("components", {})
    schemas = components.setdefault("schemas", {})

    # Embed the Problem + Page envelopes so they're always present even when
    # no route references them directly.
    schemas["Problem"] = Problem.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    page_schema = Page.model_json_schema(ref_template="#/components/schemas/{model}")
    # Pydantic generates ``Page[~T]`` for the parametrized class — normalize.
    schemas["Page"] = page_schema

    components.setdefault("securitySchemes", {}).update(_security_schemes())

    responses = components.setdefault("responses", {})
    responses["Problem"] = _problem_response_component()

    params = components.setdefault("parameters", {})
    for p in _GLOBAL_PARAMETERS:
        params[p["name"].replace("-", "")] = p

    # Annotate every operation with default error response + rate-limit
    # extension when not already declared.
    for path_item in schema.get("paths", {}).values():
        for method, operation in path_item.items():
            if method.lower() not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "head",
                "options",
            }:
                continue
            if not isinstance(operation, dict):
                continue
            operation_responses = operation.setdefault("responses", {})
            operation_responses.setdefault(
                "default", {"$ref": "#/components/responses/Problem"}
            )
            operation.setdefault("x-rate-limit", _DEFAULT_RATE_LIMIT)

    return schema


def customize_openapi(app: FastAPI) -> None:
    """Install :func:`build_openapi` as ``app.openapi`` (idempotent)."""

    def _openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        app.openapi_schema = build_openapi(app)
        return app.openapi_schema

    app.openapi = _openapi  # type: ignore[method-assign]
