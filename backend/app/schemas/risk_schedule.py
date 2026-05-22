"""Pydantic schemas for the RiskSchedule API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.loss_run import LineOfBusiness

__all__ = [
    "RiskScheduleBase",
    "RiskScheduleCreate",
    "RiskScheduleUpdate",
    "RiskScheduleRead",
    "RiskScheduleList",
]


_HEX64 = r"^[0-9a-f]{64}$"


class RiskScheduleBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    line_of_business: LineOfBusiness
    schedule_type: str = Field(min_length=1, max_length=32)
    effective_date: date
    expiration_date: date | None = None
    total_value_cents: int | None = Field(default=None, ge=0)
    items: list[dict[str, Any]] = Field(min_length=0)
    source_file_id: str | None = Field(default=None, max_length=36)
    source_file_sha256: str | None = Field(default=None, pattern=_HEX64)
    metadata_json: dict[str, Any] | None = None


class RiskScheduleCreate(RiskScheduleBase):
    supplier_id: str = Field(min_length=1, max_length=36)

    @model_validator(mode="after")
    def _check_period(self) -> RiskScheduleCreate:
        if (
            self.expiration_date is not None
            and self.expiration_date <= self.effective_date
        ):
            raise ValueError("expiration_date must be after effective_date")
        return self


class RiskScheduleUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    line_of_business: LineOfBusiness | None = None
    schedule_type: str | None = Field(default=None, min_length=1, max_length=32)
    effective_date: date | None = None
    expiration_date: date | None = None
    total_value_cents: int | None = Field(default=None, ge=0)
    items: list[dict[str, Any]] | None = None
    source_file_id: str | None = Field(default=None, max_length=36)
    source_file_sha256: str | None = Field(default=None, pattern=_HEX64)
    metadata_json: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _check_period(self) -> RiskScheduleUpdate:
        if (
            self.effective_date is not None
            and self.expiration_date is not None
            and self.expiration_date <= self.effective_date
        ):
            raise ValueError("expiration_date must be after effective_date")
        return self


class RiskScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    supplier_id: str
    line_of_business: str
    schedule_type: str
    effective_date: date
    expiration_date: date | None = None
    total_value_cents: int | None = None
    item_count: int
    items: list[dict[str, Any]]
    items_hash: str
    source_file_id: str | None = None
    source_file_sha256: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class RiskScheduleList(BaseModel):
    items: list[RiskScheduleRead]
    total: int
    limit: int
    offset: int
