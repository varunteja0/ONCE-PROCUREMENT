"""Tenant-isolation regression tests for import_service.

Covers the fixes that thread ``tenant_id`` through ``run_validation``,
``run_commit``, ``get_job_errors`` and ``count_job_errors`` so that a
cross-tenant ``job_id`` raises :class:`JobNotFoundError` instead of
mutating / leaking another tenant's rows.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ImportEntityType,
    ImportRowError,
    ImportStatus,
)
from app.services import import_service

pytestmark = pytest.mark.asyncio


FIXTURES = Path(__file__).parent / "fixtures" / "imports"


async def _seed_job(
    session: AsyncSession,
    *,
    tenant_id: str,
    fixture: str = "suppliers_valid.csv",
):
    data = (FIXTURES / fixture).read_bytes()
    job = await import_service.create_import_job(
        session,
        tenant_id=tenant_id,
        entity_type=ImportEntityType.SUPPLIER,
        original_filename=fixture,
        content_type="text/csv",
        file_bytes=data,
    )
    await session.commit()
    return job


async def test_run_validation_rejects_cross_tenant(
    async_session: AsyncSession,
) -> None:
    job_a = await _seed_job(async_session, tenant_id="t-iso-A")
    with pytest.raises(import_service.JobNotFoundError):
        await import_service.run_validation(
            async_session, tenant_id="t-iso-B", job_id=job_a.id
        )
    refreshed = await async_session.get(type(job_a), job_a.id)
    assert refreshed is not None
    # State machine was never advanced.
    assert refreshed.status == ImportStatus.PENDING


async def test_run_validation_requires_tenant_id(
    async_session: AsyncSession,
) -> None:
    job = await _seed_job(async_session, tenant_id="t-iso-req")
    with pytest.raises(import_service.JobNotFoundError):
        await import_service.run_validation(
            async_session, tenant_id="", job_id=job.id
        )


async def test_run_commit_rejects_cross_tenant(
    async_session: AsyncSession,
) -> None:
    job_a = await _seed_job(async_session, tenant_id="t-iso-cA")
    # Move job into DRY_RUN_READY so cross-tenant call reaches the filter.
    await import_service.run_validation(
        async_session, tenant_id="t-iso-cA", job_id=job_a.id
    )
    await async_session.commit()
    with pytest.raises(import_service.JobNotFoundError):
        await import_service.run_commit(tenant_id="t-iso-cB", job_id=job_a.id)


async def test_run_commit_requires_tenant_id(
    async_session: AsyncSession,
) -> None:
    job = await _seed_job(async_session, tenant_id="t-iso-cR")
    await import_service.run_validation(
        async_session, tenant_id="t-iso-cR", job_id=job.id
    )
    await async_session.commit()
    with pytest.raises(import_service.JobNotFoundError):
        await import_service.run_commit(tenant_id="", job_id=job.id)


async def test_get_job_errors_filters_by_tenant(
    async_session: AsyncSession,
) -> None:
    """Errors of tenant A's job must NOT be returned for tenant B's query."""

    job_a = await _seed_job(
        async_session, tenant_id="t-err-A", fixture="suppliers_mixed.csv"
    )
    await import_service.run_validation(
        async_session, tenant_id="t-err-A", job_id=job_a.id
    )
    await async_session.commit()

    # Manually insert an error against job A to ensure rows exist.
    async_session.add(
        ImportRowError(
            import_job_id=job_a.id,
            row_number=99,
            column="fein",
            value="bogus",
            error_code="manual",
            error_message="seeded",
        )
    )
    await async_session.commit()

    # Tenant A sees them.
    own = await import_service.get_job_errors(
        async_session, tenant_id="t-err-A", job_id=job_a.id
    )
    assert len(own) >= 1
    own_count = await import_service.count_job_errors(
        async_session, tenant_id="t-err-A", job_id=job_a.id
    )
    assert own_count >= 1

    # Tenant B does NOT see them — even though they pass the right job_id.
    leaked = await import_service.get_job_errors(
        async_session, tenant_id="t-err-B", job_id=job_a.id
    )
    assert leaked == []
    leaked_count = await import_service.count_job_errors(
        async_session, tenant_id="t-err-B", job_id=job_a.id
    )
    assert leaked_count == 0


async def test_get_job_errors_requires_tenant_id(
    async_session: AsyncSession,
) -> None:
    with pytest.raises(import_service.JobNotFoundError):
        await import_service.get_job_errors(
            async_session, tenant_id="", job_id="anything"
        )
    with pytest.raises(import_service.JobNotFoundError):
        await import_service.count_job_errors(
            async_session, tenant_id="", job_id="anything"
        )
