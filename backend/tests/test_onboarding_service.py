"""Unit tests for the onboarding state machine service.

These exercise the pure-domain rules (forward/backward arrows,
idempotency, skip semantics) directly against a real AsyncSession bound
to an in-memory SQLite engine provided by the shared conftest.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OnboardingStep, Tenant
from app.services import onboarding_service

pytestmark = pytest.mark.asyncio


async def _make_tenant(session: AsyncSession, *, name: str = "Acme") -> str:
    tenant = Tenant(name=name, slug=f"{name.lower()}-{id(name) & 0xffff:x}")
    session.add(tenant)
    await session.flush()
    return tenant.id


async def test_step_order_contains_all_steps() -> None:
    assert onboarding_service.STEP_ORDER[0] == OnboardingStep.START
    assert onboarding_service.STEP_ORDER[-1] == OnboardingStep.DONE
    assert len(set(onboarding_service.STEP_ORDER)) == len(onboarding_service.STEP_ORDER)


async def test_is_forward_transition() -> None:
    assert onboarding_service.is_forward_transition(
        OnboardingStep.START, OnboardingStep.EMAIL_PENDING
    )
    assert not onboarding_service.is_forward_transition(
        OnboardingStep.PROFILE, OnboardingStep.START
    )


async def test_create_state_is_idempotent(async_session: AsyncSession) -> None:
    tenant_id = await _make_tenant(async_session, name="One")
    first = await onboarding_service.create_state(async_session, tenant_id=tenant_id)
    second = await onboarding_service.create_state(async_session, tenant_id=tenant_id)
    assert first.tenant_id == second.tenant_id
    assert first.current_step == second.current_step == OnboardingStep.EMAIL_PENDING


async def test_advance_to_moves_forward(async_session: AsyncSession) -> None:
    tenant_id = await _make_tenant(async_session, name="Two")
    await onboarding_service.create_state(async_session, tenant_id=tenant_id)
    state = await onboarding_service.advance_to(
        async_session, tenant_id=tenant_id, target=OnboardingStep.EMAIL_VERIFIED
    )
    assert state.current_step == OnboardingStep.EMAIL_VERIFIED
    assert OnboardingStep.EMAIL_VERIFIED.value in state.completed_steps


async def test_advance_to_is_idempotent_on_repeat(async_session: AsyncSession) -> None:
    tenant_id = await _make_tenant(async_session, name="Three")
    await onboarding_service.create_state(async_session, tenant_id=tenant_id)
    a = await onboarding_service.advance_to(
        async_session, tenant_id=tenant_id, target=OnboardingStep.PROFILE
    )
    b = await onboarding_service.advance_to(
        async_session, tenant_id=tenant_id, target=OnboardingStep.PROFILE
    )
    assert a.current_step == b.current_step == OnboardingStep.PROFILE


async def test_backward_transition_rejected(async_session: AsyncSession) -> None:
    tenant_id = await _make_tenant(async_session, name="Four")
    await onboarding_service.create_state(async_session, tenant_id=tenant_id)
    await onboarding_service.advance_to(
        async_session, tenant_id=tenant_id, target=OnboardingStep.PORTAL
    )
    with pytest.raises(onboarding_service.OnboardingStateError):
        await onboarding_service.advance_to(
            async_session, tenant_id=tenant_id, target=OnboardingStep.PLAN
        )


async def test_profile_to_start_backward_allowed(async_session: AsyncSession) -> None:
    tenant_id = await _make_tenant(async_session, name="Five")
    await onboarding_service.create_state(async_session, tenant_id=tenant_id)
    await onboarding_service.advance_to(
        async_session, tenant_id=tenant_id, target=OnboardingStep.PROFILE
    )
    state = await onboarding_service.advance_to(
        async_session, tenant_id=tenant_id, target=OnboardingStep.START
    )
    assert state.current_step == OnboardingStep.START


async def test_skip_only_allowed_for_optional_steps(async_session: AsyncSession) -> None:
    tenant_id = await _make_tenant(async_session, name="Six")
    await onboarding_service.create_state(async_session, tenant_id=tenant_id)
    await onboarding_service.advance_to(
        async_session, tenant_id=tenant_id, target=OnboardingStep.PROFILE
    )
    with pytest.raises(Exception):
        await onboarding_service.skip_step(
            async_session, tenant_id=tenant_id, step=OnboardingStep.PROFILE
        )


async def test_skip_step_advances_state(async_session: AsyncSession) -> None:
    tenant_id = await _make_tenant(async_session, name="Seven")
    await onboarding_service.create_state(async_session, tenant_id=tenant_id)
    await onboarding_service.advance_to(
        async_session, tenant_id=tenant_id, target=OnboardingStep.PLAN
    )
    state = await onboarding_service.skip_step(
        async_session, tenant_id=tenant_id, step=OnboardingStep.PLAN
    )
    assert OnboardingStep.PLAN.value in state.skipped_steps
    assert state.current_step == OnboardingStep.PORTAL


async def test_mark_completed_sets_done(async_session: AsyncSession) -> None:
    tenant_id = await _make_tenant(async_session, name="Eight")
    await onboarding_service.create_state(async_session, tenant_id=tenant_id)
    state = await onboarding_service.mark_completed(async_session, tenant_id=tenant_id)
    assert state.current_step == OnboardingStep.DONE
    assert state.completed_at is not None


async def test_mark_completed_is_idempotent(async_session: AsyncSession) -> None:
    tenant_id = await _make_tenant(async_session, name="Nine")
    await onboarding_service.create_state(async_session, tenant_id=tenant_id)
    a = await onboarding_service.mark_completed(async_session, tenant_id=tenant_id)
    b = await onboarding_service.mark_completed(async_session, tenant_id=tenant_id)
    assert a.completed_at == b.completed_at


async def test_advance_after_done_rejected(async_session: AsyncSession) -> None:
    tenant_id = await _make_tenant(async_session, name="Ten")
    await onboarding_service.create_state(async_session, tenant_id=tenant_id)
    await onboarding_service.mark_completed(async_session, tenant_id=tenant_id)
    with pytest.raises(onboarding_service.OnboardingStateError):
        await onboarding_service.advance_to(
            async_session, tenant_id=tenant_id, target=OnboardingStep.PORTAL
        )


async def test_get_state_missing_raises(async_session: AsyncSession) -> None:
    with pytest.raises(Exception):
        await onboarding_service.get_state(
            async_session, tenant_id="00000000-0000-0000-0000-000000000000"
        )


async def test_step_data_merges(async_session: AsyncSession) -> None:
    tenant_id = await _make_tenant(async_session, name="Eleven")
    await onboarding_service.create_state(async_session, tenant_id=tenant_id)
    await onboarding_service.advance_to(
        async_session,
        tenant_id=tenant_id,
        target=OnboardingStep.PROFILE,
        step_data={"key1": "v1"},
    )
    state = await onboarding_service.advance_to(
        async_session,
        tenant_id=tenant_id,
        target=OnboardingStep.PLAN,
        step_data={"key2": "v2"},
    )
    assert state.step_data_json["key1"] == "v1"
    assert state.step_data_json["key2"] == "v2"
