"""Idempotent webhook-event helper.

The Stripe docs recommend ledgering every webhook by ``event.id`` and
short-circuiting duplicates so handler logic never runs twice. We persist a
row in :class:`~app.models.billing.BillingEvent` on first receipt and gate
subsequent invocations on the ``UNIQUE`` constraint on ``stripe_event_id``.

The helper here is intentionally tiny:

* :func:`claim_event` inserts the ledger row and returns ``(event, created)``
  where ``created`` is ``False`` if the row already existed (race-safe — the
  unique constraint is the source of truth).
* :func:`mark_processed` stamps ``processed_at`` after handlers succeed.
* :func:`mark_failed` stores the truncated error for ops triage.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import BillingEvent

__all__ = [
    "claim_event",
    "mark_processed",
    "mark_failed",
    "MAX_ERROR_LEN",
]


MAX_ERROR_LEN: int = 2_000


async def claim_event(
    session: AsyncSession,
    *,
    stripe_event_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> tuple[BillingEvent, bool]:
    """Idempotently insert a webhook ledger row.

    Returns ``(event, created)``. When ``created`` is ``False`` the row was
    already present (another worker won the race).
    """

    existing = await session.execute(
        select(BillingEvent).where(BillingEvent.stripe_event_id == stripe_event_id)
    )
    row = existing.scalar_one_or_none()
    if row is not None:
        return row, False

    event = BillingEvent(
        stripe_event_id=stripe_event_id,
        event_type=event_type,
        payload=payload,
    )
    session.add(event)
    try:
        await session.flush()
    except IntegrityError:
        # Lost the race; reload + return as already-claimed.
        await session.rollback()
        existing = await session.execute(
            select(BillingEvent).where(
                BillingEvent.stripe_event_id == stripe_event_id
            )
        )
        row = existing.scalar_one()
        return row, False
    return event, True


async def mark_processed(session: AsyncSession, event: BillingEvent) -> None:
    event.processed_at = datetime.now(UTC)
    event.processing_error = None
    await session.flush()


async def mark_failed(
    session: AsyncSession, event: BillingEvent, error: str
) -> None:
    event.processing_error = (error or "")[:MAX_ERROR_LEN]
    await session.flush()
