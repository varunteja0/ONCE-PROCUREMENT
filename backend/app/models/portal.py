from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, _uuid


class PortalPlatform(str, enum.Enum):
    APPLIED_EPIC = "applied_epic"
    VERTAFORE_AMS360 = "vertafore_ams360"
    VERTAFORE_SIRCON = "vertafore_sircon"
    AMTRUST = "amtrust"
    MARKEL = "markel"
    NATIONWIDE_ES = "nationwide_es"
    CNA = "cna"
    GUIDEWIRE = "guidewire"
    HAWKSOFT = "hawksoft"
    EZLYNX = "ezlynx"
    NOWCERTS = "nowcerts"


class Portal(Base, TimestampMixin):
    __tablename__ = "portals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    platform: Mapped[PortalPlatform] = mapped_column(
        Enum(PortalPlatform, name="portal_platform", native_enum=False, length=64),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    risky: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
