"""Verifier API key management endpoints.

Two routers live in this file:

* ``router`` — tenant-scoped admin surface at ``/v1/admin/verifier-keys``
  for an owner/admin tenant user to issue, list and revoke keys.
* ``internal_router`` — internal lookup at
  ``/v1/internal/verifier-keys/by-prefix/{prefix}`` guarded by the
  ``X-Internal-Token`` header (matches ``settings.verifier_internal_token``)
  and consumed only by the public verifier microservice. Returns the
  ``key_hash`` (already SHA-256 digest, not a secret in isolation) and the
  monthly cap so the verifier can complete the auth + quota check
  out-of-process.
"""

from __future__ import annotations

import hmac
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantUser
from app.config import settings
from app.db import get_db
from app.models import AuditLog, TenantUser
from app.schemas.verifier_api_key import (
    VerifierApiKeyChargeRequest,
    VerifierApiKeyChargeResponse,
    VerifierApiKeyCreate,
    VerifierApiKeyCreated,
    VerifierApiKeyListResponse,
    VerifierApiKeyLookup,
    VerifierApiKeyRead,
)
from app.services import verifier_key_service
from app.utils.logging import get_logger

__all__ = ["router", "internal_router"]


_logger = get_logger(__name__)


router = APIRouter(prefix="/admin/verifier-keys", tags=["verifier-keys"])
internal_router = APIRouter(
    prefix="/internal/verifier-keys", tags=["verifier-internal"]
)


_ADMIN_ROLES: frozenset[str] = frozenset({"admin", "owner"})


def _require_admin(
    tenant_user: CurrentTenantUser,
) -> TenantUser:
    role = (getattr(tenant_user, "role", "") or "").lower()
    if role not in _ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "admin_required",
                "message": "Verifier key management is admin-only.",
            },
        )
    return tenant_user


def _client_ip(request: Request) -> str | None:
    if request.client is not None and request.client.host:
        return request.client.host
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return None


def _write_audit(
    session: AsyncSession,
    *,
    action: str,
    tenant_id: str,
    actor_user_id: str | None,
    resource_id: str | None,
    ip_address: str | None,
    metadata: dict[str, Any] | None,
) -> None:
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type="verifier_api_key",
            resource_id=resource_id,
            metadata_json=metadata,
            ip_address=ip_address,
        )
    )


@router.post(
    "",
    response_model=VerifierApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a new verifier API key (plaintext shown once)",
)
async def create_verifier_key(
    payload: VerifierApiKeyCreate,
    request: Request,
    tenant_user: Annotated[TenantUser, Depends(_require_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VerifierApiKeyCreated:
    # ``None`` from the schema means "inherit free-tier default". ``0``
    # explicitly means "no hard cap (paid metered tier)" and is preserved.
    if payload.monthly_call_cap is None:
        effective_cap: int | None = settings.verifier_free_tier_monthly_cap
    elif payload.monthly_call_cap == 0:
        effective_cap = None
    else:
        effective_cap = payload.monthly_call_cap

    issued = await verifier_key_service.issue_key(
        session,
        tenant_id=tenant_user.tenant_id,
        name=payload.name,
        monthly_call_cap=effective_cap,
    )
    _write_audit(
        session,
        action="verifier_api_key.created",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=issued.row.id,
        ip_address=_client_ip(request),
        metadata={
            "name": issued.row.name,
            "key_prefix": issued.row.key_prefix,
            "monthly_call_cap": effective_cap,
        },
    )
    return VerifierApiKeyCreated(
        **VerifierApiKeyRead.model_validate(issued.row).model_dump(),
        plaintext=issued.plaintext,
    )


@router.get(
    "",
    response_model=VerifierApiKeyListResponse,
    summary="List verifier API keys for the current tenant",
)
async def list_verifier_keys(
    tenant_user: Annotated[TenantUser, Depends(_require_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VerifierApiKeyListResponse:
    total, rows = await verifier_key_service.list_keys(
        session, tenant_id=tenant_user.tenant_id
    )
    return VerifierApiKeyListResponse(
        total=total,
        items=[VerifierApiKeyRead.model_validate(r) for r in rows],
    )


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a verifier API key (idempotent)",
)
async def revoke_verifier_key(
    key_id: str,
    request: Request,
    tenant_user: Annotated[TenantUser, Depends(_require_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    row = await verifier_key_service.revoke_key(
        session, tenant_id=tenant_user.tenant_id, key_id=key_id
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "verifier_api_key_not_found",
                "message": "No verifier API key with that id for this tenant.",
            },
        )
    _write_audit(
        session,
        action="verifier_api_key.revoked",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=row.id,
        ip_address=_client_ip(request),
        metadata={"key_prefix": row.key_prefix},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Internal lookup (consumed by the public verifier microservice)
# ---------------------------------------------------------------------------


def _require_internal_token(
    x_internal_token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
) -> None:
    expected = settings.verifier_internal_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "internal_token_not_configured",
                "message": "VERIFIER_INTERNAL_TOKEN is empty on this backend.",
            },
        )
    if not x_internal_token or not hmac.compare_digest(
        x_internal_token, expected
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_internal_token",
                "message": "X-Internal-Token missing or does not match.",
            },
        )


@internal_router.get(
    "/by-prefix/{prefix}",
    response_model=VerifierApiKeyLookup,
    summary="Look up a verifier key by public prefix (internal use only)",
    dependencies=[Depends(_require_internal_token)],
)
async def lookup_by_prefix(
    prefix: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VerifierApiKeyLookup:
    row = await verifier_key_service.find_active_by_prefix(
        session, prefix=prefix
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "verifier_api_key_not_found",
                "message": "No active verifier API key with that prefix.",
            },
        )
    return VerifierApiKeyLookup.model_validate(row)


@internal_router.post(
    "/charge",
    response_model=VerifierApiKeyChargeResponse,
    summary="Authenticate a plaintext key and atomically increment its monthly counter",
    dependencies=[Depends(_require_internal_token)],
    responses={
        401: {"description": "Plaintext key invalid or revoked."},
        402: {"description": "Authenticated but monthly cap exceeded."},
    },
)
async def charge_verifier_key(
    payload: VerifierApiKeyChargeRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VerifierApiKeyChargeResponse:
    result = await verifier_key_service.charge_usage(
        session, plaintext=payload.plaintext
    )
    if result.status == "invalid_key":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_api_key",
                "message": "Plaintext does not match any active verifier key.",
            },
        )
    if result.status == "quota_exceeded":
        # 402 Payment Required carries the same shape so callers can render
        # ``current_period_count`` / ``monthly_call_cap`` to end users.
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "quota_exceeded",
                "message": "Monthly verifier call cap exceeded.",
                "api_key_id": result.api_key_id,
                "monthly_call_cap": result.monthly_call_cap,
                "current_period_count": result.current_period_count,
                "period_month": result.period_month,
            },
        )
    assert result.api_key_id is not None  # noqa: S101 — service contract for status=="ok"
    assert result.tenant_id is not None  # noqa: S101 — service contract for status=="ok"
    return VerifierApiKeyChargeResponse(
        api_key_id=result.api_key_id,
        tenant_id=result.tenant_id,
        monthly_call_cap=result.monthly_call_cap,
        current_period_count=result.current_period_count,
        period_month=result.period_month,
    )

