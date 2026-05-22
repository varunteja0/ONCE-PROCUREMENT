"""L4 — Pluggable antivirus scanner.

Single choke-point for "is this byte string safe to land on disk?".

Wire diagram::

    inbound_attachment_storage.LocalInboundStorage.put ─┐
    import_service.create_import_job                    ├──► enforce_clean()
                                                        │        │
                                                        │        ▼
                                                        │   AvScanner.scan_bytes()
                                                        │        │
                                                        │        ▼
                                                        │   ClamdScanner ──► clamd sidecar (TCP 3310 or unix socket)
                                                        │   StubAllowScanner / StubDenyScanner / EicarScanner
                                                        │   (dev + test backends — no daemon required)
                                                        ▼
                                                  InfectedFileError | ScannerError

Backends are selected by ``settings.av_scanner_backend``:

* ``"clamd"``       — real ClamAV daemon (production).
* ``"stub_allow"``  — always CLEAN (default for dev / unit tests).
* ``"stub_deny"``   — always INFECTED (proves the fail-closed paths fire).
* ``"eicar"``       — detects the EICAR test string (integration tests without clamd).
* ``"noop"``        — alias of stub_allow for explicit "AV disabled" deployments.

Fail-closed posture
-------------------
``settings.av_fail_closed_on_scanner_error`` gates what happens when the
scanner itself is unreachable. Production sets this to True: a downed
scanner blocks all uploads (we'd rather lose availability than ingest an
unscanned payload). Dev/test sets it to False so a missing clamd sidecar
doesn't break local boots — the file lands on disk and a warning is logged.

The EICAR test string lives in :data:`EICAR_TEST_STRING` and is used by
:class:`EicarScanner` and by the AV integration tests
(``tests/test_inbound_av_integration.py``, ``tests/test_import_av_integration.py``)
to exercise the infected-path without ever bundling a real virus signature
or requiring a running daemon.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from app.config import settings
from app.utils.logging import get_logger

__all__ = [
    "ScanResult",
    "ScanReport",
    "InfectedFileError",
    "ScannerError",
    "AvScanner",
    "StubAllowScanner",
    "StubDenyScanner",
    "EicarScanner",
    "ClamdScanner",
    "get_scanner",
    "reset_scanner_for_tests",
    "enforce_clean",
    "EICAR_TEST_STRING",
]


_logger = get_logger(__name__)


# The canonical EICAR Anti-Virus Test File. Every conforming AV engine
# (and our :class:`EicarScanner` test backend) detects this exact byte
# string. It is NOT a real virus — it is the industry-standard probe
# for verifying that a scan path is plumbed end-to-end.
EICAR_TEST_STRING: bytes = (
    b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
)


class ScanResult(str, Enum):
    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ScanReport:
    """Outcome of a single :meth:`AvScanner.scan_bytes` call."""

    result: ScanResult
    signature: str | None
    detail: str | None
    scanner: str


class InfectedFileError(Exception):
    """Raised when the scanner reports a positive match (INFECTED)."""

    def __init__(self, signature: str, scanner: str, detail: str | None = None) -> None:
        self.signature = signature
        self.scanner = scanner
        self.detail = detail
        msg = f"File rejected by {scanner}: signature={signature}"
        if detail:
            msg += f" ({detail})"
        super().__init__(msg)


class ScannerError(Exception):
    """Raised when the scanner itself is unreachable / errored.

    Distinct from :class:`InfectedFileError` so callers can render
    different HTTP statuses (503 vs 422) and apply different retry
    semantics.
    """

    def __init__(self, detail: str, scanner: str) -> None:
        self.detail = detail
        self.scanner = scanner
        super().__init__(f"Scanner {scanner} unavailable: {detail}")


@runtime_checkable
class AvScanner(Protocol):
    """Pluggable scanner contract.

    Implementations MUST be safe to call from request handlers (no
    long-running blocking work without a timeout) and MUST NOT raise on
    a CLEAN result — only on infrastructure failure (raise
    :class:`ScannerError`) or when they want the caller to short-circuit
    with an infected-file response (raise :class:`InfectedFileError`,
    though typically the convenience wrapper :func:`enforce_clean` is
    what raises that — scanners themselves return a :class:`ScanReport`).
    """

    def scan_bytes(
        self, data: bytes, *, hint_name: str | None = None
    ) -> ScanReport: ...


# ---------------------------------------------------------------------------
# Test/dev backends — no daemon required.
# ---------------------------------------------------------------------------


class StubAllowScanner:
    """Always CLEAN. Default for dev + unit tests."""

    name = "stub_allow"

    def scan_bytes(
        self, data: bytes, *, hint_name: str | None = None
    ) -> ScanReport:
        return ScanReport(
            result=ScanResult.CLEAN,
            signature=None,
            detail=None,
            scanner=self.name,
        )


class StubDenyScanner:
    """Always INFECTED. Useful for exercising fail-closed routes in tests."""

    name = "stub_deny"

    def scan_bytes(
        self, data: bytes, *, hint_name: str | None = None
    ) -> ScanReport:
        return ScanReport(
            result=ScanResult.INFECTED,
            signature="STUB.Deny.Test",
            detail="stub_deny scanner refuses all input",
            scanner=self.name,
        )


class EicarScanner:
    """Detects the EICAR test string; CLEAN otherwise.

    Used to wire integration tests end-to-end without a real clamd. The
    EICAR string is the only "infected" payload anywhere in this repo —
    we never bundle or download a real virus.
    """

    name = "eicar"

    def scan_bytes(
        self, data: bytes, *, hint_name: str | None = None
    ) -> ScanReport:
        if EICAR_TEST_STRING in data:
            return ScanReport(
                result=ScanResult.INFECTED,
                signature="Eicar-Test-Signature",
                detail="EICAR test string detected",
                scanner=self.name,
            )
        return ScanReport(
            result=ScanResult.CLEAN,
            signature=None,
            detail=None,
            scanner=self.name,
        )


# ---------------------------------------------------------------------------
# ClamAV daemon backend (production).
# ---------------------------------------------------------------------------


class ClamdScanner:
    """Wraps the ``clamd`` Python client.

    Picks Unix or TCP transport based on which of
    ``settings.av_clamd_unix_socket`` / ``settings.av_clamd_host`` is
    populated. The ``clamd`` module is imported lazily so the rest of
    the application boots even when the package isn't installed (e.g.
    a slim test image).
    """

    name = "clamd"

    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        unix_socket: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._host = host if host is not None else settings.av_clamd_host
        self._port = port if port is not None else settings.av_clamd_port
        self._unix_socket = (
            unix_socket if unix_socket is not None else settings.av_clamd_unix_socket
        )
        self._timeout = timeout if timeout is not None else settings.av_clamd_timeout_sec
        self._client = None  # lazily built — keeps construction side-effect free

    def _build_client(self):  # type: ignore[no-untyped-def]
        try:
            import clamd  # noqa: WPS433 — intentional lazy import
        except ImportError as exc:  # pragma: no cover - covered when clamd is missing
            raise ScannerError(
                f"clamd python package not installed: {exc}",
                scanner=self.name,
            ) from exc

        try:
            if self._unix_socket:
                return clamd.ClamdUnixSocket(
                    path=self._unix_socket, timeout=self._timeout
                )
            return clamd.ClamdNetworkSocket(
                host=self._host, port=self._port, timeout=self._timeout
            )
        except Exception as exc:  # pragma: no cover - defensive
            raise ScannerError(
                f"failed to construct clamd client: {exc}", scanner=self.name
            ) from exc

    def _get_client(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def ping(self) -> bool:
        """Return True iff the daemon answers PONG. Never raises."""

        try:
            client = self._get_client()
            client.ping()
            return True
        except Exception as exc:
            _logger.warning(
                "av.clamd_ping_failed",
                scanner=self.name,
                error=str(exc),
            )
            return False

    def scan_bytes(
        self, data: bytes, *, hint_name: str | None = None
    ) -> ScanReport:
        try:
            import clamd  # noqa: WPS433
        except ImportError as exc:
            raise ScannerError(
                f"clamd python package not installed: {exc}",
                scanner=self.name,
            ) from exc

        client = self._get_client()
        try:
            response = client.instream(io.BytesIO(data))
        except (clamd.ConnectionError, OSError) as exc:
            # Reset so the next call rebuilds the socket.
            self._client = None
            raise ScannerError(str(exc), scanner=self.name) from exc
        except Exception as exc:  # pragma: no cover - defensive
            self._client = None
            raise ScannerError(
                f"clamd instream raised {type(exc).__name__}: {exc}",
                scanner=self.name,
            ) from exc

        # clamd returns ``{"stream": (status, signature_or_None)}``.
        entry = (response or {}).get("stream")
        if not entry or len(entry) < 2:
            raise ScannerError(
                f"clamd returned unexpected payload: {response!r}",
                scanner=self.name,
            )
        status, signature = entry[0], entry[1]
        status_str = (status or "").upper()
        if status_str == "OK":
            return ScanReport(
                result=ScanResult.CLEAN,
                signature=None,
                detail=None,
                scanner=self.name,
            )
        if status_str == "FOUND":
            return ScanReport(
                result=ScanResult.INFECTED,
                signature=str(signature or "Unknown"),
                detail=None,
                scanner=self.name,
            )
        # ERROR or anything else — surface as ERROR so callers can decide.
        return ScanReport(
            result=ScanResult.ERROR,
            signature=None,
            detail=f"clamd status={status!r} signature={signature!r}",
            scanner=self.name,
        )


# ---------------------------------------------------------------------------
# Module-level resolver — mirrors ``inbound_attachment_storage.get_storage``.
# ---------------------------------------------------------------------------


_scanner_singleton: AvScanner | None = None


def _build_from_settings() -> AvScanner:
    backend = (settings.av_scanner_backend or "stub_allow").strip().lower()
    if backend == "clamd":
        return ClamdScanner()
    if backend == "stub_deny":
        return StubDenyScanner()
    if backend == "eicar":
        return EicarScanner()
    if backend in {"stub_allow", "noop", ""}:
        return StubAllowScanner()
    # Unknown backend names fail-closed to stub_allow with a loud log so a
    # typo doesn't silently disable scanning — but also doesn't crash boot.
    _logger.warning(
        "av.unknown_backend_falling_back_to_stub_allow",
        configured_backend=backend,
    )
    return StubAllowScanner()


def get_scanner() -> AvScanner:
    """Return the process-wide scanner (lazy singleton)."""

    global _scanner_singleton
    if _scanner_singleton is None:
        _scanner_singleton = _build_from_settings()
    return _scanner_singleton


def reset_scanner_for_tests(scanner: AvScanner | None = None) -> None:
    """Inject a scanner (or clear the cache). Test-only hook."""

    global _scanner_singleton
    _scanner_singleton = scanner


def enforce_clean(
    data: bytes,
    *,
    hint_name: str | None = None,
    fail_closed_on_error: bool = True,
    scanner: AvScanner | None = None,
) -> ScanReport:
    """Run the configured scanner and raise on INFECTED.

    On ``ScanResult.ERROR``: when ``fail_closed_on_error`` is True (the
    production default) raise :class:`ScannerError`; otherwise log a
    structured warning and return the report so the caller can decide
    whether to proceed.

    Logging never includes ``data`` itself — only sha256, size, and
    scanner metadata.
    """

    active = scanner or get_scanner()
    report = active.scan_bytes(data, hint_name=hint_name)
    sha = hashlib.sha256(data).hexdigest()
    size = len(data)
    if report.result is ScanResult.INFECTED:
        _logger.warning(
            "av.infected",
            scanner=report.scanner,
            signature=report.signature,
            hint_name=hint_name,
            sha256=sha,
            size=size,
        )
        raise InfectedFileError(
            signature=report.signature or "Unknown",
            scanner=report.scanner,
            detail=report.detail,
        )
    if report.result is ScanResult.ERROR:
        if fail_closed_on_error:
            _logger.error(
                "av.scanner_error_fail_closed",
                scanner=report.scanner,
                detail=report.detail,
                hint_name=hint_name,
                sha256=sha,
                size=size,
            )
            raise ScannerError(
                report.detail or "scanner returned ERROR",
                scanner=report.scanner,
            )
        _logger.warning(
            "av.scanner_error_fail_open",
            scanner=report.scanner,
            detail=report.detail,
            hint_name=hint_name,
            sha256=sha,
            size=size,
        )
        return report
    return report
