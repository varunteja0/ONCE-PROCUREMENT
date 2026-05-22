"""Cockpit tenants routes: list, get, switch act-as, list scoped data."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cockpit import CurrentOperator, FounderOperator
from app.db import get_db
from app.models import (
    Operator,
    OperatorRole,
    OperatorTenantGrant,
    Supplier,
    SupplierSubmission,
    Tenant,
)
from app.schemas.cockpit import (
    ActAsRequest,
    ActAsResponse,
    TenantListResponse,
    TenantSummary,
)
from app.schemas.compliance import TenantDeletionReceipt, TenantDeletionRequest
from app.schemas.supplier import SupplierRead
from app.services import operator_auth, tenant_deletion_service
from app.services.tenant_deletion_service import TenantNotFound, TenantSlugMismatch
from app.utils.logging import get_logger

__all__ = ["router"]

router = APIRouter(prefix="/tenants", tags=["cockpit-tenants"])
_logger = get_logger(__name__)


async def _accessible_tenant_ids(
    session: AsyncSession, operator: Operator
) -> set[str] | None:
    """Return ``None`` for founders (means "all tenants"), else the explicit set."""

    if operator.role == OperatorRole.FOUNDER.value:
        return None
    result = await session.execute(
        select(OperatorTenantGrant.tenant_id).where(
            OperatorTenantGrant.operator_id == operator.id
        )
    )
    return {str(t) for t in result.scalars().all()}


def _grant_permission(
    operator: Operator, tenant_id: str, accessible: set[str] | None
) -> str:
    if operator.role == OperatorRole.FOUNDER.value:
        return "write"
    if accessible is None or tenant_id not in accessible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "act_as_forbidden",
                "message": "Operator has no grant for this tenant.",
            },
        )
    return "write"


@router.get(
    "",
    response_model=TenantListResponse,
    summary="List tenants the operator can access",
)
async def list_tenants(
    operator: CurrentOperator,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TenantListResponse:
    accessible = await _accessible_tenant_ids(session, operator)
    stmt = select(Tenant)
    if accessible is not None:
        if not accessible:
            return TenantListResponse(items=[], total=0)
        stmt = stmt.where(Tenant.id.in_(accessible))
    result = await session.execute(stmt.order_by(Tenant.created_at.desc()))
    tenants = list(result.scalars().all())

    sup_counts: dict[str, int] = {}
    sub_counts: dict[str, int] = {}
    if tenants:
        tids = [t.id for t in tenants]
        sc = await session.execute(
            select(Supplier.tenant_id, func.count(Supplier.id))
            .where(Supplier.tenant_id.in_(tids))
            .group_by(Supplier.tenant_id)
        )
        sup_counts = {str(tid): int(cnt) for tid, cnt in sc.all()}
        sbc = await session.execute(
            select(SupplierSubmission.tenant_id, func.count(SupplierSubmission.id))
            .where(SupplierSubmission.tenant_id.in_(tids))
            .group_by(SupplierSubmission.tenant_id)
        )
        sub_counts = {str(tid): int(cnt) for tid, cnt in sbc.all()}

    items = [
        TenantSummary(
            id=t.id,
            name=t.name,
            slug=t.slug,
            plan=t.plan,
            is_active=t.is_active,
            created_at=t.created_at,
            supplier_count=sup_counts.get(t.id, 0),
            submission_count=sub_counts.get(t.id, 0),
        )
        for t in tenants
    ]
    return TenantListResponse(items=items, total=len(items))


@router.get(
    "/{tenant_id}",
    response_model=TenantSummary,
    summary="Get a single tenant the operator can access",
)
async def get_tenant(
    tenant_id: str,
    operator: CurrentOperator,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TenantSummary:
    accessible = await _accessible_tenant_ids(session, operator)
    _grant_permission(operator, tenant_id, accessible)
    result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "tenant_not_found", "message": "Tenant does not exist."},
        )
    return TenantSummary(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        plan=tenant.plan,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
    )


@router.post(
    "/act-as",
    response_model=ActAsResponse,
    summary="Validate that the operator may act as the given tenant",
)
async def switch_act_as(
    payload: ActAsRequest,
    operator: CurrentOperator,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ActAsResponse:
    accessible = await _accessible_tenant_ids(session, operator)
    permission = _grant_permission(operator, payload.tenant_id, accessible)
    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == payload.tenant_id))
    ).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "tenant_not_found", "message": "Tenant does not exist."},
        )
    if not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "tenant_inactive", "message": "Tenant is disabled."},
        )
    return ActAsResponse(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        permission=permission,
        expires_in=operator_auth.ACCESS_TTL_MINUTES * 60,
    )


@router.get(
    "/{tenant_id}/suppliers",
    response_model=list[SupplierRead],
    summary="List suppliers for the tenant the operator is acting as",
)
async def list_tenant_suppliers(
    tenant_id: str,
    request: Request,
    operator: CurrentOperator,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[SupplierRead]:
    accessible = await _accessible_tenant_ids(session, operator)
    _grant_permission(operator, tenant_id, accessible)

    # Honor X-Operator-Acting-Tenant header if present (must match path).
    act_as_header = request.headers.get("x-operator-acting-tenant")
    if act_as_header and act_as_header != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "act_as_mismatch",
                "message": "X-Operator-Acting-Tenant must match path tenant_id.",
            },
        )

    result = await session.execute(
        select(Supplier).where(Supplier.tenant_id == tenant_id)
    )
    suppliers = list(result.scalars().all())
    return [SupplierRead.model_validate(s) for s in suppliers]


@router.delete(
    "/{tenant_id}",
    response_model=TenantDeletionReceipt,
    summary="Permanently delete a tenant and all its data (founder-only)",
)
async def delete_tenant_endpoint(
    tenant_id: str,
    payload: TenantDeletionRequest,
    operator: FounderOperator,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TenantDeletionReceipt:
    """Hard-delete a tenant — GDPR right-to-erasure + SOC 2 evidence.

    Requires founder-level operator access and a confirmation payload that
    repeats the tenant's slug and includes a non-empty justification. The
    deletion is idempotent: a second call against an already-deleted
    tenant returns ``404 tenant_not_found``. Per-table row counts are
    persisted to ``audit_logs`` as a system-level (``tenant_id = NULL``)
    record.
    """

    try:
        receipt = await tenant_deletion_service.delete_tenant(
            session,
            tenant_id=tenant_id,
            confirm_slug=payload.confirm_tenant_slug,
            reason=payload.reason,
            operator_id=operator.id,
        )
    except TenantNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "tenant_not_found", "message": exc.message},
        ) from exc
    except TenantSlugMismatch as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "slug_mismatch",
                "message": exc.message,
                "context": exc.context,
            },
        ) from exc

    await session.commit()
    _logger.warning(
        "cockpit_tenant_deleted",
        tenant_id=tenant_id,
        tenant_slug=receipt.tenant_slug,
        operator_id=operator.id,
        row_counts=receipt.row_counts,
    )
    return receipt
