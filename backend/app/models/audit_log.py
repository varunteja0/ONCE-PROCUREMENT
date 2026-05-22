"""L3.10 — Tenant-wide tamper-evident audit trail.

Distinct from the legacy ``audit_logs`` table (see :mod:`app.models.audit`)
and from the operator-scoped ``cockpit_audit`` table — this is the
production-grade, chain-hashed, signature-exportable evidence surface
that auditors verify and SOC 2 reviewers inspect.

Key properties enforced at the model + DB layer:

* **Append-only**: the migration installs SQLite triggers raising on
  UPDATE / DELETE (Postgres deployments enforce the same via grants).
* **Chain-hashed**: every row stores ``prev_hash`` + ``this_hash``;
  ``app.services.audit_chain`` verifies the chain end-to-end.
* **ULID primary key**: lexicographically sortable so chronological
  ordering survives clock skew and the chain replay is deterministic.

The model name is :class:`AuditLogEntry` and the table name is
``audit_trail`` to disambiguate from the older :class:`AuditLog` rows
which remain in service for the L3.4 hash-digest job.
"""

from __future__ import annotations

import enum
import os
import secrets
import time
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

__all__ = [
    "AuditActorType",
    "AuditLogEntry",
    "GENESIS_HASH_PREFIX",
    "new_ulid",
]


# ---------------------------------------------------------------------------
# ULID — Crockford-base32, 26 chars, lexicographically sortable.
# ---------------------------------------------------------------------------

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode_crockford(value: int, length: int) -> str:
    out = ["0"] * length
    for i in range(length - 1, -1, -1):
        out[i] = _CROCKFORD[value & 0x1F]
        value >>= 5
    return "".join(out)


def new_ulid() -> str:
    """Generate a 26-char ULID (Crockford base32) from current ms + 80b entropy."""

    ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand = int.from_bytes(secrets.token_bytes(10), "big")
    return _encode_crockford(ms, 10) + _encode_crockford(rand, 16)


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------


class AuditActorType(str, enum.Enum):
    USER = "user"
    OPERATOR = "operator"
    SYSTEM = "system"
    INBOUND_EMAIL = "inbound_email"
    WEBHOOK = "webhook"
    WORKER = "worker"


# Genesis-hash prefix is mixed with the tenant_id to seed each per-tenant chain.
# Documented here (and re-asserted by tests) because changing it would silently
# break chain verification for every existing row.
GENESIS_HASH_PREFIX: bytes = b"once-audit-genesis-"


class AuditLogEntry(Base):
    __tablename__ = "audit_trail"
    __table_args__ = (
        Index(
            "ix_audit_trail_tenant_occurred",
            "tenant_id",
            "occurred_at",
        ),
        Index(
            "ix_audit_trail_tenant_position",
            "tenant_id",
            "chain_position",
            unique=True,
        ),
        Index(
            "ix_audit_trail_resource",
            "tenant_id",
            "resource_type",
            "resource_id",
        ),
        Index(
            "ix_audit_trail_actor",
            "tenant_id",
            "actor_type",
            "occurred_at",
        ),
        Index(
            "ix_audit_trail_action",
            "tenant_id",
            "action_verb",
            "occurred_at",
        ),
        CheckConstraint(
            "length(this_hash) = 64", name="ck_audit_trail_this_hash_hex64"
        ),
        CheckConstraint(
            "length(prev_hash) = 64", name="ck_audit_trail_prev_hash_hex64"
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    actor_type: Mapped[AuditActorType] = mapped_column(
        SAEnum(
            AuditActorType,
            name="audit_actor_type",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
            native_enum=False,
            length=32,
        ),
        nullable=False,
    )
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    action_verb: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_label: Mapped[str | None] = mapped_column(String(512), nullable=True)

    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    payload_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    this_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    chain_position: Mapped[int] = mapped_column(Integer, nullable=False)

    signature_key_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signature_b64: Mapped[str | None] = mapped_column(String(255), nullable=True)


# Suppress unused-import lint when ``os`` is needed for portable triggers later.
_ = os
