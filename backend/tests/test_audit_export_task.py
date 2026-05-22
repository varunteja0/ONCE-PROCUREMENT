"""L3.10 — Tests for the audit export Celery task (sync helper path)."""

from __future__ import annotations

import hashlib
import json
import os

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy.ext.asyncio import AsyncSession

import app.db as app_db
from app.models import Tenant
from app.models.audit_export import (
    AuditExport,
    AuditExportScope,
    AuditExportStatus,
)
from app.models.audit_log import AuditActorType
from app.services.audit_logger import record_audit_event
from app.services.audit_signer import verify_envelope
from app.workers.tasks.audit_tasks import generate_audit_export_sync

pytestmark = pytest.mark.asyncio


async def _seed(session: AsyncSession, n: int = 3, tid: str = "t-exp") -> None:
    session.add(Tenant(id=tid, name="x", slug=tid, plan="pilot", is_active=True))
    await session.commit()
    for i in range(n):
        await record_audit_event(
            session,
            tenant_id=tid,
            actor_type=AuditActorType.USER,
            action_verb="created",
            resource_type="supplier",
            resource_id=f"sup-{i}",
        )
    await session.commit()


async def _create_export(
    session: AsyncSession,
    *,
    tid: str = "t-exp",
    scope: AuditExportScope = AuditExportScope.TENANT,
    params: dict | None = None,
) -> str:
    ex = AuditExport(
        tenant_id=tid,
        scope_type=scope,
        scope_params=params or {},
        status=AuditExportStatus.PENDING,
    )
    session.add(ex)
    await session.commit()
    return ex.id


async def test_generate_export_marks_ready(
    async_session: AsyncSession,
    signing_key: Ed25519PrivateKey,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AUDIT_EXPORT_DIR", str(tmp_path))
    await _seed(async_session)
    ex_id = await _create_export(async_session)
    result = await generate_audit_export_sync(ex_id)
    assert result["status"] == "ready"
    async with app_db.AsyncSessionLocal() as s:
        row = await s.get(AuditExport, ex_id)
    assert row.status == AuditExportStatus.READY
    assert row.row_count == 3
    assert row.file_sha256 and len(row.file_sha256) == 64


async def test_generate_export_writes_pdf_and_envelope(
    async_session: AsyncSession,
    signing_key: Ed25519PrivateKey,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AUDIT_EXPORT_DIR", str(tmp_path))
    await _seed(async_session)
    ex_id = await _create_export(async_session)
    await generate_audit_export_sync(ex_id)
    async with app_db.AsyncSessionLocal() as s:
        row = await s.get(AuditExport, ex_id)
    assert os.path.exists(row.file_path)
    assert os.path.exists(row.signed_envelope_path)
    with open(row.file_path, "rb") as fh:
        pdf = fh.read()
    assert pdf.startswith(b"%PDF-")
    assert hashlib.sha256(pdf).hexdigest() == row.file_sha256


async def test_envelope_is_signed_and_verifiable(
    async_session: AsyncSession,
    signing_key: Ed25519PrivateKey,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AUDIT_EXPORT_DIR", str(tmp_path))
    await _seed(async_session)
    ex_id = await _create_export(async_session)
    await generate_audit_export_sync(ex_id)
    async with app_db.AsyncSessionLocal() as s:
        row = await s.get(AuditExport, ex_id)
    with open(row.signed_envelope_path, "rb") as fh:
        envelope = json.loads(fh.read())
    assert envelope["version"] == "1.0"
    assert envelope["row_count"] == 3
    assert envelope["pdf_sha256"] == row.file_sha256
    assert envelope["signature_b64"]
    assert verify_envelope(envelope) is True


async def test_refuses_to_export_tampered_chain(
    async_session: AsyncSession,
    signing_key: Ed25519PrivateKey,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AUDIT_EXPORT_DIR", str(tmp_path))
    await _seed(async_session)
    # Tamper.
    from sqlalchemy import text

    await async_session.execute(
        text("UPDATE audit_trail SET resource_id='X' WHERE chain_position=1")
    )
    await async_session.commit()
    ex_id = await _create_export(async_session)
    result = await generate_audit_export_sync(ex_id)
    assert result["status"] == "failed"
    assert result["reason"] == "chain_invalid"
    async with app_db.AsyncSessionLocal() as s:
        row = await s.get(AuditExport, ex_id)
    assert row.status == AuditExportStatus.FAILED
    assert "chain_invalid" in (row.error or "")


async def test_supplier_scope_filters_rows(
    async_session: AsyncSession,
    signing_key: Ed25519PrivateKey,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AUDIT_EXPORT_DIR", str(tmp_path))
    async_session.add(
        Tenant(id="t-exp", name="x", slug="t-exp", plan="pilot", is_active=True)
    )
    await async_session.commit()
    for rid in ("a", "b", "a"):
        await record_audit_event(
            async_session,
            tenant_id="t-exp",
            actor_type=AuditActorType.USER,
            action_verb="created",
            resource_type="supplier",
            resource_id=rid,
        )
    await async_session.commit()
    ex_id = await _create_export(
        async_session,
        scope=AuditExportScope.SUPPLIER,
        params={"supplier_id": "a"},
    )
    result = await generate_audit_export_sync(ex_id)
    assert result["status"] == "ready"
    assert result["row_count"] == 2


async def test_missing_export_id_returns_missing(
    signing_key: Ed25519PrivateKey,
    tmp_path,
    monkeypatch,
    _test_engine,
) -> None:  # noqa: ANN001
    monkeypatch.setenv("AUDIT_EXPORT_DIR", str(tmp_path))
    result = await generate_audit_export_sync("does-not-exist")
    assert result["status"] == "missing"
