"""Tests for app.services.extraction_service."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_result import (
    ExtractionSourceType,
    ExtractionStatus,
)
from app.services import extraction_service
from app.services.extraction_service import (
    ExtractionNotFoundError,
    InMemoryPdfLoader,
    accept_extraction,
    create_extraction_record,
    get_extraction,
    list_extractions,
    reject_extraction,
    run_extraction,
)
from tests.fixtures.pdfs import make_pdf

pytestmark = pytest.mark.asyncio


TENANT = "11111111-1111-1111-1111-111111111111"
OTHER_TENANT = "22222222-2222-2222-2222-222222222222"
DOC_ID = "33333333-3333-3333-3333-333333333333"


def _coi_blob() -> bytes:
    return make_pdf(
        [
            "ACORD 25 CERTIFICATE OF LIABILITY INSURANCE",
            "PRODUCER",
            "Smith Brokers",
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
async def loader() -> InMemoryPdfLoader:
    ldr = InMemoryPdfLoader()
    extraction_service.set_default_loader(ldr)
    try:
        yield ldr
    finally:
        extraction_service.set_default_loader(InMemoryPdfLoader())


async def test_create_extraction_record_inserts_pending_row(
    async_session: AsyncSession,
) -> None:
    row = await create_extraction_record(
        async_session,
        tenant_id=TENANT,
        document_type=ExtractionSourceType.COI,
        document_id=DOC_ID,
    )
    assert row.id and row.status == ExtractionStatus.PENDING.value
    assert row.extractor_version
    assert row.source_document_type == "coi"


async def test_run_extraction_succeeds_on_clean_pdf(
    async_session: AsyncSession, loader: InMemoryPdfLoader
) -> None:
    row = await create_extraction_record(
        async_session,
        tenant_id=TENANT,
        document_type=ExtractionSourceType.COI,
        document_id=DOC_ID,
    )
    await async_session.commit()
    loader.put(
        tenant_id=TENANT,
        source_type=ExtractionSourceType.COI,
        source_id=DOC_ID,
        blob=_coi_blob(),
    )
    result = await run_extraction(async_session, extraction_id=row.id)
    assert result.status in {
        ExtractionStatus.SUCCEEDED.value,
        ExtractionStatus.PARTIAL.value,
    }
    assert result.extracted_fields["policy_number"] == "GL-2026-00001"
    assert "policy_number" in result.field_confidences


async def test_run_extraction_records_failed_when_pdf_missing(
    async_session: AsyncSession, loader: InMemoryPdfLoader
) -> None:
    row = await create_extraction_record(
        async_session,
        tenant_id=TENANT,
        document_type=ExtractionSourceType.COI,
        document_id="missing-id",
    )
    await async_session.commit()
    result = await run_extraction(async_session, extraction_id=row.id)
    assert result.status == ExtractionStatus.FAILED.value
    assert "loader" in (result.error or "")


async def test_run_extraction_records_failed_on_encrypted_pdf(
    async_session: AsyncSession, loader: InMemoryPdfLoader
) -> None:
    row = await create_extraction_record(
        async_session,
        tenant_id=TENANT,
        document_type=ExtractionSourceType.COI,
        document_id=DOC_ID,
    )
    await async_session.commit()
    loader.put(
        tenant_id=TENANT,
        source_type=ExtractionSourceType.COI,
        source_id=DOC_ID,
        blob=b"%PDF-1.4\n/Encrypt 1 0 R\nfake\n",
    )
    result = await run_extraction(async_session, extraction_id=row.id)
    assert result.status == ExtractionStatus.FAILED.value
    assert result.error == "pdf_encrypted"


async def test_run_extraction_records_failed_on_garbage(
    async_session: AsyncSession, loader: InMemoryPdfLoader
) -> None:
    row = await create_extraction_record(
        async_session,
        tenant_id=TENANT,
        document_type=ExtractionSourceType.COI,
        document_id=DOC_ID,
    )
    await async_session.commit()
    loader.put(
        tenant_id=TENANT,
        source_type=ExtractionSourceType.COI,
        source_id=DOC_ID,
        blob=b"not a pdf",
    )
    result = await run_extraction(async_session, extraction_id=row.id)
    assert result.status == ExtractionStatus.FAILED.value


async def test_run_extraction_unknown_id(async_session: AsyncSession) -> None:
    with pytest.raises(ExtractionNotFoundError):
        await run_extraction(async_session, extraction_id="does-not-exist")


async def test_accept_extraction_merges_overrides(
    async_session: AsyncSession, loader: InMemoryPdfLoader
) -> None:
    row = await create_extraction_record(
        async_session,
        tenant_id=TENANT,
        document_type=ExtractionSourceType.COI,
        document_id=DOC_ID,
    )
    await async_session.commit()
    loader.put(
        tenant_id=TENANT,
        source_type=ExtractionSourceType.COI,
        source_id=DOC_ID,
        blob=_coi_blob(),
    )
    await run_extraction(async_session, extraction_id=row.id)
    accepted = await accept_extraction(
        async_session,
        tenant_id=TENANT,
        extraction_id=row.id,
        user_id="user-1",
        fields={"policy_number": "OVERRIDE-123"},
    )
    assert accepted.status == ExtractionStatus.ACCEPTED.value
    assert accepted.extracted_fields["policy_number"] == "OVERRIDE-123"
    assert accepted.reviewed_by_user_id == "user-1"


async def test_reject_extraction_records_reason(
    async_session: AsyncSession, loader: InMemoryPdfLoader
) -> None:
    row = await create_extraction_record(
        async_session,
        tenant_id=TENANT,
        document_type=ExtractionSourceType.COI,
        document_id=DOC_ID,
    )
    await async_session.commit()
    rejected = await reject_extraction(
        async_session,
        tenant_id=TENANT,
        extraction_id=row.id,
        user_id="user-2",
        reason="wrong document",
    )
    assert rejected.status == ExtractionStatus.REJECTED.value
    assert any("wrong document" in w for w in (rejected.warnings or []))


async def test_list_extractions_filters_by_tenant(
    async_session: AsyncSession,
) -> None:
    await create_extraction_record(
        async_session,
        tenant_id=TENANT,
        document_type=ExtractionSourceType.COI,
        document_id=DOC_ID,
    )
    await create_extraction_record(
        async_session,
        tenant_id=OTHER_TENANT,
        document_type=ExtractionSourceType.COI,
        document_id=DOC_ID,
    )
    await async_session.commit()
    rows, total = await list_extractions(async_session, tenant_id=TENANT)
    assert total == 1
    assert rows[0].tenant_id == TENANT


async def test_list_extractions_filters_by_document_type(
    async_session: AsyncSession,
) -> None:
    await create_extraction_record(
        async_session,
        tenant_id=TENANT,
        document_type=ExtractionSourceType.COI,
        document_id=DOC_ID,
    )
    await create_extraction_record(
        async_session,
        tenant_id=TENANT,
        document_type=ExtractionSourceType.EO_CERTIFICATE,
        document_id=DOC_ID,
    )
    await async_session.commit()
    rows, total = await list_extractions(
        async_session,
        tenant_id=TENANT,
        document_type=ExtractionSourceType.EO_CERTIFICATE,
    )
    assert total == 1
    assert rows[0].source_document_type == "eo_certificate"


async def test_get_extraction_isolated_by_tenant(
    async_session: AsyncSession,
) -> None:
    row = await create_extraction_record(
        async_session,
        tenant_id=TENANT,
        document_type=ExtractionSourceType.COI,
        document_id=DOC_ID,
    )
    await async_session.commit()
    assert await get_extraction(
        async_session, tenant_id=OTHER_TENANT, extraction_id=row.id
    ) is None
    assert (
        await get_extraction(async_session, tenant_id=TENANT, extraction_id=row.id)
    ).id == row.id
