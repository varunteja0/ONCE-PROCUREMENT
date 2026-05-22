"""SOC 2 compliance models — tamper-evident audit chain + key rotation log.

Both tables are append-only by convention. Schema stays SQLite-portable:
``String(36)`` UUIDs, ``String(32)`` enums, generic ``JSON``, no native
enum types, no partial indexes, no PG-only functions.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, _uuid


class AuditHashDigest(Base):
    """Daily digest of ``audit_logs`` rows for a tenant — tamper-evident chain.

    Written by the nightly ``audit.verify_nightly_hash`` Celery task. Each row
    pins the SHA-256 of the canonical-JSON serialization of the previous
    UTC day's ``AuditLog`` rows for one tenant, plus the row count and the
    previous day's digest (the chain link).

    Mismatch on re-verification = tampering. The verifier task raises and
    alerts; it never overwrites a previous digest.
    """

    __tablename__ = "audit_hash_digests"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "covers_date", name="uq_audit_hash_digests_tenant_date"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # UTC date covered by this digest (a calendar day, midnight-to-midnight).
    covers_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    # SHA-256 hex of canonical-JSON of the day's audit rows (see audit_hash_service).
    digest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # Hex digest of the immediately-prior day for this tenant (chain link).
    # Empty string for the first digest of a tenant.
    prev_digest_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=""
    )
    row_count: Mapped[int] = mapped_column(
        nullable=False, server_default="0"
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class KeyRotationLog(Base):
    """Append-only record of every key / secret rotation event.

    Records WHICH secret was rotated, WHEN, by WHICH operator, and a free-form
    ``notes`` field for the rotation justification. Stores no key material.

    Backs the SOC 2 evidence trail for CC-6.1 (logical access — key management).
    Recorded via ``POST /cockpit/compliance/key-rotations``.
    """

    __tablename__ = "key_rotation_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # Logical key name, e.g. "receipt_signing_key", "jwt_secret_key",
    # "cockpit_jwt_secret_key", "db_password", "fly_api_token".
    key_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Optional id of the *new* key when applicable (e.g. new ``SigningKey.id``).
    new_key_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Optional id of the *previous* key, for chain-of-custody.
    previous_key_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Operator id who performed the rotation. Nullable for system-initiated.
    rotated_by_operator_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("operators.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rotated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


__all__ = ["AuditHashDigest", "KeyRotationLog"]
