"""Pydantic schemas for the EOCertificate API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.eo_certificate import EOCertificateStatus

__all__ = [
    "EOCertificateBase",
    "EOCertificateCreate",
    "EOCertificateUpdate",
    "EOCertificateRead",
    "EOCertificateList",
]


_HEX64 = r"^[0-9a-f]{64}$"


class EOCertificateBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    carrier_name: str = Field(min_length=1, max_length=255)
    policy_number: str = Field(min_length=1, max_length=64)
    coverage_amount_cents: int = Field(ge=0)
    aggregate_amount_cents: int | None = Field(default=None, ge=0)
    deductible_cents: int | None = Field(default=None, ge=0)
    effective_date: date
    expiration_date: date
    named_insured: str = Field(min_length=1, max_length=255)
    additional_insureds: list[str] | None = None
    status: EOCertificateStatus = EOCertificateStatus.ACTIVE
    file_id: str | None = Field(default=None, max_length=36)
    file_sha256: str | None = Field(default=None, pattern=_HEX64)
    metadata_json: dict[str, Any] | None = None


class EOCertificateCreate(EOCertificateBase):
    supplier_id: str = Field(min_length=1, max_length=36)

    @model_validator(mode="after")
    def _check(self) -> EOCertificateCreate:
        if self.expiration_date <= self.effective_date:
            raise ValueError("expiration_date must be after effective_date")
        if (
            self.aggregate_amount_cents is not None
            and self.aggregate_amount_cents < self.coverage_amount_cents
        ):
            raise ValueError(
                "aggregate_amount_cents must be >= coverage_amount_cents"
            )
        return self


class EOCertificateUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    carrier_name: str | None = Field(default=None, min_length=1, max_length=255)
    policy_number: str | None = Field(default=None, min_length=1, max_length=64)
    coverage_amount_cents: int | None = Field(default=None, ge=0)
    aggregate_amount_cents: int | None = Field(default=None, ge=0)
    deductible_cents: int | None = Field(default=None, ge=0)
    effective_date: date | None = None
    expiration_date: date | None = None
    named_insured: str | None = Field(default=None, min_length=1, max_length=255)
    additional_insureds: list[str] | None = None
    status: EOCertificateStatus | None = None
    file_id: str | None = Field(default=None, max_length=36)
    file_sha256: str | None = Field(default=None, pattern=_HEX64)
    metadata_json: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _check_period(self) -> EOCertificateUpdate:
        if (
            self.effective_date is not None
            and self.expiration_date is not None
            and self.expiration_date <= self.effective_date
        ):
            raise ValueError("expiration_date must be after effective_date")
        return self


class EOCertificateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    supplier_id: str
    carrier_name: str
    policy_number: str
    coverage_amount_cents: int
    aggregate_amount_cents: int | None = None
    deductible_cents: int | None = None
    effective_date: date
    expiration_date: date
    named_insured: str
    additional_insureds: list[str] | None = None
    status: str
    file_id: str | None = None
    file_sha256: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class EOCertificateList(BaseModel):
    items: list[EOCertificateRead]
    total: int
    limit: int
    offset: int
