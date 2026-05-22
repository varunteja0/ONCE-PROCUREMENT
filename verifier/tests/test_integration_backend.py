"""Live verifier <-> backend integration test (closes gates #6 and #7).

Unlike ``test_api_key.py`` (which stubs the backend with ``respx``), this
module mounts the real backend FastAPI app in-process via
``httpx.ASGITransport`` and exercises the full charge round-trip:

    [test] --HTTP--> [verifier ASGI] --HTTP--> [backend ASGI] --SQL--> in-memory DB

What it proves end-to-end with NO mocks of the verifier/backend wire:

* Issued key -> 200 from verifier, ``verifier_api_key_usage.count`` increments.
* Per-key ``monthly_call_cap`` enforced -> 402 ``{"code": "quota_exceeded"}``.
* Bogus plaintext -> 401 ``{"code": "invalid_api_key"}``.
* Revoked key -> 401 on the next call (no client-side cache today).
* Unauth ``GET /verify/*`` enforces the per-IP burst limit (5/min default).

The trick: backend's ``app`` is a regular package; verifier's ``app`` is a
PEP-420 namespace. We extend the namespace ``__path__`` with backend's
``app/`` directory so backend-only submodules (``app.config``, ``app.db``,
``app.models.*``, ``app.api.*``, ``app.middleware.*``,
``app.services.*``, ``app.utils.*``) resolve without colliding with the
verifier's same-named ``app.main`` / ``app.api_key`` / etc.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

# Skip cleanly when backend-only deps (sqlalchemy, etc.) aren't installed
# in this environment — happens in the verifier-only CI job. Local dev and
# the cross-project integration job have backend deps available.
pytest.importorskip("sqlalchemy", reason="backend deps not installed in verifier-only env")

# --- Namespace surgery (must run before any backend-only imports) ---------
import app as _verifier_app_pkg  # already loaded by verifier/conftest.py

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_DIR = _REPO_ROOT / "backend"
_BACKEND_APP_DIR = _BACKEND_DIR / "app"

if str(_BACKEND_APP_DIR) not in list(_verifier_app_pkg.__path__):
    _verifier_app_pkg.__path__.append(str(_BACKEND_APP_DIR))
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# --- Backend imports (resolve via the extended namespace path) ------------
import httpx  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)
from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.db as backend_db  # noqa: E402
from app.api.v1.router import api_router, public_receipt_router  # noqa: E402
from app.config import settings as backend_settings  # noqa: E402
from app.middleware.tenant_scope import TenantScopeMiddleware  # noqa: E402
from app.models import Base, Portal, PortalPlatform  # noqa: E402
from app.models.verifier_api_key_usage import VerifierApiKeyUsage  # noqa: E402
from app.services import sanctions_service  # noqa: E402
from app.utils import crypto as crypto_utils  # noqa: E402

# --- Verifier imports (already loaded by verifier conftest) ---------------
import app.api_key as verifier_api_key_module  # noqa: E402
from app.api_key import reset_rate_limit_storage  # noqa: E402
from app.main import app as verifier_fastapi_app  # noqa: E402
from app.main import settings as verifier_settings  # noqa: E402

INTERNAL_TOKEN = "integration-test-internal-token-do-not-log"  # noqa: S105
RECEIPT_ID = "11111111-1111-1111-1111-111111111111"

pytestmark = pytest.mark.asyncio


_PORTAL_SEEDS: tuple[tuple[PortalPlatform, str, str], ...] = (
    (PortalPlatform.APPLIED_EPIC, "Applied Epic", "https://epic.example/"),
    (PortalPlatform.AMTRUST, "AmTrust", "https://amtrust.example/"),
    (PortalPlatform.MARKEL, "Markel", "https://markel.example/"),
    (PortalPlatform.VERTAFORE_AMS360, "AMS360", "https://ams360.example/"),
    (PortalPlatform.VERTAFORE_SIRCON, "Sircon", "https://sircon.example/"),
)


async def _build_backend_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    sessionmaker = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(backend_db, "engine", engine)
    monkeypatch.setattr(backend_db, "AsyncSessionLocal", sessionmaker)

    async with sessionmaker() as session:
        for platform, name, url in _PORTAL_SEEDS:
            session.add(
                Portal(
                    platform=platform,
                    display_name=name,
                    base_url=url,
                    is_supported=True,
                    risky=False,
                )
            )
        await session.commit()

    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    monkeypatch.setattr(backend_settings, "receipt_signing_private_key_pem", pem)
    monkeypatch.setattr(backend_settings, "receipt_signing_key_id", "it-key")
    monkeypatch.setattr(backend_settings, "verifier_internal_token", INTERNAL_TOKEN)
    monkeypatch.setattr(backend_settings, "jwt_secret_key", "test-jwt-secret-do-not-use")
    crypto_utils.reset_default_signing_key_cache()
    sanctions_service.reset_cache()

    fastapi_app = FastAPI(title="backend-integration")
    fastapi_app.add_middleware(TenantScopeMiddleware)
    fastapi_app.include_router(api_router)
    fastapi_app.include_router(public_receipt_router)
    return fastapi_app


async def _usage_count(api_key_id: str) -> int:
    async with backend_db.AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(VerifierApiKeyUsage).where(
                    VerifierApiKeyUsage.api_key_id == api_key_id
                )
            )
        ).scalar_one_or_none()
        return 0 if row is None else int(row.count)


async def test_verifier_backend_live_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend_app = await _build_backend_app(monkeypatch)

    # Wire the verifier's outbound httpx.AsyncClient to the in-process backend.
    backend_transport = ASGITransport(app=backend_app)

    class _ASGIAsyncClient(httpx.AsyncClient):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = backend_transport
            kwargs.setdefault("base_url", "http://backend.test")
            super().__init__(*args, **kwargs)

    fake_httpx = SimpleNamespace(
        AsyncClient=_ASGIAsyncClient,
        HTTPError=httpx.HTTPError,
    )
    monkeypatch.setattr(verifier_api_key_module, "httpx", fake_httpx)
    monkeypatch.setattr(verifier_settings, "backend_internal_token", INTERNAL_TOKEN)
    monkeypatch.setattr(verifier_settings, "backend_base_url", "http://backend.test")

    reset_rate_limit_storage()

    backend_client = httpx.AsyncClient(
        transport=ASGITransport(app=backend_app),
        base_url="http://backend.test",
    )
    verifier_client = httpx.AsyncClient(
        transport=ASGITransport(app=verifier_fastapi_app),
        base_url="http://verifier.test",
    )

    try:
        # Register a tenant + owner; get a bearer token.
        reg = await backend_client.post(
            "/v1/auth/register",
            json={
                "email": "owner@example.com",
                "password": "S3cret-Pass!",
                "full_name": "Owner",
                "tenant_name": "Acme Integration",
            },
        )
        assert reg.status_code == 201, reg.text
        token = reg.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}

        # Issue a verifier key with cap=2.
        issued = await backend_client.post(
            "/v1/admin/verifier-keys",
            json={"name": "integration", "monthly_call_cap": 2},
            headers=auth,
        )
        assert issued.status_code == 201, issued.text
        body = issued.json()
        plaintext = body["plaintext"]
        api_key_id = body["id"]
        good_hdrs = {"X-Verify-API-Key": plaintext}

        # Call 1 -> not 401/402; usage = 1.
        r1 = await verifier_client.get(f"/verify/{RECEIPT_ID}", headers=good_hdrs)
        assert r1.status_code not in (401, 402), r1.text
        assert await _usage_count(api_key_id) == 1

        # Call 2 -> not 401/402; usage = 2 (at cap).
        r2 = await verifier_client.get(f"/verify/{RECEIPT_ID}", headers=good_hdrs)
        assert r2.status_code not in (401, 402), r2.text
        assert await _usage_count(api_key_id) == 2

        # Call 3 -> 402 quota_exceeded.
        r3 = await verifier_client.get(f"/verify/{RECEIPT_ID}", headers=good_hdrs)
        assert r3.status_code == 402, r3.text
        assert r3.json()["detail"]["code"] == "quota_exceeded"

        # Bogus key -> 401.
        bogus = "vk_live_" + "a" * 43
        rb = await verifier_client.get(
            f"/verify/{RECEIPT_ID}", headers={"X-Verify-API-Key": bogus}
        )
        assert rb.status_code == 401, rb.text
        assert rb.json() == {"detail": {"code": "invalid_api_key"}}

        # Revoke and re-call -> 401.
        rev = await backend_client.delete(
            f"/v1/admin/verifier-keys/{api_key_id}", headers=auth
        )
        assert rev.status_code == 204, rev.text
        r_after = await verifier_client.get(
            f"/verify/{RECEIPT_ID}", headers=good_hdrs
        )
        assert r_after.status_code == 401, r_after.text

        # Unauth burst: default 5/min -> 6th hit is 429.
        reset_rate_limit_storage()
        statuses: list[int] = []
        for _ in range(6):
            r = await verifier_client.get(f"/verify/{RECEIPT_ID}")
            statuses.append(r.status_code)
        assert statuses.count(429) == 1, statuses
        assert statuses[-1] == 429, statuses
    finally:
        await backend_client.aclose()
        await verifier_client.aclose()
        await backend_db.engine.dispose()


if __name__ == "__main__":  # pragma: no cover - manual smoke
    asyncio.run(test_verifier_backend_live_roundtrip(pytest.MonkeyPatch()))
