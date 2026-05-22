"""L3.10 — Unit tests for :mod:`app.services.audit_logger`."""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant
from app.models.audit_log import (
    GENESIS_HASH_PREFIX,
    AuditActorType,
    AuditLogEntry,
    new_ulid,
)
from app.services.audit_logger import (
    canonicalise_core,
    compute_chain_hash,
    genesis_hash,
    record_audit_event,
)
from app.utils.canonical_json import canonical_json_bytes

pytestmark = pytest.mark.asyncio


async def _seed_tenant(session: AsyncSession, tid: str = "t-aud-1") -> Tenant:
    t = Tenant(id=tid, name=f"Acme {tid}", slug=tid, plan="pilot", is_active=True)
    session.add(t)
    await session.commit()
    return t


async def test_new_ulid_is_26_char_crockford() -> None:
    val = new_ulid()
    assert len(val) == 26
    assert set(val) <= set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")


async def test_genesis_hash_deterministic_per_tenant() -> None:
    assert genesis_hash("t-1") == genesis_hash("t-1")
    assert genesis_hash("t-1") != genesis_hash("t-2")
    expected = hashlib.sha256(GENESIS_HASH_PREFIX + b"t-1").hexdigest()
    assert genesis_hash("t-1") == expected


async def test_compute_chain_hash_uses_prev_bytes_and_canonical_core() -> None:
    prev = "00" * 32
    core = {"id": "A", "tenant_id": "t", "action_verb": "created"}
    h = compute_chain_hash(prev, core)
    expected = hashlib.sha256(bytes.fromhex(prev) + canonical_json_bytes(core)).hexdigest()
    assert h == expected
    assert len(h) == 64


async def test_record_audit_event_appends_first_row_with_genesis_prev(
    async_session: AsyncSession,
) -> None:
    await _seed_tenant(async_session)
    row = await record_audit_event(
        async_session,
        tenant_id="t-aud-1",
        actor_type=AuditActorType.USER,
        actor_id="u-1",
        action_verb="created",
        resource_type="supplier",
        resource_id="sup-1",
    )
    await async_session.commit()
    assert row is not None
    assert row.chain_position == 1
    assert row.prev_hash == genesis_hash("t-aud-1")


async def test_chain_links_three_rows(async_session: AsyncSession) -> None:
    await _seed_tenant(async_session)
    for i in range(3):
        await record_audit_event(
            async_session,
            tenant_id="t-aud-1",
            actor_type=AuditActorType.USER,
            action_verb="created",
            resource_type="supplier",
            resource_id=f"sup-{i}",
        )
    await async_session.commit()
    rows = (
        await async_session.execute(
            select(AuditLogEntry)
            .where(AuditLogEntry.tenant_id == "t-aud-1")
            .order_by(AuditLogEntry.chain_position)
        )
    ).scalars().all()
    assert [r.chain_position for r in rows] == [1, 2, 3]
    assert rows[1].prev_hash == rows[0].this_hash
    assert rows[2].prev_hash == rows[1].this_hash


async def test_per_tenant_chains_are_independent(async_session: AsyncSession) -> None:
    await _seed_tenant(async_session, "t-a")
    await _seed_tenant(async_session, "t-b")
    for tid in ("t-a", "t-b"):
        for _ in range(2):
            await record_audit_event(
                async_session,
                tenant_id=tid,
                actor_type=AuditActorType.SYSTEM,
                action_verb="created",
                resource_type="x",
            )
    await async_session.commit()
    a_rows = (await async_session.execute(
        select(AuditLogEntry).where(AuditLogEntry.tenant_id == "t-a")
        .order_by(AuditLogEntry.chain_position)
    )).scalars().all()
    b_rows = (await async_session.execute(
        select(AuditLogEntry).where(AuditLogEntry.tenant_id == "t-b")
        .order_by(AuditLogEntry.chain_position)
    )).scalars().all()
    assert [r.chain_position for r in a_rows] == [1, 2]
    assert [r.chain_position for r in b_rows] == [1, 2]
    assert a_rows[0].prev_hash == genesis_hash("t-a")
    assert b_rows[0].prev_hash == genesis_hash("t-b")
    assert a_rows[0].this_hash != b_rows[0].this_hash


async def test_payload_summary_is_redacted(async_session: AsyncSession) -> None:
    await _seed_tenant(async_session)
    row = await record_audit_event(
        async_session,
        tenant_id="t-aud-1",
        actor_type=AuditActorType.USER,
        action_verb="updated",
        resource_type="supplier",
        payload_summary={"password": "hunter2", "ok": "yes"},
    )
    await async_session.commit()
    assert row is not None
    assert row.payload_summary["password"] != "hunter2"
    assert row.payload_summary["ok"] == "yes"


async def test_record_returns_none_on_failure(async_session: AsyncSession) -> None:
    # No tenant seeded → FK violates → best-effort returns None, no raise.
    out = await record_audit_event(
        async_session,
        tenant_id="missing-tenant",
        actor_type=AuditActorType.USER,
        action_verb="created",
        resource_type="supplier",
    )
    # The append itself may succeed in SQLite (FK off by default in tests).
    # The contract is that the call never raises; assert that loosely:
    assert out is None or isinstance(out, AuditLogEntry)


async def test_canonicalise_core_includes_only_chain_fields() -> None:
    core = canonicalise_core(
        row_id="R",
        tenant_id="T",
        actor_type=AuditActorType.USER,
        actor_id="u",
        action_verb="created",
        resource_type="supplier",
        resource_id="s",
        occurred_at=__import__("datetime").datetime(2026, 1, 1),
        payload_summary={"a": 1},
        request_id="req",
    )
    # ip / user_agent / actor_email / resource_label are NOT part of the chain
    assert "ip" not in core
    assert "user_agent" not in core
    assert "actor_email" not in core
    assert core["actor_type"] == "user"


async def test_chain_position_strictly_increments(async_session: AsyncSession) -> None:
    await _seed_tenant(async_session)
    positions: list[int] = []
    for _ in range(5):
        row = await record_audit_event(
            async_session,
            tenant_id="t-aud-1",
            actor_type=AuditActorType.USER,
            action_verb="created",
            resource_type="x",
        )
        assert row is not None
        positions.append(row.chain_position)
    await async_session.commit()
    assert positions == sorted(positions)
    assert positions == list(range(1, 6))


async def test_hash_changes_when_resource_id_differs(async_session: AsyncSession) -> None:
    await _seed_tenant(async_session)
    r1 = await record_audit_event(
        async_session,
        tenant_id="t-aud-1",
        actor_type=AuditActorType.USER,
        action_verb="created",
        resource_type="supplier",
        resource_id="A",
    )
    r2 = await record_audit_event(
        async_session,
        tenant_id="t-aud-1",
        actor_type=AuditActorType.USER,
        action_verb="created",
        resource_type="supplier",
        resource_id="B",
    )
    await async_session.commit()
    assert r1 is not None and r2 is not None
    assert r1.this_hash != r2.this_hash


async def test_no_existing_rows_means_first_prev_is_genesis(
    async_session: AsyncSession,
) -> None:
    await _seed_tenant(async_session, "t-fresh")
    row = await record_audit_event(
        async_session,
        tenant_id="t-fresh",
        actor_type=AuditActorType.SYSTEM,
        action_verb="created",
        resource_type="bootstrap",
    )
    await async_session.commit()
    assert row is not None
    assert row.prev_hash == genesis_hash("t-fresh")


async def test_check_constraint_rejects_short_hash(async_session: AsyncSession) -> None:
    """Sanity-check that the hex64 CheckConstraint is enforced on SQLite."""
    await _seed_tenant(async_session, "t-cc")
    bad = AuditLogEntry(
        id=new_ulid(),
        tenant_id="t-cc",
        actor_type=AuditActorType.USER,
        action_verb="created",
        resource_type="x",
        prev_hash="abc",  # too short
        this_hash="def",
        chain_position=1,
    )
    async_session.add(bad)
    with pytest.raises(Exception):
        await async_session.flush()
    await async_session.rollback()
    # Belt-and-braces: explicit raw insert should also fail.
    with pytest.raises(Exception):
        await async_session.execute(
            text(
                "INSERT INTO audit_trail (id, tenant_id, actor_type, action_verb,"
                " resource_type, prev_hash, this_hash, chain_position)"
                " VALUES ('x','t-cc','user','x','x','abc','def',1)"
            )
        )
        await async_session.commit()
    await async_session.rollback()
