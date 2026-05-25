"""End-to-end demo happy-path: submission -> sign receipt -> offline verify.

Run with:

    cd backend
    $env:RUN_E2E_DEMO='1'
    pytest -q -v tests/integration/test_e2e_demo_flow.py

Skipped by default so it never blocks the standard ``pytest -q`` sweep.

What this test pins
-------------------
1. The signing service ``app.services.receipt_signer.sign_receipt`` produces
   a persisted ``SubmissionReceipt`` whose ``public_payload_json`` is the
   exact dict that was signed.
2. The signature on that receipt verifies under ``cryptography``'s Ed25519
   public key (offline, no DB lookup, no backend code path).
3. The canonical-JSON bytes the backend signed over are byte-identical to
   what the public verifier (``verifier/app/canonical.py``) would compute
   for the same payload.
4. The high-level ``verify_receipt`` service agrees (``verified=True``).
5. Tenant scoping holds.
"""

from __future__ import annotations

import base64
import importlib.util
import os
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ConsentRecord,
    Portal,
    PortalPlatform,
    SubmissionReceipt,
    Supplier,
    SupplierSubmission,
)
from app.services.receipt_signer import (
    clear_public_key_cache,
    sign_receipt,
    verify_receipt,
)
from app.utils.canonical_json import canonical_json_bytes as backend_canonical_bytes
from tests.factories import (
    make_consent,
    make_portal,
    make_submission,
    make_supplier,
    make_tenant,
    make_user,
)

# Load the verifier's canonical encoder by file path (standalone service).
_VERIFIER_CANONICAL = (
    Path(__file__).resolve().parents[2] / "verifier" / "app" / "canonical.py"
)
_spec = importlib.util.spec_from_file_location(
    "_verifier_canonical_e2e", _VERIFIER_CANONICAL
)
assert _spec is not None and _spec.loader is not None, (
    f"could not import verifier canonical encoder at {_VERIFIER_CANONICAL}"
)
_verifier_canonical = importlib.util.module_from_spec(_spec)
sys.modules["_verifier_canonical_e2e"] = _verifier_canonical
_spec.loader.exec_module(_verifier_canonical)
verifier_canonical_bytes = _verifier_canonical.canonical_json_bytes


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_E2E_DEMO") != "1",
    reason="set RUN_E2E_DEMO=1 to run the demo end-to-end happy-path",
)


@pytest.mark.asyncio
async def test_e2e_demo_happy_path(
    async_session: AsyncSession,
    signing_key: Ed25519PrivateKey,
) -> None:
    """Capture -> sign -> offline-verify, with byte-exact verifier parity."""

    clear_public_key_cache()

    # (a) Seed tenant + AmTrust portal + supplier + consent.
    tenant = await make_tenant(
        async_session, name="Demo Tenant", slug="demo-tenant-e2e"
    )
    owner = await make_user(async_session)
    portal: Portal = await make_portal(
        async_session, platform=PortalPlatform.AMTRUST
    )
    assert portal.platform is PortalPlatform.AMTRUST

    supplier: Supplier = await make_supplier(
        async_session, tenant, legal_name="Demo Supplier LLC"
    )
    consent: ConsentRecord = await make_consent(
        async_session, supplier=supplier, portal=portal, granted_by=owner
    )
    await async_session.flush()

    # (b) "Capture submission" via the service layer (the receipt suite
    # uses the same path; the public submission-creation API is private).
    submission: SupplierSubmission = await make_submission(
        async_session,
        supplier=supplier,
        portal=portal,
        consent=consent,
        payload_json={
            "legal_name": supplier.legal_name,
            "ein": supplier.ein,
            "line_of_business": "General Liability",
            "effective_date": "2026-06-01",
            "target_states": ["NY", "NJ"],
        },
    )

    # (c) Sign the receipt directly (no Celery).
    tos_hash = "sha256:" + "f" * 64
    receipt: SubmissionReceipt = await sign_receipt(
        async_session,
        submission=submission,
        consent=consent,
        tos_version_hash=tos_hash,
    )
    await async_session.commit()

    assert receipt.id
    assert receipt.signature_b64
    assert receipt.public_payload_json["receipt_id"] == receipt.id
    assert receipt.public_payload_json["submission_id"] == submission.id
    assert receipt.public_payload_json["consent_record_id"] == consent.id
    assert receipt.public_payload_json["portal"] == PortalPlatform.AMTRUST.value
    assert receipt.tenant_id == tenant.id

    # (d) Fetch via tenant-scoped query; verify Ed25519 signature offline.
    fetched = (
        await async_session.execute(
            select(SubmissionReceipt)
            .where(SubmissionReceipt.id == receipt.id)
            .where(SubmissionReceipt.tenant_id == tenant.id)
        )
    ).scalar_one()

    payload = dict(fetched.public_payload_json)
    signed_bytes_backend = backend_canonical_bytes(payload)
    signature = base64.b64decode(fetched.signature_b64, validate=True)

    public_key: Ed25519PublicKey = signing_key.public_key()
    public_key.verify(signature, signed_bytes_backend)

    # (e) Byte-match what the public verifier would canonicalize.
    signed_bytes_verifier = verifier_canonical_bytes(payload)
    assert signed_bytes_backend == signed_bytes_verifier, (
        "canonical-JSON drift between backend signer and public verifier"
    )
    public_key.verify(signature, signed_bytes_verifier)

    # High-level: backend's own verifier agrees.
    result = await verify_receipt(async_session, receipt.id)
    assert result["verified"] is True
    assert result["receipt"]["receipt_id"] == receipt.id
    assert result["signing_key_id"] == receipt.signing_key_id

    # Tenant isolation: a query under a different tenant_id sees nothing.
    other = (
        await async_session.execute(
            select(SubmissionReceipt).where(
                SubmissionReceipt.tenant_id
                == "00000000-0000-0000-0000-000000000000"
            )
        )
    ).scalars().all()
    assert other == []
