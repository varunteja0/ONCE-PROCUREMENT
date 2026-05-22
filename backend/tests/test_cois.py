"""Tests for :mod:`app.services.coi_monitor_service`."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.coi_monitor_service import DEFAULT_DAYS_AHEAD, find_expiring
from tests.factories import make_coi, make_supplier, make_tenant

pytestmark = pytest.mark.asyncio


class TestFindExpiring:
    async def test_returns_coi_within_window(self, async_session) -> None:
        tenant = await make_tenant(async_session)
        supplier = await make_supplier(async_session, tenant)
        soon = date.today() + timedelta(days=10)
        coi = await make_coi(async_session, supplier=supplier, expiry=soon)
        await async_session.commit()
        rows = await find_expiring(async_session, days_ahead=DEFAULT_DAYS_AHEAD)
        ids = {row.id for row in rows}
        assert coi.id in ids

    async def test_excludes_coi_outside_window(self, async_session) -> None:
        tenant = await make_tenant(async_session)
        supplier = await make_supplier(async_session, tenant)
        future = date.today() + timedelta(days=120)
        coi = await make_coi(async_session, supplier=supplier, expiry=future)
        await async_session.commit()
        rows = await find_expiring(async_session, days_ahead=30)
        assert coi.id not in {r.id for r in rows}

    async def test_includes_past_due(self, async_session) -> None:
        tenant = await make_tenant(async_session)
        supplier = await make_supplier(async_session, tenant)
        past = date.today() - timedelta(days=5)
        coi = await make_coi(async_session, supplier=supplier, expiry=past)
        await async_session.commit()
        rows = await find_expiring(async_session, days_ahead=30)
        assert coi.id in {r.id for r in rows}

    async def test_renewed_coi_is_excluded(self, async_session) -> None:
        """A COI is "renewed" if another COI for the same supplier and
        coverage_type has an ``effective_date >= old.expiry_date``."""

        tenant = await make_tenant(async_session)
        supplier = await make_supplier(async_session, tenant)
        old_expiry = date.today() + timedelta(days=15)
        old = await make_coi(
            async_session,
            supplier=supplier,
            expiry=old_expiry,
            coverage_type="GL",
        )
        # Renewal starts at the day the old one expires.
        await make_coi(
            async_session,
            supplier=supplier,
            coverage_type="GL",
            effective_date=old_expiry,
            expiry_date=old_expiry + timedelta(days=365),
        )
        await async_session.commit()
        rows = await find_expiring(async_session, days_ahead=30)
        assert old.id not in {r.id for r in rows}

    async def test_negative_days_ahead_raises(self, async_session) -> None:
        with pytest.raises(ValueError):
            await find_expiring(async_session, days_ahead=-1)

    async def test_tenant_filter_isolates_results(self, async_session) -> None:
        t1 = await make_tenant(async_session)
        t2 = await make_tenant(async_session)
        s1 = await make_supplier(async_session, t1)
        s2 = await make_supplier(async_session, t2)
        soon = date.today() + timedelta(days=7)
        c1 = await make_coi(async_session, supplier=s1, expiry=soon)
        c2 = await make_coi(async_session, supplier=s2, expiry=soon)
        await async_session.commit()
        rows = await find_expiring(async_session, tenant_id=t1.id, days_ahead=30)
        ids = {r.id for r in rows}
        assert c1.id in ids
        assert c2.id not in ids

    async def test_as_of_overrides_today(self, async_session) -> None:
        tenant = await make_tenant(async_session)
        supplier = await make_supplier(async_session, tenant)
        coi = await make_coi(
            async_session,
            supplier=supplier,
            expiry=date(2030, 6, 1),
        )
        await async_session.commit()
        # Reference far in the past → outside window.
        rows = await find_expiring(
            async_session, days_ahead=30, as_of=date(2020, 1, 1)
        )
        assert coi.id not in {r.id for r in rows}
        # Reference just before expiry → in window.
        rows = await find_expiring(
            async_session, days_ahead=30, as_of=date(2030, 5, 15)
        )
        assert coi.id in {r.id for r in rows}
