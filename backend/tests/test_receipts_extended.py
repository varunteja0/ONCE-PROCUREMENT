"""Extended /v1/receipts and /verify/{id} tests.

Combines tenant-scoped listing with the public verifier behavior including
signature tampering, key rotation, and unknown-key fallback paths.
"""

from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import AsyncClient

from app.models import SubmissionReceipt
from app.services.receipt_signer import (
    clear_public_key_cache,
    sign_receipt,
    verify_receipt,
)
from tests.factories import (
    make_consent,
    make_portal,
    make_signing_key,
    make_submission,
    make_supplier,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pem_for(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


async def _seed_signed_receipt(
    auth_client, async_session, signing_key
) -> tuple[str, str]:
    """Create a supplier/consent/portal/submission and sign a receipt.

    Returns ``(tenant_id, receipt_id)``.
    """

    client, _ = auth_client
    me = (await client.get("/v1/auth/me")).json()
    tenant_id = me["tenant_id"]

    from app.models import Tenant

    tenant = await async_session.get(Tenant, tenant_id)
    supplier = await make_supplier(async_session, tenant)
    portal = await make_portal(async_session)
    consent = await make_consent(async_session, supplier=supplier, portal=portal)
    submission = await make_submission(
        async_session, supplier=supplier, portal=portal, consent=consent
    )
    receipt = await sign_receipt(
        async_session,
        submission=submission,
        consent=consent,
        tos_version_hash="sha256:" + "a" * 64,
    )
    await async_session.commit()
    return tenant_id, receipt.id


# ---------------------------------------------------------------------------
# Tenant-scoped list / fetch
# ---------------------------------------------------------------------------


class TestList:
    # NOTE: the production route ``GET /v1/receipts`` and ``GET
    # /v1/receipts/{id}`` call ``ReceiptRead.model_validate(<ORM>)`` even
    # though ``verify_url`` is a required field that only exists on the
    # response model. Pydantic 2 rejects this, so the endpoint currently
    # 500s. The tests below pin the *intended* contract; they will pass
    # once production injects ``verify_url`` before validation (e.g. by
    # constructing the schema with explicit kwargs).
    async def test_list_scoped_to_tenant(
        self, auth_client, async_session, signing_key
    ) -> None:
        client, _ = auth_client
        _, receipt_id = await _seed_signed_receipt(
            auth_client, async_session, signing_key
        )
        r = await client.get("/v1/receipts")
        assert r.status_code == 200
        ids = [row["id"] for row in r.json()]
        assert receipt_id in ids
        assert r.headers.get("X-Total-Count") == str(len(r.json()))

    async def test_get_by_id_returns_receipt(
        self, auth_client, async_session, signing_key
    ) -> None:
        client, _ = auth_client
        _, receipt_id = await _seed_signed_receipt(
            auth_client, async_session, signing_key
        )
        r = await client.get(f"/v1/receipts/{receipt_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == receipt_id
        assert body["verify_url"].endswith(f"/verify/{receipt_id}")

    async def test_get_unknown_returns_404(self, auth_client) -> None:
        client, _ = auth_client
        r = await client.get("/v1/receipts/does-not-exist")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Public verifier endpoint
# ---------------------------------------------------------------------------


class TestPublicVerify:
    async def test_verify_unknown_id_returns_404(
        self, client: AsyncClient
    ) -> None:
        r = await client.get("/verify/no-such-receipt")
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "receipt_not_found"

    async def test_verify_valid_receipt_returns_verified_true(
        self, auth_client, async_session, signing_key, client: AsyncClient
    ) -> None:
        _, receipt_id = await _seed_signed_receipt(
            auth_client, async_session, signing_key
        )
        # Use the un-authed client (verify is public).
        client.headers.pop("Authorization", None)
        r = await client.get(f"/verify/{receipt_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["verified"] is True
        assert body["public_key_b64"]
        assert body["receipt"]["receipt_id"] == receipt_id

    async def test_tampered_signature_returns_verified_false(
        self, auth_client, async_session, signing_key, client: AsyncClient
    ) -> None:
        _, receipt_id = await _seed_signed_receipt(
            auth_client, async_session, signing_key
        )
        # Flip a byte of the signature.
        receipt = await async_session.get(SubmissionReceipt, receipt_id)
        sig = bytearray(base64.b64decode(receipt.signature_b64))
        sig[0] ^= 0xFF
        receipt.signature_b64 = base64.b64encode(bytes(sig)).decode("ascii")
        await async_session.commit()

        r = await client.get(f"/verify/{receipt_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["verified"] is False
        assert body["reason"]

    async def test_unknown_signing_key_id_returns_verified_false(
        self, auth_client, async_session, signing_key, client: AsyncClient
    ) -> None:
        _, receipt_id = await _seed_signed_receipt(
            auth_client, async_session, signing_key
        )
        receipt = await async_session.get(SubmissionReceipt, receipt_id)
        receipt.signing_key_id = "rotated-out-key-id"
        await async_session.commit()
        clear_public_key_cache()

        r = await client.get(f"/verify/{receipt_id}")
        body = r.json()
        assert body["verified"] is False


# ---------------------------------------------------------------------------
# Direct signer-level verification + key rotation
# ---------------------------------------------------------------------------


class TestDirectVerification:
    async def test_verify_unknown_receipt_raises(
        self, async_session, signing_key
    ) -> None:
        with pytest.raises(LookupError):
            await verify_receipt(async_session, "no-such-receipt")

    async def test_key_rotation_old_key_in_registry_still_verifies(
        self, async_session, signing_key, monkeypatch
    ) -> None:
        """Sign with key A (in env), register key B in DB, verify both."""

        from app.models import Tenant
        from app.utils import crypto as crypto_utils

        tenant = await async_session.execute(
            __import__("sqlalchemy").select(Tenant).limit(1)
        )
        tenant = tenant.scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(name="Rot", slug="rot")
            async_session.add(tenant)
            await async_session.flush()

        supplier = await make_supplier(async_session, tenant)
        portal = await make_portal(async_session)
        consent = await make_consent(async_session, supplier=supplier, portal=portal)
        submission = await make_submission(
            async_session, supplier=supplier, portal=portal, consent=consent
        )

        # Sign under the default test key.
        receipt_a = await sign_receipt(
            async_session,
            submission=submission,
            consent=consent,
            tos_version_hash="sha256:" + "b" * 64,
        )
        await async_session.flush()
        result_a = await verify_receipt(async_session, receipt_a.id)
        assert result_a["verified"] is True

        # Now rotate: persist a new key into the SigningKey table and verify
        # a receipt signed under the *new* key id.
        new_key = Ed25519PrivateKey.generate()
        new_pem = new_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("ascii")
        from app.config import settings

        monkeypatch.setattr(settings, "receipt_signing_private_key_pem", new_pem)
        monkeypatch.setattr(settings, "receipt_signing_key_id", "rotated-key")
        crypto_utils.reset_default_signing_key_cache()
        clear_public_key_cache()

        # Persist the rotated public key.
        await make_signing_key(
            async_session,
            key_id="rotated-key",
            public_pem=_pem_for(new_key),
        )

        submission_b = await make_submission(
            async_session, supplier=supplier, portal=portal, consent=consent
        )
        receipt_b = await sign_receipt(
            async_session,
            submission=submission_b,
            consent=consent,
            tos_version_hash="sha256:" + "c" * 64,
        )
        await async_session.commit()
        result_b = await verify_receipt(async_session, receipt_b.id)
        assert result_b["verified"] is True
        assert result_b["signing_key_id"] == "rotated-key"

    async def test_corrupt_signature_b64_yields_verified_false(
        self, async_session, signing_key
    ) -> None:
        from app.models import Tenant

        tenant = (
            await async_session.execute(
                __import__("sqlalchemy").select(Tenant).limit(1)
            )
        ).scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(name="X", slug="x")
            async_session.add(tenant)
            await async_session.flush()
        supplier = await make_supplier(async_session, tenant)
        portal = await make_portal(async_session)
        consent = await make_consent(async_session, supplier=supplier, portal=portal)
        submission = await make_submission(
            async_session, supplier=supplier, portal=portal, consent=consent
        )
        receipt = await sign_receipt(
            async_session,
            submission=submission,
            consent=consent,
            tos_version_hash="sha256:" + "d" * 64,
        )
        receipt.signature_b64 = "not-valid-base64!!!"
        await async_session.flush()
        result = await verify_receipt(async_session, receipt.id)
        assert result["verified"] is False
