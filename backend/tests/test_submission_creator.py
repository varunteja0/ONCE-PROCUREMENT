"""L3.9 — Submission-creator router tests."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Supplier, Tenant
from app.models.inbound_email import InboundEmail
from app.models.inbound_routing_rule import InboundRoutingRule, InboundRuleAction
from app.services.inbound_routers.submission_creator import (
    SubmissionCreatorRouter,
    resolve_supplier,
)

pytestmark = pytest.mark.asyncio


async def _seed(session: AsyncSession, *, primary_email=None):
    t = Tenant(name="Acme", slug="acme", plan="pilot", is_active=True)
    session.add(t)
    await session.flush()
    sup = Supplier(
        tenant_id=t.id, legal_name="Acme Supplier", primary_email=primary_email
    )
    session.add(sup)
    await session.flush()
    return t, sup


async def test_resolve_by_email_exact(async_session: AsyncSession):
    t, sup = await _seed(async_session, primary_email="ops@acme-supplier.com")
    found, reason = await resolve_supplier(
        async_session,
        tenant_id=t.id,
        from_address="ops@acme-supplier.com",
        subject=None,
    )
    assert found is not None
    assert found.id == sup.id
    assert reason == "email_exact"


async def test_resolve_by_domain(async_session: AsyncSession):
    t, sup = await _seed(async_session, primary_email="ops@acme-supplier.com")
    found, reason = await resolve_supplier(
        async_session,
        tenant_id=t.id,
        from_address="bob@acme-supplier.com",
        subject=None,
    )
    assert found is not None and found.id == sup.id
    assert reason == "email_domain"


async def test_resolve_by_subject_tag_id(async_session: AsyncSession):
    t, sup = await _seed(async_session, primary_email=None)
    found, reason = await resolve_supplier(
        async_session,
        tenant_id=t.id,
        from_address="someone@unrelated.com",
        subject=f"[supplier:{sup.id}] new quote",
    )
    assert found is not None and found.id == sup.id
    assert reason == "tag"


async def test_resolve_by_subject_tag_email(async_session: AsyncSession):
    t, sup = await _seed(async_session, primary_email="ops@acme-supplier.com")
    found, reason = await resolve_supplier(
        async_session,
        tenant_id=t.id,
        from_address="anon@x.com",
        subject="[supplier:ops@acme-supplier.com] hi",
    )
    assert found is not None and reason == "tag"


async def test_resolve_unresolved_returns_none(async_session: AsyncSession):
    t, _ = await _seed(async_session, primary_email="ops@acme-supplier.com")
    found, reason = await resolve_supplier(
        async_session,
        tenant_id=t.id,
        from_address="x@nowhere.com",
        subject="random",
    )
    assert found is None
    assert reason == "unresolved"


async def test_resolve_scoped_to_tenant(async_session: AsyncSession):
    t1, _ = await _seed(async_session, primary_email="ops@acme.com")
    t2 = Tenant(name="Other", slug="other", plan="pilot", is_active=True)
    async_session.add(t2)
    await async_session.flush()
    found, _ = await resolve_supplier(
        async_session,
        tenant_id=t2.id,
        from_address="ops@acme.com",
        subject=None,
    )
    assert found is None


async def test_router_creates_draft_submission(async_session: AsyncSession):
    t, sup = await _seed(async_session, primary_email="ops@acme-supplier.com")
    email = InboundEmail(
        tenant_id=t.id,
        message_id="<m@x>",
        from_address="ops@acme-supplier.com",
        to_address="submissions@acme.in.getonce.com",
        subject="quote",
    )
    async_session.add(email)
    await async_session.flush()
    rule = InboundRoutingRule(
        tenant_id=t.id,
        name="default",
        priority=100,
        action=InboundRuleAction.CREATE_SUBMISSION,
    )
    router = SubmissionCreatorRouter()
    result = await router.route(async_session, email=email, attachments=[], rule=rule)
    assert result.status == "routed"
    assert result.draft_submission_id is not None
    assert result.draft_supplier_id == sup.id


async def test_router_handles_no_supplier(async_session: AsyncSession):
    t = Tenant(name="Acme", slug="acme", plan="pilot", is_active=True)
    async_session.add(t)
    await async_session.flush()
    email = InboundEmail(
        tenant_id=t.id,
        message_id="<m@x>",
        from_address="x@nowhere.com",
        to_address="submissions@acme.in.getonce.com",
        subject="quote",
    )
    async_session.add(email)
    await async_session.flush()
    rule = InboundRoutingRule(
        tenant_id=t.id, name="default", priority=100, action=InboundRuleAction.CREATE_SUBMISSION
    )
    result = await SubmissionCreatorRouter().route(
        async_session, email=email, attachments=[], rule=rule
    )
    assert result.status == "routed"
    assert result.draft_submission_id is None
    assert result.draft_supplier_id is None
