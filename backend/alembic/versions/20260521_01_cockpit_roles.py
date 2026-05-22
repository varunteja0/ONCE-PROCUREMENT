"""L3.3 — Cockpit roles + audit.

Adds four tables that back the Founder Cockpit (Phase 2 done-for-you mode):

* ``operators`` — external operators of the platform (founder / engineering /
  support). Separate from ``users`` because operators are not tenant members.
* ``operator_tenant_grants`` — per-tenant access grants for non-founder
  operators. Founders implicitly have write on all tenants.
* ``operator_sessions`` — server-side refresh-token records so individual
  operator devices can be revoked without rotating the cockpit JWT secret.
* ``cockpit_audit`` — append-only row per cockpit / act-as request.

Schema stays SQLite-portable (``String(36)`` UUIDs, ``String(32)`` enums,
generic ``JSON``, no native enum types, no partial indexes).

Revision ID: 20260521_01_cockpit_roles
Revises: 20260520_03_submission_artifacts
Create Date: 2026-05-21 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260521_01_cockpit_roles"
down_revision: Union[str, None] = "20260520_03_submission_artifacts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- operators ----------------------------------------------------------
    op.create_table(
        "operators",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "role", sa.String(length=32), nullable=False, server_default="support"
        ),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="active"
        ),
        sa.Column(
            "mfa_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("mfa_secret", sa.String(length=64), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("email", name="uq_operators_email"),
    )
    op.create_index("ix_operators_email", "operators", ["email"], unique=True)
    op.create_index("ix_operators_status", "operators", ["status"])

    # --- operator_tenant_grants --------------------------------------------
    op.create_table(
        "operator_tenant_grants",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "operator_id",
            sa.String(length=36),
            sa.ForeignKey("operators.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.String(length=36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "permission",
            sa.String(length=16),
            nullable=False,
            server_default="write",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "operator_id", "tenant_id", name="uq_operator_tenant_grant"
        ),
    )
    op.create_index(
        "ix_operator_tenant_grants_operator_id",
        "operator_tenant_grants",
        ["operator_id"],
    )
    op.create_index(
        "ix_operator_tenant_grants_tenant_id",
        "operator_tenant_grants",
        ["tenant_id"],
    )

    # --- operator_sessions --------------------------------------------------
    op.create_table(
        "operator_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "operator_id",
            sa.String(length=36),
            sa.ForeignKey("operators.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.UniqueConstraint(
            "refresh_token_hash", name="uq_operator_sessions_refresh_hash"
        ),
    )
    op.create_index(
        "ix_operator_sessions_operator_id",
        "operator_sessions",
        ["operator_id"],
    )
    op.create_index(
        "ix_operator_sessions_refresh_hash",
        "operator_sessions",
        ["refresh_token_hash"],
        unique=True,
    )

    # --- cockpit_audit ------------------------------------------------------
    op.create_table(
        "cockpit_audit",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "operator_id",
            sa.String(length=36),
            sa.ForeignKey("operators.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "tenant_id_acted_as",
            sa.String(length=36),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("method", sa.String(length=8), nullable=True),
        sa.Column("path", sa.String(length=512), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("payload_redacted", sa.JSON(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_cockpit_audit_operator_id", "cockpit_audit", ["operator_id"]
    )
    op.create_index(
        "ix_cockpit_audit_tenant_id_acted_as",
        "cockpit_audit",
        ["tenant_id_acted_as"],
    )
    op.create_index("ix_cockpit_audit_action", "cockpit_audit", ["action"])
    op.create_index("ix_cockpit_audit_occurred_at", "cockpit_audit", ["occurred_at"])
    op.create_index(
        "ix_cockpit_audit_operator_occurred",
        "cockpit_audit",
        ["operator_id", "occurred_at"],
    )
    op.create_index(
        "ix_cockpit_audit_tenant_occurred",
        "cockpit_audit",
        ["tenant_id_acted_as", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_cockpit_audit_tenant_occurred", table_name="cockpit_audit")
    op.drop_index("ix_cockpit_audit_operator_occurred", table_name="cockpit_audit")
    op.drop_index("ix_cockpit_audit_occurred_at", table_name="cockpit_audit")
    op.drop_index("ix_cockpit_audit_action", table_name="cockpit_audit")
    op.drop_index(
        "ix_cockpit_audit_tenant_id_acted_as", table_name="cockpit_audit"
    )
    op.drop_index("ix_cockpit_audit_operator_id", table_name="cockpit_audit")
    op.drop_table("cockpit_audit")

    op.drop_index(
        "ix_operator_sessions_refresh_hash", table_name="operator_sessions"
    )
    op.drop_index("ix_operator_sessions_operator_id", table_name="operator_sessions")
    op.drop_table("operator_sessions")

    op.drop_index(
        "ix_operator_tenant_grants_tenant_id", table_name="operator_tenant_grants"
    )
    op.drop_index(
        "ix_operator_tenant_grants_operator_id", table_name="operator_tenant_grants"
    )
    op.drop_table("operator_tenant_grants")

    op.drop_index("ix_operators_status", table_name="operators")
    op.drop_index("ix_operators_email", table_name="operators")
    op.drop_table("operators")
