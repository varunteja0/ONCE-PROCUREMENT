"""L6.1 - per-key monthly usage counter for verifier API.

Revision ID: 20260523_02_verifier_api_key_usage
Revises: 20260523_01_verifier_api_keys
Create Date: 2026-05-23 00:00:01.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260523_02_verifier_api_key_usage"
down_revision: Union[str, None] = "20260523_01_verifier_api_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "verifier_api_key_usage",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "api_key_id",
            sa.String(length=36),
            sa.ForeignKey("verifier_api_keys.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_month", sa.String(length=7), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
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
            "api_key_id",
            "period_month",
            name="uq_verifier_api_key_usage_key_month",
        ),
    )
    op.create_index(
        "ix_verifier_api_key_usage_api_key_id",
        "verifier_api_key_usage",
        ["api_key_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_verifier_api_key_usage_api_key_id",
        table_name="verifier_api_key_usage",
    )
    op.drop_table("verifier_api_key_usage")
