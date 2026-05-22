"""Access-review service — SOC 2 evidence read path.

Lists every (tenant, user) membership for a tenant so an auditor / founder
can review who has access. Joins :class:`User` and :class:`TenantUser`
strictly scoped by ``tenant_id``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TenantUser, User
from app.schemas.compliance import AccessReviewResponse, AccessReviewUser

__all__ = ["list_tenant_users"]


async def list_tenant_users(
    session: AsyncSession,
    *,
    tenant_id: str,
) -> AccessReviewResponse:
    stmt = (
        select(User, TenantUser)
        .join(TenantUser, TenantUser.user_id == User.id)
        .where(TenantUser.tenant_id == tenant_id)
        .order_by(User.email.asc())
    )
    rows = list((await session.execute(stmt)).all())
    items = [
        AccessReviewUser(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            role=tu.role,
            tenant_user_id=tu.id,
        )
        for user, tu in rows
    ]
    return AccessReviewResponse(
        tenant_id=tenant_id,
        generated_at=datetime.now(tz=UTC),
        total=len(items),
        items=items,
    )
