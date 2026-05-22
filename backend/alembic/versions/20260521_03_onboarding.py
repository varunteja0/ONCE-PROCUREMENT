"""L3.6 — Onboarding wizard tables.

Adds two tables:

* ``onboarding_states`` — 1:1 tenant <-> wizard journey.
* ``email_verifications`` — issued 6-digit codes (stored as sha256 hashes).

Revision ID: 20260521_03_onboarding
Revises: 20260521_02_billing
Create Date: 2026-05-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260521_03_onboarding"
down_revision = "20260521_02_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "onboarding_states",
        sa.Column(
            "tenant_id",
            sa.String(length=36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "current_step",
            sa.String(length=32),
            nullable=False,
            server_default="email_pending",
        ),
        sa.Column("completed_steps", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("skipped_steps", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("step_data_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("company_profile_json", sa.JSON(), nullable=True),
        sa.Column(
            "primary_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "email_verifications",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(length=36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_email_verifications_email", "email_verifications", ["email"]
    )
    op.create_index(
        "ix_email_verifications_email_created",
        "email_verifications",
        ["email", "created_at"],
    )
    op.create_index(
        "ix_email_verifications_tenant", "email_verifications", ["tenant_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_email_verifications_tenant", table_name="email_verifications")
    op.drop_index(
        "ix_email_verifications_email_created", table_name="email_verifications"
    )
    op.drop_index("ix_email_verifications_email", table_name="email_verifications")
    op.drop_table("email_verifications")
    op.drop_table("onboarding_states")
