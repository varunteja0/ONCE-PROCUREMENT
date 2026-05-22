"""Submission-artifact tables: loss_runs, producer_licenses, eo_certificates,
acord_forms, risk_schedules.

These five tables underpin the core "Submit once. Prove it forever." pitch:
they capture the documents (loss runs, licenses, E&O certificates, ACORD
forms, risk schedules) that an MGA must hand a carrier when placing a
risk. Every row is tenant-scoped via ``tenant_id`` (cascade on tenant
delete) and supplier-scoped via ``supplier_id`` (cascade on supplier
delete).

Schema stays SQLite-portable: ``String(36)`` for UUIDs, generic ``JSON``,
``String(32)`` for enum-as-string columns, no partial indexes, no native
``ENUM`` types.

Revision ID: 20260520_03_submission_artifacts
Revises: 20260519_02_signing_keys
Create Date: 2026-05-20 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260520_03_submission_artifacts"
down_revision: Union[str, None] = "20260519_02_signing_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------
    # loss_runs
    # -------------------------------------------------------------------
    op.create_table(
        "loss_runs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            sa.String(length=36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            sa.String(length=36),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("carrier_name", sa.String(length=255), nullable=False),
        sa.Column("line_of_business", sa.String(length=64), nullable=False),
        sa.Column("total_premium_cents", sa.BigInteger(), nullable=True),
        sa.Column("total_incurred_cents", sa.BigInteger(), nullable=True),
        sa.Column("total_paid_cents", sa.BigInteger(), nullable=True),
        sa.Column("claim_count", sa.Integer(), nullable=True),
        sa.Column("file_id", sa.String(length=36), nullable=True),
        sa.Column("file_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
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
        sa.CheckConstraint(
            "period_end > period_start", name="ck_loss_runs_period_order"
        ),
    )
    op.create_index("ix_loss_runs_tenant_id", "loss_runs", ["tenant_id"])
    op.create_index("ix_loss_runs_supplier_id", "loss_runs", ["supplier_id"])
    op.create_index(
        "ix_loss_runs_tenant_supplier", "loss_runs", ["tenant_id", "supplier_id"]
    )
    op.create_index(
        "ix_loss_runs_period_end", "loss_runs", ["tenant_id", "period_end"]
    )

    # -------------------------------------------------------------------
    # producer_licenses
    # -------------------------------------------------------------------
    op.create_table(
        "producer_licenses",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            sa.String(length=36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            sa.String(length=36),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("license_number", sa.String(length=64), nullable=False),
        sa.Column(
            "license_type",
            sa.String(length=32),
            nullable=False,
            server_default="resident_producer",
        ),
        sa.Column("licensee_name", sa.String(length=255), nullable=False),
        sa.Column("npn", sa.String(length=16), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=False),
        sa.Column("lines_authorized", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
        sa.Column("file_id", sa.String(length=36), nullable=True),
        sa.Column("file_sha256", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
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
        sa.CheckConstraint(
            "expiration_date > effective_date",
            name="ck_producer_licenses_period_order",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "supplier_id",
            "state",
            "license_number",
            name="uq_producer_licenses_tenant_supplier_state_number",
        ),
    )
    op.create_index(
        "ix_producer_licenses_tenant_id", "producer_licenses", ["tenant_id"]
    )
    op.create_index(
        "ix_producer_licenses_supplier_id", "producer_licenses", ["supplier_id"]
    )
    op.create_index("ix_producer_licenses_npn", "producer_licenses", ["npn"])
    op.create_index(
        "ix_producer_licenses_tenant_expiration",
        "producer_licenses",
        ["tenant_id", "expiration_date"],
    )

    # -------------------------------------------------------------------
    # eo_certificates
    # -------------------------------------------------------------------
    op.create_table(
        "eo_certificates",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            sa.String(length=36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            sa.String(length=36),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("carrier_name", sa.String(length=255), nullable=False),
        sa.Column("policy_number", sa.String(length=64), nullable=False),
        sa.Column("coverage_amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("aggregate_amount_cents", sa.BigInteger(), nullable=True),
        sa.Column("deductible_cents", sa.BigInteger(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=False),
        sa.Column("named_insured", sa.String(length=255), nullable=False),
        sa.Column("additional_insureds", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
        sa.Column("file_id", sa.String(length=36), nullable=True),
        sa.Column("file_sha256", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
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
        sa.CheckConstraint(
            "expiration_date > effective_date",
            name="ck_eo_certificates_period_order",
        ),
        sa.CheckConstraint(
            "coverage_amount_cents >= 0",
            name="ck_eo_certificates_coverage_nonneg",
        ),
    )
    op.create_index(
        "ix_eo_certificates_tenant_id", "eo_certificates", ["tenant_id"]
    )
    op.create_index(
        "ix_eo_certificates_supplier_id", "eo_certificates", ["supplier_id"]
    )
    op.create_index(
        "ix_eo_certificates_tenant_supplier",
        "eo_certificates",
        ["tenant_id", "supplier_id"],
    )
    op.create_index(
        "ix_eo_certificates_tenant_expiration",
        "eo_certificates",
        ["tenant_id", "expiration_date"],
    )

    # -------------------------------------------------------------------
    # acord_forms
    # -------------------------------------------------------------------
    op.create_table(
        "acord_forms",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            sa.String(length=36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            sa.String(length=36),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("form_type", sa.String(length=16), nullable=False),
        sa.Column(
            "form_version",
            sa.String(length=16),
            nullable=False,
            server_default="current",
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("pdf_file_id", sa.String(length=36), nullable=True),
        sa.Column("pdf_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "superseded_by_id",
            sa.String(length=36),
            sa.ForeignKey("acord_forms.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
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
    )
    op.create_index("ix_acord_forms_tenant_id", "acord_forms", ["tenant_id"])
    op.create_index("ix_acord_forms_supplier_id", "acord_forms", ["supplier_id"])
    op.create_index(
        "ix_acord_forms_payload_hash", "acord_forms", ["payload_hash"]
    )
    op.create_index(
        "ix_acord_forms_tenant_supplier_type_status",
        "acord_forms",
        ["tenant_id", "supplier_id", "form_type", "status"],
    )

    # -------------------------------------------------------------------
    # risk_schedules
    # -------------------------------------------------------------------
    op.create_table(
        "risk_schedules",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            sa.String(length=36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            sa.String(length=36),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_of_business", sa.String(length=64), nullable=False),
        sa.Column("schedule_type", sa.String(length=32), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("total_value_cents", sa.BigInteger(), nullable=True),
        sa.Column(
            "item_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("items_hash", sa.String(length=64), nullable=False),
        sa.Column("source_file_id", sa.String(length=36), nullable=True),
        sa.Column("source_file_sha256", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
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
        sa.CheckConstraint(
            "expiration_date IS NULL OR expiration_date > effective_date",
            name="ck_risk_schedules_period_order",
        ),
        sa.CheckConstraint(
            "item_count >= 0", name="ck_risk_schedules_item_count_nonneg"
        ),
    )
    op.create_index(
        "ix_risk_schedules_tenant_id", "risk_schedules", ["tenant_id"]
    )
    op.create_index(
        "ix_risk_schedules_supplier_id", "risk_schedules", ["supplier_id"]
    )
    op.create_index(
        "ix_risk_schedules_items_hash", "risk_schedules", ["items_hash"]
    )
    op.create_index(
        "ix_risk_schedules_tenant_supplier_lob",
        "risk_schedules",
        ["tenant_id", "supplier_id", "line_of_business"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_risk_schedules_tenant_supplier_lob", table_name="risk_schedules"
    )
    op.drop_index("ix_risk_schedules_items_hash", table_name="risk_schedules")
    op.drop_index("ix_risk_schedules_supplier_id", table_name="risk_schedules")
    op.drop_index("ix_risk_schedules_tenant_id", table_name="risk_schedules")
    op.drop_table("risk_schedules")

    op.drop_index(
        "ix_acord_forms_tenant_supplier_type_status", table_name="acord_forms"
    )
    op.drop_index("ix_acord_forms_payload_hash", table_name="acord_forms")
    op.drop_index("ix_acord_forms_supplier_id", table_name="acord_forms")
    op.drop_index("ix_acord_forms_tenant_id", table_name="acord_forms")
    op.drop_table("acord_forms")

    op.drop_index(
        "ix_eo_certificates_tenant_expiration", table_name="eo_certificates"
    )
    op.drop_index(
        "ix_eo_certificates_tenant_supplier", table_name="eo_certificates"
    )
    op.drop_index("ix_eo_certificates_supplier_id", table_name="eo_certificates")
    op.drop_index("ix_eo_certificates_tenant_id", table_name="eo_certificates")
    op.drop_table("eo_certificates")

    op.drop_index(
        "ix_producer_licenses_tenant_expiration", table_name="producer_licenses"
    )
    op.drop_index("ix_producer_licenses_npn", table_name="producer_licenses")
    op.drop_index(
        "ix_producer_licenses_supplier_id", table_name="producer_licenses"
    )
    op.drop_index(
        "ix_producer_licenses_tenant_id", table_name="producer_licenses"
    )
    op.drop_table("producer_licenses")

    op.drop_index("ix_loss_runs_period_end", table_name="loss_runs")
    op.drop_index("ix_loss_runs_tenant_supplier", table_name="loss_runs")
    op.drop_index("ix_loss_runs_supplier_id", table_name="loss_runs")
    op.drop_index("ix_loss_runs_tenant_id", table_name="loss_runs")
    op.drop_table("loss_runs")
