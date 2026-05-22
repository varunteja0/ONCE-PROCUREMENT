"""Top-level cockpit router. Mounted at ``/cockpit`` from ``app.main``."""

from __future__ import annotations

from fastapi import APIRouter

from .audit import router as audit_router
from .auth import router as auth_router
from .compliance import router as compliance_router
from .mfa import router as mfa_router
from .tenants import router as tenants_router

cockpit_router = APIRouter(prefix="/cockpit")
cockpit_router.include_router(auth_router)
cockpit_router.include_router(mfa_router)
cockpit_router.include_router(tenants_router)
cockpit_router.include_router(audit_router)
cockpit_router.include_router(compliance_router)


@cockpit_router.get("/health", tags=["cockpit-meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "surface": "cockpit"}


__all__ = ["cockpit_router"]
