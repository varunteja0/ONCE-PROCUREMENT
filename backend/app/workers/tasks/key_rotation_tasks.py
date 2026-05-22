"""Key-rotation Celery tasks (SOC 2 CC-6.1 evidence).

Three tasks, scheduled via Celery Beat (see celery_app.py):

* ``keys.rotate_signing_key`` (weekly): if the active receipt-signing key
  is older than 365 days, generate a new Ed25519 keypair, register the new
  public key in ``signing_keys``, and append a ``KeyRotationLog`` + system
  ``AuditLog`` row. The OLD key is NOT revoked - it remains valid for
  verifying historical receipts. The new private key PEM is logged once
  for the operator to install in the KMS / Fly secret manager; the task
  itself never persists private material.

* ``keys.warn_jwt_secret_age`` (daily, threshold 90d): emits a structured
  alert + ``key_rotation.warn`` AuditLog row when the most recent
  ``KeyRotationLog`` entry for ``jwt_secret_key`` is missing or stale.
  Rotation remains manual (Fly secret + restart) per RUNBOOK section 6.

* ``keys.warn_db_password_age`` (daily, threshold 180d): same shape for
  ``db_password``.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import desc, select

import app.db as app_db
from app.models import AuditLog, KeyRotationLog, SigningKey
from app.schemas.compliance import KeyRotationCreate
from app.services.key_rotation_service import record_rotation
from app.utils.logging import get_logger
from app.workers.celery_app import celery_app

__all__ = [
    "rotate_signing_key_task",
    "warn_jwt_secret_age_task",
    "warn_db_password_age_task",
]


_logger = get_logger(__name__)

# Thresholds (days) for each rotation policy.
SIGNING_KEY_MAX_AGE_DAYS = 365
JWT_SECRET_MAX_AGE_DAYS = 90
DB_PASSWORD_MAX_AGE_DAYS = 180


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes. Normalize to UTC-aware."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _generate_ed25519_keypair() -> tuple[str, str]:
    """Return ``(private_pem, public_pem)`` for a fresh Ed25519 key.

    Private PEM is intended for one-shot logging so the operator can move
    it into the KMS / Fly secret manager; it is never persisted by Once.
    """
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    return private_pem, public_pem


async def _last_rotation(
    session: Any, *, key_name: str
) -> KeyRotationLog | None:
    stmt = (
        select(KeyRotationLog)
        .where(KeyRotationLog.key_name == key_name)
        .order_by(desc(KeyRotationLog.rotated_at))
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


# ---------------------------------------------------------------------------
# Task 1: automated receipt-signing-key rotation
# ---------------------------------------------------------------------------


async def _run_rotate_signing_key() -> dict[str, Any]:
    now = _utcnow()
    async with app_db.AsyncSessionLocal() as session:
        stmt = (
            select(SigningKey)
            .where(SigningKey.revoked_at.is_(None))
            .order_by(desc(SigningKey.created_at))
            .limit(1)
        )
        active = (await session.execute(stmt)).scalars().first()

        if active is None:
            _logger.warning("signing_key_rotation_no_active_key")
            return {
                "status": "skipped",
                "reason": "no_active_signing_key",
            }

        created_at = _aware(active.created_at) or now
        age_days = (now - created_at).days
        if age_days < SIGNING_KEY_MAX_AGE_DAYS:
            return {
                "status": "skipped",
                "reason": "age_below_threshold",
                "age_days": age_days,
                "threshold_days": SIGNING_KEY_MAX_AGE_DAYS,
                "active_key_id": active.id,
            }

        # Rotate: generate new keypair, register public key, append ledger.
        private_pem, public_pem = _generate_ed25519_keypair()
        new_key = SigningKey(
            id=str(uuid.uuid4()),
            algorithm="ed25519",
            public_key_pem=public_pem,
            description=(
                "Auto-rotated by keys.rotate_signing_key on "
                f"{now.date().isoformat()}"
            ),
        )
        session.add(new_key)
        await session.flush()  # populate new_key.id

        await record_rotation(
            session,
            payload=KeyRotationCreate(
                key_name="receipt_signing_key",
                new_key_id=new_key.id,
                previous_key_id=active.id,
                notes=(
                    "Automated rotation by keys.rotate_signing_key beat task."
                ),
                metadata_json={
                    "automated": True,
                    "task": "keys.rotate_signing_key",
                    "previous_age_days": age_days,
                },
            ),
            operator_id=None,
        )

        session.add(
            AuditLog(
                tenant_id=None,
                action="key_rotation",
                resource_type="signing_key",
                resource_id=new_key.id,
                metadata_json={
                    "previous_key_id": active.id,
                    "automated": True,
                    "task": "keys.rotate_signing_key",
                    "previous_age_days": age_days,
                },
            )
        )

        await session.commit()

        # One-shot operator handoff: log the new private PEM so the on-call
        # can install it. The task itself never persists private material.
        _logger.warning(
            "signing_key_rotation_private_key_handoff_required",
            new_key_id=new_key.id,
            previous_key_id=active.id,
            public_key_pem=public_pem,
            private_key_pem=private_pem,
        )

        return {
            "status": "rotated",
            "new_key_id": new_key.id,
            "previous_key_id": active.id,
            "age_days_of_previous": age_days,
        }


@celery_app.task(
    bind=False,
    name="keys.rotate_signing_key",
    acks_late=True,
)
def rotate_signing_key_task() -> dict[str, Any]:
    """Automated receipt-signing-key rotation (365-day cadence).

    Idempotent: returns ``status=skipped`` when the active key is below the
    age threshold; the freshly-rotated key has age 0 so re-running the task
    in the same window is a no-op.
    """

    started_at = _utcnow()
    _logger.info(
        "signing_key_rotation_job_started", at=started_at.isoformat()
    )
    try:
        summary = asyncio.run(_run_rotate_signing_key())
    except Exception as exc:  # pragma: no cover - top-level safety net
        _logger.exception(
            "signing_key_rotation_job_unhandled_error",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return {
            "status": "failed",
            "error_type": type(exc).__name__,
            "message": str(exc),
        }

    finished_at = _utcnow()
    summary.update(
        {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_sec": (finished_at - started_at).total_seconds(),
        }
    )
    _logger.info("signing_key_rotation_job_completed", **summary)
    return summary


# ---------------------------------------------------------------------------
# Tasks 2 & 3: secret-age alerters (no automated rotation)
# ---------------------------------------------------------------------------


async def _run_warn_secret_age(
    *, key_name: str, threshold_days: int, task_name: str
) -> dict[str, Any]:
    now = _utcnow()
    async with app_db.AsyncSessionLocal() as session:
        last = await _last_rotation(session, key_name=key_name)

        if last is None:
            age_days: int | None = None
            alert = True
            reason = "no_rotation_history"
        else:
            rotated_at = _aware(last.rotated_at) or now
            age_days = (now - rotated_at).days
            alert = age_days >= threshold_days
            reason = "age_above_threshold" if alert else "ok"

        if alert:
            session.add(
                AuditLog(
                    tenant_id=None,
                    action="key_rotation.warn",
                    resource_type="secret",
                    resource_id=key_name,
                    metadata_json={
                        "key_name": key_name,
                        "age_days": age_days,
                        "threshold_days": threshold_days,
                        "task": task_name,
                        "reason": reason,
                    },
                )
            )
            await session.commit()
            _logger.warning(
                "secret_age_alert",
                key_name=key_name,
                age_days=age_days,
                threshold_days=threshold_days,
                task=task_name,
                reason=reason,
            )
            return {
                "status": "alert",
                "key_name": key_name,
                "age_days": age_days,
                "threshold_days": threshold_days,
                "reason": reason,
            }

        return {
            "status": "ok",
            "key_name": key_name,
            "age_days": age_days,
            "threshold_days": threshold_days,
        }


def _run_warn_task(
    *, key_name: str, threshold_days: int, task_name: str
) -> dict[str, Any]:
    started_at = _utcnow()
    _logger.info(
        "secret_age_check_started",
        key_name=key_name,
        threshold_days=threshold_days,
        at=started_at.isoformat(),
    )
    try:
        summary = asyncio.run(
            _run_warn_secret_age(
                key_name=key_name,
                threshold_days=threshold_days,
                task_name=task_name,
            )
        )
    except Exception as exc:  # pragma: no cover - top-level safety net
        _logger.exception(
            "secret_age_check_unhandled_error",
            key_name=key_name,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return {
            "status": "failed",
            "key_name": key_name,
            "error_type": type(exc).__name__,
            "message": str(exc),
        }

    finished_at = _utcnow()
    summary.update(
        {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_sec": (finished_at - started_at).total_seconds(),
        }
    )
    _logger.info("secret_age_check_completed", **summary)
    return summary


@celery_app.task(
    bind=False,
    name="keys.warn_jwt_secret_age",
    acks_late=True,
)
def warn_jwt_secret_age_task() -> dict[str, Any]:
    """Alert when the jwt_secret_key rotation ledger is missing or stale.

    Rotation itself is manual (Fly secret + restart) - this task only emits
    a structured warning and ``key_rotation.warn`` AuditLog row so the
    on-call can be paged.
    """
    return _run_warn_task(
        key_name="jwt_secret_key",
        threshold_days=JWT_SECRET_MAX_AGE_DAYS,
        task_name="keys.warn_jwt_secret_age",
    )


@celery_app.task(
    bind=False,
    name="keys.warn_db_password_age",
    acks_late=True,
)
def warn_db_password_age_task() -> dict[str, Any]:
    """Alert when the database password rotation ledger is missing or stale."""
    return _run_warn_task(
        key_name="db_password",
        threshold_days=DB_PASSWORD_MAX_AGE_DAYS,
        task_name="keys.warn_db_password_age",
    )


