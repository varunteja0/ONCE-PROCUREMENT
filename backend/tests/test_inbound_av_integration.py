"""L4 — integration tests for AV scanning inside LocalInboundStorage.

These exercise the real ``LocalInboundStorage.put`` codepath with the
EICAR-string scanner so we can verify the fail-closed behaviour without
ever bundling a real virus or needing a clamd sidecar.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.av_scanner import (
    EICAR_TEST_STRING,
    EicarScanner,
    InfectedFileError,
    ScannerError,
    ScanReport,
    ScanResult,
    StubAllowScanner,
    reset_scanner_for_tests,
)
from app.services.inbound_attachment_storage import LocalInboundStorage


@pytest.fixture(autouse=True)
def _reset_scanner():
    reset_scanner_for_tests(None)
    yield
    reset_scanner_for_tests(None)


def _list_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


# ---------------------------------------------------------------------------
# Clean / infected payload behaviour
# ---------------------------------------------------------------------------


def test_clean_payload_writes_to_disk(tmp_path: Path):
    storage = LocalInboundStorage(base_path=str(tmp_path), scanner=EicarScanner())
    out = storage.put(email_id="email-clean", filename="quote.pdf", content=b"hello-pdf")
    assert out.size_bytes == len(b"hello-pdf")
    files = _list_files(tmp_path)
    assert len(files) == 1
    assert files[0].read_bytes() == b"hello-pdf"


def test_eicar_payload_rejected_and_not_written(tmp_path: Path):
    storage = LocalInboundStorage(base_path=str(tmp_path), scanner=EicarScanner())
    with pytest.raises(InfectedFileError) as exc_info:
        storage.put(
            email_id="email-evil",
            filename="probe.txt",
            content=EICAR_TEST_STRING,
        )
    assert exc_info.value.signature == "Eicar-Test-Signature"
    assert exc_info.value.scanner == "eicar"
    # Critical: nothing on disk.
    assert _list_files(tmp_path) == []


def test_infected_payload_does_not_create_email_subdir(tmp_path: Path):
    storage = LocalInboundStorage(base_path=str(tmp_path), scanner=EicarScanner())
    with pytest.raises(InfectedFileError):
        storage.put(
            email_id="email-evil-2",
            filename="evil.pdf",
            content=EICAR_TEST_STRING,
        )
    # Neither the email directory nor any file should have been created.
    assert list(tmp_path.iterdir()) == []


def test_stub_deny_blocks_everything(tmp_path: Path):
    from app.services.av_scanner import StubDenyScanner

    storage = LocalInboundStorage(base_path=str(tmp_path), scanner=StubDenyScanner())
    with pytest.raises(InfectedFileError):
        storage.put(email_id="e", filename="a.pdf", content=b"x")
    assert _list_files(tmp_path) == []


def test_stub_allow_writes_normally(tmp_path: Path):
    storage = LocalInboundStorage(base_path=str(tmp_path), scanner=StubAllowScanner())
    storage.put(email_id="e", filename="a.pdf", content=b"clean")
    assert len(_list_files(tmp_path)) == 1


# ---------------------------------------------------------------------------
# Scanner-unreachable behaviour
# ---------------------------------------------------------------------------


class _AlwaysErrorScanner:
    name = "fake_broken"

    def scan_bytes(self, data: bytes, *, hint_name: str | None = None) -> ScanReport:
        return ScanReport(
            result=ScanResult.ERROR,
            signature=None,
            detail="simulated daemon outage",
            scanner=self.name,
        )


def test_scanner_unreachable_fail_closed_raises(tmp_path: Path, monkeypatch):
    from app.config import settings as app_settings

    monkeypatch.setattr(app_settings, "av_fail_closed_on_scanner_error", True)
    storage = LocalInboundStorage(base_path=str(tmp_path), scanner=_AlwaysErrorScanner())
    with pytest.raises(ScannerError) as exc_info:
        storage.put(email_id="e", filename="a.pdf", content=b"hello")
    assert exc_info.value.scanner == "fake_broken"
    assert _list_files(tmp_path) == []


def test_scanner_unreachable_fail_open_writes(tmp_path: Path, monkeypatch):
    from app.config import settings as app_settings

    monkeypatch.setattr(app_settings, "av_fail_closed_on_scanner_error", False)
    storage = LocalInboundStorage(base_path=str(tmp_path), scanner=_AlwaysErrorScanner())
    out = storage.put(email_id="e", filename="a.pdf", content=b"hello")
    assert out.size_bytes == 5
    assert len(_list_files(tmp_path)) == 1


# ---------------------------------------------------------------------------
# Inbound ingestion: per-attachment quarantine, not whole-email failure.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inbound_ingest_skips_infected_attachments(async_session, tmp_path):
    from app.models import Tenant
    from app.services import inbound_email_service as svc
    from app.services.inbound_attachment_storage import reset_storage_for_tests

    storage = LocalInboundStorage(base_path=str(tmp_path), scanner=EicarScanner())
    reset_storage_for_tests(storage)
    try:
        tenant = Tenant(name="Acme", slug="acme", plan="pilot", is_active=True)
        async_session.add(tenant)
        await async_session.flush()
        tenant.inbound_secret_token = None
        await async_session.commit()
        parsed = svc.ParsedEmail(
            message_id="<av-skip-1@x>",
            from_address="vendor@example.com",
            to_address="submissions@acme.in.getonce.com",
            subject="mixed",
            attachments=[
                svc.ParsedAttachment("clean.pdf", "application/pdf", b"clean-bytes"),
                svc.ParsedAttachment("evil.pdf", "application/pdf", EICAR_TEST_STRING),
            ],
        )
        email, was_dup = await svc.ingest(async_session, parsed)
        assert was_dup is False
        # Clean attachment kept, EICAR attachment dropped.
        assert email.attachment_count == 1
    finally:
        reset_storage_for_tests(None)
