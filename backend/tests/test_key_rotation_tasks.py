"""Tests for the key-rotation Celery tasks (SOC 2 CC-6.1 evidence).

Covers:

* ``keys.rotate_signing_key``: skipped when no active key, skipped when
  active key is below the 365d age threshold, rotates (new SigningKey +
  KeyRotationLog + AuditLog rows) when threshold is exceeded, and is
  idempotent within the same window.
* ``keys.warn_jwt_secret_age``: alerts when no rotation history, alerts
  when stale, ok when recent.
* ``keys.warn_db_password_age``: alerts when stale.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

import app.db as app_db
from app.models import AuditLog, KeyRotationLog, SigningKey
from app.workers.tasks.key_rotation_tasks import (
    rotate_signing_key_task,
    warn_db_password_age_task,
    warn_jwt_secret_age_task,
)

pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime.now(tz=UTC)


async def _insert_signing_key(*, age_days: int) -> str:
    async with app_db.AsyncSessionLocal() as session:
        key = SigningKey(
            id=str(uuid.uuid4()),
            algorithm="ed25519",
            public_key_pem=(
                "-----BEGIN PUBLIC KEY-----\nseed-public-key-pem\n"
                "-----END PUBLIC KEY-----\n"
            ),
            description=f"seed key (age={age_days}d)",
            created_at=_now() - timedelta(days=age_days),
        )
        session.add(key)
        await session.commit()
        await session.refresh(key)
        return key.id


async def _insert_rotation_log(
    *, key_name: str, age_days: int
) -> str:
    async with app_db.AsyncSessionLocal() as session:
        row = KeyRotationLog(
            key_name=key_name,
            notes="seed rotation",
            rotated_at=_now() - timedelta(days=age_days),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row.id


# ---------------------------------------------------------------------------
# keys.rotate_signing_key
# ---------------------------------------------------------------------------


async def test_rotate_signing_key_no_existing_key_skips(cockpit_app) -> None:  # noqa: ANN001
    summary = await asyncio.to_thread(rotate_signing_key_task)
    assert summary["status"] == "skipped"
    assert summary["reason"] == "no_active_signing_key"


async def test_rotate_signing_key_below_threshold_skips(cockpit_app) -> None:  # noqa: ANN001
    key_id = await _insert_signing_key(age_days=30)
    summary = await asyncio.to_thread(rotate_signing_key_task)
    assert summary["status"] == "skipped"
    assert summary["reason"] == "age_below_threshold"
    assert summary["age_days"] >= 29
    assert summary["active_key_id"] == key_id

    # No new SigningKey, no KeyRotationLog, no AuditLog row written.
    async with app_db.AsyncSessionLocal() as session:
        signing_count = int(
            (
                await session.execute(select(func.count(SigningKey.id)))
            ).scalar_one()
            or 0
        )
        rotation_count = int(
            (
                await session.execute(select(func.count(KeyRotationLog.id)))
            ).scalar_one()
            or 0
        )
    assert signing_count == 1
    assert rotation_count == 0


async def test_rotate_signing_key_triggers_rotation(cockpit_app) -> None:  # noqa: ANN001
    old_key_id = await _insert_signing_key(age_days=400)

    summary = await asyncio.to_thread(rotate_signing_key_task)
    assert summary["status"] == "rotated"
    assert summary["previous_key_id"] == old_key_id
    assert summary["new_key_id"] != old_key_id
    assert summary["age_days_of_previous"] >= 399
    new_key_id = summary["new_key_id"]

    async with app_db.AsyncSessionLocal() as session:
        # A new SigningKey row exists; the OLD key is NOT revoked.
        signing_count = int(
            (
                await session.execute(select(func.count(SigningKey.id)))
            ).scalar_one()
            or 0
        )
        assert signing_count == 2

        old = (
            await session.execute(
                select(SigningKey).where(SigningKey.id == old_key_id)
            )
        ).scalar_one()
        assert old.revoked_at is None

        new = (
            await session.execute(
                select(SigningKey).where(SigningKey.id == new_key_id)
            )
        ).scalar_one()
        assert new.algorithm == "ed25519"
        assert "BEGIN PUBLIC KEY" in new.public_key_pem

        # KeyRotationLog row recorded with automated=True.
        rot = (
            await session.execute(
                select(KeyRotationLog).where(
                    KeyRotationLog.key_name == "receipt_signing_key"
                )
            )
        ).scalar_one()
        assert rot.new_key_id == new_key_id
        assert rot.previous_key_id == old_key_id
        assert rot.rotated_by_operator_id is None
        assert rot.metadata_json is not None
        assert rot.metadata_json["automated"] is True
        assert rot.metadata_json["task"] == "keys.rotate_signing_key"

        # AuditLog system-level row (tenant_id IS NULL).
        audit = (
            await session.execute(
                select(AuditLog).where(AuditLog.action == "key_rotation")
            )
        ).scalar_one()
        assert audit.tenant_id is None
        assert audit.resource_type == "signing_key"
        assert audit.resource_id == new_key_id
        assert audit.metadata_json is not None
        assert audit.metadata_json["previous_key_id"] == old_key_id
        assert audit.metadata_json["automated"] is True


async def test_rotate_signing_key_idempotent_within_window(  # noqa: ANN001
    cockpit_app,
) -> None:
    await _insert_signing_key(age_days=400)

    first = await asyncio.to_thread(rotate_signing_key_task)
    assert first["status"] == "rotated"

    # Second run picks the freshly-rotated key (age 0) and skips.
    second = await asyncio.to_thread(rotate_signing_key_task)
    assert second["status"] == "skipped"
    assert second["reason"] == "age_below_threshold"

    async with app_db.AsyncSessionLocal() as session:
        rotation_count = int(
            (
                await session.execute(
                    select(func.count(KeyRotationLog.id)).where(
                        KeyRotationLog.key_name == "receipt_signing_key"
                    )
                )
            ).scalar_one()
            or 0
        )
    assert rotation_count == 1


# ---------------------------------------------------------------------------
# keys.warn_jwt_secret_age
# ---------------------------------------------------------------------------


async def test_warn_jwt_secret_no_history_alerts(cockpit_app) -> None:  # noqa: ANN001
    summary = await asyncio.to_thread(warn_jwt_secret_age_task)
    assert summary["status"] == "alert"
    assert summary["key_name"] == "jwt_secret_key"
    assert summary["threshold_days"] == 90
    assert summary["age_days"] is None
    assert summary["reason"] == "no_rotation_history"

    async with app_db.AsyncSessionLocal() as session:
        audit = (
            await session.execute(
                select(AuditLog).where(AuditLog.action == "key_rotation.warn")
            )
        ).scalar_one()
        assert audit.tenant_id is None
        assert audit.resource_id == "jwt_secret_key"
        assert audit.metadata_json is not None
        assert audit.metadata_json["reason"] == "no_rotation_history"


async def test_warn_jwt_secret_recent_ok(cockpit_app) -> None:  # noqa: ANN001
    await _insert_rotation_log(key_name="jwt_secret_key", age_days=5)
    summary = await asyncio.to_thread(warn_jwt_secret_age_task)
    assert summary["status"] == "ok"
    assert summary["key_name"] == "jwt_secret_key"
    assert summary["threshold_days"] == 90
    assert summary["age_days"] is not None
    assert summary["age_days"] <= 5

    # No new warn AuditLog row written.
    async with app_db.AsyncSessionLocal() as session:
        warn_count = int(
            (
                await session.execute(
                    select(func.count(AuditLog.id)).where(
                        AuditLog.action == "key_rotation.warn"
                    )
                )
            ).scalar_one()
            or 0
        )
    assert warn_count == 0


async def test_warn_jwt_secret_old_alerts(cockpit_app) -> None:  # noqa: ANN001
    await _insert_rotation_log(key_name="jwt_secret_key", age_days=120)
    summary = await asyncio.to_thread(warn_jwt_secret_age_task)
    assert summary["status"] == "alert"
    assert summary["key_name"] == "jwt_secret_key"
    assert summary["threshold_days"] == 90
    assert summary["age_days"] is not None
    assert summary["age_days"] >= 119
    assert summary["reason"] == "age_above_threshold"


# ---------------------------------------------------------------------------
# keys.warn_db_password_age
# ---------------------------------------------------------------------------


async def test_warn_db_password_old_alerts(cockpit_app) -> None:  # noqa: ANN001
    await _insert_rotation_log(key_name="db_password", age_days=200)
    summary = await asyncio.to_thread(warn_db_password_age_task)
    assert summary["status"] == "alert"
    assert summary["key_name"] == "db_password"
    assert summary["threshold_days"] == 180
    assert summary["age_days"] is not None
    assert summary["age_days"] >= 199
    assert summary["reason"] == "age_above_threshold"

    async with app_db.AsyncSessionLocal() as session:
        audit = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.action == "key_rotation.warn",
                )
            )
        ).scalar_one()
        assert audit.resource_id == "db_password"
        assert audit.metadata_json is not None
        assert audit.metadata_json["threshold_days"] == 180


async def test_warn_db_password_recent_ok(cockpit_app) -> None:  # noqa: ANN001
    await _insert_rotation_log(key_name="db_password", age_days=10)
    summary = await asyncio.to_thread(warn_db_password_age_task)
    assert summary["status"] == "ok"
    assert summary["age_days"] is not None
    assert summary["age_days"] <= 10
