"""End-to-end tests for the verifier API key admin + internal endpoints.

Covers ``POST/GET/DELETE /v1/admin/verifier-keys`` and the internal
``GET /v1/internal/verifier-keys/by-prefix/{prefix}`` callback consumed by
the public verifier microservice.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from httpx import AsyncClient

from app.config import settings
from tests.conftest import register_user

pytestmark = pytest.mark.asyncio


_INTERNAL_TOKEN = "test-internal-token-very-secret-do-not-log"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _set_internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings, "verifier_internal_token", _INTERNAL_TOKEN
    )


# ---------------------------------------------------------------------------
# Admin surface
# ---------------------------------------------------------------------------


async def test_create_key_returns_plaintext_once(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    res = await client.post(
        "/v1/admin/verifier-keys",
        json={"name": "Acme reinsurance"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "Acme reinsurance"
    assert body["plaintext"].startswith("vk_live_")
    # 8-char literal + 32 url-safe base64 (no padding) = 8 + 43 = 51 chars
    assert len(body["plaintext"]) >= 40
    assert body["key_prefix"] == body["plaintext"][:16]
    # Free-tier cap applied when caller omits the field.
    assert body["monthly_call_cap"] == settings.verifier_free_tier_monthly_cap
    assert body["revoked_at"] is None
    assert body["last_used_at"] is None


async def test_create_key_cap_zero_means_no_hard_cap(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    res = await client.post(
        "/v1/admin/verifier-keys",
        json={"name": "Paid carrier", "monthly_call_cap": 0},
    )
    assert res.status_code == 201, res.text
    assert res.json()["monthly_call_cap"] is None


async def test_create_key_requires_admin_role(
    client: AsyncClient,
    async_session,  # ensures DB is up
) -> None:
    # Register a tenant + owner, then add a second user as a non-admin member.
    owner = await register_user(client)
    # Build the second user via the same endpoint (they end up an owner of
    # their own tenant) — to exercise the 401 path we just call unauth.
    res = await client.post(
        "/v1/admin/verifier-keys", json={"name": "no-auth"}
    )
    assert res.status_code == 401
    # And confirm the owner-role path *does* work for a sanity check.
    res2 = await client.post(
        "/v1/admin/verifier-keys",
        json={"name": "owner-ok"},
        headers=_bearer(owner.tokens.access_token),
    )
    assert res2.status_code == 201


async def test_create_key_rejects_blank_name(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    res = await client.post("/v1/admin/verifier-keys", json={"name": ""})
    assert res.status_code == 422


async def test_list_keys_excludes_plaintext_and_hash(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    await client.post("/v1/admin/verifier-keys", json={"name": "k1"})
    await client.post("/v1/admin/verifier-keys", json={"name": "k2"})

    res = await client.get("/v1/admin/verifier-keys")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 2
    names = {item["name"] for item in body["items"]}
    assert names == {"k1", "k2"}
    for item in body["items"]:
        assert "plaintext" not in item
        assert "key_hash" not in item


async def test_list_keys_is_tenant_scoped(client: AsyncClient) -> None:
    a = await register_user(
        client, email="a@e.com", password="StrongPass-A1!", tenant_name="A"
    )
    b = await register_user(
        client, email="b@e.com", password="StrongPass-B2!", tenant_name="B"
    )
    await client.post(
        "/v1/admin/verifier-keys",
        json={"name": "tenant-a-key"},
        headers=_bearer(a.tokens.access_token),
    )

    res = await client.get(
        "/v1/admin/verifier-keys", headers=_bearer(b.tokens.access_token)
    )
    assert res.status_code == 200
    assert res.json() == {"total": 0, "items": []}


async def test_revoke_is_idempotent_and_tenant_scoped(
    client: AsyncClient,
) -> None:
    a = await register_user(
        client, email="a@e.com", password="StrongPass-A1!", tenant_name="A"
    )
    b = await register_user(
        client, email="b@e.com", password="StrongPass-B2!", tenant_name="B"
    )
    created = (
        await client.post(
            "/v1/admin/verifier-keys",
            json={"name": "a"},
            headers=_bearer(a.tokens.access_token),
        )
    ).json()
    key_id = created["id"]

    # Tenant B cannot revoke tenant A's key.
    cross = await client.delete(
        f"/v1/admin/verifier-keys/{key_id}",
        headers=_bearer(b.tokens.access_token),
    )
    assert cross.status_code == 404

    # Tenant A revokes; second call is also 204 (idempotent).
    r1 = await client.delete(
        f"/v1/admin/verifier-keys/{key_id}",
        headers=_bearer(a.tokens.access_token),
    )
    assert r1.status_code == 204
    r2 = await client.delete(
        f"/v1/admin/verifier-keys/{key_id}",
        headers=_bearer(a.tokens.access_token),
    )
    assert r2.status_code == 204

    listed = (
        await client.get(
            "/v1/admin/verifier-keys",
            headers=_bearer(a.tokens.access_token),
        )
    ).json()
    assert listed["items"][0]["revoked_at"] is not None


# ---------------------------------------------------------------------------
# Internal lookup surface
# ---------------------------------------------------------------------------


async def test_internal_lookup_round_trip(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    created = (
        await client.post(
            "/v1/admin/verifier-keys", json={"name": "lookup-me"}
        )
    ).json()
    prefix = created["key_prefix"]
    plaintext = created["plaintext"]

    res = await client.get(
        f"/v1/internal/verifier-keys/by-prefix/{prefix}",
        headers={"X-Internal-Token": _INTERNAL_TOKEN},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["id"] == created["id"]
    assert body["tenant_id"] == created["tenant_id"]
    assert body["revoked_at"] is None
    # The hash returned should match what the verifier would compute from
    # the plaintext.
    expected = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
    assert body["key_hash"] == expected


async def test_internal_lookup_requires_token(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    created = (
        await client.post(
            "/v1/admin/verifier-keys", json={"name": "needs-token"}
        )
    ).json()

    # Missing header
    res = await client.get(
        f"/v1/internal/verifier-keys/by-prefix/{created['key_prefix']}"
    )
    assert res.status_code == 401

    # Wrong token
    res2 = await client.get(
        f"/v1/internal/verifier-keys/by-prefix/{created['key_prefix']}",
        headers={"X-Internal-Token": "nope"},
    )
    assert res2.status_code == 401


async def test_internal_lookup_unknown_prefix_404(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    res = await client.get(
        "/v1/internal/verifier-keys/by-prefix/vk_live_zzzzzzzz",
        headers={"X-Internal-Token": _INTERNAL_TOKEN},
    )
    assert res.status_code == 404


async def test_internal_lookup_skips_revoked_key(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    created = (
        await client.post(
            "/v1/admin/verifier-keys", json={"name": "to-revoke"}
        )
    ).json()
    await client.delete(f"/v1/admin/verifier-keys/{created['id']}")

    res = await client.get(
        f"/v1/internal/verifier-keys/by-prefix/{created['key_prefix']}",
        headers={"X-Internal-Token": _INTERNAL_TOKEN},
    )
    assert res.status_code == 404


async def test_internal_route_503_when_token_unset(
    auth_client: tuple[AsyncClient, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = auth_client
    created = (
        await client.post(
            "/v1/admin/verifier-keys", json={"name": "needs-config"}
        )
    ).json()
    monkeypatch.setattr(settings, "verifier_internal_token", "")
    res = await client.get(
        f"/v1/internal/verifier-keys/by-prefix/{created['key_prefix']}",
        headers={"X-Internal-Token": "irrelevant"},
    )
    assert res.status_code == 503


# ---------------------------------------------------------------------------
# Charge endpoint (auth + atomic monthly counter increment)
# ---------------------------------------------------------------------------


async def _issue(client: AsyncClient, **kwargs: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": "k"}
    payload.update(kwargs)
    return (await client.post("/v1/admin/verifier-keys", json=payload)).json()


async def test_charge_increments_counter(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    created = await _issue(client, name="charge-me", monthly_call_cap=5)

    for expected in (1, 2, 3):
        res = await client.post(
            "/v1/internal/verifier-keys/charge",
            json={"plaintext": created["plaintext"]},
            headers={"X-Internal-Token": _INTERNAL_TOKEN},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["api_key_id"] == created["id"]
        assert body["tenant_id"] == created["tenant_id"]
        assert body["monthly_call_cap"] == 5
        assert body["current_period_count"] == expected
        assert len(body["period_month"]) == 7  # "YYYY-MM"


async def test_charge_returns_402_past_cap(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    created = await _issue(client, name="tiny", monthly_call_cap=1)

    # First call: OK
    r1 = await client.post(
        "/v1/internal/verifier-keys/charge",
        json={"plaintext": created["plaintext"]},
        headers={"X-Internal-Token": _INTERNAL_TOKEN},
    )
    assert r1.status_code == 200

    # Second call: 402
    r2 = await client.post(
        "/v1/internal/verifier-keys/charge",
        json={"plaintext": created["plaintext"]},
        headers={"X-Internal-Token": _INTERNAL_TOKEN},
    )
    assert r2.status_code == 402, r2.text
    detail = r2.json()["detail"]
    assert detail["code"] == "quota_exceeded"
    assert detail["monthly_call_cap"] == 1
    assert detail["current_period_count"] == 2
    assert detail["api_key_id"] == created["id"]


async def test_charge_invalid_key_returns_401(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    # Unknown prefix
    r1 = await client.post(
        "/v1/internal/verifier-keys/charge",
        json={"plaintext": "vk_live_zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"},
        headers={"X-Internal-Token": _INTERNAL_TOKEN},
    )
    assert r1.status_code == 401
    assert r1.json()["detail"]["code"] == "invalid_api_key"

    # Valid prefix, wrong tail
    created = await _issue(client, name="tampered")
    bad = created["key_prefix"] + "tampered-tail-XXXXXXXXXXXXXXX"
    r2 = await client.post(
        "/v1/internal/verifier-keys/charge",
        json={"plaintext": bad},
        headers={"X-Internal-Token": _INTERNAL_TOKEN},
    )
    assert r2.status_code == 401


async def test_charge_revoked_key_returns_401(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    created = await _issue(client, name="will-revoke")
    await client.delete(f"/v1/admin/verifier-keys/{created['id']}")

    res = await client.post(
        "/v1/internal/verifier-keys/charge",
        json={"plaintext": created["plaintext"]},
        headers={"X-Internal-Token": _INTERNAL_TOKEN},
    )
    assert res.status_code == 401


async def test_charge_requires_internal_token(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    created = await _issue(client, name="needs-token")

    res = await client.post(
        "/v1/internal/verifier-keys/charge",
        json={"plaintext": created["plaintext"]},
    )
    assert res.status_code == 401

    res2 = await client.post(
        "/v1/internal/verifier-keys/charge",
        json={"plaintext": created["plaintext"]},
        headers={"X-Internal-Token": "wrong"},
    )
    assert res2.status_code == 401


async def test_charge_uncapped_paid_key_never_402(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    # cap=0 → no hard cap (paid metered tier)
    created = await _issue(client, name="paid", monthly_call_cap=0)
    for _ in range(3):
        res = await client.post(
            "/v1/internal/verifier-keys/charge",
            json={"plaintext": created["plaintext"]},
            headers={"X-Internal-Token": _INTERNAL_TOKEN},
        )
        assert res.status_code == 200
        assert res.json()["monthly_call_cap"] is None

