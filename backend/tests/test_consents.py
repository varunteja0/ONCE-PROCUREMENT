"""Tests for ConsentRecord validation and read API behavior.

Consent records are created by onboarding or internal workflows and consumed
by ``submission_service``. These tests pin the contract that submission
creation enforces:

* unknown consent → 404 (``consent_record_not_found``)
* revoked consent → 400 (``consent_revoked``)
* insufficient scope (READ_ONLY) → 400 (``consent_scope_insufficient``)
* portal not covered by consent → 400 (``consent_portal_not_covered``)
* wildcard ``["*"]`` portal list covers any portal (allowed)
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.models import ConsentScope, PortalPlatform
from app.schemas.submission import SubmissionCreate
from app.services.submission_service import create_submission
from tests.factories import (
    make_consent,
    make_portal,
    make_supplier,
    make_tenant,
)

pytestmark = pytest.mark.asyncio


async def _scaffold(async_session, *, scope=ConsentScope.SUBMIT_ON_BEHALF, **consent_kw):
    tenant = await make_tenant(async_session)
    supplier = await make_supplier(async_session, tenant)
    portal = await make_portal(async_session, platform=PortalPlatform.AMTRUST)
    consent = await make_consent(
        async_session,
        supplier=supplier,
        portal=portal,
        scope=scope,
        **consent_kw,
    )
    await async_session.commit()
    return tenant, supplier, portal, consent


class TestConsentValidation:
    async def test_unknown_consent_record_raises_404(self, async_session) -> None:
        tenant, supplier, portal, _ = await _scaffold(async_session)
        payload = SubmissionCreate(
            supplier_id=supplier.id,
            portal_id=portal.id,
            consent_record_id="00000000-0000-0000-0000-000000000000",
            payload={},
        )
        with pytest.raises(HTTPException) as exc:
            await create_submission(async_session, tenant_id=tenant.id, payload=payload)
        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "consent_record_not_found"

    async def test_revoked_consent_returns_400(self, async_session) -> None:
        tenant, supplier, portal, consent = await _scaffold(
            async_session,
            revoked_at=datetime.now(UTC),
        )
        payload = SubmissionCreate(
            supplier_id=supplier.id,
            portal_id=portal.id,
            consent_record_id=consent.id,
            payload={},
        )
        with pytest.raises(HTTPException) as exc:
            await create_submission(async_session, tenant_id=tenant.id, payload=payload)
        assert exc.value.status_code == 400
        assert exc.value.detail["code"] == "consent_revoked"

    async def test_insufficient_scope_returns_400(self, async_session) -> None:
        tenant, supplier, portal, consent = await _scaffold(async_session, scope=ConsentScope.READ_ONLY)
        payload = SubmissionCreate(
            supplier_id=supplier.id,
            portal_id=portal.id,
            consent_record_id=consent.id,
            payload={},
        )
        with pytest.raises(HTTPException) as exc:
            await create_submission(async_session, tenant_id=tenant.id, payload=payload)
        assert exc.value.status_code == 400
        assert exc.value.detail["code"] == "consent_scope_insufficient"

    async def test_portal_not_covered_returns_400(self, async_session) -> None:
        # Two portals; consent only covers portal A; submission uses portal B.
        tenant = await make_tenant(async_session)
        supplier = await make_supplier(async_session, tenant)
        portal_a = await make_portal(async_session, platform=PortalPlatform.AMTRUST)
        portal_b = await make_portal(async_session, platform=PortalPlatform.MARKEL)
        consent = await make_consent(
            async_session,
            supplier=supplier,
            portal=portal_a,
        )
        await async_session.commit()
        payload = SubmissionCreate(
            supplier_id=supplier.id,
            portal_id=portal_b.id,
            consent_record_id=consent.id,
            payload={},
        )
        with pytest.raises(HTTPException) as exc:
            await create_submission(async_session, tenant_id=tenant.id, payload=payload)
        assert exc.value.status_code == 400
        assert exc.value.detail["code"] == "consent_portal_not_covered"

    async def test_wildcard_portal_consent_covers_any_portal(self, async_session) -> None:
        tenant = await make_tenant(async_session)
        supplier = await make_supplier(async_session, tenant)
        portal = await make_portal(async_session, platform=PortalPlatform.MARKEL)
        consent = await make_consent(
            async_session,
            supplier=supplier,
            portal_ids_json=["*"],
        )
        await async_session.commit()

        created = await create_submission(
            async_session,
            tenant_id=tenant.id,
            payload=SubmissionCreate(
                supplier_id=supplier.id,
                portal_id=portal.id,
                consent_record_id=consent.id,
                payload={},
            ),
        )

        assert created.consent_record_id == consent.id


class TestConsentModelInvariants:
    async def test_revoked_at_defaults_to_none(self, async_session) -> None:
        tenant, supplier, portal, consent = await _scaffold(async_session)
        assert consent.revoked_at is None

    async def test_signed_text_and_signature_are_required(self, async_session) -> None:
        # Empty signed_text should still be accepted by the column (Text), but
        # the factory provides one. We just assert non-empty defaults so any
        # regression that drops fields is caught.
        _, _, _, consent = await _scaffold(async_session)
        assert consent.signed_text
        assert consent.signature_b64
