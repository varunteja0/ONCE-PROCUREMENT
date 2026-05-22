from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "TokenPair",
    "RefreshRequest",
    "UserMe",
]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    full_name: str = Field(min_length=1, max_length=255)
    tenant_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class UserMe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    full_name: str | None = None
    tenant_id: str
    role: str
