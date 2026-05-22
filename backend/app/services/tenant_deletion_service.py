"""Tenant deletion service — SOC 2 + GDPR right-to-erasure.

Hard-deletes a tenant and every row that references it via the ``tenant_id``
column. Discovers child tables dynamically from
:data:`app.models.Base.metadata` so newly-added tenant-scoped tables are
covered automatically.

* Founder-only — the endpoint guards this; the service trusts its caller.
* Idempotent — second call on an already-deleted tenant returns ``None``
  and the endpoint maps that to ``404``.
* Writes an :class:`AuditLog` row with ``tenant_id = NULL`` (system event)
  containing the per-table row counts. The deleted tenant's own audit rows
  are gone too, so this system-level record is the only surviving trail.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Base, Tenant
from app.schemas.compliance import TenantDeletionReceipt
from app.services.exceptions import OnceError
from app.utils.logging import get_logger

__all__ = ["delete_tenant", "TenantSlugMismatch", "TenantNotFound"]


_logger = get_logger(__name__)


class TenantSlugMismatch(OnceError):
    """The ``confirm_tenant_slug`` payload did not match the target tenant."""


class TenantNotFound(OnceError):
    """The tenant does not exist (or was already deleted)."""


def _tenant_scoped_tables() -> list[str]:
    """Names of tables that have a ``tenant_id`` column, ordered for delete.

    Excludes ``tenants`` itself (deleted last). The tenant's own
    ``audit_logs`` rows ARE included — GDPR-style hard erasure. The only
    surviving record is the system-level (``tenant_id = NULL``)
    ``tenant.deleted`` audit row written at the end with row counts.
    """

    names: list[str] = []
    for table in Base.metadata.tables.values():
        if table.name == "tenants":
            continue
        if "tenant_id" not in table.columns:
            continue
        names.append(table.name)
    # Deterministic order — alphabetical is fine for receipts.
    return sorted(names)


async def _count_rows(
    session: AsyncSession, *, table_name: str, tenant_id: str
) -> int:
    table = Base.metadata.tables[table_name]
    stmt = select(func.count()).select_from(table).where(
        table.c.tenant_id == tenant_id
    )
    return int((await session.execute(stmt)).scalar_one() or 0)


async def delete_tenant(
    session: AsyncSession,
    *,
    tenant_id: str,
    confirm_slug: str,
    reason: str,
    operator_id: str | None,
) -> TenantDeletionReceipt:
    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if tenant is None:
        raise TenantNotFound("tenant not found", tenant_id=tenant_id)
    if tenant.slug != confirm_slug:
        raise TenantSlugMismatch(
            "confirm_tenant_slug does not match target tenant",
            tenant_id=tenant_id,
            expected_slug=tenant.slug,
        )

    slug = tenant.slug
    child_tables = _tenant_scoped_tables()
    row_counts: dict[str, int] = {}
    for name in child_tables:
        row_counts[name] = await _count_rows(
            session, table_name=name, tenant_id=tenant_id
        )

    # Delete child rows explicitly so the receipt's row counts match the
    # actual deletions even on DBs / FKs that do not cascade. Order does
    # not matter once we suppress FK checks via the explicit deletes —
    # SQLite is fine with this, Postgres handles FKs deferrable by table
    # but our schema uses ON DELETE CASCADE for tenant_id FKs anyway.
    for name in child_tables:
        if row_counts[name] == 0:
            continue
        table = Base.metadata.tables[name]
        await session.execute(
            delete(table).where(table.c.tenant_id == tenant_id)
        )

    await session.execute(delete(Tenant).where(Tenant.id == tenant_id))

    audit_row = AuditLog(
        tenant_id=None,  # system-level event — tenant no longer exists
        actor_user_id=None,
        action="tenant.deleted",
        resource_type="tenant",
        resource_id=tenant_id,
        metadata_json={
            "tenant_slug": slug,
            "reason": reason,
            "operator_id": operator_id,
            "row_counts": row_counts,
        },
        ip_address=None,
    )
    session.add(audit_row)
    await session.flush()

    deleted_at = datetime.now(tz=UTC)
    _logger.warning(
        "tenant_deleted",
        tenant_id=tenant_id,
        tenant_slug=slug,
        operator_id=operator_id,
        row_counts=row_counts,
        audit_log_id=audit_row.id,
    )
    return TenantDeletionReceipt(
        tenant_id=tenant_id,
        tenant_slug=slug,
        deleted_at=deleted_at,
        row_counts=row_counts,
        audit_log_id=audit_row.id,
    )
