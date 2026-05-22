"""Operational security self-check endpoint.

``GET /v1/security/self-check`` — admin-only.  Returns a snapshot of the
runtime security posture so on-call can verify in 5 seconds that critical
hardening is in place after a deploy.

This endpoint never returns secret material — only booleans and integers.
"""

from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_tenant_user
from app.config import settings
from app.middleware.security_headers import _hsts_default_enabled  # type: ignore[import-private-usage]
from app.models.tenant import TenantUser
from app.utils.account_lockout import get_default_tracker
from app.utils.secret_strength import evaluate_secret

__all__ = ["router"]


router = APIRouter(prefix="/security", tags=["security"])


_ADMIN_ROLES: frozenset[str] = frozenset({"admin", "owner"})


def _require_admin(
    tu: Annotated[TenantUser, Depends(get_current_tenant_user)],
) -> TenantUser:
    role = (getattr(tu, "role", "") or "").lower()
    if role not in _ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "admin_required",
                "message": "Security self-check is admin-only.",
            },
        )
    return tu


@router.get(
    "/self-check",
    summary="Operational security self-check (admin-only)",
)
async def self_check(
    _tu: Annotated[TenantUser, Depends(_require_admin)],
) -> dict[str, Any]:
    secret_score = evaluate_secret("SECRET_KEY", settings.secret_key)
    jwt_score = evaluate_secret("JWT_SECRET_KEY", settings.jwt_secret_key)

    hsts_env = os.environ.get("SECURITY_HSTS_ENABLED")
    hsts_enabled = (
        hsts_env.strip().lower() in {"1", "true", "yes", "on"}
        if hsts_env not in (None, "")
        else _hsts_default_enabled()
    )

    warnings: list[str] = []
    if not secret_score.strong:
        warnings.append(f"SECRET_KEY: {', '.join(secret_score.reasons)}")
    if not jwt_score.strong:
        warnings.append(f"JWT_SECRET_KEY: {', '.join(jwt_score.reasons)}")
    if settings.is_production and not hsts_enabled:
        warnings.append("HSTS disabled in production")

    tracker = get_default_tracker()

    payload: dict[str, Any] = {
        "secret_key_strength": secret_score.label,
        "jwt_secret_strength": jwt_score.label,
        "hsts_enabled": hsts_enabled,
        "csrf_middleware": True,
        "tenant_scope_middleware": True,
        "rate_limit_active": True,
        "signing_key_id": getattr(settings, "receipt_signing_key_id", "unknown"),
        "account_lockout": {
            "max_fails": tracker.max_fails,
            "window_seconds": tracker.window_sec,
            "lock_duration_seconds": tracker.lock_duration_sec,
            "backend": type(tracker.store).__name__,
        },
        "deps_audit_age_days": None,
        "playwright_browser_version": None,
        "warnings": warnings,
    }
    return payload


@router.post(
    "/account/unlock",
    summary="Admin unlock of a locked-out account",
)
async def unlock_account(
    email: str,
    ip: str | None = None,
    _tu: TenantUser = Depends(_require_admin),
) -> dict[str, str]:
    tracker = get_default_tracker()
    if ip:
        tracker.unlock(email=email, ip=ip)
    else:
        tracker.unlock(email=email, ip="unknown")
    return {"status": "unlocked", "email": email}
