"""L3.10 — Integration tests for the audit REST API.

Tests run against the conftest ``test_app``, which mounts the v1 router
(including ``/v1/audit/*``) and the tenant_scope middleware but NOT the
audit middleware — so each test seeds rows directly via
``record_audit_event`` to keep assertions deterministic.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

import app.db as app_db
from app.models.audit_log import AuditActorType
from app.services.audit_logger import record_audit_event

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _no_celery_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the Celery enqueue with a no-op so tests don't hang waiting
    on a real broker. The export row stays in ``pending`` — which is exactly
    what the API contract returns and what the rate-limit test asserts.
    """

    from app.workers.tasks import audit_tasks as _at

    class _NoopAsyncResult:
        id = "test-task"

    def _noop(*args, **kwargs):  # noqa: ANN001
        return _NoopAsyncResult()

    monkeypatch.setattr(_at.generate_audit_export_task, "apply_async", _noop)
    monkeypatch.setattr(_at.generate_audit_export_task, "delay", _noop)


async def _seed(tenant_id: str, n: int = 3) -> list[str]:
    """Append *n* audit rows for *tenant_id*. Returns the new row ids."""
    ids: list[str] = []
    async with app_db.AsyncSessionLocal() as s:
        for i in range(n):
            row = await record_audit_event(
                s,
                tenant_id=tenant_id,
                actor_type=AuditActorType.USER,
                actor_id="u-1",
                action_verb="created" if i % 2 == 0 else "updated",
                resource_type="supplier" if i % 2 == 0 else "submission",
                resource_id=f"r-{i}",
            )
            assert row is not None
            ids.append(row.id)
        await s.commit()
    return ids


async def _tenant_id_from(client: AsyncClient) -> str:
    """Extract the auth'd user's tenant_id by hitting /v1/auth/me."""
    r = await client.get("/v1/auth/me")
    assert r.status_code == 200, r.text
    body = r.json()
    return body.get("tenant_id") or body.get("user", {}).get("tenant_id")


async def test_list_audit_rows_returns_seeded_rows(auth_client) -> None:  # noqa: ANN001
    client, _user = auth_client
    tid = await _tenant_id_from(client)
    await _seed(tid, n=3)
    r = await client.get("/v1/audit")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert body["items"][0]["chain_position"] in {1, 2, 3}


async def test_list_filters_by_actor_type(auth_client) -> None:  # noqa: ANN001
    client, _ = auth_client
    tid = await _tenant_id_from(client)
    await _seed(tid, n=2)
    async with app_db.AsyncSessionLocal() as s:
        await record_audit_event(
            s,
            tenant_id=tid,
            actor_type=AuditActorType.SYSTEM,
            action_verb="created",
            resource_type="cron",
        )
        await s.commit()
    r = await client.get("/v1/audit", params={"actor_type": "system"})
    assert r.status_code == 200
    body = r.json()
    assert all(it["actor_type"] == "system" for it in body["items"])
    assert body["total"] == 1


async def test_list_filters_by_resource_type(auth_client) -> None:  # noqa: ANN001
    client, _ = auth_client
    tid = await _tenant_id_from(client)
    await _seed(tid, n=4)  # mixed supplier/submission
    r = await client.get("/v1/audit", params={"resource_type": "supplier"})
    assert r.status_code == 200
    body = r.json()
    assert all(it["resource_type"] == "supplier" for it in body["items"])


async def test_get_audit_row_returns_404_for_unknown(auth_client) -> None:  # noqa: ANN001
    client, _ = auth_client
    r = await client.get("/v1/audit/no-such-id")
    assert r.status_code == 404


async def test_get_audit_row_by_id(auth_client) -> None:  # noqa: ANN001
    client, _ = auth_client
    tid = await _tenant_id_from(client)
    ids = await _seed(tid, n=1)
    r = await client.get(f"/v1/audit/{ids[0]}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == ids[0]


async def test_chain_verify_endpoint_returns_valid(auth_client) -> None:  # noqa: ANN001
    client, _ = auth_client
    tid = await _tenant_id_from(client)
    await _seed(tid, n=4)
    r = await client.get("/v1/audit/chain/verify")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["valid"] is True
    assert body["rows_checked"] == 4
    assert body["breaks"] == []


async def test_chain_verify_detects_tampering(auth_client) -> None:  # noqa: ANN001
    client, _ = auth_client
    tid = await _tenant_id_from(client)
    await _seed(tid, n=3)
    from sqlalchemy import text

    async with app_db.AsyncSessionLocal() as s:
        await s.execute(
            text("UPDATE audit_trail SET resource_id='X' WHERE chain_position=2")
        )
        await s.commit()
    r = await client.get("/v1/audit/chain/verify")
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert body["breaks"]


async def test_by_resource_returns_history(auth_client) -> None:  # noqa: ANN001
    client, _ = auth_client
    tid = await _tenant_id_from(client)
    async with app_db.AsyncSessionLocal() as s:
        for verb in ("created", "updated", "updated"):
            await record_audit_event(
                s,
                tenant_id=tid,
                actor_type=AuditActorType.USER,
                action_verb=verb,
                resource_type="supplier",
                resource_id="abc-123",
            )
        await s.commit()
    r = await client.get("/v1/audit/by-resource/supplier/abc-123")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    # Ascending by occurred_at.
    assert body["items"][0]["chain_position"] < body["items"][-1]["chain_position"]


async def test_create_export_returns_202_pending(auth_client) -> None:  # noqa: ANN001
    client, _ = auth_client
    tid = await _tenant_id_from(client)
    await _seed(tid, n=2)
    r = await client.post(
        "/v1/audit/exports",
        json={"scope": "tenant", "scope_params": {}},
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] in {"pending", "generating", "ready", "failed"}
    assert body["scope_type"] == "tenant"


async def test_second_active_export_is_rate_limited(auth_client) -> None:  # noqa: ANN001
    client, _ = auth_client
    tid = await _tenant_id_from(client)
    await _seed(tid, n=2)
    # First request will create a PENDING export. Even if Celery isn't
    # available the row stays PENDING — which is what the limiter checks.
    r1 = await client.post(
        "/v1/audit/exports", json={"scope": "tenant", "scope_params": {}}
    )
    assert r1.status_code == 202, r1.text
    r2 = await client.post(
        "/v1/audit/exports", json={"scope": "tenant", "scope_params": {}}
    )
    assert r2.status_code == 429, r2.text
    assert r2.json()["detail"]["code"] == "export_in_progress"


async def test_list_exports_returns_created(auth_client) -> None:  # noqa: ANN001
    client, _ = auth_client
    tid = await _tenant_id_from(client)
    await _seed(tid, n=1)
    await client.post(
        "/v1/audit/exports", json={"scope": "tenant", "scope_params": {}}
    )
    r = await client.get("/v1/audit/exports")
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_download_not_ready_returns_409(auth_client) -> None:  # noqa: ANN001
    client, _ = auth_client
    tid = await _tenant_id_from(client)
    await _seed(tid, n=1)
    create = await client.post(
        "/v1/audit/exports", json={"scope": "tenant", "scope_params": {}}
    )
    ex_id = create.json()["id"]
    r = await client.get(f"/v1/audit/exports/{ex_id}/download")
    assert r.status_code in (409, 410)


async def test_cross_tenant_isolation(auth_client) -> None:  # noqa: ANN001
    client, _ = auth_client
    tid = await _tenant_id_from(client)
    await _seed(tid, n=2)
    # Seed rows for another tenant; they must NOT appear in /v1/audit.
    await _seed("other-tenant-xyz", n=3)
    r = await client.get("/v1/audit")
    body = r.json()
    assert body["total"] == 2
    assert all(it["tenant_id"] == tid for it in body["items"])
