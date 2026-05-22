from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta

from sqlalchemy import and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.coi import CertificateOfInsurance
from app.utils.logging import get_logger

__all__ = ["find_expiring", "DEFAULT_DAYS_AHEAD"]


_logger = get_logger(__name__)


DEFAULT_DAYS_AHEAD: int = 30


async def find_expiring(
    session: AsyncSession,
    *,
    tenant_id: str | None = None,
    days_ahead: int = DEFAULT_DAYS_AHEAD,
    as_of: date | None = None,
) -> Sequence[CertificateOfInsurance]:
    """Return COIs expiring within ``days_ahead`` days that have no renewal.

    A COI is considered "renewed" if another COI exists for the same
    ``supplier_id`` and ``coverage_type`` whose ``effective_date`` is on
    or after this COI's ``expiry_date``. Past-due COIs (expiry < today)
    that have not been renewed are also returned so they can be escalated.

    Args:
        session: Async DB session.
        tenant_id: Optional tenant filter. When ``None`` all tenants are
            scanned (used by the global Celery beat sweep).
        days_ahead: Window in days from ``as_of`` to consider as
            "expiring soon". Defaults to 30.
        as_of: Reference date. Defaults to ``date.today()``.
    """

    if days_ahead < 0:
        raise ValueError("days_ahead must be non-negative")

    reference = as_of or date.today()
    horizon = reference + timedelta(days=days_ahead)

    Newer = aliased(CertificateOfInsurance)
    renewal_exists = (
        select(Newer.id)
        .where(
            Newer.supplier_id == CertificateOfInsurance.supplier_id,
            Newer.coverage_type == CertificateOfInsurance.coverage_type,
            Newer.id != CertificateOfInsurance.id,
            Newer.effective_date >= CertificateOfInsurance.expiry_date,
        )
        .correlate(CertificateOfInsurance)
    )

    conditions = [
        CertificateOfInsurance.expiry_date <= horizon,
        ~exists(renewal_exists),
    ]
    if tenant_id is not None:
        conditions.append(CertificateOfInsurance.tenant_id == tenant_id)

    stmt = (
        select(CertificateOfInsurance)
        .where(and_(*conditions))
        .order_by(CertificateOfInsurance.expiry_date.asc())
    )

    result = await session.execute(stmt)
    rows = result.scalars().all()

    _logger.info(
        "coi_monitor_find_expiring",
        tenant_id=tenant_id,
        days_ahead=days_ahead,
        as_of=reference.isoformat(),
        horizon=horizon.isoformat(),
        count=len(rows),
    )
    return rows
