from __future__ import annotations

from app.models.acord_form import AcordForm, AcordFormStatus, AcordFormType
from app.models.audit import AuditLog
from app.models.audit_export import (
    AuditExport,
    AuditExportScope,
    AuditExportStatus,
)

# --- /L3.9 inbound ---
# --- L3.10 audit ---
# Tamper-evident tenant audit trail. Lives alongside the legacy ``audit_logs``
# (kept for the L3.4 nightly hash-digest job); the new model uses table
# ``audit_trail`` and a richer schema with chain hashes + ULID PKs.
from app.models.audit_log import AuditActorType, AuditLogEntry
from app.models.base import Base, TenantScopedMixin, TimestampMixin
from app.models.billing import (
    BillingCustomer,
    BillingEvent,
    BillingInvoice,
    BillingPriceConfig,
    BillingSubscription,
    InvoiceStatus,
    PriceKey,
    SubscriptionStatus,
)
from app.models.cockpit_audit import CockpitAudit
from app.models.coi import CertificateOfInsurance
from app.models.compliance import AuditHashDigest, KeyRotationLog
from app.models.consent import ConsentRecord, ConsentScope
from app.models.email_verification import EmailVerification
from app.models.eo_certificate import EOCertificate, EOCertificateStatus

# --- L3.8 pdf extraction ---
from app.models.extraction_result import (
    ExtractionResult,
    ExtractionSourceType,
    ExtractionStatus,
)

# --- /L3.8 pdf extraction ---
# --- L3.7 imports ---
from app.models.import_job import ImportEntityType, ImportJob, ImportStatus
from app.models.import_row_error import ImportRowError
from app.models.inbound_attachment import InboundAttachment

# --- L3.9 inbound ---
from app.models.inbound_email import InboundEmail, InboundEmailStatus
from app.models.inbound_routing_rule import InboundRoutingRule, InboundRuleAction
from app.models.loss_run import LineOfBusiness, LossRun, LossRunStatus

# --- /L3.7 imports ---
from app.models.onboarding import OnboardingState, OnboardingStep
from app.models.operator import (
    Operator,
    OperatorRole,
    OperatorStatus,
    OperatorTenantGrant,
)
from app.models.operator_recovery_code import OperatorRecoveryCode
from app.models.operator_session import OperatorSession
from app.models.portal import Portal, PortalPlatform
from app.models.producer_license import (
    LicenseStatus,
    LicenseType,
    ProducerLicense,
)
from app.models.receipt import SubmissionReceipt
from app.models.risk_schedule import RiskSchedule
from app.models.signing_key import SigningKey
from app.models.submission import SubmissionStatus, SupplierSubmission
from app.models.supplier import Supplier
from app.models.tenant import Tenant, TenantUser
from app.models.user import User
from app.models.verifier_api_key import VerifierApiKey
from app.models.verifier_api_key_usage import VerifierApiKeyUsage

# --- /L3.10 audit ---

__all__ = [
    "Base",
    "TimestampMixin",
    "TenantScopedMixin",
    "Tenant",
    "TenantUser",
    "User",
    "Supplier",
    "Portal",
    "PortalPlatform",
    "SupplierSubmission",
    "SubmissionStatus",
    "SubmissionReceipt",
    "SigningKey",
    "ConsentRecord",
    "ConsentScope",
    "EmailVerification",
    "ImportJob",
    "ImportEntityType",
    "ImportStatus",
    "ImportRowError",
    "OnboardingState",
    "OnboardingStep",
    "CertificateOfInsurance",
    "AuditLog",
    "CockpitAudit",
    "Operator",
    "OperatorRole",
    "OperatorStatus",
    "OperatorTenantGrant",
    "OperatorSession",
    "OperatorRecoveryCode",
    "LossRun",
    "LossRunStatus",
    "LineOfBusiness",
    "ProducerLicense",
    "LicenseStatus",
    "LicenseType",
    "EOCertificate",
    "EOCertificateStatus",
    "AcordForm",
    "AcordFormStatus",
    "AcordFormType",
    "RiskSchedule",
    "AuditHashDigest",
    "KeyRotationLog",
    "BillingCustomer",
    "BillingSubscription",
    "BillingInvoice",
    "BillingEvent",
    "BillingPriceConfig",
    "SubscriptionStatus",
    "InvoiceStatus",
    "PriceKey",
    "ExtractionResult",
    "ExtractionSourceType",
    "ExtractionStatus",
    "VerifierApiKey",
    "VerifierApiKeyUsage",
    "InboundEmail",
    "InboundEmailStatus",
    "InboundAttachment",
    "InboundRoutingRule",
    "InboundRuleAction",
    # --- L3.10 audit ---
    "AuditLogEntry",
    "AuditActorType",
    "AuditExport",
    "AuditExportScope",
    "AuditExportStatus",
    # --- /L3.10 audit ---
]
