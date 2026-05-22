"""Merge L3 application schema into canonical Alembic history.

Revision ID: 20260523_03_merge_l3_application_schema
Revises: 20260521_03_onboarding, 20260523_02_verifier_api_key_usage
Create Date: 2026-05-23 00:00:02.000000

This reconciles the application-schema work that was previously parked under
``backend/app/alembic/versions`` into the single production Alembic chain.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260523_03_merge_l3_application_schema"
down_revision: Union[str, Sequence[str], None] = (
    "20260521_03_onboarding",
    "20260523_02_verifier_api_key_usage",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inbound_emails",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("message_id", sa.String(length=998), nullable=False),
        sa.Column("in_reply_to", sa.String(length=998), nullable=True),
        sa.Column("from_address", sa.String(length=320), nullable=False, index=True),
        sa.Column("from_name", sa.String(length=255), nullable=True),
        sa.Column("to_address", sa.String(length=320), nullable=False, index=True),
        sa.Column("cc_addresses", sa.JSON(), nullable=True),
        sa.Column("subject", sa.String(length=998), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("raw_body_text", sa.Text(), nullable=True),
        sa.Column("raw_body_html", sa.Text(), nullable=True),
        sa.Column("headers", sa.JSON(), nullable=True),
        sa.Column("spam_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="received", index=True),
        sa.Column("routing_error", sa.Text(), nullable=True),
        sa.Column("attachment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("draft_submission_id", sa.String(length=36), sa.ForeignKey("supplier_submissions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("draft_supplier_id", sa.String(length=36), sa.ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("raw_storage_url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("message_id", name="uq_inbound_emails_message_id"),
    )
    op.create_index("ix_inbound_emails_tenant_status", "inbound_emails", ["tenant_id", "status"])
    op.create_index("ix_inbound_emails_tenant_received", "inbound_emails", ["tenant_id", "received_at"])

    op.create_table(
        "inbound_attachments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("inbound_email_id", sa.String(length=36), sa.ForeignKey("inbound_emails.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_url", sa.String(length=1024), nullable=False),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_inbound_attachments_email", "inbound_attachments", ["inbound_email_id"])
    op.create_index("ix_inbound_attachments_sha256", "inbound_attachments", ["sha256"])

    op.create_table(
        "inbound_routing_rules",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("match_from_domain", sa.String(length=255), nullable=True),
        sa.Column("match_subject_regex", sa.String(length=1024), nullable=True),
        sa.Column("match_attachment_kind", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False, server_default="create_submission"),
        sa.Column("action_params", sa.JSON(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_inbound_rules_tenant_priority", "inbound_routing_rules", ["tenant_id", "priority"])
    op.create_index("ix_inbound_rules_tenant_active", "inbound_routing_rules", ["tenant_id", "active"])

    op.create_table(
        "extraction_results",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_document_type", sa.String(length=32), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("raw_text_url", sa.String(length=1024), nullable=True),
        sa.Column("extracted_fields", sa.JSON(), nullable=True),
        sa.Column("field_confidences", sa.JSON(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("extractor_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_extraction_results_tenant_source", "extraction_results", ["tenant_id", "source_document_type", "source_document_id"])
    op.create_index("ix_extraction_results_tenant_status", "extraction_results", ["tenant_id", "status"])

    op.create_table(
        "import_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("entity_type", sa.String(length=32), nullable=False, index=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending", index=True),
        sa.Column("file_url", sa.String(length=1024), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_report_url", sa.String(length=1024), nullable=True),
        sa.Column("mapping", sa.JSON(), nullable=True),
        sa.Column("on_duplicate", sa.String(length=16), nullable=False, server_default="error"),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.String(length=2000), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "import_row_errors",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("import_job_id", sa.String(length=36), sa.ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("row_number", sa.Integer(), nullable=False, index=True),
        sa.Column("column", sa.String(length=128), nullable=True),
        sa.Column("value", sa.String(length=200), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=False, index=True),
        sa.Column("error_message", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "audit_trail",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=True),
        sa.Column("actor_email", sa.String(length=320), nullable=True),
        sa.Column("action_verb", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("resource_label", sa.String(length=512), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("payload_summary", sa.JSON(), nullable=True),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("this_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("chain_position", sa.Integer(), nullable=False),
        sa.Column("signature_key_id", sa.String(length=64), nullable=True),
        sa.Column("signature_b64", sa.String(length=255), nullable=True),
        sa.CheckConstraint("length(this_hash) = 64", name="ck_audit_trail_this_hash_hex64"),
        sa.CheckConstraint("length(prev_hash) = 64", name="ck_audit_trail_prev_hash_hex64"),
    )
    op.create_index("ix_audit_trail_tenant_occurred", "audit_trail", ["tenant_id", "occurred_at"])
    op.create_index("ix_audit_trail_tenant_position", "audit_trail", ["tenant_id", "chain_position"], unique=True)
    op.create_index("ix_audit_trail_resource", "audit_trail", ["tenant_id", "resource_type", "resource_id"])
    op.create_index("ix_audit_trail_actor", "audit_trail", ["tenant_id", "actor_type", "occurred_at"])
    op.create_index("ix_audit_trail_action", "audit_trail", ["tenant_id", "action_verb", "occurred_at"])

    op.create_table(
        "audit_exports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_params", sa.JSON(), nullable=True),
        sa.Column("requested_by_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("file_sha256", sa.String(length=64), nullable=True),
        sa.Column("signed_envelope_path", sa.String(length=1024), nullable=True),
        sa.Column("envelope_sha256", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_audit_exports_tenant_requested", "audit_exports", ["tenant_id", "requested_at"])
    op.create_index("ix_audit_exports_tenant_status", "audit_exports", ["tenant_id", "status"])

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("""
            CREATE TRIGGER trg_audit_trail_no_update
            BEFORE UPDATE ON audit_trail
            BEGIN
                SELECT RAISE(ABORT, 'audit_trail is append-only');
            END;
            """)
        op.execute("""
            CREATE TRIGGER trg_audit_trail_no_delete
            BEFORE DELETE ON audit_trail
            BEGIN
                SELECT RAISE(ABORT, 'audit_trail is append-only');
            END;
            """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_audit_trail_no_delete")
        op.execute("DROP TRIGGER IF EXISTS trg_audit_trail_no_update")

    op.drop_index("ix_audit_exports_tenant_status", table_name="audit_exports")
    op.drop_index("ix_audit_exports_tenant_requested", table_name="audit_exports")
    op.drop_table("audit_exports")
    op.drop_index("ix_audit_trail_action", table_name="audit_trail")
    op.drop_index("ix_audit_trail_actor", table_name="audit_trail")
    op.drop_index("ix_audit_trail_resource", table_name="audit_trail")
    op.drop_index("ix_audit_trail_tenant_position", table_name="audit_trail")
    op.drop_index("ix_audit_trail_tenant_occurred", table_name="audit_trail")
    op.drop_table("audit_trail")
    op.drop_table("import_row_errors")
    op.drop_table("import_jobs")
    op.drop_index("ix_extraction_results_tenant_status", table_name="extraction_results")
    op.drop_index("ix_extraction_results_tenant_source", table_name="extraction_results")
    op.drop_table("extraction_results")
    op.drop_index("ix_inbound_rules_tenant_active", table_name="inbound_routing_rules")
    op.drop_index("ix_inbound_rules_tenant_priority", table_name="inbound_routing_rules")
    op.drop_table("inbound_routing_rules")
    op.drop_index("ix_inbound_attachments_sha256", table_name="inbound_attachments")
    op.drop_index("ix_inbound_attachments_email", table_name="inbound_attachments")
    op.drop_table("inbound_attachments")
    op.drop_index("ix_inbound_emails_tenant_received", table_name="inbound_emails")
    op.drop_index("ix_inbound_emails_tenant_status", table_name="inbound_emails")
    op.drop_table("inbound_emails")
