"""Cockpit "act-as" middleware.

Responsibilities:

1. For every request whose path starts with ``/cockpit/`` (the operator
   surface), record an entry in ``cockpit_audit`` after the response is
   produced. Failures to record are warn-logged, never fatal.

2. For any request carrying ``X-Operator-Acting-Tenant: <tenant_id>``:

   * decode the cockpit JWT (separate secret) from
     ``Authorization: Bearer ...`` *or* the ``once_cockpit_access`` cookie;
   * confirm the operator is active;
   * confirm the operator either has the ``founder`` role (implicit grant on
     all active tenants) or owns an ``operator_tenant_grants`` row for the
     target tenant;
   * confirm the target tenant exists and is active;
   * rewrite ``request.state.tenant_id`` so the downstream tenant-scoped
     resolver yields data for that tenant, and stamp
     ``request.state.operator_id`` + ``request.state.acting_as_tenant_id``
     so audit logging downstream can attribute the action.

Failures emit RFC 9457 ``application/problem+json`` 401/403 responses.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from typing import Final

from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

import app.db as app_db
from app.models import Operator, OperatorStatus, OperatorTenantGrant, Tenant
from app.services.cockpit_audit import write_audit_async
from app.services.operator_auth import (
    TOKEN_TYPE_ACCESS,
    OperatorAuthError,
    decode_token,
)
from app.utils.logging import get_logger

__all__ = [
    "OperatorActAsMiddleware",
    "ACT_AS_HEADER",
    "COCKPIT_COOKIE_NAME",
    "COCKPIT_PATH_PREFIX",
]


_logger = get_logger(__name__)

ACT_AS_HEADER: Final[str] = "x-operator-acting-tenant"
COCKPIT_COOKIE_NAME: Final[str] = "once_cockpit_access"
COCKPIT_PATH_PREFIX: Final[str] = "/cockpit/"

# Paths exempt from "must have cockpit auth" when X-Operator-Acting-Tenant is absent.
_COCKPIT_BYPASS_AUTH: tuple[str, ...] = (
    "/cockpit/auth/login",
    "/cockpit/auth/refresh",
    "/cockpit/auth/csrf",
    "/cockpit/health",
)


def _problem(status_code: int, code: str, message: str) -> JSONResponse:
    body = {
        "type": f"https://once.dev/problems/{code.replace('_', '-')}",
        "title": message,
        "status": status_code,
        "detail": {"code": code, "message": message},
    }
    return JSONResponse(
        status_code=status_code,
        content=body,
        media_type="application/problem+json",
    )


def _extract_cockpit_token(request: Request) -> str | None:
    auth = request.headers.get("authorization") or request.headers.get(
        "Authorization"
    )
    if auth:
        scheme, _, token = auth.partition(" ")
        if scheme.lower() == "bearer" and token:
            return token.strip()
    cookie = request.cookies.get(COCKPIT_COOKIE_NAME)
    if cookie:
        return cookie.strip()
    return None


def _client_ip(request: Request) -> str | None:
    if request.client is not None and request.client.host:
        return request.client.host
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip() or None
    return None


def _enabled() -> bool:
    raw = os.environ.get("ENABLE_COCKPIT_ACT_AS_MIDDLEWARE")
    if raw is None:
        return True
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class OperatorActAsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not _enabled():
            return await call_next(request)

        path = request.url.path
        is_cockpit_path = path.startswith(COCKPIT_PATH_PREFIX) or path == "/cockpit"
        act_as_tenant = request.headers.get(ACT_AS_HEADER) or request.headers.get(
            ACT_AS_HEADER.title()
        )

        operator_id_for_audit: str | None = None
        tenant_for_audit: str | None = None
        action: str = "cockpit.request" if is_cockpit_path else "cockpit.act_as"

        # ----- Resolve operator identity (required for act-as + most cockpit paths) -----
        if act_as_tenant or (
            is_cockpit_path and not any(path.startswith(p) for p in _COCKPIT_BYPASS_AUTH)
        ):
            token = _extract_cockpit_token(request)
            if not token:
                resp = _problem(
                    401,
                    "operator_unauthenticated",
                    "Cockpit endpoint requires operator authentication.",
                )
                await self._audit(
                    request,
                    response=resp,
                    operator_id=None,
                    tenant_acted_as=act_as_tenant,
                    action=action,
                )
                return resp

            try:
                payload = decode_token(token, expected_type=TOKEN_TYPE_ACCESS)
            except OperatorAuthError as exc:
                resp = _problem(exc.status_code, exc.code, exc.message)
                await self._audit(
                    request,
                    response=resp,
                    operator_id=None,
                    tenant_acted_as=act_as_tenant,
                    action=action,
                )
                return resp

            operator_id_for_audit = str(payload.get("sub") or "") or None
            request.state.operator_id = operator_id_for_audit
            request.state.operator_role = payload.get("role")

            if act_as_tenant:
                try:
                    await self._validate_act_as(
                        operator_id=operator_id_for_audit,
                        tenant_id=act_as_tenant,
                    )
                except OperatorAuthError as exc:
                    resp = _problem(exc.status_code, exc.code, exc.message)
                    await self._audit(
                        request,
                        response=resp,
                        operator_id=operator_id_for_audit,
                        tenant_acted_as=act_as_tenant,
                        action=action,
                    )
                    return resp
                # Rewrite tenant scope for downstream resolvers.
                request.state.tenant_id = act_as_tenant
                request.state.acting_as_tenant_id = act_as_tenant
                tenant_for_audit = act_as_tenant

        response = await call_next(request)

        if is_cockpit_path or act_as_tenant:
            await self._audit(
                request,
                response=response,
                operator_id=operator_id_for_audit,
                tenant_acted_as=tenant_for_audit or act_as_tenant,
                action=action,
            )

        return response

    async def _validate_act_as(self, *, operator_id: str | None, tenant_id: str) -> None:
        if not operator_id:
            raise OperatorAuthError(
                "operator_unauthenticated",
                "Cockpit token missing operator id.",
                status_code=401,
            )
        async with app_db.AsyncSessionLocal() as session:
            op_result = await session.execute(
                select(Operator).where(Operator.id == operator_id)
            )
            operator = op_result.scalar_one_or_none()
            if operator is None:
                raise OperatorAuthError(
                    "operator_unknown", "Operator no longer exists.", status_code=401
                )
            if operator.status != OperatorStatus.ACTIVE.value:
                raise OperatorAuthError(
                    "operator_suspended",
                    "Operator account is suspended.",
                    status_code=403,
                )

            tenant_result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = tenant_result.scalar_one_or_none()
            if tenant is None:
                raise OperatorAuthError(
                    "tenant_not_found",
                    "Target tenant does not exist.",
                    status_code=404,
                )
            if not tenant.is_active:
                raise OperatorAuthError(
                    "tenant_inactive",
                    "Target tenant is disabled.",
                    status_code=403,
                )

            if operator.role == "founder":
                return

            grant_result = await session.execute(
                select(OperatorTenantGrant).where(
                    OperatorTenantGrant.operator_id == operator.id,
                    OperatorTenantGrant.tenant_id == tenant_id,
                )
            )
            grant = grant_result.scalar_one_or_none()
            if grant is None:
                raise OperatorAuthError(
                    "act_as_forbidden",
                    "Operator has no grant for this tenant.",
                    status_code=403,
                )

    async def _audit(
        self,
        request: Request,
        *,
        response: Response,
        operator_id: str | None,
        tenant_acted_as: str | None,
        action: str,
    ) -> None:
        try:
            req_id = getattr(request.state, "request_id", None)
            await write_audit_async(
                operator_id=operator_id,
                tenant_id_acted_as=tenant_acted_as,
                action=action,
                resource_type="http_request",
                resource_id=None,
                request_id=req_id,
                method=request.method,
                path=request.url.path,
                status_code=getattr(response, "status_code", None),
                ip=_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                payload={
                    "query": str(request.url.query) or None,
                    "headers": {
                        k: v for k, v in request.headers.items() if k.lower() != "cookie"
                    },
                },
            )
        except Exception as exc:  # pragma: no cover - defensive
            _logger.warning("cockpit_audit_middleware_error", error=str(exc))
