from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Supplier
from app.schemas.supplier import SupplierCreate, SupplierUpdate
from app.utils.logging import get_logger

__all__ = [
    "list_suppliers",
    "count_suppliers",
    "create_supplier",
    "get_supplier",
    "update_supplier",
    "delete_supplier",
]


_logger = get_logger(__name__)

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50


def _clamp_limit(limit: int) -> int:
    if limit <= 0:
        return _DEFAULT_LIMIT
    return min(limit, _MAX_LIMIT)


def _clamp_offset(offset: int) -> int:
    return max(offset, 0)


def _apply_search(stmt: Any, search: str | None) -> Any:
    if not search:
        return stmt
    term = f"%{search.strip().lower()}%"
    if term == "%%":
        return stmt
    return stmt.where(
        or_(
            func.lower(Supplier.legal_name).like(term),
            func.lower(func.coalesce(Supplier.dba_name, "")).like(term),
            func.lower(func.coalesce(Supplier.primary_email, "")).like(term),
            func.coalesce(Supplier.ein, "").like(f"%{search.strip()}%"),
        )
    )


async def list_suppliers(
    session: AsyncSession,
    *,
    tenant_id: str,
    search: str | None = None,
    limit: int = _DEFAULT_LIMIT,
    offset: int = 0,
) -> list[Supplier]:
    stmt = select(Supplier).where(Supplier.tenant_id == tenant_id)
    stmt = _apply_search(stmt, search)
    stmt = stmt.order_by(Supplier.created_at.desc(), Supplier.id.desc())
    stmt = stmt.limit(_clamp_limit(limit)).offset(_clamp_offset(offset))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_suppliers(
    session: AsyncSession,
    *,
    tenant_id: str,
    search: str | None = None,
) -> int:
    stmt = select(func.count(Supplier.id)).where(Supplier.tenant_id == tenant_id)
    stmt = _apply_search(stmt, search)
    result = await session.execute(stmt)
    return int(result.scalar_one() or 0)


def _payload_to_model_kwargs(payload: SupplierCreate | SupplierUpdate) -> dict[str, Any]:
    data = payload.model_dump(exclude_unset=True)
    if "website" in data and data["website"] is not None:
        data["website"] = str(data["website"])
    if "primary_email" in data and data["primary_email"] is not None:
        data["primary_email"] = str(data["primary_email"])
    return data


async def create_supplier(
    session: AsyncSession,
    *,
    tenant_id: str,
    payload: SupplierCreate,
) -> Supplier:
    data = _payload_to_model_kwargs(payload)
    supplier = Supplier(tenant_id=tenant_id, **data)
    session.add(supplier)
    await session.flush()
    await session.refresh(supplier)
    _logger.info("supplier_created", tenant_id=tenant_id, supplier_id=supplier.id)
    return supplier


async def get_supplier(
    session: AsyncSession,
    *,
    tenant_id: str,
    supplier_id: str,
) -> Supplier:
    stmt = select(Supplier).where(
        Supplier.id == supplier_id,
        Supplier.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    supplier = result.scalar_one_or_none()
    if supplier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "supplier_not_found", "message": "Supplier does not exist."},
        )
    return supplier


async def update_supplier(
    session: AsyncSession,
    *,
    tenant_id: str,
    supplier_id: str,
    payload: SupplierUpdate,
) -> Supplier:
    supplier = await get_supplier(
        session, tenant_id=tenant_id, supplier_id=supplier_id
    )
    data = _payload_to_model_kwargs(payload)
    if not data:
        return supplier
    for field, value in data.items():
        setattr(supplier, field, value)
    await session.flush()
    await session.refresh(supplier)
    _logger.info(
        "supplier_updated",
        tenant_id=tenant_id,
        supplier_id=supplier.id,
        fields=sorted(data.keys()),
    )
    return supplier


async def delete_supplier(
    session: AsyncSession,
    *,
    tenant_id: str,
    supplier_id: str,
) -> Supplier:
    """Hard-delete a supplier scoped to ``tenant_id``.

    The Supplier model currently has no ``is_active`` flag, so deletion is
    permanent. Callers MUST emit an ``AuditLog`` entry to preserve provenance.
    """

    supplier = await get_supplier(
        session, tenant_id=tenant_id, supplier_id=supplier_id
    )
    await session.delete(supplier)
    await session.flush()
    _logger.info("supplier_deleted", tenant_id=tenant_id, supplier_id=supplier_id)
    return supplier
