"""Service layer for the :class:`~app.models.LossRun` entity.

All operations are tenant-scoped. Cross-tenant access never raises 403 —
it returns ``None`` (or raises ``NotFoundError``) so the API surface
cannot leak whether a resource exists under another tenant.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LossRun, Supplier
from app.schemas.loss_run import LossRunCreate, LossRunUpdate
from app.services.exceptions import OnceError
from app.utils.logging import get_logger

__all__ = [
    "NotFoundError",
    "SupplierNotInTenantError",
    "create",
    "get",
    "list_by_supplier",
    "update",
    "delete",
]


_logger = get_logger(__name__)

_MAX_LIMIT = 200


class NotFoundError(OnceError):
    """The requested loss run does not exist for this tenant."""


class SupplierNotInTenantError(OnceError):
    """The supplier_id supplied does not belong to the caller's tenant."""


async def _assert_supplier_in_tenant(
    session: AsyncSession, *, tenant_id: str, supplier_id: str
) -> None:
    stmt = select(Supplier.id).where(
        Supplier.id == supplier_id, Supplier.tenant_id == tenant_id
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise SupplierNotInTenantError(
            "supplier not found in tenant",
            tenant_id=tenant_id,
            supplier_id=supplier_id,
        )


def _payload_dict(payload: LossRunCreate | LossRunUpdate) -> dict[str, Any]:
    data = payload.model_dump(exclude_unset=True)
    # Enum -> string-backed columns
    for key in ("line_of_business", "status"):
        val = data.get(key)
        if val is not None and hasattr(val, "value"):
            data[key] = val.value
    return data


async def create(
    session: AsyncSession,
    *,
    tenant_id: str,
    payload: LossRunCreate,
) -> LossRun:
    await _assert_supplier_in_tenant(
        session, tenant_id=tenant_id, supplier_id=payload.supplier_id
    )
    data = _payload_dict(payload)
    row = LossRun(tenant_id=tenant_id, **data)
    session.add(row)
    await session.flush()
    await session.refresh(row)
    _logger.info(
        "loss_run_created",
        tenant_id=tenant_id,
        supplier_id=row.supplier_id,
        loss_run_id=row.id,
    )
    return row


async def get(
    session: AsyncSession, *, tenant_id: str, id: str
) -> LossRun | None:
    stmt = select(LossRun).where(LossRun.id == id, LossRun.tenant_id == tenant_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_by_supplier(
    session: AsyncSession,
    *,
    tenant_id: str,
    supplier_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[LossRun], int]:
    limit = max(1, min(limit, _MAX_LIMIT))
    offset = max(0, offset)
    stmt = select(LossRun).where(LossRun.tenant_id == tenant_id)
    count_stmt = select(func.count(LossRun.id)).where(LossRun.tenant_id == tenant_id)
    if supplier_id is not None:
        stmt = stmt.where(LossRun.supplier_id == supplier_id)
        count_stmt = count_stmt.where(LossRun.supplier_id == supplier_id)
    stmt = stmt.order_by(LossRun.created_at.desc(), LossRun.id.desc())
    stmt = stmt.limit(limit).offset(offset)
    items_result = await session.execute(stmt)
    total_result = await session.execute(count_stmt)
    items = list(items_result.scalars().all())
    total = int(total_result.scalar_one() or 0)
    return items, total


async def update(
    session: AsyncSession,
    *,
    tenant_id: str,
    id: str,
    payload: LossRunUpdate,
) -> LossRun:
    row = await get(session, tenant_id=tenant_id, id=id)
    if row is None:
        raise NotFoundError("loss run not found", loss_run_id=id, tenant_id=tenant_id)
    data = _payload_dict(payload)
    for key, value in data.items():
        setattr(row, key, value)
    await session.flush()
    await session.refresh(row)
    _logger.info(
        "loss_run_updated",
        tenant_id=tenant_id,
        loss_run_id=row.id,
        fields=sorted(data.keys()),
    )
    return row


async def delete(session: AsyncSession, *, tenant_id: str, id: str) -> LossRun:
    row = await get(session, tenant_id=tenant_id, id=id)
    if row is None:
        raise NotFoundError("loss run not found", loss_run_id=id, tenant_id=tenant_id)
    await session.delete(row)
    await session.flush()
    _logger.info("loss_run_deleted", tenant_id=tenant_id, loss_run_id=id)
    return row
