from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, _uuid


class Supplier(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dba_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ein: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    naics_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    primary_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    primary_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
