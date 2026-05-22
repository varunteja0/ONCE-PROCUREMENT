"""Operator model — external operators of the Once platform.

Operators (founder / engineering / support) are **not** tenant users; they
live in a separate table with a separate JWT secret, separate session
records, and a per-tenant grant table that gates the "act-as" capability.

Schema stays SQLite-portable: ``String(36)`` UUIDs, ``String(32)``
enum-as-string columns, no native enum types.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, _uuid


class OperatorRole(str, enum.Enum):
    FOUNDER = "founder"
    ENGINEERING = "engineering"
    SUPPORT = "support"


class OperatorStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class Operator(Base, TimestampMixin):
    __tablename__ = "operators"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(
        String(320), nullable=False, unique=True, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default=OperatorRole.SUPPORT.value
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=OperatorStatus.ACTIVE.value, index=True
    )
    mfa_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OperatorTenantGrant(Base, TimestampMixin):
    """Per-tenant access grant for non-founder operators."""

    __tablename__ = "operator_tenant_grants"
    __table_args__ = (
        UniqueConstraint(
            "operator_id", "tenant_id", name="uq_operator_tenant_grant"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    operator_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("operators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # "read" | "write"; founders implicitly have write on all tenants.
    permission: Mapped[str] = mapped_column(
        String(16), nullable=False, default="write"
    )
