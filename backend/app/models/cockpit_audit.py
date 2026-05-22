"""Append-only audit log for every cockpit-routed request.

Every action an operator performs (including the act-of-acting-as a tenant)
is captured here. Rows attribute the action to the OPERATOR — not the tenant
user — so post-hoc audits can distinguish founder/operator activity from
real tenant activity.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, _uuid


class CockpitAudit(Base):
    __tablename__ = "cockpit_audit"
    __table_args__ = (
        Index(
            "ix_cockpit_audit_operator_occurred",
            "operator_id",
            "occurred_at",
        ),
        Index(
            "ix_cockpit_audit_tenant_occurred",
            "tenant_id_acted_as",
            "occurred_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    operator_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("operators.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tenant_id_acted_as: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    method: Mapped[str | None] = mapped_column(String(8), nullable=True)
    path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status_code: Mapped[int | None] = mapped_column(nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    payload_redacted: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
