"""Tenant-isolation regression tests for inbound_email_service.

Covers the service-layer fix that requires ``tenant_id`` on
``retry_routing`` and ``quarantine``: a cross-tenant ``email_id`` must
raise :class:`InboundIngestError` instead of mutating another tenant's
row.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InboundEmail, Tenant
from app.models.inbound_email import InboundEmailStatus
from app.services import inbound_email_service as svc

pytestmark = pytest.mark.asyncio


async def _seed_tenant(session: AsyncSession, slug: str) -> Tenant:
    tenant = Tenant(name=slug.title(), slug=slug, plan="pilot", is_active=True)
    session.add(tenant)
    await session.flush()
    return tenant


async def _seed_email(
    session: AsyncSession, tenant: Tenant, *, message_id: str
) -> InboundEmail:
    email = InboundEmail(
        tenant_id=tenant.id,
        message_id=message_id,
        from_address="broker@example.com",
        to_address=f"submissions@{tenant.slug}.in.getonce.com",
        subject="Quote",
        status=InboundEmailStatus.FAILED,
        raw_storage_url="local://x",
    )
    session.add(email)
    await session.flush()
    return email


async def test_retry_routing_rejects_cross_tenant(async_session: AsyncSession):
    tenant_a = await _seed_tenant(async_session, "acme")
    tenant_b = await _seed_tenant(async_session, "globex")
    email_a = await _seed_email(async_session, tenant_a, message_id="<a@x>")
    await async_session.commit()

    with pytest.raises(svc.InboundIngestError):
        await svc.retry_routing(
            async_session, tenant_id=tenant_b.id, email_id=email_a.id
        )

    refreshed = await async_session.get(InboundEmail, email_a.id)
    assert refreshed is not None
    # Status must not have been mutated by the failed cross-tenant call.
    assert refreshed.status == InboundEmailStatus.FAILED


async def test_quarantine_rejects_cross_tenant(async_session: AsyncSession):
    tenant_a = await _seed_tenant(async_session, "acme")
    tenant_b = await _seed_tenant(async_session, "globex")
    email_a = await _seed_email(async_session, tenant_a, message_id="<q@x>")
    email_a.status = InboundEmailStatus.PARSING
    await async_session.flush()
    await async_session.commit()

    with pytest.raises(svc.InboundIngestError):
        await svc.quarantine(
            async_session, tenant_id=tenant_b.id, email_id=email_a.id
        )

    refreshed = await async_session.get(InboundEmail, email_a.id)
    assert refreshed is not None
    assert refreshed.status == InboundEmailStatus.PARSING
    assert refreshed.routing_error != "manual_quarantine"


async def test_retry_routing_requires_tenant_id(async_session: AsyncSession):
    tenant = await _seed_tenant(async_session, "acme")
    email = await _seed_email(async_session, tenant, message_id="<r@x>")
    await async_session.commit()
    with pytest.raises(svc.InboundIngestError):
        await svc.retry_routing(async_session, tenant_id="", email_id=email.id)


async def test_quarantine_requires_tenant_id(async_session: AsyncSession):
    tenant = await _seed_tenant(async_session, "acme")
    email = await _seed_email(async_session, tenant, message_id="<q2@x>")
    await async_session.commit()
    with pytest.raises(svc.InboundIngestError):
        await svc.quarantine(async_session, tenant_id="", email_id=email.id)


async def test_retry_routing_missing_email_id(async_session: AsyncSession):
    tenant = await _seed_tenant(async_session, "acme")
    await async_session.commit()
    with pytest.raises(svc.InboundIngestError):
        await svc.retry_routing(
            async_session, tenant_id=tenant.id, email_id="no-such"
        )
