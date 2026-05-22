from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

__all__ = [
    "OperatorRoleLiteral",
    "OperatorStatusLiteral",
    "OperatorRead",
    "OperatorMe",
    "OperatorLoginRequest",
    "OperatorRefreshRequest",
    "OperatorTokenPair",
    "OperatorCreateRequest",
    "OperatorTenantGrantRead",
    "MfaEnrollResponse",
    "MfaConfirmRequest",
    "MfaConfirmResponse",
    "MfaDisableRequest",
    "MfaStatusResponse",
]


OperatorRoleLiteral = Literal["founder", "engineering", "support"]
OperatorStatusLiteral = Literal["active", "suspended"]


class OperatorLoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    totp_code: str | None = Field(default=None, min_length=6, max_length=8)


class OperatorRefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class OperatorTokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int = Field(description="Access token TTL in seconds.")


class OperatorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    role: OperatorRoleLiteral
    status: OperatorStatusLiteral
    mfa_required: bool
    last_login_at: datetime | None = None
    created_at: datetime


class OperatorMe(OperatorRead):
    """Profile returned by /cockpit/auth/me — includes accessible tenant ids."""

    accessible_tenant_ids: list[str] = Field(default_factory=list)
    all_tenants: bool = False


class OperatorCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    role: OperatorRoleLiteral = "support"
    mfa_required: bool = False
    grant_all_tenants: bool = False


class OperatorTenantGrantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    operator_id: str
    tenant_id: str
    permission: str
    created_at: datetime


class MfaEnrollResponse(BaseModel):
    """Returned from POST /cockpit/mfa/enroll. Plaintext secret is shown ONCE."""

    secret: str
    provisioning_uri: str
    qr_svg: str


class MfaConfirmRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str = Field(min_length=6, max_length=8)


class MfaConfirmResponse(BaseModel):
    """Returned from POST /cockpit/mfa/confirm. Recovery codes are shown ONCE."""

    recovery_codes: list[str]


class MfaDisableRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str = Field(min_length=6, max_length=16)


class MfaStatusResponse(BaseModel):
    mfa_required: bool
    enrolled: bool
    unused_recovery_count: int
