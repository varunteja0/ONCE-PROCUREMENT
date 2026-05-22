from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

__all__ = [
    "SupplierCreate",
    "SupplierUpdate",
    "SupplierRead",
    "SupplierListItem",
]


class _SupplierBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    legal_name: str = Field(min_length=1, max_length=255)
    dba_name: str | None = Field(default=None, max_length=255)
    ein: str | None = Field(default=None, max_length=32)
    naics_code: str | None = Field(default=None, max_length=16)
    primary_email: EmailStr | None = None
    primary_phone: str | None = Field(default=None, max_length=32)
    address_json: dict[str, Any] | None = None
    website: HttpUrl | None = None


class SupplierCreate(_SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    legal_name: str | None = Field(default=None, min_length=1, max_length=255)
    dba_name: str | None = Field(default=None, max_length=255)
    ein: str | None = Field(default=None, max_length=32)
    naics_code: str | None = Field(default=None, max_length=16)
    primary_email: EmailStr | None = None
    primary_phone: str | None = Field(default=None, max_length=32)
    address_json: dict[str, Any] | None = None
    website: HttpUrl | None = None


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    legal_name: str
    dba_name: str | None = None
    ein: str | None = None
    naics_code: str | None = None
    primary_email: str | None = None
    primary_phone: str | None = None
    address_json: dict[str, Any] | None = None
    website: str | None = None
    created_at: datetime
    updated_at: datetime


class SupplierListItem(BaseModel):
    """Lightweight projection for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    legal_name: str
    dba_name: str | None = None
    primary_email: str | None = None
    created_at: datetime
