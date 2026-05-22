"""Unit tests for ``app.utils.idempotent_event``."""

from __future__ import annotations

import asyncio

import pytest

from app.models.billing import BillingEvent
from app.utils.idempotent_event import (
    MAX_ERROR_LEN,
    claim_event,
    mark_failed,
    mark_processed,
)

pytestmark = pytest.mark.asyncio


async def test_claim_event_inserts_new_row(async_session) -> None:
    event, created = await claim_event(
        async_session,
        stripe_event_id="evt_test_1",
        event_type="invoice.paid",
        payload={"id": "evt_test_1"},
    )
    assert created is True
    assert event.stripe_event_id == "evt_test_1"
    assert event.processed_at is None


async def test_claim_event_idempotent_second_call(async_session) -> None:
    _, created1 = await claim_event(
        async_session, stripe_event_id="evt_dup", event_type="invoice.paid"
    )
    _, created2 = await claim_event(
        async_session, stripe_event_id="evt_dup", event_type="invoice.paid"
    )
    assert created1 is True
    assert created2 is False


async def test_mark_processed_stamps_timestamp(async_session) -> None:
    event, _ = await claim_event(
        async_session, stripe_event_id="evt_proc", event_type="invoice.paid"
    )
    await mark_processed(async_session, event)
    assert event.processed_at is not None
    assert event.processing_error is None


async def test_mark_failed_truncates_long_errors(async_session) -> None:
    event, _ = await claim_event(
        async_session, stripe_event_id="evt_fail", event_type="invoice.paid"
    )
    huge = "x" * (MAX_ERROR_LEN + 500)
    await mark_failed(async_session, event, huge)
    assert event.processing_error is not None
    assert len(event.processing_error) == MAX_ERROR_LEN


async def test_repeat_claims_only_one_row_exists(async_session) -> None:
    # Sequentially issue several claims on the same event id — the unique
    # constraint must prevent duplicates and the second claim must report
    # created=False (idempotent behaviour relied on by webhook handler).
    _, c1 = await claim_event(
        async_session,
        stripe_event_id="evt_race",
        event_type="invoice.paid",
    )
    _, c2 = await claim_event(
        async_session,
        stripe_event_id="evt_race",
        event_type="invoice.paid",
    )
    _, c3 = await claim_event(
        async_session,
        stripe_event_id="evt_race",
        event_type="invoice.paid",
    )
    assert [c1, c2, c3] == [True, False, False]

    from sqlalchemy import func, select

    cnt = (
        await async_session.execute(
            select(func.count(BillingEvent.id)).where(
                BillingEvent.stripe_event_id == "evt_race"
            )
        )
    ).scalar_one()
    assert cnt == 1


# `asyncio` retained for backwards compat with prior revision of this module.
_ = asyncio
