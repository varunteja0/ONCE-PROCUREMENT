"""Service layer for the :class:`~app.models.AcordForm` entity.

``payload_hash`` is auto-computed from the canonical-JSON encoding of
``payload`` on every create/update so callers cannot accidentally desync
the stored hash from the stored payload. Setting ``superseded_by_id``
flips the predecessor's status to :data:`AcordFormStatus.SUPERSEDED` so
list/active queries do not return stale revisions.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AcordForm, AcordFormStatus, Supplier
from app.schemas.acord_form import AcordFormCreate, AcordFormUpdate
from app.services.exceptions import OnceError
from app.utils.canonical_json import payload_sha256
from app.utils.logging import get_logger

__all__ = [
    "NotFoundError",
    "SupplierNotInTenantError",
    "InvalidSupersedeReferenceError",
    "create",
    "get",
    "list_by_supplier",
    "update",
    "delete",
]


_logger = get_logger(__name__)

_MAX_LIMIT = 200


class NotFoundError(OnceError):
    """The requested ACORD form does not exist for this tenant."""


class SupplierNotInTenantError(OnceError):
    """The supplier_id supplied does not belong to the caller's tenant."""


class InvalidSupersedeReferenceError(OnceError):
    """``superseded_by_id`` does not reference a valid ACORD form in this tenant."""


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


async def _assert_supersede_target_in_tenant(
    session: AsyncSession, *, tenant_id: str, target_id: str
) -> None:
    stmt = select(AcordForm.id).where(
        AcordForm.id == target_id, AcordForm.tenant_id == tenant_id
    )
    if (await session.execute(stmt)).scalar_one_or_none() is None:
        raise InvalidSupersedeReferenceError(
            "superseded_by_id does not exist in tenant",
            tenant_id=tenant_id,
            superseded_by_id=target_id,
        )


def _payload_dict(payload: AcordFormCreate | AcordFormUpdate) -> dict[str, Any]:
    data = payload.model_dump(exclude_unset=True)
    for key in ("form_type", "status"):
        val = data.get(key)
        if val is not None and hasattr(val, "value"):
            data[key] = val.value
    return data


async def _mark_predecessor_superseded(
    session: AsyncSession, *, tenant_id: str, predecessor_id: str
) -> None:
    predecessor = (
        await session.execute(
            select(AcordForm).where(
                AcordForm.id == predecessor_id, AcordForm.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if predecessor is not None and predecessor.status != AcordFormStatus.SUPERSEDED.value:
        predecessor.status = AcordFormStatus.SUPERSEDED.value


async def create(
    session: AsyncSession,
    *,
    tenant_id: str,
    payload: AcordFormCreate,
) -> AcordForm:
    await _assert_supplier_in_tenant(
        session, tenant_id=tenant_id, supplier_id=payload.supplier_id
    )
    data = _payload_dict(payload)
    data["payload_hash"] = payload_sha256(payload.payload)

    superseded_by_id = data.get("superseded_by_id")
    if superseded_by_id is not None:
        await _assert_supersede_target_in_tenant(
            session, tenant_id=tenant_id, target_id=superseded_by_id
        )

    row = AcordForm(tenant_id=tenant_id, **data)
    session.add(row)
    await session.flush()
    await session.refresh(row)
    _logger.info(
        "acord_form_created",
        tenant_id=tenant_id,
        supplier_id=row.supplier_id,
        acord_form_id=row.id,
        form_type=row.form_type,
    )
    return row


async def get(
    session: AsyncSession, *, tenant_id: str, id: str
) -> AcordForm | None:
    stmt = select(AcordForm).where(
        AcordForm.id == id, AcordForm.tenant_id == tenant_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_by_supplier(
    session: AsyncSession,
    *,
    tenant_id: str,
    supplier_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AcordForm], int]:
    limit = max(1, min(limit, _MAX_LIMIT))
    offset = max(0, offset)
    stmt = select(AcordForm).where(AcordForm.tenant_id == tenant_id)
    count_stmt = select(func.count(AcordForm.id)).where(
        AcordForm.tenant_id == tenant_id
    )
    if supplier_id is not None:
        stmt = stmt.where(AcordForm.supplier_id == supplier_id)
        count_stmt = count_stmt.where(AcordForm.supplier_id == supplier_id)
    stmt = stmt.order_by(
        AcordForm.created_at.desc(), AcordForm.id.desc()
    ).limit(limit).offset(offset)
    items = list((await session.execute(stmt)).scalars().all())
    total = int((await session.execute(count_stmt)).scalar_one() or 0)
    return items, total


async def update(
    session: AsyncSession,
    *,
    tenant_id: str,
    id: str,
    payload: AcordFormUpdate,
) -> AcordForm:
    row = await get(session, tenant_id=tenant_id, id=id)
    if row is None:
        raise NotFoundError(
            "ACORD form not found", acord_form_id=id, tenant_id=tenant_id
        )
    data = _payload_dict(payload)

    if "payload" in data and data["payload"] is not None:
        data["payload_hash"] = payload_sha256(data["payload"])

    new_superseded_by = data.get("superseded_by_id")
    if new_superseded_by is not None and new_superseded_by != row.superseded_by_id:
        if new_superseded_by == row.id:
            raise InvalidSupersedeReferenceError(
                "ACORD form cannot supersede itself", acord_form_id=id
            )
        await _assert_supersede_target_in_tenant(
            session, tenant_id=tenant_id, target_id=new_superseded_by
        )

    for key, value in data.items():
        setattr(row, key, value)

    if new_superseded_by is not None:
        await _mark_predecessor_superseded(
            session, tenant_id=tenant_id, predecessor_id=row.id
        )

    await session.flush()
    await session.refresh(row)
    _logger.info(
        "acord_form_updated",
        tenant_id=tenant_id,
        acord_form_id=row.id,
        fields=sorted(data.keys()),
    )
    return row


async def delete(session: AsyncSession, *, tenant_id: str, id: str) -> AcordForm:
    row = await get(session, tenant_id=tenant_id, id=id)
    if row is None:
        raise NotFoundError(
            "ACORD form not found", acord_form_id=id, tenant_id=tenant_id
        )
    await session.delete(row)
    await session.flush()
    _logger.info("acord_form_deleted", tenant_id=tenant_id, acord_form_id=id)
    return row
