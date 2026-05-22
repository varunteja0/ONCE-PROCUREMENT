"""Pydantic schemas for the L3.6 self-serve onboarding wizard."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.onboarding import OnboardingStep

__all__ = [
    "OnboardingStartRequest",
    "OnboardingStartResponse",
    "VerifyEmailRequest",
    "VerifyEmailResponse",
    "CompanyProfileRequest",
    "ConnectPortalRequest",
    "AddSupplierRequest",
    "RunFirstSubmissionRequest",
    "SkipStepRequest",
    "OnboardingStateRead",
    "OnboardingCompleteResponse",
    "SkippableStep",
]


# Only the steps after EMAIL_VERIFIED may be skipped.
SkippableStep = Literal["plan", "portal", "supplier", "submission"]


class OnboardingStartRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    company_name: str = Field(min_length=1, max_length=255)
    # Honeypot — silent reject when populated by bots.
    website_url: str | None = Field(default=None, max_length=512)


class OnboardingStartResponse(BaseModel):
    onboarding_session_token: str
    tenant_id: str
    expires_in_seconds: int
    # In ``app_env=development`` the verification code is also returned so a
    # founder can pair-program the flow without scanning .eml files. Always
    # ``None`` outside development.
    dev_verification_code: str | None = None


class VerifyEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=4, max_length=12)


class VerifyEmailResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    tenant_id: str
    current_step: OnboardingStep


class CompanyProfileRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    legal_name: str = Field(min_length=1, max_length=255)
    fein: str = Field(min_length=9, max_length=32, description="Federal EIN.")
    naic_code: str | None = Field(default=None, max_length=16)
    primary_state: str = Field(min_length=2, max_length=2)
    employees: int | None = Field(default=None, ge=0, le=1_000_000)
    gwp_band: str | None = Field(default=None, max_length=64)
    role_in_mga: str | None = Field(default=None, max_length=128)


class ConnectPortalRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    portal_id: str = Field(min_length=1, max_length=36)
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=512)


class AddSupplierRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    legal_name: str = Field(min_length=1, max_length=255)
    fein: str | None = Field(default=None, max_length=32)
    state: str = Field(min_length=2, max_length=2)
    primary_email: EmailStr | None = None


class RunFirstSubmissionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    supplier_id: str = Field(min_length=1, max_length=36)
    portal_id: str = Field(min_length=1, max_length=36)


class SkipStepRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: SkippableStep


class OnboardingStateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: str
    current_step: OnboardingStep
    completed_steps: dict[str, Any] = Field(default_factory=dict)
    skipped_steps: dict[str, Any] = Field(default_factory=dict)
    company_profile_json: dict[str, Any] | None = None
    started_at: datetime
    last_activity_at: datetime
    completed_at: datetime | None = None


class OnboardingCompleteResponse(BaseModel):
    tenant_id: str
    dashboard_url: str
    current_step: OnboardingStep


class SubmissionPollRead(BaseModel):
    """Returned by ``POST /run-first-submission`` and the subsequent poll."""

    submission_id: str
    status: str
