from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["TenantRead", "TenantUpdate"]


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    plan: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TenantUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    plan: str | None = Field(default=None, min_length=1, max_length=32)
