"""Pydantic schemas for the LossRun API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.loss_run import LineOfBusiness, LossRunStatus

__all__ = [
    "LossRunBase",
    "LossRunCreate",
    "LossRunUpdate",
    "LossRunRead",
    "LossRunList",
]


_HEX64 = r"^[0-9a-f]{64}$"


class LossRunBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    period_start: date
    period_end: date
    carrier_name: str = Field(min_length=1, max_length=255)
    line_of_business: LineOfBusiness
    total_premium_cents: int | None = Field(default=None, ge=0)
    total_incurred_cents: int | None = Field(default=None, ge=0)
    total_paid_cents: int | None = Field(default=None, ge=0)
    claim_count: int | None = Field(default=None, ge=0)
    file_id: str | None = Field(default=None, max_length=36)
    file_sha256: str | None = Field(default=None, pattern=_HEX64)
    metadata_json: dict[str, Any] | None = None


class LossRunCreate(LossRunBase):
    supplier_id: str = Field(min_length=1, max_length=36)
    status: LossRunStatus = LossRunStatus.UPLOADED

    @model_validator(mode="after")
    def _check_period(self) -> LossRunCreate:
        if self.period_end <= self.period_start:
            raise ValueError("period_end must be after period_start")
        return self


class LossRunUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    period_start: date | None = None
    period_end: date | None = None
    carrier_name: str | None = Field(default=None, min_length=1, max_length=255)
    line_of_business: LineOfBusiness | None = None
    total_premium_cents: int | None = Field(default=None, ge=0)
    total_incurred_cents: int | None = Field(default=None, ge=0)
    total_paid_cents: int | None = Field(default=None, ge=0)
    claim_count: int | None = Field(default=None, ge=0)
    file_id: str | None = Field(default=None, max_length=36)
    file_sha256: str | None = Field(default=None, pattern=_HEX64)
    status: LossRunStatus | None = None
    parsed_at: datetime | None = None
    parse_error: str | None = Field(default=None, max_length=10_000)
    metadata_json: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _check_period(self) -> LossRunUpdate:
        if (
            self.period_start is not None
            and self.period_end is not None
            and self.period_end <= self.period_start
        ):
            raise ValueError("period_end must be after period_start")
        return self

    @field_validator("line_of_business", mode="before")
    @classmethod
    def _coerce_lob(cls, value: Any) -> Any:
        if value is None or isinstance(value, LineOfBusiness):
            return value
        try:
            return LineOfBusiness(value)
        except ValueError as exc:
            raise ValueError(f"invalid line_of_business: {value!r}") from exc


class LossRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    supplier_id: str
    period_start: date
    period_end: date
    carrier_name: str
    line_of_business: str
    total_premium_cents: int | None = None
    total_incurred_cents: int | None = None
    total_paid_cents: int | None = None
    claim_count: int | None = None
    file_id: str | None = None
    file_sha256: str | None = None
    status: str
    parsed_at: datetime | None = None
    parse_error: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class LossRunList(BaseModel):
    items: list[LossRunRead]
    total: int
    limit: int
    offset: int
