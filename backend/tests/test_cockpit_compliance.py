"""Tests for the cockpit SOC 2 compliance endpoints.

Covers ``/cockpit/compliance/audit-export`` (JSONL + CSV),
``/cockpit/compliance/access-review``,
``/cockpit/compliance/audit-hash-digests``, and the
``/cockpit/compliance/key-rotations`` ledger (POST + GET).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

import app.db as app_db
from app.models import AuditHashDigest, AuditLog, Tenant, TenantUser, User
from tests.conftest_helpers import FounderHandle

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_tenant(slug: str = "acme") -> tuple[str, str, str]:
    """Insert a tenant + user + tenant_user. Returns (tenant_id, user_id, slug)."""

    async with app_db.AsyncSessionLocal() as session:
        tenant = Tenant(name=f"Tenant {slug}", slug=slug)
        session.add(tenant)
        await session.flush()
        user = User(
            email=f"{slug}-owner@example.com",
            hashed_password="x" * 60,
            full_name=f"{slug} Owner",
        )
        session.add(user)
        await session.flush()
        session.add(
            TenantUser(tenant_id=tenant.id, user_id=user.id, role="owner")
        )
        await session.commit()
        return tenant.id, user.id, tenant.slug


async def _seed_audit_rows(tenant_id: str, count: int = 5) -> None:
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    async with app_db.AsyncSessionLocal() as session:
        for i in range(count):
            session.add(
                AuditLog(
                    tenant_id=tenant_id,
                    actor_user_id=None,
                    action=f"test.event.{i}",
                    resource_type="test",
                    resource_id=f"r-{i}",
                    metadata_json={"i": i, "k": "v"},
                    ip_address="127.0.0.1",
                    occurred_at=base + timedelta(minutes=i),
                )
            )
        await session.commit()


# ---------------------------------------------------------------------------
# Audit export — JSONL + CSV
# ---------------------------------------------------------------------------


async def test_audit_export_jsonl_returns_rows_in_window(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    tenant_id, _, _ = await _seed_tenant("acme")
    await _seed_audit_rows(tenant_id, count=3)

    res = await cockpit_client.get(
        "/cockpit/compliance/audit-export",
        headers=founder_operator.headers,
        params={
            "tenant_id": tenant_id,
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-02T00:00:00Z",
            "format": "jsonl",
        },
    )
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("application/x-ndjson")
    lines = [ln for ln in res.text.splitlines() if ln.strip()]
    assert len(lines) == 3
    parsed = [json.loads(ln) for ln in lines]
    actions = [row["action"] for row in parsed]
    assert actions == ["test.event.0", "test.event.1", "test.event.2"]


async def test_audit_export_csv_writes_header_and_rows(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    tenant_id, _, _ = await _seed_tenant("acme")
    await _seed_audit_rows(tenant_id, count=2)

    res = await cockpit_client.get(
        "/cockpit/compliance/audit-export",
        headers=founder_operator.headers,
        params={
            "tenant_id": tenant_id,
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-02T00:00:00Z",
            "format": "csv",
        },
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    body = res.text.splitlines()
    assert body[0].startswith("id,tenant_id,actor_user_id,action,")
    assert len(body) == 1 + 2  # header + 2 rows


async def test_audit_export_requires_auth(cockpit_client: AsyncClient) -> None:
    res = await cockpit_client.get(
        "/cockpit/compliance/audit-export",
        params={
            "tenant_id": "anything",
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-02T00:00:00Z",
        },
    )
    assert res.status_code == 401


async def test_audit_export_non_founder_forbidden(
    cockpit_client: AsyncClient, support_operator: FounderHandle
) -> None:
    res = await cockpit_client.get(
        "/cockpit/compliance/audit-export",
        headers=support_operator.headers,
        params={
            "tenant_id": "anything",
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-02T00:00:00Z",
        },
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "founder_required"


async def test_audit_export_invalid_window_rejected(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    tenant_id, _, _ = await _seed_tenant("acme")
    # end <= start
    res = await cockpit_client.get(
        "/cockpit/compliance/audit-export",
        headers=founder_operator.headers,
        params={
            "tenant_id": tenant_id,
            "start": "2026-01-02T00:00:00Z",
            "end": "2026-01-01T00:00:00Z",
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "invalid_window"


async def test_audit_export_window_too_large_rejected(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    tenant_id, _, _ = await _seed_tenant("acme")
    res = await cockpit_client.get(
        "/cockpit/compliance/audit-export",
        headers=founder_operator.headers,
        params={
            "tenant_id": tenant_id,
            "start": "2024-01-01T00:00:00Z",
            "end": "2026-01-01T00:00:00Z",
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "window_too_large"


async def test_audit_export_unknown_tenant_404(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    res = await cockpit_client.get(
        "/cockpit/compliance/audit-export",
        headers=founder_operator.headers,
        params={
            "tenant_id": "00000000-0000-0000-0000-000000000000",
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-02T00:00:00Z",
        },
    )
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "tenant_not_found"


# ---------------------------------------------------------------------------
# Access review
# ---------------------------------------------------------------------------


async def test_access_review_lists_tenant_users(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    tenant_id, _, _ = await _seed_tenant("acme")
    res = await cockpit_client.get(
        "/cockpit/compliance/access-review",
        headers=founder_operator.headers,
        params={"tenant_id": tenant_id},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["tenant_id"] == tenant_id
    assert body["total"] == 1
    assert body["items"][0]["email"] == "acme-owner@example.com"
    assert body["items"][0]["role"] == "owner"


async def test_access_review_unknown_tenant_404(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    res = await cockpit_client.get(
        "/cockpit/compliance/access-review",
        headers=founder_operator.headers,
        params={"tenant_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Audit hash digests
# ---------------------------------------------------------------------------


async def test_audit_hash_digests_list_returns_rows(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    tenant_id, _, _ = await _seed_tenant("acme")
    async with app_db.AsyncSessionLocal() as session:
        session.add(
            AuditHashDigest(
                tenant_id=tenant_id,
                covers_date=datetime(2026, 1, 1, tzinfo=UTC),
                digest_sha256="a" * 64,
                prev_digest_sha256="",
                row_count=0,
            )
        )
        session.add(
            AuditHashDigest(
                tenant_id=tenant_id,
                covers_date=datetime(2026, 1, 2, tzinfo=UTC),
                digest_sha256="b" * 64,
                prev_digest_sha256="a" * 64,
                row_count=3,
            )
        )
        await session.commit()

    res = await cockpit_client.get(
        "/cockpit/compliance/audit-hash-digests",
        headers=founder_operator.headers,
        params={"tenant_id": tenant_id},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    # Most-recent first
    assert body["items"][0]["digest_sha256"] == "b" * 64
    assert body["items"][1]["digest_sha256"] == "a" * 64


# ---------------------------------------------------------------------------
# Key rotation ledger
# ---------------------------------------------------------------------------


async def test_key_rotation_post_records_entry(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    res = await cockpit_client.post(
        "/cockpit/compliance/key-rotations",
        headers=founder_operator.headers,
        json={
            "key_name": "receipt_signing_key",
            "new_key_id": "k-002",
            "previous_key_id": "k-001",
            "notes": "Quarterly Ed25519 rotation per RUNBOOK §2.",
            "metadata_json": {"deploy_ref": "v1.2.3"},
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["key_name"] == "receipt_signing_key"
    assert body["new_key_id"] == "k-002"
    assert body["rotated_by_operator_id"] == founder_operator.operator_id


async def test_key_rotation_post_unknown_key_name_rejected(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    res = await cockpit_client.post(
        "/cockpit/compliance/key-rotations",
        headers=founder_operator.headers,
        json={
            "key_name": "bogus_key",
            "notes": "Should fail — not in ALLOWED_KEY_NAMES.",
        },
    )
    assert res.status_code == 422


async def test_key_rotation_post_requires_founder(
    cockpit_client: AsyncClient, support_operator: FounderHandle
) -> None:
    res = await cockpit_client.post(
        "/cockpit/compliance/key-rotations",
        headers=support_operator.headers,
        json={
            "key_name": "receipt_signing_key",
            "notes": "Should fail — support is not a founder.",
        },
    )
    assert res.status_code == 403


async def test_key_rotation_get_lists_entries(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    # Create two entries.
    for new_id, prev_id in [("k-002", "k-001"), ("k-003", "k-002")]:
        await cockpit_client.post(
            "/cockpit/compliance/key-rotations",
            headers=founder_operator.headers,
            json={
                "key_name": "receipt_signing_key",
                "new_key_id": new_id,
                "previous_key_id": prev_id,
                "notes": "Quarterly rotation.",
            },
        )

    res = await cockpit_client.get(
        "/cockpit/compliance/key-rotations",
        headers=founder_operator.headers,
        params={"key_name": "receipt_signing_key"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    new_ids = [r["new_key_id"] for r in body["items"]]
    assert set(new_ids) == {"k-002", "k-003"}


# ---------------------------------------------------------------------------
# Anonymous (no auth header) -> 401 across every compliance endpoint.
# SOC 2 evidence: verification-gate negative-path coverage.
# ---------------------------------------------------------------------------


async def test_access_review_requires_auth(cockpit_client: AsyncClient) -> None:
    res = await cockpit_client.get(
        "/cockpit/compliance/access-review",
        params={"tenant_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "operator_unauthenticated"


async def test_audit_hash_digests_requires_auth(
    cockpit_client: AsyncClient,
) -> None:
    res = await cockpit_client.get(
        "/cockpit/compliance/audit-hash-digests",
        params={"tenant_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "operator_unauthenticated"


async def test_create_key_rotation_requires_auth(
    cockpit_client: AsyncClient,
) -> None:
    res = await cockpit_client.post(
        "/cockpit/compliance/key-rotations",
        json={
            "key_name": "receipt_signing_key",
            "new_key_id": "k-002",
            "previous_key_id": "k-001",
            "notes": "Anonymous request must be rejected before role check.",
        },
    )
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "operator_unauthenticated"


async def test_list_key_rotations_requires_auth(
    cockpit_client: AsyncClient,
) -> None:
    res = await cockpit_client.get(
        "/cockpit/compliance/key-rotations",
        params={"key_name": "receipt_signing_key"},
    )
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "operator_unauthenticated"
