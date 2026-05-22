"""signing_keys registry table.

Adds the ``signing_keys`` table that backs the receipt-verification key
registry. The table stores only the public half of each Ed25519 key plus
metadata (algorithm, optional description, creation/revocation timestamps).
Private keys remain in the ``RECEIPT_SIGNING_PRIVATE_KEY_PEM`` env var.

Revision ID: 20260519_02_signing_keys
Revises: 0001
Create Date: 2026-05-19 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260519_02_signing_keys"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signing_keys",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "algorithm",
            sa.String(length=16),
            nullable=False,
            server_default="ed25519",
        ),
        sa.Column("public_key_pem", sa.Text(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_signing_keys_revoked_at",
        "signing_keys",
        ["revoked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_signing_keys_revoked_at", table_name="signing_keys")
    op.drop_table("signing_keys")
