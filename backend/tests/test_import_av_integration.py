"""L4 — integration tests for AV scanning inside ``import_service.create_import_job``."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ImportEntityType, ImportJob
from app.services import import_service
from app.services.av_scanner import (
    EICAR_TEST_STRING,
    EicarScanner,
    ScanReport,
    ScanResult,
    StubAllowScanner,
    reset_scanner_for_tests,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _isolate_av_scanner_and_storage(tmp_path: Path, monkeypatch):
    reset_scanner_for_tests(None)
    # Re-home the import storage under tmp_path so we never touch the
    # repo-relative ./.once/imports directory.
    monkeypatch.setattr(
        import_service.settings, "import_storage_path", str(tmp_path)
    )
    yield
    reset_scanner_for_tests(None)


async def _count_jobs(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count(ImportJob.id))) or 0)


async def test_eicar_csv_rejected_with_infected_upload_error(
    async_session: AsyncSession,
):
    reset_scanner_for_tests(EicarScanner())
    payload = b"name,fein\n" + EICAR_TEST_STRING + b"\n"
    before = await _count_jobs(async_session)
    with pytest.raises(import_service.InfectedUploadError) as exc_info:
        await import_service.create_import_job(
            async_session,
            tenant_id="tenant-av-1",
            entity_type=ImportEntityType.SUPPLIER,
            original_filename="evil.csv",
            content_type="text/csv",
            file_bytes=payload,
        )
    assert exc_info.value.signature == "Eicar-Test-Signature"
    assert exc_info.value.scanner == "eicar"
    assert "infected" in str(exc_info.value).lower()
    # The half-created job row was rolled back inside create_import_job.
    after = await _count_jobs(async_session)
    assert after == before


async def test_eicar_csv_does_not_write_file(
    async_session: AsyncSession, tmp_path: Path
):
    reset_scanner_for_tests(EicarScanner())
    payload = b"name,fein\n" + EICAR_TEST_STRING + b"\n"
    with pytest.raises(import_service.InfectedUploadError):
        await import_service.create_import_job(
            async_session,
            tenant_id="tenant-av-2",
            entity_type=ImportEntityType.SUPPLIER,
            original_filename="evil.csv",
            content_type="text/csv",
            file_bytes=payload,
        )
    # No CSV bytes should be on disk anywhere under the storage root.
    on_disk = [p for p in tmp_path.rglob("*.csv") if p.is_file()]
    assert on_disk == []


async def test_clean_csv_creates_job(async_session: AsyncSession):
    reset_scanner_for_tests(StubAllowScanner())
    payload = b"name,fein,state,city,address_line1,zip\nAcme,12-3456789,CA,Oakland,1 Main,94601\n"
    before = await _count_jobs(async_session)
    job = await import_service.create_import_job(
        async_session,
        tenant_id="tenant-av-3",
        entity_type=ImportEntityType.SUPPLIER,
        original_filename="clean.csv",
        content_type="text/csv",
        file_bytes=payload,
    )
    assert job.id
    assert job.original_filename == "clean.csv"
    after = await _count_jobs(async_session)
    assert after == before + 1


class _BrokenScanner:
    name = "fake_broken_import"

    def scan_bytes(self, data: bytes, *, hint_name: str | None = None) -> ScanReport:
        return ScanReport(
            result=ScanResult.ERROR,
            signature=None,
            detail="simulated outage in import path",
            scanner=self.name,
        )


async def test_scanner_unavailable_fail_closed_raises(
    async_session: AsyncSession, monkeypatch
):
    monkeypatch.setattr(
        import_service.settings, "av_fail_closed_on_scanner_error", True
    )
    reset_scanner_for_tests(_BrokenScanner())
    before = await _count_jobs(async_session)
    with pytest.raises(import_service.ScannerUnavailableError) as exc_info:
        await import_service.create_import_job(
            async_session,
            tenant_id="tenant-av-4",
            entity_type=ImportEntityType.SUPPLIER,
            original_filename="x.csv",
            content_type="text/csv",
            file_bytes=b"name,fein\nAcme,12-3456789\n",
        )
    assert exc_info.value.scanner == "fake_broken_import"
    assert exc_info.value.error_code == "av_scanner_unavailable"
    after = await _count_jobs(async_session)
    assert after == before


async def test_scanner_unavailable_fail_open_creates_job(
    async_session: AsyncSession, monkeypatch
):
    monkeypatch.setattr(
        import_service.settings, "av_fail_closed_on_scanner_error", False
    )
    reset_scanner_for_tests(_BrokenScanner())
    job = await import_service.create_import_job(
        async_session,
        tenant_id="tenant-av-5",
        entity_type=ImportEntityType.SUPPLIER,
        original_filename="x.csv",
        content_type="text/csv",
        file_bytes=b"name,fein\nAcme,12-3456789\n",
    )
    assert job.id


async def test_infected_upload_error_code_is_av_infected_file():
    # Pure class-shape test — no DB needed.
    err = import_service.InfectedUploadError(
        signature="Eicar-Test-Signature", scanner="eicar"
    )
    assert err.error_code == "av_infected_file"
    assert "Eicar-Test-Signature" in str(err)
