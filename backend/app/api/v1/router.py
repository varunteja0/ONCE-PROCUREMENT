from __future__ import annotations

from fastapi import APIRouter

from .acord_forms import router as acord_forms_router
from .auth import router as auth_router
from .billing import router as billing_router
from .consents import router as consents_router
from .eo_certificates import router as eo_certificates_router
from .health import router as health_router
from .loss_runs import router as loss_runs_router
from .portals import router as portals_router
from .producer_licenses import router as producer_licenses_router
from .public_keys import router as public_keys_router
from .receipts import public_receipt_router
from .receipts import router as receipts_router
from .risk_schedules import router as risk_schedules_router
from .security import router as security_router
from .submissions import router as submissions_router
from .suppliers import router as suppliers_router
from .tenants import router as tenants_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(tenants_router)
api_router.include_router(suppliers_router)
api_router.include_router(portals_router)
api_router.include_router(submissions_router)
api_router.include_router(consents_router)
api_router.include_router(receipts_router)
api_router.include_router(public_keys_router)
api_router.include_router(loss_runs_router)
api_router.include_router(producer_licenses_router)
api_router.include_router(eo_certificates_router)
api_router.include_router(acord_forms_router)
api_router.include_router(risk_schedules_router)
api_router.include_router(security_router)

# --- L3.5 billing ---
api_router.include_router(billing_router)
# --- /L3.5 billing ---

# --- L3.6 onboarding ---
from .onboarding import router as onboarding_router  # noqa: E402

api_router.include_router(onboarding_router)
# --- /L3.6 onboarding ---

# --- L3.7 imports ---
from .imports import router as imports_router  # noqa: E402

api_router.include_router(imports_router)
# --- /L3.7 imports ---

# --- L3.8 extractions ---
from .extractions import router as extractions_router  # noqa: E402

api_router.include_router(extractions_router)
# --- /L3.8 extractions ---

# --- L6.1 verifier API keys ---
from .verifier_keys import internal_router as verifier_keys_internal_router  # noqa: E402
from .verifier_keys import router as verifier_keys_router  # noqa: E402

api_router.include_router(verifier_keys_router)
api_router.include_router(verifier_keys_internal_router)
# --- /L6.1 verifier API keys ---

# --- L3.9 inbound ---
from .inbound import router as inbound_router  # noqa: E402

api_router.include_router(inbound_router)
# --- /L3.9 inbound ---

# --- L3.10 audit ---
from .audit import router as audit_router  # noqa: E402

api_router.include_router(audit_router)
# --- /L3.10 audit ---

# `public_receipt_router` is registered separately by `app.main` (no /v1 prefix)
# so the public verifier endpoint stays at `/verify/{receipt_id}`.
__all__ = ["api_router", "public_receipt_router"]
