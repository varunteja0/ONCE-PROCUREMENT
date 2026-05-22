"""Pydantic schemas for the ProducerLicense API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.producer_license import LicenseStatus, LicenseType

__all__ = [
    "ProducerLicenseBase",
    "ProducerLicenseCreate",
    "ProducerLicenseUpdate",
    "ProducerLicenseRead",
    "ProducerLicenseList",
]


_US_STATES: frozenset[str] = frozenset(
    {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        "DC", "PR", "VI", "GU", "AS", "MP",
    }
)

_HEX64 = r"^[0-9a-f]{64}$"
_NPN_PATTERN = r"^\d{1,16}$"


def _validate_state(value: str) -> str:
    if value is None:
        return value
    upper = value.strip().upper()
    if upper not in _US_STATES:
        raise ValueError(f"invalid US state code: {value!r}")
    return upper


class ProducerLicenseBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    state: str = Field(min_length=2, max_length=2)
    license_number: str = Field(min_length=1, max_length=64)
    license_type: LicenseType = LicenseType.RESIDENT_PRODUCER
    licensee_name: str = Field(min_length=1, max_length=255)
    npn: str | None = Field(default=None, pattern=_NPN_PATTERN)
    effective_date: date
    expiration_date: date
    lines_authorized: list[str] | None = None
    status: LicenseStatus = LicenseStatus.ACTIVE
    file_id: str | None = Field(default=None, max_length=36)
    file_sha256: str | None = Field(default=None, pattern=_HEX64)
    metadata_json: dict[str, Any] | None = None

    @field_validator("state")
    @classmethod
    def _state_must_be_us(cls, value: str) -> str:
        return _validate_state(value)


class ProducerLicenseCreate(ProducerLicenseBase):
    supplier_id: str = Field(min_length=1, max_length=36)

    @model_validator(mode="after")
    def _check_period(self) -> ProducerLicenseCreate:
        if self.expiration_date <= self.effective_date:
            raise ValueError("expiration_date must be after effective_date")
        return self


class ProducerLicenseUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    state: str | None = Field(default=None, min_length=2, max_length=2)
    license_number: str | None = Field(default=None, min_length=1, max_length=64)
    license_type: LicenseType | None = None
    licensee_name: str | None = Field(default=None, min_length=1, max_length=255)
    npn: str | None = Field(default=None, pattern=_NPN_PATTERN)
    effective_date: date | None = None
    expiration_date: date | None = None
    lines_authorized: list[str] | None = None
    status: LicenseStatus | None = None
    file_id: str | None = Field(default=None, max_length=36)
    file_sha256: str | None = Field(default=None, pattern=_HEX64)
    metadata_json: dict[str, Any] | None = None

    @field_validator("state")
    @classmethod
    def _state_must_be_us(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_state(value)

    @model_validator(mode="after")
    def _check_period(self) -> ProducerLicenseUpdate:
        if (
            self.effective_date is not None
            and self.expiration_date is not None
            and self.expiration_date <= self.effective_date
        ):
            raise ValueError("expiration_date must be after effective_date")
        return self


class ProducerLicenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    supplier_id: str
    state: str
    license_number: str
    license_type: str
    licensee_name: str
    npn: str | None = None
    effective_date: date
    expiration_date: date
    lines_authorized: list[str] | None = None
    status: str
    file_id: str | None = None
    file_sha256: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class ProducerLicenseList(BaseModel):
    items: list[ProducerLicenseRead]
    total: int
    limit: int
    offset: int
