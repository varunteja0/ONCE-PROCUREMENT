"""Cockpit dependencies + auth-resolving helpers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.middleware.operator_act_as import COCKPIT_COOKIE_NAME
from app.models import Operator, OperatorRole, OperatorStatus
from app.services.operator_auth import (
    TOKEN_TYPE_ACCESS,
    OperatorAuthError,
    decode_token,
)

__all__ = [
    "get_current_operator",
    "CurrentOperator",
    "require_founder",
    "FounderOperator",
]


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("authorization") or request.headers.get(
        "Authorization"
    )
    if auth:
        scheme, _, tok = auth.partition(" ")
        if scheme.lower() == "bearer" and tok:
            return tok.strip()
    cookie = request.cookies.get(COCKPIT_COOKIE_NAME)
    if cookie:
        return cookie.strip()
    return None


async def get_current_operator(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Operator:
    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "operator_unauthenticated",
                "message": "Cockpit endpoint requires operator authentication.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(token, expected_type=TOKEN_TYPE_ACCESS)
    except OperatorAuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    operator_id = str(payload["sub"])
    result = await session.execute(select(Operator).where(Operator.id == operator_id))
    operator = result.scalar_one_or_none()
    if operator is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "operator_unknown",
                "message": "Operator no longer exists.",
            },
        )
    if operator.status != OperatorStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "operator_suspended",
                "message": "Operator account is suspended.",
            },
        )
    return operator


CurrentOperator = Annotated[Operator, Depends(get_current_operator)]


async def require_founder(
    operator: CurrentOperator,
) -> Operator:
    """Gate an endpoint to operators with role ``FOUNDER``.

    Founders are the only operators allowed to perform destructive or
    secret-management actions (tenant deletion, key-rotation logging).
    Non-founder operators receive ``403 founder_required``.
    """

    if operator.role != OperatorRole.FOUNDER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "founder_required",
                "message": "This action requires founder-level operator access.",
            },
        )
    return operator


FounderOperator = Annotated[Operator, Depends(require_founder)]
