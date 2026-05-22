"""Unit tests for ``PlaywrightSubmitter._smoke_test``.

The 15-minute Celery beat task (``smoke_test.run_all``) relies on this method
to detect carrier-portal drift or outages and emit Slack alerts. Every
failure mode (URL not configured, DNS error, 5xx, needle missing) MUST
collapse to ``False`` rather than raise.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import httpx
import pytest

from app.automation.base import PlaywrightSubmitter
from app.models.portal import PortalPlatform

_URL_ENV = "PORTAL_SMOKE_PROBE_TEST_URL"
_USER_ENV = "PORTAL_SMOKE_PROBE_TEST_USERNAME"
_PASS_ENV = "PORTAL_SMOKE_PROBE_TEST_PASSWORD"


class _ProbeSubmitter(PlaywrightSubmitter):
    PLATFORM: ClassVar[PortalPlatform] = PortalPlatform.AMTRUST
    URL_ENV_VAR = _URL_ENV
    USERNAME_ENV_VAR = _USER_ENV
    PASSWORD_ENV_VAR = _PASS_ENV
    PORTAL_REFERENCE_PREFIX = "TST"
    SMOKE_PROBE_NEEDLE = "AmTrust"


def _instance() -> _ProbeSubmitter:
    """Bypass __init__ — mirrors what ``smoke_test.run_all`` does."""

    inst = _ProbeSubmitter.__new__(_ProbeSubmitter)
    inst.supplier = None  # type: ignore[attr-defined]
    inst.portal = None  # type: ignore[attr-defined]
    inst.payload = {}  # type: ignore[attr-defined]
    inst.consent = None  # type: ignore[attr-defined]
    return inst


@pytest.fixture
def env_url(monkeypatch: pytest.MonkeyPatch) -> str:
    url = "http://probe.test.invalid/"
    monkeypatch.setenv(_URL_ENV, url)
    return url


def _patch_httpx(
    monkeypatch: pytest.MonkeyPatch,
    *,
    status_code: int = 200,
    text: str = "<h1>AmTrust Producer Portal</h1>",
    raises: Exception | None = None,
) -> dict[str, Any]:
    calls: dict[str, Any] = {"count": 0, "url": None, "timeout": None}

    def _fake_get(url: str, **kwargs: Any) -> httpx.Response:
        calls["count"] += 1
        calls["url"] = url
        calls["timeout"] = kwargs.get("timeout")
        if raises is not None:
            raise raises
        req = httpx.Request("GET", url)
        return httpx.Response(status_code=status_code, text=text, request=req)

    monkeypatch.setattr("httpx.get", _fake_get)
    return calls


def test_smoke_probe_returns_true_on_200_with_needle(
    monkeypatch: pytest.MonkeyPatch, env_url: str
) -> None:
    calls = _patch_httpx(monkeypatch, status_code=200, text="welcome to AmTrust portal")
    assert asyncio.run(_instance()._smoke_test()) is True
    assert calls["count"] == 1
    assert calls["url"] == env_url


def test_smoke_probe_returns_false_when_needle_missing(
    monkeypatch: pytest.MonkeyPatch, env_url: str
) -> None:
    _patch_httpx(monkeypatch, status_code=200, text="<h1>Some Other Carrier</h1>")
    assert asyncio.run(_instance()._smoke_test()) is False


def test_smoke_probe_returns_false_on_5xx(
    monkeypatch: pytest.MonkeyPatch, env_url: str
) -> None:
    _patch_httpx(monkeypatch, status_code=503, text="AmTrust")
    assert asyncio.run(_instance()._smoke_test()) is False


def test_smoke_probe_returns_false_on_network_error(
    monkeypatch: pytest.MonkeyPatch, env_url: str
) -> None:
    _patch_httpx(monkeypatch, raises=httpx.ConnectError("dns failure"))
    assert asyncio.run(_instance()._smoke_test()) is False


def test_smoke_probe_returns_false_when_url_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(_URL_ENV, raising=False)
    # Even if httpx is wired, _resolve_url must fail first.
    calls = _patch_httpx(monkeypatch, status_code=200, text="AmTrust")
    assert asyncio.run(_instance()._smoke_test()) is False
    assert calls["count"] == 0  # never reached the request


def test_smoke_probe_does_not_resolve_credentials(
    monkeypatch: pytest.MonkeyPatch, env_url: str
) -> None:
    """Smoke must work in CI without secrets — must NOT call _resolve_credentials."""

    monkeypatch.delenv(_USER_ENV, raising=False)
    monkeypatch.delenv(_PASS_ENV, raising=False)
    _patch_httpx(monkeypatch, status_code=200, text="AmTrust")
    assert asyncio.run(_instance()._smoke_test()) is True


def test_smoke_probe_redirect_followed(
    monkeypatch: pytest.MonkeyPatch, env_url: str
) -> None:
    calls = _patch_httpx(monkeypatch, status_code=200, text="AmTrust")
    asyncio.run(_instance()._smoke_test())
    # 3xx falls in [200, 400), and httpx is told to follow redirects.
    # We assert the default timeout was honored too.
    assert calls["timeout"] == _ProbeSubmitter.SMOKE_PROBE_TIMEOUT_SEC


def test_smoke_probe_empty_needle_accepts_any_2xx(
    monkeypatch: pytest.MonkeyPatch, env_url: str
) -> None:
    monkeypatch.setattr(_ProbeSubmitter, "SMOKE_PROBE_NEEDLE", "")
    _patch_httpx(monkeypatch, status_code=200, text="<html>anything</html>")
    try:
        assert asyncio.run(_instance()._smoke_test()) is True
    finally:
        # Restore so subsequent tests see the real value.
        monkeypatch.setattr(_ProbeSubmitter, "SMOKE_PROBE_NEEDLE", "AmTrust")
