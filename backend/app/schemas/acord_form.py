"""Pydantic schemas for the AcordForm API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.acord_form import AcordFormStatus, AcordFormType

__all__ = [
    "AcordFormBase",
    "AcordFormCreate",
    "AcordFormUpdate",
    "AcordFormRead",
    "AcordFormList",
]


_HEX64 = r"^[0-9a-f]{64}$"


class AcordFormBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    form_type: AcordFormType
    form_version: str = Field(default="current", min_length=1, max_length=16)
    payload: dict[str, Any] = Field(min_length=1)
    effective_date: date | None = None
    expiration_date: date | None = None
    pdf_file_id: str | None = Field(default=None, max_length=36)
    pdf_sha256: str | None = Field(default=None, pattern=_HEX64)
    status: AcordFormStatus = AcordFormStatus.DRAFT
    metadata_json: dict[str, Any] | None = None


class AcordFormCreate(AcordFormBase):
    supplier_id: str = Field(min_length=1, max_length=36)
    superseded_by_id: str | None = Field(default=None, max_length=36)

    @model_validator(mode="after")
    def _check_period(self) -> AcordFormCreate:
        if (
            self.effective_date is not None
            and self.expiration_date is not None
            and self.expiration_date <= self.effective_date
        ):
            raise ValueError("expiration_date must be after effective_date")
        return self


class AcordFormUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    form_type: AcordFormType | None = None
    form_version: str | None = Field(default=None, min_length=1, max_length=16)
    payload: dict[str, Any] | None = Field(default=None, min_length=1)
    effective_date: date | None = None
    expiration_date: date | None = None
    pdf_file_id: str | None = Field(default=None, max_length=36)
    pdf_sha256: str | None = Field(default=None, pattern=_HEX64)
    status: AcordFormStatus | None = None
    superseded_by_id: str | None = Field(default=None, max_length=36)
    metadata_json: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _check_period(self) -> AcordFormUpdate:
        if (
            self.effective_date is not None
            and self.expiration_date is not None
            and self.expiration_date <= self.effective_date
        ):
            raise ValueError("expiration_date must be after effective_date")
        return self


class AcordFormRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    supplier_id: str
    form_type: str
    form_version: str
    payload: dict[str, Any]
    payload_hash: str
    effective_date: date | None = None
    expiration_date: date | None = None
    pdf_file_id: str | None = None
    pdf_sha256: str | None = None
    status: str
    superseded_by_id: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class AcordFormList(BaseModel):
    items: list[AcordFormRead]
    total: int
    limit: int
    offset: int
