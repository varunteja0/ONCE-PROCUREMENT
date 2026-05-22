"""Additional pytest fixtures that don't belong in the root ``conftest.py``.

These fixtures are imported by individual test modules via plain ``from
tests.conftest_helpers import ...``. They intentionally do NOT register
themselves as autouse so the root conftest stays the single source of truth
for default app/client/session wiring.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import api_router, public_receipt_router
from app.middleware.tenant_scope import TenantScopeMiddleware
from app.observability import register_exception_handlers

__all__ = [
    "TwoTenants",
    "two_tenants",
    "app_with_handlers",
    "client_with_handlers",
]


@dataclass(slots=True)
class TwoTenants:
    """Convenience bundle of two registered tenants with bearer headers."""

    a_token: str
    b_token: str
    a_email: str
    b_email: str

    @property
    def a_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.a_token}"}

    @property
    def b_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.b_token}"}


@pytest_asyncio.fixture
async def two_tenants(client: AsyncClient) -> TwoTenants:
    """Register two independent tenants and yield their bearer tokens."""

    from tests.factories import register_and_token

    a = await register_and_token(
        client,
        email="tenant-a-owner@example.com",
        tenant_name="Tenant A",
    )
    b = await register_and_token(
        client,
        email="tenant-b-owner@example.com",
        tenant_name="Tenant B",
    )
    return TwoTenants(
        a_token=a["access_token"],
        b_token=b["access_token"],
        a_email=a["email"],
        b_email=b["email"],
    )


@pytest_asyncio.fixture
async def app_with_handlers(_test_engine, signing_key) -> FastAPI:  # type: ignore[no-untyped-def]
    """FastAPI app that also wires the structured exception handlers.

    The root ``test_app`` deliberately omits the production middleware stack to
    keep the surface minimal; tests of the observability layer need the
    handlers, so we build a dedicated app here.
    """

    app = FastAPI(title="once-test-handlers")
    app.add_middleware(TenantScopeMiddleware)
    register_exception_handlers(app)
    app.include_router(api_router)
    app.include_router(public_receipt_router)
    return app


@pytest_asyncio.fixture
async def client_with_handlers(
    app_with_handlers: FastAPI,
) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app_with_handlers)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Cockpit fixtures (operator surface) - used by Phase 5 SOC 2 evidence tests.
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class FounderHandle:
    """Bundle of a registered FOUNDER operator + a valid cockpit access JWT."""

    operator_id: str
    email: str
    access_token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}


@pytest_asyncio.fixture
async def cockpit_app(_test_engine, signing_key) -> FastAPI:  # type: ignore[no-untyped-def]
    """FastAPI app that mounts BOTH the v1 router and the cockpit router.

    The default ``test_app`` only exposes ``/v1/*`` + the public receipt
    verifier. Cockpit tests need ``/cockpit/*`` too - keep the dedicated
    fixture here so root conftest stays minimal.
    """

    from app.api.cockpit.router import cockpit_router

    app = FastAPI(title="once-test-cockpit")
    app.add_middleware(TenantScopeMiddleware)
    app.include_router(api_router)
    app.include_router(public_receipt_router)
    app.include_router(cockpit_router)
    return app


@pytest_asyncio.fixture
async def cockpit_client(cockpit_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=cockpit_app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def founder_operator(cockpit_app: FastAPI) -> FounderHandle:
    """Insert a FOUNDER operator into the DB and mint a cockpit access JWT."""

    import app.db as app_db
    from app.models import Operator, OperatorRole, OperatorStatus
    from app.services.operator_auth import (
        create_access_token,
        operator_password_hash,
    )

    async with app_db.AsyncSessionLocal() as session:
        op = Operator(
            email="founder@once.test",
            hashed_password=operator_password_hash("S3cret-Founder-Pass!"),
            role=OperatorRole.FOUNDER.value,
            status=OperatorStatus.ACTIVE.value,
        )
        session.add(op)
        await session.commit()
        await session.refresh(op)

    token, _exp = create_access_token(op)
    return FounderHandle(operator_id=op.id, email=op.email, access_token=token)


@pytest_asyncio.fixture
async def support_operator(cockpit_app: FastAPI) -> FounderHandle:
    """Non-founder (SUPPORT) operator - used for 403 founder-required tests."""

    import app.db as app_db
    from app.models import Operator, OperatorRole, OperatorStatus
    from app.services.operator_auth import (
        create_access_token,
        operator_password_hash,
    )

    async with app_db.AsyncSessionLocal() as session:
        op = Operator(
            email="support@once.test",
            hashed_password=operator_password_hash("S3cret-Support-Pass!"),
            role=OperatorRole.SUPPORT.value,
            status=OperatorStatus.ACTIVE.value,
        )
        session.add(op)
        await session.commit()
        await session.refresh(op)

    token, _exp = create_access_token(op)
    return FounderHandle(operator_id=op.id, email=op.email, access_token=token)
