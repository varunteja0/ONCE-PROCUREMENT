"""Snapshot-style tests for the generated OpenAPI document."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from app.api.v1.openapi_customization import build_openapi, customize_openapi


class _Pet(BaseModel):
    id: str
    name: str


def _build_app() -> FastAPI:
    app = FastAPI(title="Once API (test)", version="1.2.3")

    @app.get("/v1/pets", tags=["public"])
    async def list_pets() -> list[_Pet]:
        return []

    @app.post("/v1/pets", tags=["public"], status_code=201)
    async def create_pet(pet: _Pet) -> _Pet:
        return pet

    customize_openapi(app)
    return app


class TestOpenApiInfo:
    def test_info_block_present(self) -> None:
        schema = build_openapi(_build_app())
        info = schema["info"]
        assert info["title"] == "Once API (test)"
        assert info["version"] == "1.2.3"
        assert info["contact"]["email"] == "support@getonce.com"

    def test_servers_list_contains_dev_and_prod(self) -> None:
        schema = build_openapi(_build_app())
        urls = {s["url"] for s in schema["servers"]}
        assert "http://localhost:8000" in urls
        assert "https://api.getonce.com" in urls


class TestSecuritySchemes:
    def test_bearer_and_csrf_registered(self) -> None:
        schema = build_openapi(_build_app())
        schemes = schema["components"]["securitySchemes"]
        assert "BearerAuth" in schemes
        assert "CsrfTokenHeader" in schemes
        assert schemes["BearerAuth"]["scheme"] == "bearer"
        assert schemes["BearerAuth"]["bearerFormat"] == "JWT"
        assert schemes["CsrfTokenHeader"]["in"] == "header"
        assert schemes["CsrfTokenHeader"]["name"] == "X-CSRF-Token"


class TestErrorComponent:
    def test_problem_schema_present(self) -> None:
        schema = build_openapi(_build_app())
        assert "Problem" in schema["components"]["schemas"]
        problem = schema["components"]["schemas"]["Problem"]
        # Required RFC 9457 fields are surfaced.
        props = problem.get("properties", {})
        for field in ("type", "title", "status", "detail"):
            assert field in props

    def test_problem_response_component_registered(self) -> None:
        schema = build_openapi(_build_app())
        responses = schema["components"]["responses"]
        assert "Problem" in responses
        content = responses["Problem"]["content"]
        assert "application/problem+json" in content


class TestPageSchema:
    def test_page_schema_present(self) -> None:
        schema = build_openapi(_build_app())
        assert "Page" in schema["components"]["schemas"]
        page = schema["components"]["schemas"]["Page"]
        props = page.get("properties", {})
        for field in ("items", "limit"):
            assert field in props


class TestGlobalParameters:
    def test_global_headers_registered(self) -> None:
        schema = build_openapi(_build_app())
        params = schema["components"]["parameters"]
        # Stored without hyphens for valid OpenAPI parameter keys.
        for key in ("IdempotencyKey", "IfMatch", "IfNoneMatch", "XRequestID"):
            assert key in params


class TestPerOperationDecorations:
    def test_every_operation_has_default_error_response(self) -> None:
        schema = build_openapi(_build_app())
        for path_item in schema["paths"].values():
            for method, op in path_item.items():
                if method.lower() not in {"get", "post", "patch", "delete"}:
                    continue
                assert "default" in op["responses"]
                assert (
                    op["responses"]["default"]["$ref"]
                    == "#/components/responses/Problem"
                )

    def test_every_operation_has_rate_limit_extension(self) -> None:
        schema = build_openapi(_build_app())
        for path_item in schema["paths"].values():
            for method, op in path_item.items():
                if method.lower() not in {"get", "post", "patch", "delete"}:
                    continue
                assert "x-rate-limit" in op
                assert op["x-rate-limit"]["policy"].endswith("client IP")


class TestTags:
    def test_tag_metadata_attached(self) -> None:
        schema = build_openapi(_build_app())
        tag_names = {t["name"] for t in schema["tags"]}
        for expected in ("auth", "tenants", "suppliers", "submissions", "receipts"):
            assert expected in tag_names


class TestIdempotency:
    def test_customize_openapi_is_idempotent(self) -> None:
        app = _build_app()
        first = app.openapi()
        second = app.openapi()
        assert first is second  # cached
