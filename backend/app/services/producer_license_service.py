"""Service layer for the :class:`~app.models.ProducerLicense` entity."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProducerLicense, Supplier
from app.schemas.producer_license import (
    ProducerLicenseCreate,
    ProducerLicenseUpdate,
)
from app.services.exceptions import OnceError
from app.utils.logging import get_logger

__all__ = [
    "NotFoundError",
    "SupplierNotInTenantError",
    "DuplicateLicenseError",
    "create",
    "get",
    "list_by_supplier",
    "update",
    "delete",
]


_logger = get_logger(__name__)

_MAX_LIMIT = 200


class NotFoundError(OnceError):
    """The requested producer license does not exist for this tenant."""


class SupplierNotInTenantError(OnceError):
    """The supplier_id supplied does not belong to the caller's tenant."""


class DuplicateLicenseError(OnceError):
    """A license already exists with the same (supplier, state, number)."""


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


def _payload_dict(
    payload: ProducerLicenseCreate | ProducerLicenseUpdate,
) -> dict[str, Any]:
    data = payload.model_dump(exclude_unset=True)
    for key in ("license_type", "status"):
        val = data.get(key)
        if val is not None and hasattr(val, "value"):
            data[key] = val.value
    return data


async def create(
    session: AsyncSession,
    *,
    tenant_id: str,
    payload: ProducerLicenseCreate,
) -> ProducerLicense:
    await _assert_supplier_in_tenant(
        session, tenant_id=tenant_id, supplier_id=payload.supplier_id
    )
    data = _payload_dict(payload)
    row = ProducerLicense(tenant_id=tenant_id, **data)
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateLicenseError(
            "producer license already exists",
            tenant_id=tenant_id,
            supplier_id=payload.supplier_id,
            state=payload.state,
            license_number=payload.license_number,
        ) from exc
    await session.refresh(row)
    _logger.info(
        "producer_license_created",
        tenant_id=tenant_id,
        supplier_id=row.supplier_id,
        license_id=row.id,
        state=row.state,
    )
    return row


async def get(
    session: AsyncSession, *, tenant_id: str, id: str
) -> ProducerLicense | None:
    stmt = select(ProducerLicense).where(
        ProducerLicense.id == id, ProducerLicense.tenant_id == tenant_id
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_by_supplier(
    session: AsyncSession,
    *,
    tenant_id: str,
    supplier_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ProducerLicense], int]:
    limit = max(1, min(limit, _MAX_LIMIT))
    offset = max(0, offset)
    stmt = select(ProducerLicense).where(ProducerLicense.tenant_id == tenant_id)
    count_stmt = select(func.count(ProducerLicense.id)).where(
        ProducerLicense.tenant_id == tenant_id
    )
    if supplier_id is not None:
        stmt = stmt.where(ProducerLicense.supplier_id == supplier_id)
        count_stmt = count_stmt.where(ProducerLicense.supplier_id == supplier_id)
    stmt = stmt.order_by(
        ProducerLicense.expiration_date.asc(), ProducerLicense.id.asc()
    ).limit(limit).offset(offset)
    items_result = await session.execute(stmt)
    total_result = await session.execute(count_stmt)
    return list(items_result.scalars().all()), int(total_result.scalar_one() or 0)


async def update(
    session: AsyncSession,
    *,
    tenant_id: str,
    id: str,
    payload: ProducerLicenseUpdate,
) -> ProducerLicense:
    row = await get(session, tenant_id=tenant_id, id=id)
    if row is None:
        raise NotFoundError(
            "producer license not found", license_id=id, tenant_id=tenant_id
        )
    data = _payload_dict(payload)
    for key, value in data.items():
        setattr(row, key, value)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateLicenseError(
            "producer license already exists",
            tenant_id=tenant_id,
            license_id=id,
        ) from exc
    await session.refresh(row)
    _logger.info(
        "producer_license_updated",
        tenant_id=tenant_id,
        license_id=row.id,
        fields=sorted(data.keys()),
    )
    return row


async def delete(
    session: AsyncSession, *, tenant_id: str, id: str
) -> ProducerLicense:
    row = await get(session, tenant_id=tenant_id, id=id)
    if row is None:
        raise NotFoundError(
            "producer license not found", license_id=id, tenant_id=tenant_id
        )
    await session.delete(row)
    await session.flush()
    _logger.info("producer_license_deleted", tenant_id=tenant_id, license_id=id)
    return row
