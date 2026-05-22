"""Service layer for the :class:`~app.models.EOCertificate` entity."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EOCertificate, Supplier
from app.schemas.eo_certificate import EOCertificateCreate, EOCertificateUpdate
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
    """The requested E&O certificate does not exist for this tenant."""


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
    payload: EOCertificateCreate | EOCertificateUpdate,
) -> dict[str, Any]:
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and hasattr(data["status"], "value"):
        data["status"] = data["status"].value
    return data


async def create(
    session: AsyncSession,
    *,
    tenant_id: str,
    payload: EOCertificateCreate,
) -> EOCertificate:
    await _assert_supplier_in_tenant(
        session, tenant_id=tenant_id, supplier_id=payload.supplier_id
    )
    data = _payload_dict(payload)
    row = EOCertificate(tenant_id=tenant_id, **data)
    session.add(row)
    await session.flush()
    await session.refresh(row)
    _logger.info(
        "eo_certificate_created",
        tenant_id=tenant_id,
        supplier_id=row.supplier_id,
        eo_certificate_id=row.id,
    )
    return row


async def get(
    session: AsyncSession, *, tenant_id: str, id: str
) -> EOCertificate | None:
    stmt = select(EOCertificate).where(
        EOCertificate.id == id, EOCertificate.tenant_id == tenant_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_by_supplier(
    session: AsyncSession,
    *,
    tenant_id: str,
    supplier_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[EOCertificate], int]:
    limit = max(1, min(limit, _MAX_LIMIT))
    offset = max(0, offset)
    stmt = select(EOCertificate).where(EOCertificate.tenant_id == tenant_id)
    count_stmt = select(func.count(EOCertificate.id)).where(
        EOCertificate.tenant_id == tenant_id
    )
    if supplier_id is not None:
        stmt = stmt.where(EOCertificate.supplier_id == supplier_id)
        count_stmt = count_stmt.where(EOCertificate.supplier_id == supplier_id)
    stmt = stmt.order_by(
        EOCertificate.expiration_date.asc(), EOCertificate.id.asc()
    ).limit(limit).offset(offset)
    items = list((await session.execute(stmt)).scalars().all())
    total = int((await session.execute(count_stmt)).scalar_one() or 0)
    return items, total


async def update(
    session: AsyncSession,
    *,
    tenant_id: str,
    id: str,
    payload: EOCertificateUpdate,
) -> EOCertificate:
    row = await get(session, tenant_id=tenant_id, id=id)
    if row is None:
        raise NotFoundError(
            "E&O certificate not found", eo_certificate_id=id, tenant_id=tenant_id
        )
    data = _payload_dict(payload)
    for key, value in data.items():
        setattr(row, key, value)
    await session.flush()
    await session.refresh(row)
    _logger.info(
        "eo_certificate_updated",
        tenant_id=tenant_id,
        eo_certificate_id=row.id,
        fields=sorted(data.keys()),
    )
    return row


async def delete(
    session: AsyncSession, *, tenant_id: str, id: str
) -> EOCertificate:
    row = await get(session, tenant_id=tenant_id, id=id)
    if row is None:
        raise NotFoundError(
            "E&O certificate not found", eo_certificate_id=id, tenant_id=tenant_id
        )
    await session.delete(row)
    await session.flush()
    _logger.info(
        "eo_certificate_deleted", tenant_id=tenant_id, eo_certificate_id=id
    )
    return row
