"""AcordForm model — ACORD-standardized insurance form payload.

ACORD (Association for Cooperative Operations Research and Development)
publishes the standard family of P&C insurance forms used across the
industry: 125 (Commercial Insurance Application), 126 (Commercial General
Liability section), 127 (Business Auto section), 130 (Workers Comp), 140
(Property), 25 (Certificate of Insurance).

We persist the form *payload* as structured JSON (the canonical fields the
form would capture) and compute ``payload_hash`` from the canonical-JSON
encoding so we can detect changes between versions cheaply. ``status``
plus ``superseded_by_id`` give us simple linear versioning: a finalized
form is superseded by a newer draft pointing back via ``superseded_by_id``.
"""

from __future__ import annotations

import enum
from datetime import date
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, _uuid

__all__ = ["AcordForm", "AcordFormStatus", "AcordFormType"]


class AcordFormType(str, enum.Enum):
    ACORD_25 = "acord_25"
    ACORD_125 = "acord_125"
    ACORD_126 = "acord_126"
    ACORD_127 = "acord_127"
    ACORD_130 = "acord_130"
    ACORD_140 = "acord_140"


class AcordFormStatus(str, enum.Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"
    SUBMITTED = "submitted"
    SUPERSEDED = "superseded"


class AcordForm(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "acord_forms"
    __table_args__ = (
        Index(
            "ix_acord_forms_tenant_supplier_type_status",
            "tenant_id",
            "supplier_id",
            "form_type",
            "status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    supplier_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    form_type: Mapped[str] = mapped_column(String(16), nullable=False)
    form_version: Mapped[str] = mapped_column(
        String(16), nullable=False, default="current"
    )

    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    pdf_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    pdf_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AcordFormStatus.DRAFT.value
    )
    superseded_by_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("acord_forms.id", ondelete="SET NULL"),
        nullable=True,
    )

    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
