"""operator recovery codes table

Revision ID: 20260524_01_operator_recovery_codes
Revises: 20260523_03_merge_l3_application_schema
Create Date: 2026-05-24 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260524_01_operator_recovery_codes"
down_revision: Union[str, Sequence[str], None] = "20260523_03_merge_l3_application_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "operator_recovery_codes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "operator_id",
            sa.String(length=36),
            sa.ForeignKey("operators.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("code_hash", name="uq_operator_recovery_code_hash"),
        sa.UniqueConstraint(
            "operator_id", "code_hash", name="uq_operator_recovery_op_hash"
        ),
    )
    op.create_index(
        "ix_operator_recovery_codes_operator_id",
        "operator_recovery_codes",
        ["operator_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_operator_recovery_codes_operator_id",
        table_name="operator_recovery_codes",
    )
    op.drop_table("operator_recovery_codes")
