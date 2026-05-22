"""Cockpit auth routes: login, refresh, logout, me, csrf."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cockpit import CurrentOperator
from app.db import get_db
from app.middleware.operator_act_as import COCKPIT_COOKIE_NAME
from app.models import OperatorRole, OperatorTenantGrant
from app.schemas.cockpit import CsrfTokenResponse
from app.schemas.operator import (
    OperatorLoginRequest,
    OperatorMe,
    OperatorRefreshRequest,
    OperatorTokenPair,
)
from app.services import operator_auth
from app.services.cockpit_audit import write_audit
from app.utils.account_lockout import get_default_tracker
from app.utils.logging import get_logger

__all__ = ["router"]

router = APIRouter(prefix="/auth", tags=["cockpit-auth"])
_logger = get_logger(__name__)
_security_logger = get_logger("security.cockpit_login")

CSRF_COOKIE_NAME = "once_cockpit_csrf"


def _client_ip(request: Request) -> str | None:
    if request.client is not None and request.client.host:
        return request.client.host
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip() or None
    return None


def _set_cockpit_cookies(response: Response, *, access: str, refresh: str) -> None:
    response.set_cookie(
        COCKPIT_COOKIE_NAME,
        access,
        max_age=operator_auth.ACCESS_TTL_MINUTES * 60,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        "once_cockpit_refresh",
        refresh,
        max_age=operator_auth.REFRESH_TTL_MINUTES * 60,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/cockpit/auth",
    )


@router.get(
    "/csrf",
    response_model=CsrfTokenResponse,
    summary="Issue a CSRF token for the cockpit session",
)
async def csrf_token(response: Response) -> CsrfTokenResponse:
    token = secrets.token_urlsafe(24)[:32]
    response.set_cookie(
        CSRF_COOKIE_NAME,
        token,
        max_age=60 * 60,
        httponly=False,
        secure=True,
        samesite="lax",
        path="/",
    )
    return CsrfTokenResponse(csrf_token=token)


@router.post(
    "/login",
    response_model=OperatorTokenPair,
    summary="Operator login (5/min/IP)",
)
async def login(
    payload: OperatorLoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OperatorTokenPair:
    ip = _client_ip(request) or "unknown"
    ua = request.headers.get("user-agent")
    tracker = get_default_tracker()
    status_check = tracker.check(payload.email, ip)
    if status_check.locked:
        _security_logger.warning(
            "cockpit_login_locked", email=payload.email, ip=ip,
            retry_after=status_check.retry_after_seconds,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "account_locked",
                "message": "Too many failed attempts; try again later.",
                "retry_after_seconds": status_check.retry_after_seconds,
            },
            headers={"Retry-After": str(status_check.retry_after_seconds)},
        )

    try:
        operator, access, refresh, expires_in = (
            await operator_auth.authenticate_operator(
                session,
                email=payload.email,
                password=payload.password,
                ip=ip,
                user_agent=ua,
                totp_code=payload.totp_code,
            )
        )
    except operator_auth.OperatorAuthError as exc:
        if exc.code in {"invalid_credentials", "invalid_mfa"}:
            tracker.record_failure(payload.email, ip)
        await write_audit(
            session,
            operator_id=None,
            tenant_id_acted_as=None,
            action="cockpit.login_failed",
            resource_type="operator",
            resource_id=None,
            request_id=getattr(request.state, "request_id", None),
            method=request.method,
            path=request.url.path,
            status_code=exc.status_code,
            ip=ip,
            user_agent=ua,
            payload={"email": payload.email, "code": exc.code},
        )
        _security_logger.info(
            "cockpit_login_denied", email=payload.email, ip=ip, code=exc.code
        )
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    tracker.record_success(payload.email, ip)
    _set_cockpit_cookies(response, access=access, refresh=refresh)
    await write_audit(
        session,
        operator_id=operator.id,
        tenant_id_acted_as=None,
        action="cockpit.login",
        resource_type="operator",
        resource_id=operator.id,
        request_id=getattr(request.state, "request_id", None),
        method=request.method,
        path=request.url.path,
        status_code=200,
        ip=ip,
        user_agent=ua,
        payload={"email": payload.email, "role": operator.role},
    )
    _security_logger.info(
        "cockpit_login_success",
        operator_id=operator.id,
        email=operator.email,
        ip=ip,
        role=operator.role,
    )
    return OperatorTokenPair(
        access_token=access, refresh_token=refresh, expires_in=expires_in
    )


@router.post(
    "/refresh",
    response_model=OperatorTokenPair,
    summary="Rotate cockpit access + refresh tokens",
)
async def refresh(
    payload: OperatorRefreshRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OperatorTokenPair:
    ip = _client_ip(request) or "unknown"
    ua = request.headers.get("user-agent")
    try:
        operator, access, new_refresh, expires_in = (
            await operator_auth.refresh_operator_session(
                session, refresh_token=payload.refresh_token, ip=ip, user_agent=ua,
            )
        )
    except operator_auth.OperatorAuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    _set_cockpit_cookies(response, access=access, refresh=new_refresh)
    await write_audit(
        session,
        operator_id=operator.id,
        tenant_id_acted_as=None,
        action="cockpit.refresh",
        resource_type="operator_session",
        resource_id=operator.id,
        request_id=getattr(request.state, "request_id", None),
        method=request.method,
        path=request.url.path,
        status_code=200,
        ip=ip,
        user_agent=ua,
    )
    return OperatorTokenPair(
        access_token=access, refresh_token=new_refresh, expires_in=expires_in
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current refresh token",
)
async def logout(
    payload: OperatorRefreshRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    operator: CurrentOperator,
) -> Response:
    await operator_auth.revoke_session(session, refresh_token=payload.refresh_token)
    await write_audit(
        session,
        operator_id=operator.id,
        tenant_id_acted_as=None,
        action="cockpit.logout",
        resource_type="operator_session",
        resource_id=operator.id,
        request_id=getattr(request.state, "request_id", None),
        method=request.method,
        path=request.url.path,
        status_code=204,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    response.delete_cookie(COCKPIT_COOKIE_NAME, path="/")
    response.delete_cookie("once_cockpit_refresh", path="/cockpit/auth")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=OperatorMe,
    summary="Current operator profile (and accessible tenants)",
)
async def me(
    operator: CurrentOperator,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OperatorMe:
    is_founder = operator.role == OperatorRole.FOUNDER.value
    accessible: list[str] = []
    if not is_founder:
        grants = await session.execute(
            select(OperatorTenantGrant.tenant_id).where(
                OperatorTenantGrant.operator_id == operator.id
            )
        )
        accessible = [str(t) for t in grants.scalars().all()]
    return OperatorMe(
        id=operator.id,
        email=operator.email,
        role=operator.role,  # type: ignore[arg-type]
        status=operator.status,  # type: ignore[arg-type]
        mfa_required=operator.mfa_required,
        last_login_at=operator.last_login_at,
        created_at=operator.created_at,
        accessible_tenant_ids=accessible,
        all_tenants=is_founder,
    )
