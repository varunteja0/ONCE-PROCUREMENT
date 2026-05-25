"""Tests for Ed25519 receipt signing & verification."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ConsentRecord,
    ConsentScope,
    Portal,
    PortalPlatform,
    SubmissionReceipt,
    SubmissionStatus,
    Supplier,
    SupplierSubmission,
    Tenant,
    TenantUser,
    User,
)
from app.services import receipt_signer
from app.utils.security import hash_password

pytestmark = pytest.mark.asyncio


async def _build_signing_world(
    session: AsyncSession,
) -> tuple[SupplierSubmission, ConsentRecord]:
    """Seed the minimum graph needed to sign a receipt."""

    tenant = Tenant(name="Sig Tenant", slug="sig-tenant")
    user = User(
        email="sig-owner@example.com",
        hashed_password=hash_password("Sup3rSecret!"),
        full_name="Sig Owner",
        is_active=True,
    )
    session.add_all([tenant, user])
    await session.flush()
    session.add(TenantUser(tenant_id=tenant.id, user_id=user.id, role="owner"))

    supplier = Supplier(
        tenant_id=tenant.id,
        legal_name="Synthetic Supplier LLC",
        ein="98-7654321",
    )
    session.add(supplier)
    await session.flush()

    consent = ConsentRecord(
        tenant_id=tenant.id,
        supplier_id=supplier.id,
        scope=ConsentScope.SUBMIT_ON_BEHALF,
        portal_ids_json=["*"],
        granted_at=datetime.now(UTC),
        granted_by_user_id=user.id,
        signed_text="I authorize Once to submit on my behalf.",
        signature_b64="ZmFrZS1jb25zZW50",
    )
    session.add(consent)
    await session.flush()

    portal = (await session.execute(select(Portal).where(Portal.platform == PortalPlatform.APPLIED_EPIC))).scalar_one()

    now = datetime.now(UTC)
    submission = SupplierSubmission(
        tenant_id=tenant.id,
        supplier_id=supplier.id,
        portal_id=portal.id,
        status=SubmissionStatus.COMPLETED,
        payload_json={"legal_name": "Synthetic Supplier LLC", "ein": "98-7654321"},
        attempt_count=1,
        consent_record_id=consent.id,
        claimed_at=now,
        started_at=now,
        completed_at=now,
    )
    session.add(submission)
    await session.commit()
    return submission, consent


async def test_sign_then_verify_returns_verified_true(
    async_session: AsyncSession,
    signing_key,  # noqa: ARG001 - configured via fixture side-effect
) -> None:
    submission, consent = await _build_signing_world(async_session)

    receipt = await receipt_signer.sign_receipt(
        async_session,
        submission=submission,
        consent=consent,
        tos_version_hash="sha256:tos-fixture-v1",
    )
    await async_session.commit()

    assert receipt.signature_b64
    assert receipt.public_payload_json["submission_id"] == submission.id
    assert receipt.payload_hash

    verification = await receipt_signer.verify_receipt(async_session, receipt.id)
    assert verification["verified"] is True
    assert verification["signing_key_id"] == receipt.signing_key_id
    assert verification["public_key_pem"].startswith("-----BEGIN PUBLIC KEY-----")
    assert verification["receipt"]["submission_id"] == submission.id


async def test_receipt_rows_are_immutable_after_insert(
    async_session: AsyncSession,
    signing_key,  # noqa: ARG001
) -> None:
    submission, consent = await _build_signing_world(async_session)

    receipt = await receipt_signer.sign_receipt(
        async_session,
        submission=submission,
        consent=consent,
        tos_version_hash="sha256:tos-fixture-v1",
    )
    await async_session.commit()

    receipt_id = receipt.id
    original_hash = receipt.payload_hash
    tampered = dict(receipt.public_payload_json)
    tampered["payload_hash"] = "sha256:0" * 8
    receipt.public_payload_json = tampered
    with pytest.raises(ValueError, match="immutable"):
        await async_session.commit()
    await async_session.rollback()

    refreshed = (
        await async_session.execute(select(SubmissionReceipt).where(SubmissionReceipt.id == receipt_id))
    ).scalar_one()
    assert refreshed.public_payload_json["payload_hash"] == original_hash
