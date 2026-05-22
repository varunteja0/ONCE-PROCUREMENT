"""L3.9 — Inbound routing rule.

Rules are evaluated in ascending ``priority`` order (lower = first). The
first matching rule wins; built-in fallback rule at priority 999
guarantees every email is routed somewhere.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, _uuid

__all__ = ["InboundRoutingRule", "InboundRuleAction"]


class InboundRuleAction(str, enum.Enum):
    CREATE_SUBMISSION = "create_submission"
    QUARANTINE = "quarantine"
    DISCARD = "discard"
    TAG_ONLY = "tag_only"


class InboundRoutingRule(Base, TenantScopedMixin):
    __tablename__ = "inbound_routing_rules"
    __table_args__ = (
        Index("ix_inbound_rules_tenant_priority", "tenant_id", "priority"),
        Index("ix_inbound_rules_tenant_active", "tenant_id", "active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    match_from_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    match_subject_regex: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    match_attachment_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)

    action: Mapped[InboundRuleAction] = mapped_column(
        Enum(InboundRuleAction, name="inbound_rule_action", native_enum=False, length=32),
        nullable=False,
        default=InboundRuleAction.CREATE_SUBMISSION,
    )
    action_params: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
