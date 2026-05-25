"""Smoke tests for the new insurance domain models — carriers, quotes,
policies, loss_run_claims — plus the ACORD-25 enrichment columns on
``certificates_of_insurance``.

These tests validate:
- ORM mapping (create + commit + reload)
- Tenant scoping defaults
- JSON column round-trip
- Unique constraints
- Money-as-BigInteger-cents discipline
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Carrier,
    CarrierKind,
    CarrierStatus,
    CertificateOfInsurance,
    LossRun,
    LossRunClaim,
    LossRunClaimStatus,
    LossRunStatus,
    Policy,
    PolicyStatus,
    Quote,
    QuoteStatus,
    Supplier,
    Tenant,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _mk_tenant(session: AsyncSession) -> Tenant:
    t = Tenant(
        name=f"acme-{uuid.uuid4().hex[:8]}",
        display_name="Acme Test",
        slug=f"acme-{uuid.uuid4().hex[:8]}",
    )
    session.add(t)
    await session.flush()
    return t


async def _mk_supplier(session: AsyncSession, tenant_id: str) -> Supplier:
    s = Supplier(
        tenant_id=tenant_id,
        legal_name="Acme Roofing LLC",
        dba_name="Acme Roofing",
        primary_email=f"ops-{uuid.uuid4().hex[:6]}@example.com",
    )
    session.add(s)
    await session.flush()
    return s


async def _mk_carrier(session: AsyncSession, tenant_id: str, **kwargs: object) -> Carrier:
    defaults: dict[str, object] = {
        "tenant_id": tenant_id,
        "legal_name": "Acme Mutual Insurance Co",
        "naic_code": uuid.uuid4().hex[:5],
        "kind": CarrierKind.ADMITTED,
        "status": CarrierStatus.ACTIVE,
    }
    defaults.update(kwargs)
    c = Carrier(**defaults)  # type: ignore[arg-type]
    session.add(c)
    await session.flush()
    return c


# ---------------------------------------------------------------------------
# Carrier
# ---------------------------------------------------------------------------


class TestCarrier:
    @pytest.mark.asyncio
    async def test_create_and_reload(self, async_session: AsyncSession) -> None:
        tenant = await _mk_tenant(async_session)
        carrier = await _mk_carrier(
            async_session,
            tenant.id,
            legal_name="Travelers Indemnity Company",
            naic_code="25658",
            am_best_rating="A++",
            states_licensed_json=["CA", "NY", "TX"],
            lines_of_business_json=["general_liability", "workers_comp"],
            is_preferred=True,
        )
        await async_session.commit()

        loaded = (await async_session.execute(select(Carrier).where(Carrier.id == carrier.id))).scalar_one()
        assert loaded.legal_name == "Travelers Indemnity Company"
        assert loaded.tenant_id == tenant.id
        assert loaded.kind == CarrierKind.ADMITTED
        assert loaded.status == CarrierStatus.ACTIVE
        assert loaded.is_preferred is True
        assert loaded.states_licensed_json == ["CA", "NY", "TX"]

    @pytest.mark.asyncio
    async def test_unique_tenant_naic(self, async_session: AsyncSession) -> None:
        tenant = await _mk_tenant(async_session)
        await _mk_carrier(async_session, tenant.id, naic_code="12345")
        await async_session.commit()

        await _mk_carrier(
            async_session,
            tenant.id,
            legal_name="Duplicate Carrier",
            naic_code="12345",
        )
        with pytest.raises(IntegrityError):
            await async_session.commit()
        await async_session.rollback()

    @pytest.mark.asyncio
    async def test_different_tenants_may_share_naic(self, async_session: AsyncSession) -> None:
        t1 = await _mk_tenant(async_session)
        t2 = await _mk_tenant(async_session)
        await _mk_carrier(async_session, t1.id, naic_code="99999")
        await _mk_carrier(async_session, t2.id, naic_code="99999")
        await async_session.commit()  # must not raise


# ---------------------------------------------------------------------------
# Quote
# ---------------------------------------------------------------------------


class TestQuote:
    @pytest.mark.asyncio
    async def test_money_as_cents(self, async_session: AsyncSession) -> None:
        tenant = await _mk_tenant(async_session)
        supplier = await _mk_supplier(async_session, tenant.id)
        carrier = await _mk_carrier(async_session, tenant.id)

        quote = Quote(
            tenant_id=tenant.id,
            supplier_id=supplier.id,
            carrier_id=carrier.id,
            line_of_business="general_liability",
            status=QuoteStatus.INDICATION,
            premium_cents=125_000_00,  # $125,000.00
            fees_cents=1_500_00,
            taxes_cents=375_00,
            commission_basis_points=1250,  # 12.5%
            currency="USD",
            coverages_json={"each_occurrence": 1_000_000, "aggregate": 2_000_000},
            valid_until=datetime.now(UTC) + timedelta(days=30),
        )
        async_session.add(quote)
        await async_session.commit()

        loaded = (await async_session.execute(select(Quote).where(Quote.id == quote.id))).scalar_one()
        assert loaded.premium_cents == 125_000_00
        assert isinstance(loaded.premium_cents, int)
        assert loaded.commission_basis_points == 1250
        assert loaded.coverages_json == {
            "each_occurrence": 1_000_000,
            "aggregate": 2_000_000,
        }
        assert loaded.status == QuoteStatus.INDICATION


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


class TestPolicy:
    @pytest.mark.asyncio
    async def test_unique_carrier_policy_number(self, async_session: AsyncSession) -> None:
        tenant = await _mk_tenant(async_session)
        supplier = await _mk_supplier(async_session, tenant.id)
        carrier = await _mk_carrier(async_session, tenant.id)

        eff = date(2026, 1, 1)
        exp = date(2027, 1, 1)
        p1 = Policy(
            tenant_id=tenant.id,
            supplier_id=supplier.id,
            carrier_id=carrier.id,
            policy_number="GL-001",
            line_of_business="general_liability",
            status=PolicyStatus.IN_FORCE,
            effective_date=eff,
            expiration_date=exp,
        )
        async_session.add(p1)
        await async_session.commit()

        p2 = Policy(
            tenant_id=tenant.id,
            supplier_id=supplier.id,
            carrier_id=carrier.id,
            policy_number="GL-001",  # duplicate
            line_of_business="general_liability",
            status=PolicyStatus.PENDING,
            effective_date=eff,
            expiration_date=exp,
        )
        async_session.add(p2)
        with pytest.raises(IntegrityError):
            await async_session.commit()
        await async_session.rollback()


# ---------------------------------------------------------------------------
# LossRunClaim
# ---------------------------------------------------------------------------


class TestLossRunClaim:
    @pytest.mark.asyncio
    async def test_create_with_money_totals(self, async_session: AsyncSession) -> None:
        tenant = await _mk_tenant(async_session)
        supplier = await _mk_supplier(async_session, tenant.id)
        loss_run = LossRun(
            tenant_id=tenant.id,
            supplier_id=supplier.id,
            line_of_business="general_liability",
            status=LossRunStatus.RECEIVED,
            period_start=date(2023, 1, 1),
            period_end=date(2025, 12, 31),
        )
        async_session.add(loss_run)
        await async_session.flush()

        claim = LossRunClaim(
            tenant_id=tenant.id,
            loss_run_id=loss_run.id,
            claim_number="CLM-2024-0001",
            claimant_name="John Doe",
            loss_date=date(2024, 6, 15),
            status=LossRunClaimStatus.CLOSED,
            paid_indemnity_cents=25_000_00,
            paid_expense_cents=3_500_00,
            reserve_indemnity_cents=0,
            reserve_expense_cents=0,
            total_incurred_cents=28_500_00,
            state="CA",
        )
        async_session.add(claim)
        await async_session.commit()

        loaded = (await async_session.execute(select(LossRunClaim).where(LossRunClaim.id == claim.id))).scalar_one()
        assert loaded.tenant_id == tenant.id
        assert loaded.loss_run_id == loss_run.id
        assert loaded.paid_indemnity_cents == 25_000_00
        assert loaded.total_incurred_cents == 28_500_00
        assert loaded.status == LossRunClaimStatus.CLOSED
        # defaulted money cols
        assert loaded.recovery_cents == 0
        assert loaded.reserve_indemnity_cents == 0


# ---------------------------------------------------------------------------
# COI ACORD-25 enrichment columns
# ---------------------------------------------------------------------------


class TestCOIAcord25Fields:
    @pytest.mark.asyncio
    async def test_acord25_fields_round_trip(self, async_session: AsyncSession) -> None:
        tenant = await _mk_tenant(async_session)
        supplier = await _mk_supplier(async_session, tenant.id)

        coi = CertificateOfInsurance(
            tenant_id=tenant.id,
            supplier_id=supplier.id,
            carrier_name="Travelers Indemnity",
            policy_number="COI-001",
            coverage_type="general_liability",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2027, 1, 1),
            certificate_holder="Mega Mart Inc.",
            producer_name="Marsh McLennan Agency",
            producer_naic="MMA-9876",
            additional_insureds_json=[
                {"name": "Mega Mart Inc.", "relationship": "landlord"},
                {"name": "Big Bank N.A.", "relationship": "mortgagee"},
            ],
            waiver_of_subrogation=True,
            primary_and_noncontributory=True,
            policy_form_number="CG 00 01 04 13",
            description_of_operations="Roofing operations at 123 Main St.",
            acord25_limits_json={
                "each_occurrence": 1_000_000,
                "general_aggregate": 2_000_000,
                "products_completed_ops": 2_000_000,
            },
        )
        async_session.add(coi)
        await async_session.commit()

        loaded = (
            await async_session.execute(select(CertificateOfInsurance).where(CertificateOfInsurance.id == coi.id))
        ).scalar_one()
        assert loaded.certificate_holder == "Mega Mart Inc."
        assert loaded.producer_name == "Marsh McLennan Agency"
        assert loaded.waiver_of_subrogation is True
        assert loaded.primary_and_noncontributory is True
        assert loaded.policy_form_number == "CG 00 01 04 13"
        assert loaded.additional_insureds_json is not None
        assert len(loaded.additional_insureds_json) == 2
        assert loaded.additional_insureds_json[0]["name"] == "Mega Mart Inc."
        assert loaded.acord25_limits_json is not None
        assert loaded.acord25_limits_json["each_occurrence"] == 1_000_000

    @pytest.mark.asyncio
    async def test_acord25_fields_all_nullable(self, async_session: AsyncSession) -> None:
        """Legacy COIs (uploaded before ACORD-25 enrichment) must still work."""
        tenant = await _mk_tenant(async_session)
        supplier = await _mk_supplier(async_session, tenant.id)

        coi = CertificateOfInsurance(
            tenant_id=tenant.id,
            supplier_id=supplier.id,
            carrier_name="Legacy Carrier",
            policy_number="LEGACY-001",
            coverage_type="general_liability",
            effective_date=date(2025, 1, 1),
            expiry_date=date(2026, 1, 1),
        )
        async_session.add(coi)
        await async_session.commit()

        loaded = (
            await async_session.execute(select(CertificateOfInsurance).where(CertificateOfInsurance.id == coi.id))
        ).scalar_one()
        assert loaded.certificate_holder is None
        assert loaded.additional_insureds_json is None
        assert loaded.waiver_of_subrogation is None
        assert loaded.acord25_limits_json is None
