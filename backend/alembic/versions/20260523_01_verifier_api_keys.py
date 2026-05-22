"""L6.1 - tenant-scoped verifier API keys.

Revision ID: 20260523_01_verifier_api_keys
Revises: 20260522_01_soc2_evidence
Create Date: 2026-05-23 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260523_01_verifier_api_keys"
down_revision: Union[str, None] = "20260522_01_soc2_evidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "verifier_api_keys",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            sa.String(length=36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("monthly_call_cap", sa.Integer(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by_operator_id",
            sa.String(length=36),
            sa.ForeignKey("operators.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("key_prefix", name="uq_verifier_api_keys_key_prefix"),
    )
    op.create_index("ix_verifier_api_keys_tenant_id", "verifier_api_keys", ["tenant_id"])
    op.create_index("ix_verifier_api_keys_key_prefix", "verifier_api_keys", ["key_prefix"])


def downgrade() -> None:
    op.drop_index("ix_verifier_api_keys_key_prefix", table_name="verifier_api_keys")
    op.drop_index("ix_verifier_api_keys_tenant_id", table_name="verifier_api_keys")
    op.drop_table("verifier_api_keys")
