from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant, TenantUser, User
from app.schemas.auth import RegisterRequest, TokenPair
from app.utils.logging import get_logger
from app.utils.security import (
    TokenDecodeError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

__all__ = [
    "register_user_and_tenant",
    "authenticate",
    "refresh",
    "issue_token_pair",
]


_logger = get_logger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = _SLUG_RE.sub("-", normalized.lower()).strip("-")
    if not slug:
        slug = "tenant"
    return slug[:48]


async def _unique_tenant_slug(session: AsyncSession, base: str) -> str:
    slug = base
    suffix = 0
    while True:
        existing = await session.execute(select(Tenant.id).where(Tenant.slug == slug))
        if existing.scalar_one_or_none() is None:
            return slug
        suffix += 1
        slug = f"{base[:40]}-{uuid.uuid4().hex[:6]}"
        if suffix > 8:
            return f"{base[:32]}-{uuid.uuid4().hex[:8]}"


def issue_token_pair(user: User, tenant_user: TenantUser) -> TokenPair:
    extra: dict[str, Any] = {"role": tenant_user.role, "email": user.email}
    access = create_access_token(sub=user.id, tenant_id=tenant_user.tenant_id, extra_claims=extra)
    refresh_tok = create_refresh_token(
        sub=user.id, tenant_id=tenant_user.tenant_id, extra_claims={"role": tenant_user.role}
    )
    return TokenPair(access_token=access, refresh_token=refresh_tok)


async def register_user_and_tenant(
    session: AsyncSession, payload: RegisterRequest
) -> tuple[User, Tenant, TenantUser]:
    email = payload.email.lower().strip()

    existing = await session.execute(select(User.id).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "email_already_registered", "message": "Email is already registered."},
        )

    base_slug = _slugify(payload.tenant_name)
    slug = await _unique_tenant_slug(session, base_slug)

    tenant = Tenant(name=payload.tenant_name.strip(), slug=slug)
    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        is_active=True,
    )
    session.add_all([tenant, user])
    await session.flush()

    tenant_user = TenantUser(tenant_id=tenant.id, user_id=user.id, role="owner")
    session.add(tenant_user)

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        _logger.warning("auth_register_integrity_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "registration_conflict",
                "message": "Could not register user — conflict detected.",
            },
        ) from exc

    _logger.info(
        "auth_register_success",
        user_id=user.id,
        tenant_id=tenant.id,
        email=email,
    )
    return user, tenant, tenant_user


async def authenticate(
    session: AsyncSession, email: str, password: str
) -> tuple[User, TenantUser]:
    normalized = email.lower().strip()
    result = await session.execute(select(User).where(User.email == normalized))
    user = result.scalar_one_or_none()

    invalid_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "invalid_credentials", "message": "Invalid email or password."},
        headers={"WWW-Authenticate": "Bearer"},
    )

    if user is None or not verify_password(password, user.hashed_password):
        _logger.info("auth_login_failed", email=normalized)
        raise invalid_exc

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "user_inactive", "message": "User account is disabled."},
        )

    tu_result = await session.execute(
        select(TenantUser).where(TenantUser.user_id == user.id).limit(1)
    )
    tenant_user = tu_result.scalar_one_or_none()
    if tenant_user is None:
        _logger.error("auth_login_no_tenant", user_id=user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "no_tenant_membership",
                "message": "User is not a member of any tenant.",
            },
        )

    user.last_login_at = datetime.now(tz=UTC)
    await session.flush()

    return user, tenant_user


async def refresh(session: AsyncSession, refresh_token: str) -> TokenPair:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except TokenDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_refresh_token", "message": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = str(payload["sub"])
    tenant_id_claim = payload.get("tenant_id")

    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "user_not_found_or_inactive", "message": "User not found or inactive."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    stmt = select(TenantUser).where(TenantUser.user_id == user.id)
    if tenant_id_claim:
        stmt = stmt.where(TenantUser.tenant_id == str(tenant_id_claim))
    tenant_user = (await session.execute(stmt.limit(1))).scalar_one_or_none()
    if tenant_user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "no_tenant_membership",
                "message": "User is no longer a member of the tenant in the refresh token.",
            },
        )

    return issue_token_pair(user, tenant_user)
