"""Tests for the Celery wrapper in app.workers.tasks.extraction_tasks."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_result import ExtractionSourceType
from app.services import extraction_service
from app.services.extraction_service import InMemoryPdfLoader
from app.workers.celery_app import celery_app
from app.workers.tasks.extraction_tasks import extract_document
from tests.fixtures.pdfs import make_pdf

pytestmark = pytest.mark.asyncio

TENANT = "11111111-1111-1111-1111-111111111111"


def _coi_blob() -> bytes:
    return make_pdf(
        [
            "ACORD 25 CERTIFICATE OF LIABILITY INSURANCE",
            "INSURED",
            "Acme Inc",
            "FEIN: 12-3456789",
            "INSURER A: The Hartford NAIC # 19682",
            "COMMERCIAL GENERAL LIABILITY",
            "POLICY NUMBER: GL-2026-00001",
            "EFF 01/15/2026 EXP 01/15/2027",
            "$1,000,000 each occurrence",
            "$2,000,000 general aggregate",
            "CERTIFICATE HOLDER",
            "Big Co LLC",
            "CERTIFICATE NUMBER: CERT-9999",
        ]
    )


@pytest_asyncio.fixture
async def eager_celery() -> None:
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False


@pytest_asyncio.fixture
async def loader() -> InMemoryPdfLoader:
    ldr = InMemoryPdfLoader()
    extraction_service.set_default_loader(ldr)
    yield ldr
    extraction_service.set_default_loader(InMemoryPdfLoader())


async def _apply(extraction_id: str) -> dict:
    import asyncio as _aio

    return await _aio.to_thread(
        lambda: extract_document.apply(args=[extraction_id]).get()
    )


async def test_task_runs_extraction_and_returns_status(
    async_session: AsyncSession,
    eager_celery: None,
    loader: InMemoryPdfLoader,
) -> None:
    row = await extraction_service.create_extraction_record(
        async_session,
        tenant_id=TENANT,
        document_type=ExtractionSourceType.COI,
        document_id="doc-1",
    )
    await async_session.commit()
    loader.put(
        tenant_id=TENANT,
        source_type="coi",
        source_id="doc-1",
        blob=_coi_blob(),
    )
    result = await _apply(row.id)
    assert result["extraction_id"] == row.id
    assert result["status"] in {"succeeded", "partial"}
    assert result["fields_count"] > 0


async def test_task_returns_not_found_for_missing_extraction(
    async_session: AsyncSession,
    eager_celery: None,
    loader: InMemoryPdfLoader,
) -> None:
    result = await _apply("no-such-id")
    assert result == {"extraction_id": "no-such-id", "status": "not_found"}


async def test_task_records_failed_for_missing_pdf(
    async_session: AsyncSession,
    eager_celery: None,
    loader: InMemoryPdfLoader,
) -> None:
    row = await extraction_service.create_extraction_record(
        async_session,
        tenant_id=TENANT,
        document_type=ExtractionSourceType.COI,
        document_id="doc-missing",
    )
    await async_session.commit()
    result = await _apply(row.id)
    assert result["status"] == "failed"


async def test_task_is_registered_with_celery() -> None:
    assert "extractions.extract_document" in celery_app.tasks


async def test_task_returns_warnings_count(
    async_session: AsyncSession,
    eager_celery: None,
    loader: InMemoryPdfLoader,
) -> None:
    row = await extraction_service.create_extraction_record(
        async_session,
        tenant_id=TENANT,
        document_type=ExtractionSourceType.COI,
        document_id="doc-2",
    )
    await async_session.commit()
    loader.put(
        tenant_id=TENANT,
        source_type="coi",
        source_id="doc-2",
        blob=_coi_blob(),
    )
    result = await _apply(row.id)
    assert "warnings_count" in result


async def test_task_failed_pdf_produces_fields_count_zero(
    async_session: AsyncSession,
    eager_celery: None,
    loader: InMemoryPdfLoader,
) -> None:
    row = await extraction_service.create_extraction_record(
        async_session,
        tenant_id=TENANT,
        document_type=ExtractionSourceType.COI,
        document_id="doc-bad",
    )
    await async_session.commit()
    loader.put(
        tenant_id=TENANT,
        source_type="coi",
        source_id="doc-bad",
        blob=b"not a pdf",
    )
    result = await _apply(row.id)
    assert result["status"] == "failed"
    assert result["fields_count"] == 0
