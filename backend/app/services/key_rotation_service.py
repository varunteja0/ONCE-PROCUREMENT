"""Key rotation log service — append-only ledger for SOC 2 CC-6.1.

The service stores no key material; it records who rotated which key
when, plus optional cross-references (``new_key_id`` /
``previous_key_id``) and a free-form ``notes`` justification.
"""

from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KeyRotationLog
from app.schemas.compliance import (
    KeyRotationCreate,
    KeyRotationListResponse,
    KeyRotationRead,
)
from app.utils.logging import get_logger

__all__ = ["record_rotation", "list_rotations", "ALLOWED_KEY_NAMES"]


_logger = get_logger(__name__)

# Closed enum of rotation targets. Keeps the audit trail clean and
# prevents typos like "jwtsecret" vs "jwt_secret_key".
ALLOWED_KEY_NAMES: frozenset[str] = frozenset(
    {
        "receipt_signing_key",
        "jwt_secret_key",
        "cockpit_jwt_secret_key",
        "db_password",
        "redis_password",
        "fly_api_token",
        "sentry_dsn",
        "operator_password",
    }
)


async def record_rotation(
    session: AsyncSession,
    *,
    payload: KeyRotationCreate,
    operator_id: str | None,
) -> KeyRotationLog:
    if payload.key_name not in ALLOWED_KEY_NAMES:
        from app.services.exceptions import OnceError

        raise OnceError(
            "unknown_key_name",
            key_name=payload.key_name,
            allowed=sorted(ALLOWED_KEY_NAMES),
        )
    row = KeyRotationLog(
        key_name=payload.key_name,
        new_key_id=payload.new_key_id,
        previous_key_id=payload.previous_key_id,
        rotated_by_operator_id=operator_id,
        notes=payload.notes,
        metadata_json=payload.metadata_json,
    )
    session.add(row)
    await session.flush()
    _logger.info(
        "key_rotation_recorded",
        key_name=row.key_name,
        new_key_id=row.new_key_id,
        previous_key_id=row.previous_key_id,
        rotated_by_operator_id=row.rotated_by_operator_id,
        rotation_log_id=row.id,
    )
    return row


async def list_rotations(
    session: AsyncSession,
    *,
    key_name: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> KeyRotationListResponse:
    base = select(KeyRotationLog)
    count_stmt = select(func.count(KeyRotationLog.id))
    if key_name:
        base = base.where(KeyRotationLog.key_name == key_name)
        count_stmt = count_stmt.where(KeyRotationLog.key_name == key_name)

    total = int((await session.execute(count_stmt)).scalar_one() or 0)
    rows = list(
        (
            await session.execute(
                base.order_by(desc(KeyRotationLog.rotated_at))
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return KeyRotationListResponse(
        total=total,
        items=[KeyRotationRead.model_validate(r) for r in rows],
    )
