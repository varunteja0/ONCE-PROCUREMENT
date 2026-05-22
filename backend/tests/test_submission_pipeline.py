"""End-to-end tests for the in-process submission pipeline.

The pipeline contract (CONTRACTS.md §5) is exercised here through
:func:`app.services.submission_pipeline.process_submission`. The submitter
contract is fixed at ``submitter.submit(*, supplier, portal, payload,
consent)``; a fake submitter is wired in via ``_patch_pipeline`` to keep
tests hermetic. Receipt signing exercises the real signer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

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
)
from app.services import submission_pipeline
from app.services.exceptions import PortalPermanentError, SubmissionNotClaimable

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


_REQUIRED_FIELDS: tuple[str, ...] = (
    "legal_name",
    "ein",
    "primary_email",
    "naics_code",
    "coi_carrier",
    "coi_policy_number",
    "coi_expiry",
)


@dataclass(slots=True)
class _FakeOutcome:
    """Structurally compatible with ``automation.base.SubmitterOutcome``."""

    success: bool
    portal_reference: str | None
    result_payload: dict[str, Any] = field(default_factory=dict)
    screenshot_url: str | None = None


class _FakeSubmitter:
    """Validates payload completeness and returns a deterministic outcome."""

    async def submit(
        self,
        *,
        supplier: Supplier,
        portal: Portal,
        payload: dict[str, Any],
        consent: ConsentRecord,
    ) -> _FakeOutcome:
        missing = [f for f in _REQUIRED_FIELDS if not (payload or {}).get(f)]
        if missing:
            raise PortalPermanentError("missing_fields", missing=missing)
        return _FakeOutcome(
            success=True,
            portal_reference="EPIC-TEST-REF",
            result_payload={"echo": dict(payload), "supplier_id": supplier.id},
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_FULL_PAYLOAD: dict[str, Any] = {
    "legal_name": "Acme Underwriting LLC",
    "ein": "12-3456789",
    "primary_email": "ops@acme.example",
    "naics_code": "524210",
    "coi_carrier": "Travelers",
    "coi_policy_number": "TRV-100-XYZ",
    "coi_expiry": "2026-12-31",
}


async def _seed_tenant_supplier_consent(
    session: AsyncSession,
) -> tuple[str, Supplier, ConsentRecord, Portal]:
    """Create a tenant, owner, supplier and wildcard consent record."""

    from app.models import Tenant, TenantUser, User
    from app.utils.security import hash_password

    tenant = Tenant(name="Pipeline Tenant", slug="pipeline-tenant")
    user = User(
        email="pipeline-owner@example.com",
        hashed_password=hash_password("Sup3rSecret!"),
        full_name="Pipeline Owner",
        is_active=True,
    )
    session.add_all([tenant, user])
    await session.flush()

    session.add(TenantUser(tenant_id=tenant.id, user_id=user.id, role="owner"))

    supplier = Supplier(
        tenant_id=tenant.id,
        legal_name="Acme Underwriting LLC",
        ein="12-3456789",
        primary_email="ops@acme.example",
        naics_code="524210",
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
        signature_b64="ZmFrZS1zaWc=",
    )
    session.add(consent)
    await session.flush()

    portal = (
        await session.execute(
            select(Portal).where(Portal.platform == PortalPlatform.APPLIED_EPIC)
        )
    ).scalar_one()

    await session.commit()
    return tenant.id, supplier, consent, portal


def _patch_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wire the fake submitter and shim signer into the pipeline module."""

    monkeypatch.setattr(
        submission_pipeline, "_get_submitter", lambda platform: _FakeSubmitter()
    )


def _enable_in_process(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "enable_in_process_processor", True)


# ---------------------------------------------------------------------------
# Tests — direct pipeline invocation
# ---------------------------------------------------------------------------


async def test_process_submission_full_payload_marks_completed_and_creates_receipt(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    signing_key,  # noqa: ARG001 - ensures signing key is configured
) -> None:
    _enable_in_process(monkeypatch)
    _patch_pipeline(monkeypatch)

    tenant_id, supplier, consent, portal = await _seed_tenant_supplier_consent(
        async_session
    )
    submission = SupplierSubmission(
        tenant_id=tenant_id,
        supplier_id=supplier.id,
        portal_id=portal.id,
        status=SubmissionStatus.QUEUED,
        payload_json=dict(_FULL_PAYLOAD),
        consent_record_id=consent.id,
    )
    async_session.add(submission)
    await async_session.commit()

    result = await submission_pipeline.process_submission(
        submission.id, async_session
    )

    assert result.status is SubmissionStatus.COMPLETED
    assert result.error is None
    assert result.receipt_id is not None

    await async_session.refresh(submission)
    assert submission.status is SubmissionStatus.COMPLETED
    assert submission.completed_at is not None
    assert submission.last_error is None

    receipt = (
        await async_session.execute(
            select(SubmissionReceipt).where(
                SubmissionReceipt.submission_id == submission.id
            )
        )
    ).scalar_one()
    assert receipt.id == result.receipt_id
    assert receipt.tenant_id == tenant_id
    assert receipt.signature_b64
    assert receipt.public_payload_json["submission_id"] == submission.id


async def test_process_submission_missing_field_fails_with_last_error(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    signing_key,  # noqa: ARG001
) -> None:
    _enable_in_process(monkeypatch)
    _patch_pipeline(monkeypatch)

    tenant_id, supplier, consent, portal = await _seed_tenant_supplier_consent(
        async_session
    )
    broken_payload = {k: v for k, v in _FULL_PAYLOAD.items() if k != "coi_policy_number"}
    submission = SupplierSubmission(
        tenant_id=tenant_id,
        supplier_id=supplier.id,
        portal_id=portal.id,
        status=SubmissionStatus.QUEUED,
        payload_json=broken_payload,
        consent_record_id=consent.id,
    )
    async_session.add(submission)
    await async_session.commit()

    result = await submission_pipeline.process_submission(
        submission.id, async_session
    )

    assert result.status is SubmissionStatus.FAILED
    assert result.error
    assert "missing_fields" in result.error

    await async_session.refresh(submission)
    assert submission.status is SubmissionStatus.FAILED
    assert submission.last_error and "missing_fields" in submission.last_error
    assert submission.completed_at is not None

    receipts = (
        await async_session.execute(
            select(SubmissionReceipt).where(
                SubmissionReceipt.submission_id == submission.id
            )
        )
    ).scalars().all()
    assert receipts == []


async def test_process_submission_is_atomically_claimable_once(
    async_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    signing_key,  # noqa: ARG001
) -> None:
    _enable_in_process(monkeypatch)
    _patch_pipeline(monkeypatch)

    tenant_id, supplier, consent, portal = await _seed_tenant_supplier_consent(
        async_session
    )
    submission = SupplierSubmission(
        tenant_id=tenant_id,
        supplier_id=supplier.id,
        portal_id=portal.id,
        status=SubmissionStatus.QUEUED,
        payload_json=dict(_FULL_PAYLOAD),
        consent_record_id=consent.id,
    )
    async_session.add(submission)
    await async_session.commit()

    first = await submission_pipeline.process_submission(
        submission.id, async_session
    )
    assert first.status is SubmissionStatus.COMPLETED

    with pytest.raises(SubmissionNotClaimable):
        await submission_pipeline.process_submission(submission.id, async_session)

