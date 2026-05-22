"""Tests for the realistic seed.

Covers determinism, idempotency, reset semantics, tamper detection, status
distribution, business-day skew, expiring-COI counts, license-state
coverage and FEIN format.

All tests run against the same in-memory SQLite engine the rest of the
backend suite uses (see ``tests/conftest.py``). The ``_test_engine``
fixture is depended on indirectly through ``async_session`` so the schema
is built and the default portals are seeded before the realistic seed
runs.
"""

from __future__ import annotations

import base64
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CertificateOfInsurance,
    ConsentRecord,
    Portal,
    ProducerLicense,
    SigningKey,
    SubmissionReceipt,
    SubmissionStatus,
    Supplier,
    SupplierSubmission,
    Tenant,
    User,
)
from app.utils.canonical_json import canonical_json_bytes
from app.utils.crypto import verify
from scripts._seed_data import SEED_MARKER
from scripts.seed_realistic import seed
from scripts.seed_realistic_reset import reset

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_once(seed_secret: int = 42, **overrides) -> dict:
    """Wipe-then-seed so tests start from a known state under the marker."""

    await reset(seed_secret=seed_secret)
    # Strip portals so we don't collide with the conftest-seeded portals.
    # The realistic seed uses deterministic IDs, so the existing portals
    # have different IDs and coexist peacefully.
    return await seed(seed_secret=seed_secret, **overrides)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_determinism_same_seed_same_supplier_names(async_session: AsyncSession) -> None:
    """Two runs with the same seed produce identical row counts + names."""

    first = await _seed_once(42)
    names_first = sorted(
        s for (s,) in (await async_session.execute(select(Supplier.legal_name))).all()
    )
    await reset(seed_secret=42)

    second = await seed(seed_secret=42)
    names_second = sorted(
        s for (s,) in (await async_session.execute(select(Supplier.legal_name))).all()
    )

    assert first["suppliers"] == second["suppliers"]
    assert names_first == names_second
    assert first["__random_state_hash__"] == second["__random_state_hash__"]


async def test_idempotent_second_run_is_no_op(async_session: AsyncSession) -> None:
    """Running seed twice without reset is a no-op (no duplicates)."""

    await _seed_once(42)
    count_before = (
        await async_session.execute(select(func.count(Supplier.id)))
    ).scalar_one()

    # Re-run with the same seed — must short-circuit on existing tenant.
    second = await seed(seed_secret=42)
    count_after = (
        await async_session.execute(select(func.count(Supplier.id)))
    ).scalar_one()

    assert second.get("__skipped__") is True
    assert count_before == count_after


async def test_reset_removes_all_marker_rows(async_session: AsyncSession) -> None:
    await _seed_once(42)
    await reset(seed_secret=42)

    assert (await async_session.execute(select(func.count(Tenant.id)))).scalar_one() == 0
    assert (await async_session.execute(select(func.count(Supplier.id)))).scalar_one() == 0
    assert (await async_session.execute(select(func.count(SubmissionReceipt.id)))).scalar_one() == 0


async def test_reset_preserves_unmarked_rows(async_session: AsyncSession) -> None:
    """A pre-existing tenant/user not in the seed-marker space survives reset."""

    # Insert a user-created tenant + user.
    async_session.add_all(
        [
            Tenant(id="user-tenant-99", name="User Tenant", slug="user-tenant"),
            User(id="user-user-99", email="real@example.com", hashed_password="x"),
        ]
    )
    await async_session.commit()

    await _seed_once(42)
    await reset(seed_secret=42)

    assert (
        await async_session.execute(select(Tenant).where(Tenant.id == "user-tenant-99"))
    ).scalar_one_or_none() is not None
    assert (
        await async_session.execute(select(User).where(User.id == "user-user-99"))
    ).scalar_one_or_none() is not None


async def test_tampered_receipts_fail_signature_verification(
    async_session: AsyncSession,
) -> None:
    await _seed_once(42)

    key = (
        await async_session.execute(select(SigningKey).limit(1))
    ).scalar_one()
    receipts = (
        await async_session.execute(select(SubmissionReceipt))
    ).scalars().all()

    bad = 0
    for r in receipts:
        sig = base64.b64decode(r.signature_b64)
        ok = verify(key.public_key_pem, canonical_json_bytes(r.public_payload_json), sig)
        if not ok:
            bad += 1

    # Exactly 12 receipts were tampered by the seed.
    assert bad == 12, f"expected 12 tampered receipts, got {bad}"


async def test_submission_status_distribution(async_session: AsyncSession) -> None:
    await _seed_once(42)
    total = (
        await async_session.execute(select(func.count(SupplierSubmission.id)))
    ).scalar_one()
    completed = (
        await async_session.execute(
            select(func.count(SupplierSubmission.id)).where(
                SupplierSubmission.status == SubmissionStatus.COMPLETED
            )
        )
    ).scalar_one()
    failed = (
        await async_session.execute(
            select(func.count(SupplierSubmission.id)).where(
                SupplierSubmission.status == SubmissionStatus.FAILED
            )
        )
    ).scalar_one()

    assert total == 800
    assert completed / total >= 0.65, f"completed ratio too low: {completed/total:.2%}"
    assert failed / total <= 0.12, f"failed ratio too high: {failed/total:.2%}"


async def test_business_day_skew(async_session: AsyncSession) -> None:
    await _seed_once(42)
    rows = (
        await async_session.execute(
            select(SupplierSubmission.completed_at).where(
                SupplierSubmission.completed_at.is_not(None)
            )
        )
    ).all()
    weekend = sum(1 for (ts,) in rows if ts and ts.weekday() >= 5)
    assert weekend / max(1, len(rows)) < 0.05, (
        f"too many weekend submissions: {weekend}/{len(rows)}"
    )


async def test_expiring_coi_count_is_18(async_session: AsyncSession) -> None:
    await _seed_once(42)
    today = date.today()
    horizon = today + timedelta(days=30)
    expiring = (
        await async_session.execute(
            select(func.count(CertificateOfInsurance.id)).where(
                CertificateOfInsurance.expiry_date >= today,
                CertificateOfInsurance.expiry_date <= horizon,
            )
        )
    ).scalar_one()
    assert expiring == 18


async def test_all_twelve_license_states_present(async_session: AsyncSession) -> None:
    await _seed_once(42)
    states = {
        s
        for (s,) in (
            await async_session.execute(select(ProducerLicense.state).distinct())
        ).all()
    }
    expected = {"CA", "TX", "FL", "NY", "IL", "GA", "PA", "OH", "NC", "MI", "WA", "AZ"}
    assert expected.issubset(states), f"missing license states: {expected - states}"


async def test_all_feins_start_with_99(async_session: AsyncSession) -> None:
    await _seed_once(42)
    rows = (await async_session.execute(select(Supplier.ein))).all()
    assert rows, "expected at least one supplier"
    for (ein,) in rows:
        assert ein and ein.startswith("99-"), f"bad FEIN prefix: {ein!r}"


async def test_dry_run_does_not_write(async_session: AsyncSession) -> None:
    """--dry-run must populate counts without touching the DB."""

    before = (await async_session.execute(select(func.count(Supplier.id)))).scalar_one()
    counts = await seed(seed_secret=42, dry_run=True)
    after = (await async_session.execute(select(func.count(Supplier.id)))).scalar_one()
    assert after == before
    assert counts["suppliers"] == 50
    assert counts["submission_receipts"] >= 500


async def test_consent_records_present_for_first_35_suppliers(
    async_session: AsyncSession,
) -> None:
    await _seed_once(42)
    consents = (
        await async_session.execute(select(func.count(ConsentRecord.id)))
    ).scalar_one()
    # >=35 because completed submissions for the long-tail suppliers may
    # synthesize additional consents on the fly.
    assert consents >= 35


async def test_seed_marker_stamped_on_supplier_address(
    async_session: AsyncSession,
) -> None:
    await _seed_once(42)
    rows = (await async_session.execute(select(Supplier.address_json))).all()
    assert rows
    for (addr,) in rows:
        assert addr["_seed_marker"] == SEED_MARKER


async def test_portals_seeded_with_supported_flags(async_session: AsyncSession) -> None:
    await _seed_once(42)
    supported = (
        await async_session.execute(
            select(func.count(Portal.id)).where(Portal.is_supported == True)  # noqa: E712
        )
    ).scalar_one()
    # The seed marks 5 portals supported; conftest seeds another 5 with
    # different IDs that are also supported. Either way ≥5 supported.
    assert supported >= 5
