"""Tests for the nightly audit-hash Celery task + service.

Covers:

* Happy path: a fresh tenant + audit rows produces a digest row, and the
  task summary reports ``tenants_new``.
* Idempotency: running the task twice does NOT duplicate digest rows.
* Tamper detection: mutating an ``AuditLog`` row after the digest is
  stored causes ``verify_daily_digest`` to raise ``AuditHashMismatch``
  and the task to report ``tenants_mismatched``.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import func, select, update

import app.db as app_db
from app.models import AuditHashDigest, AuditLog, Tenant
from app.services.audit_hash_service import (
    AuditHashMismatch,
    ensure_daily_digest,
    verify_daily_digest,
)
from app.workers.tasks.audit_tasks import verify_nightly_audit_hash_task

pytestmark = pytest.mark.asyncio


def _yesterday() -> datetime.date:  # type: ignore[name-defined]
    return (datetime.now(tz=UTC) - timedelta(days=1)).date()


async def _seed_tenant() -> str:
    async with app_db.AsyncSessionLocal() as session:
        tenant = Tenant(name="Acme MGA", slug="acme")
        session.add(tenant)
        await session.commit()
        return tenant.id


async def _seed_yesterday_audit_rows(tenant_id: str, count: int = 3) -> None:
    yday = _yesterday()
    base = datetime.combine(yday, time(12, 0), tzinfo=UTC)
    async with app_db.AsyncSessionLocal() as session:
        for i in range(count):
            session.add(
                AuditLog(
                    tenant_id=tenant_id,
                    action=f"test.event.{i}",
                    resource_type="test",
                    resource_id=f"r-{i}",
                    metadata_json={"i": i},
                    occurred_at=base + timedelta(minutes=i),
                )
            )
        await session.commit()


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------


async def test_ensure_daily_digest_persists_row(cockpit_app) -> None:  # noqa: ANN001
    tenant_id = await _seed_tenant()
    await _seed_yesterday_audit_rows(tenant_id, count=3)
    yday = _yesterday()

    async with app_db.AsyncSessionLocal() as session:
        row = await ensure_daily_digest(
            session, tenant_id=tenant_id, day_utc=yday
        )
        await session.commit()
        assert row.tenant_id == tenant_id
        assert row.row_count == 3
        assert len(row.digest_sha256) == 64
        assert row.prev_digest_sha256 == ""


async def test_ensure_daily_digest_idempotent(cockpit_app) -> None:  # noqa: ANN001
    tenant_id = await _seed_tenant()
    await _seed_yesterday_audit_rows(tenant_id, count=2)
    yday = _yesterday()

    async with app_db.AsyncSessionLocal() as session:
        first = await ensure_daily_digest(
            session, tenant_id=tenant_id, day_utc=yday
        )
        await session.commit()
    async with app_db.AsyncSessionLocal() as session:
        second = await ensure_daily_digest(
            session, tenant_id=tenant_id, day_utc=yday
        )
        await session.commit()
        assert second.id == first.id

    async with app_db.AsyncSessionLocal() as session:
        total = int(
            (
                await session.execute(
                    select(func.count(AuditHashDigest.id)).where(
                        AuditHashDigest.tenant_id == tenant_id
                    )
                )
            ).scalar_one()
            or 0
        )
        assert total == 1


async def test_verify_detects_tampering(cockpit_app) -> None:  # noqa: ANN001
    tenant_id = await _seed_tenant()
    await _seed_yesterday_audit_rows(tenant_id, count=3)
    yday = _yesterday()

    async with app_db.AsyncSessionLocal() as session:
        await ensure_daily_digest(session, tenant_id=tenant_id, day_utc=yday)
        await session.commit()

    # Tamper: mutate one audit row's metadata after the digest was stored.
    async with app_db.AsyncSessionLocal() as session:
        await session.execute(
            update(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .where(AuditLog.action == "test.event.0")
            .values(metadata_json={"i": 0, "tampered": True})
        )
        await session.commit()

    async with app_db.AsyncSessionLocal() as session:
        with pytest.raises(AuditHashMismatch) as excinfo:
            await verify_daily_digest(
                session, tenant_id=tenant_id, day_utc=yday
            )
        assert excinfo.value.context["reason"] == "mismatch"


# ---------------------------------------------------------------------------
# Task-level tests
# ---------------------------------------------------------------------------


async def test_task_creates_digest_for_all_tenants(cockpit_app) -> None:  # noqa: ANN001
    tenant_id = await _seed_tenant()
    await _seed_yesterday_audit_rows(tenant_id, count=2)

    # Task is sync; it uses asyncio.run internally on AsyncSessionLocal.
    # Run in a thread so it doesn't collide with the pytest-asyncio loop.
    summary = await asyncio.to_thread(verify_nightly_audit_hash_task)
    assert summary["status"] == "ok"
    assert summary["tenants_total"] >= 1
    assert summary["tenants_new"] >= 1
    assert summary["tenants_mismatched"] == 0

    async with app_db.AsyncSessionLocal() as session:
        total = int(
            (
                await session.execute(
                    select(func.count(AuditHashDigest.id)).where(
                        AuditHashDigest.tenant_id == tenant_id
                    )
                )
            ).scalar_one()
            or 0
        )
        assert total == 1


async def test_task_idempotent_no_duplicate_rows(cockpit_app) -> None:  # noqa: ANN001
    tenant_id = await _seed_tenant()
    await _seed_yesterday_audit_rows(tenant_id, count=2)

    first = await asyncio.to_thread(verify_nightly_audit_hash_task)
    second = await asyncio.to_thread(verify_nightly_audit_hash_task)
    assert first["status"] == "ok"
    assert second["status"] == "ok"
    # On the second run nothing is new; everything is verified.
    assert second["tenants_new"] == 0
    assert second["tenants_verified"] >= 1

    async with app_db.AsyncSessionLocal() as session:
        total = int(
            (
                await session.execute(
                    select(func.count(AuditHashDigest.id)).where(
                        AuditHashDigest.tenant_id == tenant_id
                    )
                )
            ).scalar_one()
            or 0
        )
        assert total == 1


async def test_task_reports_mismatch_on_tamper(cockpit_app) -> None:  # noqa: ANN001
    tenant_id = await _seed_tenant()
    await _seed_yesterday_audit_rows(tenant_id, count=3)

    # First run - persist digest.
    first = await asyncio.to_thread(verify_nightly_audit_hash_task)
    assert first["status"] == "ok"

    # Tamper one row.
    async with app_db.AsyncSessionLocal() as session:
        await session.execute(
            update(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .where(AuditLog.action == "test.event.0")
            .values(action="test.event.0.TAMPERED")
        )
        await session.commit()

    # Second run - must detect.
    second = await asyncio.to_thread(verify_nightly_audit_hash_task)
    assert second["status"] == "alert"
    assert second["tenants_mismatched"] >= 1
    assert any(
        m["tenant_id"] == tenant_id for m in second["mismatches"]
    )
