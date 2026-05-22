"""L5.1 - SOC 2 evidence: audit hash digests + key rotation logs.

Revision ID: 20260522_01_soc2_evidence
Revises: 20260521_01_cockpit_roles
Create Date: 2026-05-22 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260522_01_soc2_evidence"
down_revision: Union[str, None] = "20260521_01_cockpit_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_hash_digests",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            sa.String(length=36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("covers_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("digest_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "prev_digest_sha256",
            sa.String(length=64),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "row_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "covers_date",
            name="uq_audit_hash_digests_tenant_date",
        ),
    )
    op.create_index(
        "ix_audit_hash_digests_tenant_id",
        "audit_hash_digests",
        ["tenant_id"],
    )
    op.create_index(
        "ix_audit_hash_digests_covers_date",
        "audit_hash_digests",
        ["covers_date"],
    )

    op.create_table(
        "key_rotation_logs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("key_name", sa.String(length=64), nullable=False),
        sa.Column("new_key_id", sa.String(length=36), nullable=True),
        sa.Column("previous_key_id", sa.String(length=36), nullable=True),
        sa.Column(
            "rotated_by_operator_id",
            sa.String(length=36),
            sa.ForeignKey("operators.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.String(length=1024), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "rotated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_key_rotation_logs_key_name",
        "key_rotation_logs",
        ["key_name"],
    )
    op.create_index(
        "ix_key_rotation_logs_rotated_at",
        "key_rotation_logs",
        ["rotated_at"],
    )
    op.create_index(
        "ix_key_rotation_logs_rotated_by_operator_id",
        "key_rotation_logs",
        ["rotated_by_operator_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_key_rotation_logs_rotated_by_operator_id",
        table_name="key_rotation_logs",
    )
    op.drop_index(
        "ix_key_rotation_logs_rotated_at", table_name="key_rotation_logs"
    )
    op.drop_index(
        "ix_key_rotation_logs_key_name", table_name="key_rotation_logs"
    )
    op.drop_table("key_rotation_logs")

    op.drop_index(
        "ix_audit_hash_digests_covers_date", table_name="audit_hash_digests"
    )
    op.drop_index(
        "ix_audit_hash_digests_tenant_id", table_name="audit_hash_digests"
    )
    op.drop_table("audit_hash_digests")