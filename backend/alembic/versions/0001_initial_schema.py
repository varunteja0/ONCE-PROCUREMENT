"""Initial schema for Once.

Creates every table, index, and foreign key for the canonical model set:
tenants, users, portals, tenant_users, suppliers, consent_records,
certificates_of_insurance, supplier_submissions, submission_receipts,
audit_logs.

All UUID columns use ``sa.String(length=36)``; JSON columns use the generic
``sa.JSON()`` so the schema stays SQLite-portable. Enums are stored as
``sa.String(length=32)`` rather than native database enums.

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------
    # tenants
    # -------------------------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("plan", sa.String(length=32), nullable=False, server_default="pilot"),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    # -------------------------------------------------------------------
    # users
    # -------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # -------------------------------------------------------------------
    # portals
    # -------------------------------------------------------------------
    op.create_table(
        "portals",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column(
            "is_supported",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "risky",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_portals_platform", "portals", ["platform"])

    # -------------------------------------------------------------------
    # tenant_users
    # -------------------------------------------------------------------
    op.create_table(
        "tenant_users",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="admin"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_tenant_users_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_tenant_users_user_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_tenant_users_tenant_user"),
    )
    op.create_index("ix_tenant_users_tenant_id", "tenant_users", ["tenant_id"])
    op.create_index("ix_tenant_users_user_id", "tenant_users", ["user_id"])

    # -------------------------------------------------------------------
    # suppliers
    # -------------------------------------------------------------------
    op.create_table(
        "suppliers",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("dba_name", sa.String(length=255), nullable=True),
        sa.Column("ein", sa.String(length=32), nullable=True),
        sa.Column("naics_code", sa.String(length=16), nullable=True),
        sa.Column("primary_email", sa.String(length=320), nullable=True),
        sa.Column("primary_phone", sa.String(length=32), nullable=True),
        sa.Column("address_json", sa.JSON(), nullable=True),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_suppliers_tenant_id_tenants",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_suppliers_tenant_id", "suppliers", ["tenant_id"])
    op.create_index("ix_suppliers_ein", "suppliers", ["ein"])

    # -------------------------------------------------------------------
    # consent_records
    # -------------------------------------------------------------------
    op.create_table(
        "consent_records",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("supplier_id", sa.String(length=36), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("portal_ids_json", sa.JSON(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("signed_text", sa.Text(), nullable=False),
        sa.Column("signature_b64", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_consent_records_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_consent_records_supplier_id_suppliers",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["users.id"],
            name="fk_consent_records_granted_by_user_id_users",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_consent_records_tenant_id", "consent_records", ["tenant_id"])
    op.create_index("ix_consent_records_supplier_id", "consent_records", ["supplier_id"])
    op.create_index(
        "ix_consent_records_granted_by_user_id",
        "consent_records",
        ["granted_by_user_id"],
    )

    # -------------------------------------------------------------------
    # certificates_of_insurance
    # -------------------------------------------------------------------
    op.create_table(
        "certificates_of_insurance",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("supplier_id", sa.String(length=36), nullable=False),
        sa.Column("carrier_name", sa.String(length=255), nullable=False),
        sa.Column("policy_number", sa.String(length=128), nullable=False),
        sa.Column("coverage_type", sa.String(length=32), nullable=False),
        sa.Column("limit_each_occurrence", sa.Numeric(18, 2), nullable=True),
        sa.Column("limit_aggregate", sa.Numeric(18, 2), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("file_url", sa.String(length=1024), nullable=True),
        sa.Column("uploaded_by_user_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_coi_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_coi_supplier_id_suppliers",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
            name="fk_coi_uploaded_by_user_id_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_certificates_of_insurance_tenant_id",
        "certificates_of_insurance",
        ["tenant_id"],
    )
    op.create_index(
        "ix_certificates_of_insurance_supplier_id",
        "certificates_of_insurance",
        ["supplier_id"],
    )
    op.create_index(
        "ix_certificates_of_insurance_expiry_date",
        "certificates_of_insurance",
        ["expiry_date"],
    )
    op.create_index(
        "ix_coi_tenant_expiry",
        "certificates_of_insurance",
        ["tenant_id", "expiry_date"],
    )

    # -------------------------------------------------------------------
    # supplier_submissions
    # -------------------------------------------------------------------
    op.create_table(
        "supplier_submissions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("supplier_id", sa.String(length=36), nullable=False),
        sa.Column("portal_id", sa.String(length=36), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_record_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_supplier_submissions_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_supplier_submissions_supplier_id_suppliers",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["portal_id"],
            ["portals.id"],
            name="fk_supplier_submissions_portal_id_portals",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["consent_record_id"],
            ["consent_records.id"],
            name="fk_supplier_submissions_consent_record_id_consent_records",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_supplier_submissions_tenant_id", "supplier_submissions", ["tenant_id"]
    )
    op.create_index(
        "ix_supplier_submissions_supplier_id", "supplier_submissions", ["supplier_id"]
    )
    op.create_index(
        "ix_supplier_submissions_portal_id", "supplier_submissions", ["portal_id"]
    )
    op.create_index(
        "ix_supplier_submissions_status", "supplier_submissions", ["status"]
    )
    op.create_index(
        "ix_supplier_submissions_tenant_status",
        "supplier_submissions",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_supplier_submissions_supplier_status",
        "supplier_submissions",
        ["supplier_id", "status"],
    )

    # -------------------------------------------------------------------
    # submission_receipts
    # -------------------------------------------------------------------
    op.create_table(
        "submission_receipts",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("submission_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("supplier_id", sa.String(length=36), nullable=False),
        sa.Column("portal_platform", sa.String(length=64), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_hash", sa.String(length=128), nullable=False),
        sa.Column("tos_version_hash", sa.String(length=128), nullable=False),
        sa.Column("consent_record_id", sa.String(length=36), nullable=False),
        sa.Column("signing_key_id", sa.String(length=128), nullable=False),
        sa.Column("signature_b64", sa.Text(), nullable=False),
        sa.Column("public_payload_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["supplier_submissions.id"],
            name="fk_submission_receipts_submission_id_supplier_submissions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_submission_receipts_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_submission_receipts_supplier_id_suppliers",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["consent_record_id"],
            ["consent_records.id"],
            name="fk_submission_receipts_consent_record_id_consent_records",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("submission_id", name="uq_submission_receipts_submission_id"),
    )
    op.create_index(
        "ix_submission_receipts_submission_id",
        "submission_receipts",
        ["submission_id"],
        unique=True,
    )
    op.create_index(
        "ix_submission_receipts_tenant_id", "submission_receipts", ["tenant_id"]
    )
    op.create_index(
        "ix_submission_receipts_supplier_id", "submission_receipts", ["supplier_id"]
    )
    op.create_index(
        "ix_submission_receipts_consent_record_id",
        "submission_receipts",
        ["consent_record_id"],
    )

    # -------------------------------------------------------------------
    # audit_logs
    # -------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_audit_logs_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_audit_logs_actor_user_id_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_occurred_at", "audit_logs", ["occurred_at"])


def downgrade() -> None:
    # audit_logs
    op.drop_index("ix_audit_logs_occurred_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    # submission_receipts
    op.drop_index(
        "ix_submission_receipts_consent_record_id", table_name="submission_receipts"
    )
    op.drop_index(
        "ix_submission_receipts_supplier_id", table_name="submission_receipts"
    )
    op.drop_index("ix_submission_receipts_tenant_id", table_name="submission_receipts")
    op.drop_index(
        "ix_submission_receipts_submission_id", table_name="submission_receipts"
    )
    op.drop_table("submission_receipts")

    # supplier_submissions
    op.drop_index(
        "ix_supplier_submissions_supplier_status", table_name="supplier_submissions"
    )
    op.drop_index(
        "ix_supplier_submissions_tenant_status", table_name="supplier_submissions"
    )
    op.drop_index("ix_supplier_submissions_status", table_name="supplier_submissions")
    op.drop_index(
        "ix_supplier_submissions_portal_id", table_name="supplier_submissions"
    )
    op.drop_index(
        "ix_supplier_submissions_supplier_id", table_name="supplier_submissions"
    )
    op.drop_index(
        "ix_supplier_submissions_tenant_id", table_name="supplier_submissions"
    )
    op.drop_table("supplier_submissions")

    # certificates_of_insurance
    op.drop_index("ix_coi_tenant_expiry", table_name="certificates_of_insurance")
    op.drop_index(
        "ix_certificates_of_insurance_expiry_date",
        table_name="certificates_of_insurance",
    )
    op.drop_index(
        "ix_certificates_of_insurance_supplier_id",
        table_name="certificates_of_insurance",
    )
    op.drop_index(
        "ix_certificates_of_insurance_tenant_id",
        table_name="certificates_of_insurance",
    )
    op.drop_table("certificates_of_insurance")

    # consent_records
    op.drop_index(
        "ix_consent_records_granted_by_user_id", table_name="consent_records"
    )
    op.drop_index("ix_consent_records_supplier_id", table_name="consent_records")
    op.drop_index("ix_consent_records_tenant_id", table_name="consent_records")
    op.drop_table("consent_records")

    # suppliers
    op.drop_index("ix_suppliers_ein", table_name="suppliers")
    op.drop_index("ix_suppliers_tenant_id", table_name="suppliers")
    op.drop_table("suppliers")

    # tenant_users
    op.drop_index("ix_tenant_users_user_id", table_name="tenant_users")
    op.drop_index("ix_tenant_users_tenant_id", table_name="tenant_users")
    op.drop_table("tenant_users")

    # portals
    op.drop_index("ix_portals_platform", table_name="portals")
    op.drop_table("portals")

    # users
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    # tenants
    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")
