"""Tests for the Accept-header q-value parser in app.content_negotiation."""

from __future__ import annotations

from starlette.requests import Request

from app.content_negotiation import negotiate


def _req(accept: str | None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if accept is not None:
        headers.append((b"accept", accept.encode("latin-1")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
    }
    return Request(scope)


def test_missing_accept_returns_default_html() -> None:
    assert negotiate(_req(None)) == "html"


def test_empty_accept_returns_default() -> None:
    assert negotiate(_req(""), default="json") == "json"


def test_explicit_html() -> None:
    assert negotiate(_req("text/html")) == "html"


def test_explicit_json() -> None:
    assert negotiate(_req("application/json")) == "json"


def test_jose_media_type() -> None:
    assert negotiate(_req("application/jose+json")) == "jose"


def test_browser_accept_header_picks_html() -> None:
    # Realistic Chrome Accept header.
    accept = (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    )
    assert negotiate(_req(accept)) == "html"


def test_q_value_overrides_order() -> None:
    # JSON has a higher q than HTML — JSON wins despite appearing first.
    accept = "text/html;q=0.5,application/json;q=0.9"
    assert negotiate(_req(accept)) == "json"


def test_zero_q_value_skipped() -> None:
    # text/html explicitly rejected; fall through to json.
    accept = "text/html;q=0,application/json"
    assert negotiate(_req(accept)) == "json"


def test_unknown_media_types_fall_through_to_default() -> None:
    assert negotiate(_req("image/png,application/pdf")) == "html"


def test_wildcard_resolves_to_default() -> None:
    assert negotiate(_req("*/*"), default="json") == "json"


def test_application_wildcard_prefers_json() -> None:
    assert negotiate(_req("application/*")) == "json"


def test_equal_q_left_wins() -> None:
    # Stable tiebreaker: leftmost q-tied entry wins (browser-like).
    accept = "application/json,text/html"
    assert negotiate(_req(accept)) == "json"


def test_invalid_q_value_treated_as_one() -> None:
    accept = "text/html;q=notanumber,application/json;q=0.5"
    assert negotiate(_req(accept)) == "html"
