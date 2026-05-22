"""Shared pytest fixtures for the Once backend test suite.

The fixtures here keep tests fully hermetic:

* a fresh in-memory SQLite database (``sqlite+aiosqlite:///:memory:`` with
  :class:`~sqlalchemy.pool.StaticPool`) is built per test and bound to
  :data:`app.db.engine` / :data:`app.db.AsyncSessionLocal` so every code path
  in the application picks it up transparently;
* the canonical :class:`~app.models.Portal` rows referenced by the rest of the
  suite (Applied Epic, AmTrust, Markel, Vertafore AMS360, Sircon) are seeded
  before any test runs;
* a freshly generated Ed25519 signing key is wired into the runtime so the
  receipt signer does not require a real PEM in the environment;
* :class:`httpx.AsyncClient` is mounted against the FastAPI app through
  :class:`httpx.ASGITransport`, including an ``auth_client`` variant that has
  already registered and authenticated a default user.

Pytest-asyncio runs in *auto* mode (see ``backend/pytest.ini``); every
``async def test_*`` is auto-marked. Do NOT set a module-level
``pytestmark = pytest.mark.asyncio`` — it incorrectly marks sync tests in
the same file and produces hundreds of warnings.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass

import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import app.db as app_db
from app.api.v1.router import api_router, public_receipt_router
from app.config import settings
from app.middleware.tenant_scope import TenantScopeMiddleware
from app.models import Base, Portal, PortalPlatform
from app.schemas.auth import TokenPair
from app.services import sanctions_service
from app.utils import crypto as crypto_utils

# ---------------------------------------------------------------------------
# Default seed data
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _PortalSeed:
    platform: PortalPlatform
    display_name: str
    base_url: str


_DEFAULT_PORTAL_SEEDS: tuple[_PortalSeed, ...] = (
    _PortalSeed(PortalPlatform.APPLIED_EPIC, "Applied Epic", "https://epic.example/"),
    _PortalSeed(PortalPlatform.AMTRUST, "AmTrust", "https://amtrust.example/"),
    _PortalSeed(PortalPlatform.MARKEL, "Markel", "https://markel.example/"),
    _PortalSeed(
        PortalPlatform.VERTAFORE_AMS360,
        "Vertafore AMS360",
        "https://ams360.example/",
    ),
    _PortalSeed(
        PortalPlatform.VERTAFORE_SIRCON,
        "Sircon",
        "https://sircon.example/",
    ),
)


# ---------------------------------------------------------------------------
# Database / engine fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def _test_engine() -> AsyncIterator[AsyncEngine]:
    """Build a fresh in-memory SQLite engine and patch ``app.db``."""

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
        class_=AsyncSession,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    prev_engine = app_db.engine
    prev_sessionmaker = app_db.AsyncSessionLocal
    app_db.engine = engine
    app_db.AsyncSessionLocal = sessionmaker

    async with sessionmaker() as session:
        for seed in _DEFAULT_PORTAL_SEEDS:
            session.add(
                Portal(
                    platform=seed.platform,
                    display_name=seed.display_name,
                    base_url=seed.base_url,
                    is_supported=True,
                    risky=False,
                )
            )
        await session.commit()

    try:
        yield engine
    finally:
        app_db.engine = prev_engine
        app_db.AsyncSessionLocal = prev_sessionmaker
        await engine.dispose()


@pytest_asyncio.fixture
async def async_session(_test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Yield a standalone :class:`AsyncSession` bound to the test engine."""

    async with app_db.AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()


# ---------------------------------------------------------------------------
# Cryptographic key fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def signing_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[Ed25519PrivateKey]:
    """Patch the receipt signer to use a freshly generated Ed25519 key."""

    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")

    monkeypatch.setattr(settings, "receipt_signing_private_key_pem", pem)
    monkeypatch.setattr(settings, "receipt_signing_key_id", "test-key")
    crypto_utils.reset_default_signing_key_cache()
    try:
        yield key
    finally:
        crypto_utils.reset_default_signing_key_cache()


# ---------------------------------------------------------------------------
# Sanctions cache fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_sanctions_cache() -> Iterator[None]:
    """Ensure the process-wide sanctions cache cannot leak across tests."""

    sanctions_service.reset_cache()
    try:
        yield
    finally:
        sanctions_service.reset_cache()


# ---------------------------------------------------------------------------
# App / client fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_app(_test_engine: AsyncEngine, signing_key: Ed25519PrivateKey) -> FastAPI:
    """Build a minimal FastAPI app exposing the v1 routes for tests.

    A bespoke app avoids the production middleware stack (rate limiting,
    CORS, lifespan-managed engine disposal) while still mounting the real
    routers and tenant-scope middleware so behavior under test mirrors prod.
    """

    app = FastAPI(title="once-test")
    app.add_middleware(TenantScopeMiddleware)
    app.include_router(api_router)
    app.include_router(public_receipt_router)
    return app


@pytest_asyncio.fixture
async def client(test_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Async HTTP client mounted on the FastAPI app over ASGI."""

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RegisteredUser:
    """Bundle returned by :func:`register_user` for easy assertion access."""

    email: str
    password: str
    full_name: str
    tenant_name: str
    tokens: TokenPair


async def register_user(
    client: AsyncClient,
    *,
    email: str = "owner@example.com",
    password: str = "S3cret-Pass!",
    full_name: str = "Owner Example",
    tenant_name: str = "Acme MGA",
) -> RegisteredUser:
    """Register a tenant + owner via the public auth endpoint."""

    response = await client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
            "tenant_name": tenant_name,
        },
    )
    assert response.status_code == 201, response.text
    tokens = TokenPair(**response.json())
    return RegisteredUser(
        email=email,
        password=password,
        full_name=full_name,
        tenant_name=tenant_name,
        tokens=tokens,
    )


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient) -> AsyncIterator[tuple[AsyncClient, RegisteredUser]]:
    """``client`` already authenticated as a freshly registered owner."""

    registered = await register_user(client)
    client.headers["Authorization"] = f"Bearer {registered.tokens.access_token}"
    try:
        yield client, registered
    finally:
        client.headers.pop("Authorization", None)


# Re-export the helper so tests can import it from ``tests.conftest`` if needed.
__all__ = [
    "RegisteredUser",
    "register_user",
]


# ---------------------------------------------------------------------------
# Cockpit fixtures (Phase 5 SOC 2 evidence surface)
#
# Imported here so they auto-discover for any test module without needing
# explicit `from tests.conftest_helpers import ...` re-imports (which trip
# pyflakes F811 against function parameters).
# ---------------------------------------------------------------------------
from tests.conftest_helpers import (  # noqa: E402, F401
    cockpit_app,
    cockpit_client,
    founder_operator,
    support_operator,
)
