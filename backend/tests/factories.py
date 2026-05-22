"""Hand-rolled async model factories for the Once test suite.

Stdlib-friendly (no factory-boy dependency). Each factory commits/flushes as
needed and returns a fully hydrated ORM instance so tests can immediately read
``.id`` and relationship fields.

All factories accept ``**overrides`` to customize the produced row without
having to repeat the full constructor signature in every test.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CertificateOfInsurance,
    ConsentRecord,
    ConsentScope,
    Portal,
    PortalPlatform,
    SigningKey,
    SubmissionReceipt,
    SubmissionStatus,
    Supplier,
    SupplierSubmission,
    Tenant,
    TenantUser,
    User,
)
from app.utils.security import hash_password

__all__ = [
    "make_tenant",
    "make_user",
    "make_tenant_user",
    "make_supplier",
    "make_portal",
    "make_consent",
    "make_submission",
    "make_receipt",
    "make_signing_key",
    "make_coi",
    "make_auth_headers",
    "register_and_token",
    "unique_email",
    "unique_slug",
]


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}+{secrets.token_hex(4)}@example.com"


def unique_slug(prefix: str = "t") -> str:
    return f"{prefix}-{secrets.token_hex(4)}"


async def make_tenant(session: AsyncSession, **overrides: Any) -> Tenant:
    defaults: dict[str, Any] = {
        "name": "Factory Tenant",
        "slug": unique_slug("tenant"),
        "plan": "pilot",
        "is_active": True,
    }
    defaults.update(overrides)
    tenant = Tenant(**defaults)
    session.add(tenant)
    await session.flush()
    return tenant


async def make_user(session: AsyncSession, **overrides: Any) -> User:
    defaults: dict[str, Any] = {
        "email": unique_email("factory-user"),
        "hashed_password": hash_password("Factory-Pass-1!"),
        "full_name": "Factory User",
        "is_active": True,
    }
    defaults.update(overrides)
    user = User(**defaults)
    session.add(user)
    await session.flush()
    return user


async def make_tenant_user(
    session: AsyncSession,
    *,
    tenant: Tenant,
    user: User,
    role: str = "owner",
) -> TenantUser:
    tu = TenantUser(tenant_id=tenant.id, user_id=user.id, role=role)
    session.add(tu)
    await session.flush()
    return tu


async def make_supplier(
    session: AsyncSession, tenant: Tenant, **overrides: Any
) -> Supplier:
    defaults: dict[str, Any] = {
        "legal_name": "Factory Supplier LLC",
        "ein": "12-3456789",
        "primary_email": unique_email("supplier"),
        "naics_code": "524210",
    }
    defaults.update(overrides)
    supplier = Supplier(tenant_id=tenant.id, **defaults)
    session.add(supplier)
    await session.flush()
    return supplier


async def make_portal(
    session: AsyncSession,
    *,
    platform: PortalPlatform = PortalPlatform.AMTRUST,
    **overrides: Any,
) -> Portal:
    """Fetch the seeded portal for ``platform`` or build a new one if missing.

    The default :mod:`conftest` seeds the canonical PortalPlatform rows, so most
    tests will simply receive the seeded row.
    """

    existing = (
        await session.execute(select(Portal).where(Portal.platform == platform))
    ).scalar_one_or_none()
    if existing is not None and not overrides:
        return existing
    defaults: dict[str, Any] = {
        "platform": platform,
        "display_name": platform.value.replace("_", " ").title(),
        "base_url": f"https://{platform.value}.example/",
        "is_supported": True,
        "risky": False,
    }
    defaults.update(overrides)
    portal = Portal(**defaults)
    session.add(portal)
    await session.flush()
    return portal


async def make_consent(
    session: AsyncSession,
    *,
    supplier: Supplier,
    portal: Portal | None = None,
    granted_by: User | None = None,
    **overrides: Any,
) -> ConsentRecord:
    if granted_by is None:
        granted_by = await make_user(session)
    defaults: dict[str, Any] = {
        "scope": ConsentScope.SUBMIT_ON_BEHALF,
        "portal_ids_json": ["*"] if portal is None else [portal.id],
        "granted_at": datetime.now(UTC),
        "granted_by_user_id": granted_by.id,
        "signed_text": "I authorize Once to submit on my behalf.",
        "signature_b64": "ZmFrZS1jb25zZW50",
    }
    defaults.update(overrides)
    consent = ConsentRecord(
        tenant_id=supplier.tenant_id,
        supplier_id=supplier.id,
        **defaults,
    )
    session.add(consent)
    await session.flush()
    return consent


async def make_submission(
    session: AsyncSession,
    *,
    supplier: Supplier,
    portal: Portal,
    consent: ConsentRecord | None = None,
    **overrides: Any,
) -> SupplierSubmission:
    defaults: dict[str, Any] = {
        "status": SubmissionStatus.QUEUED,
        "payload_json": {"legal_name": supplier.legal_name},
        "attempt_count": 0,
    }
    defaults.update(overrides)
    submission = SupplierSubmission(
        tenant_id=supplier.tenant_id,
        supplier_id=supplier.id,
        portal_id=portal.id,
        consent_record_id=consent.id if consent is not None else None,
        **defaults,
    )
    session.add(submission)
    await session.flush()
    return submission


async def make_receipt(
    session: AsyncSession,
    *,
    submission: SupplierSubmission,
    consent: ConsentRecord,
    portal: Portal,
    signing_key_id: str = "test-key",
    **overrides: Any,
) -> SubmissionReceipt:
    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "portal_platform": portal.platform.value,
        "submitted_at": now,
        "payload_hash": "sha256:" + secrets.token_hex(32),
        "tos_version_hash": "sha256:" + secrets.token_hex(32),
        "signing_key_id": signing_key_id,
        "signature_b64": "",
        "public_payload_json": {},
    }
    defaults.update(overrides)
    receipt = SubmissionReceipt(
        submission_id=submission.id,
        tenant_id=submission.tenant_id,
        supplier_id=submission.supplier_id,
        consent_record_id=consent.id,
        **defaults,
    )
    session.add(receipt)
    await session.flush()
    return receipt


async def make_signing_key(
    session: AsyncSession,
    *,
    key_id: str,
    public_pem: str,
    revoked: bool = False,
) -> SigningKey:
    key = SigningKey(
        id=key_id,
        algorithm="ed25519",
        public_key_pem=public_pem,
        description="factory",
        revoked_at=datetime.now(UTC) if revoked else None,
    )
    session.add(key)
    await session.flush()
    return key


async def make_coi(
    session: AsyncSession,
    *,
    supplier: Supplier,
    expiry: date | None = None,
    coverage_type: str = "GL",
    **overrides: Any,
) -> CertificateOfInsurance:
    expiry = expiry or (date.today() + timedelta(days=60))
    defaults: dict[str, Any] = {
        "carrier_name": "Acme Carrier",
        "policy_number": f"POL-{uuid.uuid4().hex[:10]}",
        "coverage_type": coverage_type,
        "effective_date": expiry - timedelta(days=365),
        "expiry_date": expiry,
    }
    defaults.update(overrides)
    coi = CertificateOfInsurance(
        tenant_id=supplier.tenant_id,
        supplier_id=supplier.id,
        **defaults,
    )
    session.add(coi)
    await session.flush()
    return coi


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


async def register_and_token(
    client: AsyncClient,
    *,
    email: str | None = None,
    password: str = "S3cret-Pass!",
    full_name: str = "Factory Owner",
    tenant_name: str | None = None,
) -> dict[str, Any]:
    """Register a tenant+owner and return ``{email, password, tokens, body}``."""

    email = email or unique_email("factory")
    tenant_name = tenant_name or f"Factory Tenant {secrets.token_hex(3)}"
    response = await client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
            "tenant_name": tenant_name,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {
        "email": email,
        "password": password,
        "tenant_name": tenant_name,
        "access_token": body["access_token"],
        "refresh_token": body["refresh_token"],
        "body": body,
    }


async def make_auth_headers(
    client: AsyncClient,
    *,
    email: str | None = None,
    password: str = "S3cret-Pass!",
    tenant_name: str | None = None,
) -> dict[str, str]:
    """Register and return ``{"Authorization": "Bearer ..."}`` headers."""

    reg = await register_and_token(
        client, email=email, password=password, tenant_name=tenant_name
    )
    return {"Authorization": f"Bearer {reg['access_token']}"}
