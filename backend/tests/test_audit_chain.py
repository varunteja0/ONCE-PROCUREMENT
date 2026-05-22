"""L3.10 — Tests for :mod:`app.services.audit_chain` verifier."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant
from app.models.audit_log import AuditActorType
from app.services.audit_chain import verify_chain
from app.services.audit_logger import record_audit_event

pytestmark = pytest.mark.asyncio


async def _seed_tenant(session: AsyncSession, tid: str = "t-chain") -> None:
    session.add(Tenant(id=tid, name="x", slug=tid, plan="pilot", is_active=True))
    await session.commit()


async def _append_n(session: AsyncSession, tid: str, n: int) -> None:
    for i in range(n):
        await record_audit_event(
            session,
            tenant_id=tid,
            actor_type=AuditActorType.USER,
            action_verb="created",
            resource_type="supplier",
            resource_id=f"s-{i}",
        )
    await session.commit()


async def test_empty_chain_is_valid(async_session: AsyncSession) -> None:
    await _seed_tenant(async_session, "t-empty")
    result = await verify_chain(async_session, tenant_id="t-empty")
    assert result.valid is True
    assert result.rows_checked == 0
    assert result.breaks == []


async def test_clean_chain_5_rows_valid(async_session: AsyncSession) -> None:
    await _seed_tenant(async_session)
    await _append_n(async_session, "t-chain", 5)
    result = await verify_chain(async_session, tenant_id="t-chain")
    assert result.valid is True
    assert result.rows_checked == 5
    assert result.breaks == []


async def test_tampered_resource_id_detected(async_session: AsyncSession) -> None:
    await _seed_tenant(async_session)
    await _append_n(async_session, "t-chain", 4)
    await async_session.execute(
        text("UPDATE audit_trail SET resource_id='HACKED' WHERE chain_position=2")
    )
    await async_session.commit()
    result = await verify_chain(async_session, tenant_id="t-chain")
    assert result.valid is False
    # Position 2 fails this_hash; positions 3 & 4 then mismatch prev_hash.
    reasons = {b.reason for b in result.breaks}
    assert "this_hash_mismatch" in reasons


async def test_tampered_this_hash_detected(async_session: AsyncSession) -> None:
    await _seed_tenant(async_session)
    await _append_n(async_session, "t-chain", 3)
    await async_session.execute(
        text("UPDATE audit_trail SET this_hash='" + "a" * 64 + "' WHERE chain_position=1")
    )
    await async_session.commit()
    result = await verify_chain(async_session, tenant_id="t-chain")
    assert result.valid is False
    assert any(b.reason == "this_hash_mismatch" for b in result.breaks)


async def test_deleted_row_creates_position_gap(async_session: AsyncSession) -> None:
    await _seed_tenant(async_session)
    await _append_n(async_session, "t-chain", 4)
    await async_session.execute(
        text("DELETE FROM audit_trail WHERE chain_position=2")
    )
    await async_session.commit()
    result = await verify_chain(async_session, tenant_id="t-chain")
    assert result.valid is False
    assert any(b.reason == "position_gap" for b in result.breaks)


async def test_partial_range_verification(async_session: AsyncSession) -> None:
    await _seed_tenant(async_session)
    await _append_n(async_session, "t-chain", 6)
    # Verify only positions 3..5 — should pick up the correct prev for 3.
    result = await verify_chain(
        async_session, tenant_id="t-chain", from_position=3, to_position=5
    )
    assert result.valid is True
    assert result.rows_checked == 3
    assert result.from_position == 3
    assert result.to_position == 5


async def test_cross_tenant_isolation(async_session: AsyncSession) -> None:
    await _seed_tenant(async_session, "t-a")
    await _seed_tenant(async_session, "t-b")
    await _append_n(async_session, "t-a", 3)
    # Tampering tenant-b's empty chain shouldn't affect tenant-a.
    result = await verify_chain(async_session, tenant_id="t-a")
    assert result.valid is True
    assert result.rows_checked == 3
    other = await verify_chain(async_session, tenant_id="t-b")
    assert other.valid is True


async def test_swapped_prev_hash_detected(async_session: AsyncSession) -> None:
    await _seed_tenant(async_session)
    await _append_n(async_session, "t-chain", 3)
    await async_session.execute(
        text("UPDATE audit_trail SET prev_hash='" + "0" * 64 + "' WHERE chain_position=2")
    )
    await async_session.commit()
    result = await verify_chain(async_session, tenant_id="t-chain")
    assert result.valid is False
    reasons = {b.reason for b in result.breaks}
    assert "prev_hash_mismatch" in reasons or "this_hash_mismatch" in reasons


async def test_break_records_carry_diagnostic_fields(
    async_session: AsyncSession,
) -> None:
    await _seed_tenant(async_session)
    await _append_n(async_session, "t-chain", 2)
    await async_session.execute(
        text("UPDATE audit_trail SET action_verb='FAKE' WHERE chain_position=1")
    )
    await async_session.commit()
    result = await verify_chain(async_session, tenant_id="t-chain")
    assert not result.valid
    b = result.breaks[0]
    assert b.chain_position == 1
    assert b.expected_this_hash != b.actual_this_hash


async def test_verify_does_not_mutate(async_session: AsyncSession) -> None:
    await _seed_tenant(async_session)
    await _append_n(async_session, "t-chain", 4)
    before = (
        await async_session.execute(text("SELECT COUNT(*) FROM audit_trail"))
    ).scalar_one()
    await verify_chain(async_session, tenant_id="t-chain")
    await verify_chain(async_session, tenant_id="t-chain")
    after = (
        await async_session.execute(text("SELECT COUNT(*) FROM audit_trail"))
    ).scalar_one()
    assert before == after == 4
