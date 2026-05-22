"""Tests for app.middleware.security_headers."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from httpx import ASGITransport, AsyncClient

from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
    build_security_headers,
)


def _app(hsts_enabled: bool = True, csp_report_uri: str | None = None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        SecurityHeadersMiddleware,
        hsts_enabled=hsts_enabled,
        csp_report_uri=csp_report_uri,
    )

    @app.get("/json")
    async def json() -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/html", response_class=HTMLResponse)
    async def html() -> str:
        return "<html><body>hi</body></html>"

    return app


async def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://example.test")


class TestStaticHeaders:
    @pytest.mark.parametrize(
        "header,value",
        [
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Referrer-Policy", "strict-origin-when-cross-origin"),
            ("Cross-Origin-Opener-Policy", "same-origin"),
            ("Cross-Origin-Resource-Policy", "same-site"),
        ],
    )
    async def test_always_present(self, header: str, value: str) -> None:
        async with await _client(_app()) as c:
            r = await c.get("/json")
        assert r.headers.get(header) == value

    async def test_permissions_policy_denies_dangerous_features(self) -> None:
        async with await _client(_app()) as c:
            r = await c.get("/json")
        pol = r.headers.get("Permissions-Policy", "")
        for feature in ("camera=()", "microphone=()", "geolocation=()", "payment=()"):
            assert feature in pol


class TestHSTS:
    async def test_hsts_emitted_when_enabled_on_public_host(self) -> None:
        async with await _client(_app(hsts_enabled=True)) as c:
            r = await c.get("/json", headers={"Host": "api.getonce.com"})
        assert r.headers.get("Strict-Transport-Security", "").startswith("max-age=63072000")

    async def test_hsts_not_emitted_on_localhost(self) -> None:
        async with await _client(_app(hsts_enabled=True)) as c:
            r = await c.get("/json", headers={"Host": "localhost"})
        assert "Strict-Transport-Security" not in r.headers

    async def test_hsts_disabled_env_toggle(self) -> None:
        async with await _client(_app(hsts_enabled=False)) as c:
            r = await c.get("/json", headers={"Host": "api.getonce.com"})
        assert "Strict-Transport-Security" not in r.headers


class TestCSP:
    async def test_csp_absent_on_json_response(self) -> None:
        async with await _client(_app()) as c:
            r = await c.get("/json")
        assert "Content-Security-Policy" not in r.headers

    async def test_csp_present_on_html_response(self) -> None:
        async with await _client(_app()) as c:
            r = await c.get("/html")
        csp = r.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    async def test_csp_includes_report_uri_when_configured(self) -> None:
        async with await _client(_app(csp_report_uri="/csp-report")) as c:
            r = await c.get("/html")
        assert "report-uri /csp-report" in r.headers.get("Content-Security-Policy", "")


class TestBuildHelper:
    def test_helper_returns_no_csp_when_not_html(self) -> None:
        headers = build_security_headers(is_local=False, hsts_enabled=True, is_html=False, csp_report_uri=None)
        assert "Content-Security-Policy" not in headers
        assert "Strict-Transport-Security" in headers

    def test_helper_omits_hsts_on_local(self) -> None:
        headers = build_security_headers(is_local=True, hsts_enabled=True, is_html=True, csp_report_uri=None)
        assert "Strict-Transport-Security" not in headers
        assert "Content-Security-Policy" in headers
