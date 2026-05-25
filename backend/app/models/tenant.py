from __future__ import annotations

import secrets

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, _uuid


def _inbound_secret() -> str:
    """URL-safe per-tenant routing token (audit gap G — inbound email)."""

    return secrets.token_urlsafe(24)[:32]


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="pilot")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Per-tenant shared secret embedded in the inbound mailbox local-part
    # ("submissions+<token>@<slug>.in.getonce.com"). Nullable for backwards
    # compatibility with tenants created before 20260525_03 — those rows
    # bypass token enforcement until backfilled by an operator.
    inbound_secret_token: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, default=_inbound_secret
    )


class TenantUser(Base, TimestampMixin):
    __tablename__ = "tenant_users"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_tenant_users_tenant_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="admin")
