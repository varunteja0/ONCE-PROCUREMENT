"""Service layer for the :class:`~app.models.RiskSchedule` entity.

``items_hash`` is auto-computed from the canonical-JSON encoding of the
``items`` list on every create/update, and ``item_count`` is forced to
``len(items)`` so the two are guaranteed consistent.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RiskSchedule, Supplier
from app.schemas.risk_schedule import RiskScheduleCreate, RiskScheduleUpdate
from app.services.exceptions import OnceError
from app.utils.canonical_json import payload_sha256
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
    """The requested risk schedule does not exist for this tenant."""


class SupplierNotInTenantError(OnceError):
    """The supplier_id supplied does not belong to the caller's tenant."""


async def _assert_supplier_in_tenant(
    session: AsyncSession, *, tenant_id: str, supplier_id: str
) -> None:
    stmt = select(Supplier.id).where(
        Supplier.id == supplier_id, Supplier.tenant_id == tenant_id
    )
    if (await session.execute(stmt)).scalar_one_or_none() is None:
        raise SupplierNotInTenantError(
            "supplier not found in tenant",
            tenant_id=tenant_id,
            supplier_id=supplier_id,
        )


def _payload_dict(
    payload: RiskScheduleCreate | RiskScheduleUpdate,
) -> dict[str, Any]:
    data = payload.model_dump(exclude_unset=True)
    if "line_of_business" in data and hasattr(data["line_of_business"], "value"):
        data["line_of_business"] = data["line_of_business"].value
    return data


async def create(
    session: AsyncSession,
    *,
    tenant_id: str,
    payload: RiskScheduleCreate,
) -> RiskSchedule:
    await _assert_supplier_in_tenant(
        session, tenant_id=tenant_id, supplier_id=payload.supplier_id
    )
    data = _payload_dict(payload)
    items = data.get("items", [])
    data["items_hash"] = payload_sha256(items)
    data["item_count"] = len(items)
    row = RiskSchedule(tenant_id=tenant_id, **data)
    session.add(row)
    await session.flush()
    await session.refresh(row)
    _logger.info(
        "risk_schedule_created",
        tenant_id=tenant_id,
        supplier_id=row.supplier_id,
        risk_schedule_id=row.id,
        item_count=row.item_count,
    )
    return row


async def get(
    session: AsyncSession, *, tenant_id: str, id: str
) -> RiskSchedule | None:
    stmt = select(RiskSchedule).where(
        RiskSchedule.id == id, RiskSchedule.tenant_id == tenant_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_by_supplier(
    session: AsyncSession,
    *,
    tenant_id: str,
    supplier_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[RiskSchedule], int]:
    limit = max(1, min(limit, _MAX_LIMIT))
    offset = max(0, offset)
    stmt = select(RiskSchedule).where(RiskSchedule.tenant_id == tenant_id)
    count_stmt = select(func.count(RiskSchedule.id)).where(
        RiskSchedule.tenant_id == tenant_id
    )
    if supplier_id is not None:
        stmt = stmt.where(RiskSchedule.supplier_id == supplier_id)
        count_stmt = count_stmt.where(RiskSchedule.supplier_id == supplier_id)
    stmt = stmt.order_by(
        RiskSchedule.created_at.desc(), RiskSchedule.id.desc()
    ).limit(limit).offset(offset)
    items = list((await session.execute(stmt)).scalars().all())
    total = int((await session.execute(count_stmt)).scalar_one() or 0)
    return items, total


async def update(
    session: AsyncSession,
    *,
    tenant_id: str,
    id: str,
    payload: RiskScheduleUpdate,
) -> RiskSchedule:
    row = await get(session, tenant_id=tenant_id, id=id)
    if row is None:
        raise NotFoundError(
            "risk schedule not found", risk_schedule_id=id, tenant_id=tenant_id
        )
    data = _payload_dict(payload)
    if "items" in data and data["items"] is not None:
        data["items_hash"] = payload_sha256(data["items"])
        data["item_count"] = len(data["items"])
    for key, value in data.items():
        setattr(row, key, value)
    await session.flush()
    await session.refresh(row)
    _logger.info(
        "risk_schedule_updated",
        tenant_id=tenant_id,
        risk_schedule_id=row.id,
        fields=sorted(data.keys()),
    )
    return row


async def delete(
    session: AsyncSession, *, tenant_id: str, id: str
) -> RiskSchedule:
    row = await get(session, tenant_id=tenant_id, id=id)
    if row is None:
        raise NotFoundError(
            "risk schedule not found", risk_schedule_id=id, tenant_id=tenant_id
        )
    await session.delete(row)
    await session.flush()
    _logger.info("risk_schedule_deleted", tenant_id=tenant_id, risk_schedule_id=id)
    return row
