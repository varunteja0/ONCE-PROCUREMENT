"""L4 — unit tests for ``app.services.av_scanner``.

These run without a clamd daemon. ``ClamdScanner`` tests fake the
``clamd`` python module via ``sys.modules`` so we never touch the
network.
"""

from __future__ import annotations

import io
import sys
import types
from typing import Any

import pytest

from app.config import settings
from app.services import av_scanner
from app.services.av_scanner import (
    EICAR_TEST_STRING,
    ClamdScanner,
    EicarScanner,
    InfectedFileError,
    ScannerError,
    ScanReport,
    ScanResult,
    StubAllowScanner,
    StubDenyScanner,
    enforce_clean,
    get_scanner,
    reset_scanner_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_scanner_singleton():
    reset_scanner_for_tests(None)
    yield
    reset_scanner_for_tests(None)


# ---------------------------------------------------------------------------
# Stub backends
# ---------------------------------------------------------------------------


def test_stub_allow_returns_clean():
    report = StubAllowScanner().scan_bytes(b"anything", hint_name="x.pdf")
    assert report.result is ScanResult.CLEAN
    assert report.signature is None
    assert report.scanner == "stub_allow"


def test_stub_deny_returns_infected():
    report = StubDenyScanner().scan_bytes(b"anything")
    assert report.result is ScanResult.INFECTED
    assert report.signature == "STUB.Deny.Test"
    assert report.scanner == "stub_deny"


def test_eicar_scanner_detects_eicar_string():
    report = EicarScanner().scan_bytes(EICAR_TEST_STRING)
    assert report.result is ScanResult.INFECTED
    assert report.signature == "Eicar-Test-Signature"


def test_eicar_scanner_detects_eicar_string_in_larger_payload():
    payload = b"prefix-bytes\n" + EICAR_TEST_STRING + b"\nsuffix-bytes"
    report = EicarScanner().scan_bytes(payload)
    assert report.result is ScanResult.INFECTED


def test_eicar_scanner_passes_clean_payload():
    report = EicarScanner().scan_bytes(b"hello world, totally clean")
    assert report.result is ScanResult.CLEAN
    assert report.signature is None


# ---------------------------------------------------------------------------
# enforce_clean
# ---------------------------------------------------------------------------


def test_enforce_clean_returns_report_on_clean():
    reset_scanner_for_tests(StubAllowScanner())
    report = enforce_clean(b"clean")
    assert report.result is ScanResult.CLEAN


def test_enforce_clean_raises_on_infected():
    reset_scanner_for_tests(StubDenyScanner())
    with pytest.raises(InfectedFileError) as exc_info:
        enforce_clean(b"anything", hint_name="evil.exe")
    assert exc_info.value.signature == "STUB.Deny.Test"
    assert exc_info.value.scanner == "stub_deny"


def test_enforce_clean_eicar_raises():
    reset_scanner_for_tests(EicarScanner())
    with pytest.raises(InfectedFileError) as exc_info:
        enforce_clean(EICAR_TEST_STRING, hint_name="probe.txt")
    assert exc_info.value.signature == "Eicar-Test-Signature"


class _ErrorScanner:
    name = "broken"

    def scan_bytes(self, data: bytes, *, hint_name: str | None = None) -> ScanReport:
        return ScanReport(
            result=ScanResult.ERROR,
            signature=None,
            detail="simulated outage",
            scanner=self.name,
        )


def test_enforce_clean_fail_closed_raises_scanner_error():
    reset_scanner_for_tests(_ErrorScanner())
    with pytest.raises(ScannerError) as exc_info:
        enforce_clean(b"hi", fail_closed_on_error=True)
    assert exc_info.value.scanner == "broken"


def test_enforce_clean_fail_open_returns_report():
    reset_scanner_for_tests(_ErrorScanner())
    report = enforce_clean(b"hi", fail_closed_on_error=False)
    assert report.result is ScanResult.ERROR
    assert report.detail == "simulated outage"


def test_enforce_clean_accepts_explicit_scanner_argument():
    # explicit kwarg must win over the module singleton
    reset_scanner_for_tests(StubDenyScanner())
    report = enforce_clean(b"x", scanner=StubAllowScanner())
    assert report.result is ScanResult.CLEAN


# ---------------------------------------------------------------------------
# get_scanner backend selection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "backend,expected_cls",
    [
        ("stub_allow", StubAllowScanner),
        ("stub_deny", StubDenyScanner),
        ("eicar", EicarScanner),
        ("noop", StubAllowScanner),
        ("clamd", ClamdScanner),
    ],
)
def test_get_scanner_respects_backend_setting(monkeypatch, backend, expected_cls):
    monkeypatch.setattr(settings, "av_scanner_backend", backend)
    reset_scanner_for_tests(None)
    inst = get_scanner()
    assert isinstance(inst, expected_cls)


def test_get_scanner_unknown_backend_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "av_scanner_backend", "totally-bogus")
    reset_scanner_for_tests(None)
    assert isinstance(get_scanner(), StubAllowScanner)


def test_get_scanner_is_singleton(monkeypatch):
    monkeypatch.setattr(settings, "av_scanner_backend", "stub_allow")
    reset_scanner_for_tests(None)
    a = get_scanner()
    b = get_scanner()
    assert a is b


def test_reset_scanner_for_tests_replaces_singleton():
    sentinel = StubDenyScanner()
    reset_scanner_for_tests(sentinel)
    assert get_scanner() is sentinel


# ---------------------------------------------------------------------------
# ClamdScanner — faked via sys.modules so no real socket is opened.
# ---------------------------------------------------------------------------


class _FakeStream:
    def __init__(self, response: dict[str, Any] | Exception):
        self._response = response
        self.last_stream: bytes | None = None

    def instream(self, buf: io.BytesIO) -> dict[str, Any]:
        self.last_stream = buf.read()
        if isinstance(self._response, Exception):
            raise self._response
        return self._response

    def ping(self) -> bytes:
        return b"PONG"


def _install_fake_clamd(monkeypatch, fake_client, *, connection_error_cls=None):
    fake_module = types.ModuleType("clamd")

    class _CE(Exception):
        pass

    fake_module.ConnectionError = connection_error_cls or _CE

    def _net(**_kwargs):
        return fake_client

    def _unix(**_kwargs):
        return fake_client

    fake_module.ClamdNetworkSocket = _net
    fake_module.ClamdUnixSocket = _unix
    monkeypatch.setitem(sys.modules, "clamd", fake_module)
    return fake_module


def test_clamd_scanner_clean(monkeypatch):
    fake = _FakeStream({"stream": ("OK", None)})
    _install_fake_clamd(monkeypatch, fake)
    scanner = ClamdScanner(host="x", port=1, timeout=0.1)
    report = scanner.scan_bytes(b"hello", hint_name="foo.pdf")
    assert report.result is ScanResult.CLEAN
    assert report.scanner == "clamd"
    assert fake.last_stream == b"hello"


def test_clamd_scanner_infected(monkeypatch):
    fake = _FakeStream({"stream": ("FOUND", "Eicar-Test-Signature")})
    _install_fake_clamd(monkeypatch, fake)
    scanner = ClamdScanner(host="x", port=1, timeout=0.1)
    report = scanner.scan_bytes(EICAR_TEST_STRING)
    assert report.result is ScanResult.INFECTED
    assert report.signature == "Eicar-Test-Signature"


def test_clamd_scanner_error_status_returns_error_report(monkeypatch):
    fake = _FakeStream({"stream": ("ERROR", "scan failed")})
    _install_fake_clamd(monkeypatch, fake)
    scanner = ClamdScanner(host="x", port=1, timeout=0.1)
    report = scanner.scan_bytes(b"x")
    assert report.result is ScanResult.ERROR
    assert "ERROR" in (report.detail or "")


def test_clamd_scanner_connection_error_raises_scanner_error(monkeypatch):
    class _CE(Exception):
        pass

    fake = _FakeStream(_CE("connection refused"))
    _install_fake_clamd(monkeypatch, fake, connection_error_cls=_CE)
    scanner = ClamdScanner(host="x", port=1, timeout=0.1)
    with pytest.raises(ScannerError) as exc_info:
        scanner.scan_bytes(b"x")
    assert exc_info.value.scanner == "clamd"


def test_clamd_scanner_oserror_raises_scanner_error(monkeypatch):
    fake = _FakeStream(OSError("socket dead"))
    _install_fake_clamd(monkeypatch, fake)
    scanner = ClamdScanner(host="x", port=1, timeout=0.1)
    with pytest.raises(ScannerError):
        scanner.scan_bytes(b"x")


def test_clamd_scanner_unexpected_payload_raises_scanner_error(monkeypatch):
    fake = _FakeStream({"stream": None})
    _install_fake_clamd(monkeypatch, fake)
    scanner = ClamdScanner(host="x", port=1, timeout=0.1)
    with pytest.raises(ScannerError):
        scanner.scan_bytes(b"x")


def test_clamd_scanner_ping_true(monkeypatch):
    fake = _FakeStream({"stream": ("OK", None)})
    _install_fake_clamd(monkeypatch, fake)
    scanner = ClamdScanner(host="x", port=1, timeout=0.1)
    assert scanner.ping() is True


def test_clamd_scanner_ping_false_on_missing_module(monkeypatch):
    # Remove ``clamd`` from sys.modules and block re-import.
    monkeypatch.setitem(sys.modules, "clamd", None)
    scanner = ClamdScanner(host="x", port=1, timeout=0.1)
    assert scanner.ping() is False


def test_clamd_scanner_unix_socket_path(monkeypatch):
    fake = _FakeStream({"stream": ("OK", None)})
    _install_fake_clamd(monkeypatch, fake)
    scanner = ClamdScanner(unix_socket="/tmp/clamd.sock", timeout=0.1)
    report = scanner.scan_bytes(b"hi")
    assert report.result is ScanResult.CLEAN


def test_infected_file_error_message_does_not_include_bytes():
    """Sanity: the InfectedFileError text must never carry the raw payload."""

    reset_scanner_for_tests(StubDenyScanner())
    secret = b"super-secret-confidential-payload-do-not-log"
    with pytest.raises(InfectedFileError) as exc_info:
        enforce_clean(secret, hint_name="leak.bin")
    assert "super-secret" not in str(exc_info.value)
    assert "super-secret" not in (exc_info.value.detail or "")
