"""Tests for AuditLog row creation across API actions.

These exercise the side-effect that mutating endpoints produce one or more
``AuditLog`` rows with the documented action / resource_type / tenant_id
linkage. We query the row count directly via ``async_session`` after each
API call.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import AuditLog
from tests.factories import register_and_token

pytestmark = pytest.mark.asyncio


async def _audit_rows(async_session, *, action: str) -> list[AuditLog]:
    result = await async_session.execute(
        select(AuditLog).where(AuditLog.action == action)
    )
    return list(result.scalars().all())


class TestAuth:
    async def test_register_writes_user_registered_row(
        self, client, async_session
    ) -> None:
        await register_and_token(client, email="audit-reg@example.com")
        rows = await _audit_rows(async_session, action="user.registered")
        assert len(rows) == 1
        assert rows[0].resource_type == "user"
        assert rows[0].tenant_id is not None
        assert rows[0].actor_user_id is not None

    async def test_login_writes_login_row(
        self, client, async_session
    ) -> None:
        reg = await register_and_token(
            client, email="audit-login@example.com"
        )
        await client.post(
            "/v1/auth/login",
            json={"email": reg["email"], "password": reg["password"]},
        )
        rows = await _audit_rows(async_session, action="user.login")
        assert len(rows) >= 1
        assert rows[0].resource_type == "user"


class TestSupplier:
    async def test_create_writes_supplier_created_row(
        self, auth_client, async_session
    ) -> None:
        client, _ = auth_client
        await client.post(
            "/v1/suppliers", json={"legal_name": "AuditCo", "ein": "11-2222222"}
        )
        rows = await _audit_rows(async_session, action="supplier.created")
        assert len(rows) == 1
        assert rows[0].resource_type == "supplier"
        assert rows[0].resource_id is not None

    async def test_update_writes_supplier_updated_row(
        self, auth_client, async_session
    ) -> None:
        client, _ = auth_client
        created = (
            await client.post("/v1/suppliers", json={"legal_name": "U Co"})
        ).json()
        await client.patch(
            f"/v1/suppliers/{created['id']}", json={"dba_name": "U DBA"}
        )
        rows = await _audit_rows(async_session, action="supplier.updated")
        assert len(rows) == 1
        assert rows[0].metadata_json == {"fields": ["dba_name"]}

    async def test_delete_writes_supplier_deleted_row(
        self, auth_client, async_session
    ) -> None:
        client, _ = auth_client
        created = (
            await client.post("/v1/suppliers", json={"legal_name": "Del Co"})
        ).json()
        await client.delete(f"/v1/suppliers/{created['id']}")
        rows = await _audit_rows(async_session, action="supplier.deleted")
        assert len(rows) == 1
