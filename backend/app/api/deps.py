from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import TenantUser, User
from app.utils.logging import get_logger
from app.utils.security import TokenDecodeError, decode_token

__all__ = [
    "oauth2_scheme",
    "get_current_user",
    "get_current_tenant_id",
    "get_current_tenant_user",
    "CurrentUser",
    "CurrentTenantId",
    "CurrentTenantUser",
]


_logger = get_logger(__name__)

oauth2_scheme: OAuth2PasswordBearer = OAuth2PasswordBearer(tokenUrl="/v1/auth/login")


def _credentials_exception(detail_code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": detail_code, "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    try:
        payload = decode_token(token, expected_type="access")
    except TokenDecodeError as exc:
        raise _credentials_exception("invalid_token", str(exc)) from exc

    user_id = str(payload["sub"])
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise _credentials_exception("missing_tenant_claim", "Access token missing tenant claim.")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise _credentials_exception("user_not_found", "User no longer exists.")
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "user_inactive", "message": "User account is disabled."},
        )

    user._jwt_tenant_id = str(tenant_id)
    user._jwt_role = payload.get("role")
    return user


def get_current_tenant_id(
    user: Annotated[User, Depends(get_current_user)],
) -> str:
    tenant_id = getattr(user, "_jwt_tenant_id", None)
    if not tenant_id:
        raise _credentials_exception(
            "missing_tenant_claim", "Access token missing tenant claim."
        )
    return str(tenant_id)


async def get_current_tenant_user(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TenantUser:
    tenant_id = get_current_tenant_id(user)
    result = await session.execute(
        select(TenantUser).where(
            TenantUser.user_id == user.id,
            TenantUser.tenant_id == tenant_id,
        )
    )
    tenant_user = result.scalar_one_or_none()
    if tenant_user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "not_a_tenant_member",
                "message": "User is not a member of the requested tenant.",
            },
        )
    return tenant_user


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentTenantId = Annotated[str, Depends(get_current_tenant_id)]
CurrentTenantUser = Annotated[TenantUser, Depends(get_current_tenant_user)]
