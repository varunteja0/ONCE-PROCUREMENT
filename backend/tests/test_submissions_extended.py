"""Extended /v1/submissions endpoint tests.

Covers create validation (missing supplier/portal/consent, unsupported portal,
risky portal gate), list filters, get/retry transitions, and the receipt
fetch sub-route.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.models import (
    Portal,
    PortalPlatform,
    SubmissionStatus,
)
from tests.factories import (
    make_consent,
    make_portal,
    make_supplier,
    register_and_token,  # noqa: F401 — re-export needed
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _stub_enqueue(monkeypatch):
    """Prevent the API from blocking on a Celery broker connection.

    In production ``submission_service._enqueue`` either runs the pipeline
    inline or dispatches via Celery+Redis. In tests we don't want either —
    the row-level state transitions are what we're exercising here.
    """

    async def _noop(submission_id, session):  # noqa: ARG001
        return None

    monkeypatch.setattr(
        "app.services.submission_service._enqueue", _noop
    )


# ---------------------------------------------------------------------------
# Small helper to bootstrap a submission scaffold for the authed tenant.
# ---------------------------------------------------------------------------


async def _bootstrap(auth_client, async_session) -> dict[str, str]:
    """Create supplier+consent+portal in the tenant of ``auth_client`` and
    return the IDs needed to POST a submission."""

    client, registered = auth_client
    me = await client.get("/v1/auth/me")
    tenant_id = me.json()["tenant_id"]

    from app.models import Tenant

    tenant = await async_session.get(Tenant, tenant_id)
    supplier = await make_supplier(async_session, tenant)
    portal = await make_portal(async_session, platform=PortalPlatform.AMTRUST)
    consent = await make_consent(async_session, supplier=supplier, portal=portal)
    await async_session.commit()

    return {
        "supplier_id": supplier.id,
        "portal_id": portal.id,
        "consent_record_id": consent.id,
    }


class TestCreate:
    async def test_happy_path_returns_201_with_queued_status(
        self, auth_client, async_session
    ) -> None:
        client, _ = auth_client
        ids = await _bootstrap(auth_client, async_session)
        r = await client.post("/v1/submissions", json=ids)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["status"] == SubmissionStatus.QUEUED.value
        assert body["attempt_count"] == 0

    async def test_unknown_supplier_returns_404(
        self, auth_client, async_session
    ) -> None:
        client, _ = auth_client
        ids = await _bootstrap(auth_client, async_session)
        ids["supplier_id"] = "00000000-0000-0000-0000-000000000000"
        r = await client.post("/v1/submissions", json=ids)
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "supplier_not_found"

    async def test_unknown_portal_returns_404(
        self, auth_client, async_session
    ) -> None:
        client, _ = auth_client
        ids = await _bootstrap(auth_client, async_session)
        ids["portal_id"] = "00000000-0000-0000-0000-000000000000"
        r = await client.post("/v1/submissions", json=ids)
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "portal_not_found"

    async def test_unknown_consent_returns_404(
        self, auth_client, async_session
    ) -> None:
        client, _ = auth_client
        ids = await _bootstrap(auth_client, async_session)
        ids["consent_record_id"] = "00000000-0000-0000-0000-000000000000"
        r = await client.post("/v1/submissions", json=ids)
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "consent_record_not_found"

    async def test_unsupported_portal_returns_400(
        self, auth_client, async_session
    ) -> None:
        client, _ = auth_client
        ids = await _bootstrap(auth_client, async_session)
        # Flip the portal to unsupported.
        portal = await async_session.get(Portal, ids["portal_id"])
        portal.is_supported = False
        await async_session.commit()
        r = await client.post("/v1/submissions", json=ids)
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "portal_unsupported"

    async def test_risky_portal_gated_by_feature_flag(
        self, auth_client, async_session, monkeypatch
    ) -> None:
        client, _ = auth_client
        ids = await _bootstrap(auth_client, async_session)
        portal = await async_session.get(Portal, ids["portal_id"])
        portal.risky = True
        await async_session.commit()
        monkeypatch.setattr(settings, "enable_tos_risky_platforms", False)

        r = await client.post("/v1/submissions", json=ids)
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "portal_risky_disabled"


class TestRetry:
    async def test_retry_queued_returns_409(
        self, auth_client, async_session
    ) -> None:
        client, _ = auth_client
        ids = await _bootstrap(auth_client, async_session)
        created = (await client.post("/v1/submissions", json=ids)).json()
        r = await client.post(f"/v1/submissions/{created['id']}/retry")
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "submission_not_retryable"

    async def test_retry_failed_returns_200_and_transitions_to_retrying(
        self, auth_client, async_session
    ) -> None:
        client, _ = auth_client
        ids = await _bootstrap(auth_client, async_session)
        created = (await client.post("/v1/submissions", json=ids)).json()

        # Move to FAILED out-of-band.
        from app.models import SupplierSubmission

        sub = await async_session.get(SupplierSubmission, created["id"])
        sub.status = SubmissionStatus.FAILED
        sub.last_error = "test-induced"
        await async_session.commit()

        r = await client.post(f"/v1/submissions/{created['id']}/retry")
        assert r.status_code == 200
        assert r.json()["status"] == SubmissionStatus.RETRYING.value
        assert r.json()["last_error"] is None

    async def test_retry_unknown_returns_404(self, auth_client) -> None:
        client, _ = auth_client
        r = await client.post("/v1/submissions/no-such-id/retry")
        assert r.status_code == 404


class TestList:
    async def test_filter_by_status(self, auth_client, async_session) -> None:
        client, _ = auth_client
        ids = await _bootstrap(auth_client, async_session)
        c1 = (await client.post("/v1/submissions", json=ids)).json()
        c2 = (await client.post("/v1/submissions", json=ids)).json()

        from app.models import SupplierSubmission

        sub2 = await async_session.get(SupplierSubmission, c2["id"])
        sub2.status = SubmissionStatus.FAILED
        await async_session.commit()

        r = await client.get(
            "/v1/submissions", params={"status": SubmissionStatus.FAILED.value}
        )
        assert r.status_code == 200
        rows = r.json()
        ids_returned = {row["id"] for row in rows}
        assert c2["id"] in ids_returned
        assert c1["id"] not in ids_returned

    async def test_filter_by_supplier(self, auth_client, async_session) -> None:
        client, _ = auth_client
        ids = await _bootstrap(auth_client, async_session)
        created = (await client.post("/v1/submissions", json=ids)).json()
        r = await client.get(
            "/v1/submissions", params={"supplier_id": ids["supplier_id"]}
        )
        assert any(row["id"] == created["id"] for row in r.json())

    async def test_total_count_header_present(
        self, auth_client, async_session
    ) -> None:
        client, _ = auth_client
        ids = await _bootstrap(auth_client, async_session)
        await client.post("/v1/submissions", json=ids)
        r = await client.get("/v1/submissions")
        assert r.headers.get("X-Total-Count") == str(len(r.json()))


class TestReceiptFetch:
    async def test_no_receipt_yet_returns_404(
        self, auth_client, async_session
    ) -> None:
        client, _ = auth_client
        ids = await _bootstrap(auth_client, async_session)
        created = (await client.post("/v1/submissions", json=ids)).json()
        r = await client.get(f"/v1/submissions/{created['id']}/receipt")
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "receipt_not_found"

    async def test_unknown_submission_receipt_returns_404(
        self, auth_client
    ) -> None:
        client, _ = auth_client
        r = await client.get("/v1/submissions/no-such-id/receipt")
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "submission_not_found"
