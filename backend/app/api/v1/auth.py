from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantUser, CurrentUser, get_current_user
from app.db import get_db
from app.models import AuditLog, TenantUser, User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserMe,
)
from app.services import auth_service
from app.utils.account_lockout import get_default_tracker
from app.utils.logging import get_logger
from app.utils.rate_limit import limiter

__all__ = ["router"]


router = APIRouter(prefix="/auth", tags=["auth"])
_logger = get_logger(__name__)


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    if request.client is not None and request.client.host:
        return request.client.host
    return None


def _write_audit(
    session: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None,
    tenant_id: str | None,
    actor_user_id: str | None,
    ip_address: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_json=metadata,
            ip_address=ip_address,
        )
    )


@limiter.limit("20/minute")
@router.post(
    "/register",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user and tenant",
)
async def register(
    payload: RegisterRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    user, tenant, tenant_user = await auth_service.register_user_and_tenant(session, payload)
    tokens = auth_service.issue_token_pair(user, tenant_user)
    _write_audit(
        session,
        action="user.registered",
        resource_type="user",
        resource_id=user.id,
        tenant_id=tenant.id,
        actor_user_id=user.id,
        ip_address=_client_ip(request),
        metadata={"email": user.email, "tenant_slug": tenant.slug},
    )
    _logger.info("user_registered", user_id=user.id, tenant_id=tenant.id)
    return tokens


@limiter.limit("10/minute")
@router.post(
    "/login",
    response_model=TokenPair,
    summary="Authenticate and get tokens (sliding-window lockout)",
)
async def login(
    payload: LoginRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    ip = _client_ip(request) or "unknown"
    tracker = get_default_tracker()
    lockout = tracker.check(payload.email, ip)
    if lockout.locked:
        _logger.warning(
            "auth_login_locked",
            email=payload.email,
            ip=ip,
            retry_after=lockout.retry_after_seconds,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "account_locked",
                "message": "Too many failed login attempts; try again later.",
                "retry_after_seconds": lockout.retry_after_seconds,
            },
            headers={"Retry-After": str(lockout.retry_after_seconds)},
        )

    try:
        user, tenant_user = await auth_service.authenticate(session, payload.email, payload.password)
    except HTTPException as exc:
        # Only credential failures count toward lockout; "user_inactive"
        # and "no_tenant_membership" expose existence and must not.
        detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
        if detail.get("code") == "invalid_credentials":
            tracker.record_failure(payload.email, ip)
        raise

    tracker.record_success(payload.email, ip)
    tokens = auth_service.issue_token_pair(user, tenant_user)
    _write_audit(
        session,
        action="user.login",
        resource_type="user",
        resource_id=user.id,
        tenant_id=tenant_user.tenant_id,
        actor_user_id=user.id,
        ip_address=ip,
        metadata={"email": user.email},
    )
    _logger.info("user_login", user_id=user.id, tenant_id=tenant_user.tenant_id)
    return tokens


@limiter.limit("30/minute")
@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Exchange refresh token for new pair",
)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    tokens = await auth_service.refresh(session, payload.refresh_token)
    _write_audit(
        session,
        action="token.refresh",
        resource_type="token",
        resource_id=None,
        tenant_id=None,
        actor_user_id=None,
        ip_address=_client_ip(request),
        metadata=None,
    )
    _logger.info("token_refresh")
    return tokens


@limiter.limit("30/minute")
@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a refresh token",
)
async def logout(
    payload: RefreshRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await auth_service.revoke_refresh_token(session, payload.refresh_token)
    _write_audit(
        session,
        action="token.revoked",
        resource_type="token",
        resource_id=None,
        tenant_id=None,
        actor_user_id=None,
        ip_address=_client_ip(request),
        metadata=None,
    )
    _logger.info("token_revoked")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserMe, summary="Current authenticated user")
async def me(
    user: CurrentUser,
    tenant_user: CurrentTenantUser,
) -> UserMe:
    return UserMe(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        tenant_id=tenant_user.tenant_id,
        role=tenant_user.role,
    )


# Re-export for documentation/introspection of dependency wiring.
_ = (get_current_user, User, TenantUser)
