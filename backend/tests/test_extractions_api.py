"""Tests for the /v1/extractions HTTP surface."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services import extraction_service
from app.services.extraction_service import InMemoryPdfLoader
from tests.conftest import RegisteredUser, register_user
from tests.fixtures.pdfs import make_pdf

pytestmark = pytest.mark.asyncio


def _coi_blob() -> bytes:
    return make_pdf(
        [
            "ACORD 25 CERTIFICATE OF LIABILITY INSURANCE",
            "PRODUCER",
            "Smith Brokers",
            "INSURED",
            "Acme Inc",
            "FEIN: 12-3456789",
            "INSURER A: The Hartford NAIC # 19682",
            "COMMERCIAL GENERAL LIABILITY",
            "POLICY NUMBER: GL-2026-00001",
            "EFF 01/15/2026 EXP 01/15/2027",
            "$1,000,000 each occurrence",
            "$2,000,000 general aggregate",
            "CERTIFICATE HOLDER",
            "Big Co LLC",
            "CERTIFICATE NUMBER: CERT-9999",
        ]
    )


@pytest.fixture(autouse=True)
def _no_celery_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace ``extract_document.delay`` with a no-op so tests never touch Redis."""

    from app.workers.tasks import extraction_tasks

    monkeypatch.setattr(
        extraction_tasks.extract_document,
        "delay",
        lambda *a, **kw: None,
    )


@pytest.fixture
def loader_with_blob() -> InMemoryPdfLoader:
    ldr = InMemoryPdfLoader()
    extraction_service.set_default_loader(ldr)
    yield ldr
    extraction_service.set_default_loader(InMemoryPdfLoader())


async def _enqueue(client: AsyncClient, document_id: str = "doc-1") -> dict:
    resp = await client.post(
        "/v1/extractions/document",
        json={"document_type": "coi", "document_id": document_id},
    )
    assert resp.status_code == 202, resp.text
    return resp.json()


async def test_enqueue_returns_pending(
    auth_client: tuple[AsyncClient, RegisteredUser],
    loader_with_blob: InMemoryPdfLoader,
) -> None:
    client, _ = auth_client
    body = await _enqueue(client)
    assert body["status"] == "pending"
    assert body["source_document_type"] == "coi"
    assert body["source_document_id"] == "doc-1"


async def test_enqueue_rejects_unknown_doc_type(
    auth_client: tuple[AsyncClient, RegisteredUser],
) -> None:
    client, _ = auth_client
    resp = await client.post(
        "/v1/extractions/document",
        json={"document_type": "bogus", "document_id": "doc-1"},
    )
    assert resp.status_code == 422


async def test_enqueue_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/v1/extractions/document",
        json={"document_type": "coi", "document_id": "doc-1"},
    )
    assert resp.status_code in (401, 403)


async def test_get_extraction_round_trip(
    auth_client: tuple[AsyncClient, RegisteredUser],
    loader_with_blob: InMemoryPdfLoader,
) -> None:
    client, _ = auth_client
    body = await _enqueue(client)
    resp = await client.get(f"/v1/extractions/{body['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == body["id"]


async def test_get_extraction_not_found(
    auth_client: tuple[AsyncClient, RegisteredUser],
) -> None:
    client, _ = auth_client
    resp = await client.get("/v1/extractions/does-not-exist")
    assert resp.status_code == 404


async def test_list_extractions(
    auth_client: tuple[AsyncClient, RegisteredUser],
    loader_with_blob: InMemoryPdfLoader,
) -> None:
    client, _ = auth_client
    await _enqueue(client, "d1")
    await _enqueue(client, "d2")
    resp = await client.get("/v1/extractions")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 2


async def test_list_extractions_filter_by_type(
    auth_client: tuple[AsyncClient, RegisteredUser],
    loader_with_blob: InMemoryPdfLoader,
) -> None:
    client, _ = auth_client
    await _enqueue(client, "d1")
    resp = await client.get("/v1/extractions?document_type=eo_certificate")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_accept_endpoint_marks_accepted(
    auth_client: tuple[AsyncClient, RegisteredUser],
    loader_with_blob: InMemoryPdfLoader,
) -> None:
    client, _ = auth_client
    body = await _enqueue(client)
    # Run extraction synchronously via service (celery skipped under tests).
    loader_with_blob.put(
        tenant_id=body["tenant_id"],
        source_type="coi",
        source_id=body["source_document_id"],
        blob=_coi_blob(),
    )
    from app.db import AsyncSessionLocal
    async with AsyncSessionLocal() as s:
        await extraction_service.run_extraction(s, extraction_id=body["id"])
    resp = await client.post(
        f"/v1/extractions/{body['id']}/accept",
        json={"fields": {"policy_number": "MANUAL-1"}},
    )
    assert resp.status_code == 200, resp.text
    out = resp.json()
    assert out["status"] == "accepted"
    assert out["extracted_fields"]["policy_number"] == "MANUAL-1"
    assert out["reviewed_by_user_id"]


async def test_reject_endpoint_marks_rejected(
    auth_client: tuple[AsyncClient, RegisteredUser],
    loader_with_blob: InMemoryPdfLoader,
) -> None:
    client, _ = auth_client
    body = await _enqueue(client)
    resp = await client.post(
        f"/v1/extractions/{body['id']}/reject",
        json={"reason": "wrong document"},
    )
    assert resp.status_code == 200
    out = resp.json()
    assert out["status"] == "rejected"
    assert any("wrong document" in w for w in (out.get("warnings") or []))


async def test_accept_unknown_id_returns_404(
    auth_client: tuple[AsyncClient, RegisteredUser],
) -> None:
    client, _ = auth_client
    resp = await client.post(
        "/v1/extractions/missing/accept", json={"fields": {}}
    )
    assert resp.status_code == 404


async def test_tenant_isolation_on_get(
    client: AsyncClient,
    loader_with_blob: InMemoryPdfLoader,
) -> None:
    # Tenant A creates an extraction.
    user_a = await register_user(
        client,
        email="a@example.com",
        full_name="A",
        tenant_name="Tenant A",
    )
    client.headers["Authorization"] = f"Bearer {user_a.tokens.access_token}"
    body = await _enqueue(client)
    # Switch to tenant B.
    client.headers.pop("Authorization")
    user_b = await register_user(
        client,
        email="b@example.com",
        full_name="B",
        tenant_name="Tenant B",
    )
    client.headers["Authorization"] = f"Bearer {user_b.tokens.access_token}"
    resp = await client.get(f"/v1/extractions/{body['id']}")
    assert resp.status_code == 404
