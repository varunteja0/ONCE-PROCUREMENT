from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Final, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

__all__ = [
    "TokenType",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "TokenDecodeError",
]


TokenType = Literal["access", "refresh"]

_ACCESS: Final[TokenType] = "access"
_REFRESH: Final[TokenType] = "refresh"

_pwd_context: CryptContext = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenDecodeError(Exception):
    """Raised when a JWT cannot be decoded or fails validation."""


def hash_password(plain_password: str) -> str:
    if not isinstance(plain_password, str) or plain_password == "":
        raise ValueError("password must be a non-empty string")
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return _pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        return False


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _encode(
    *,
    sub: str,
    tenant_id: str | None,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    issued_at = _now_utc()
    expires_at = issued_at + expires_delta
    payload: dict[str, Any] = {
        "sub": sub,
        "tenant_id": tenant_id,
        "type": token_type,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    if extra_claims:
        for key, value in extra_claims.items():
            if key in {"sub", "exp", "iat", "type"}:
                continue
            payload[key] = value
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(
    sub: str,
    tenant_id: str | None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    return _encode(
        sub=sub,
        tenant_id=tenant_id,
        token_type=_ACCESS,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        extra_claims=extra_claims,
    )


def create_refresh_token(
    sub: str,
    tenant_id: str | None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    return _encode(
        sub=sub,
        tenant_id=tenant_id,
        token_type=_REFRESH,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
        extra_claims=extra_claims,
    )


def decode_token(
    token: str,
    expected_type: TokenType | None = None,
) -> dict[str, Any]:
    if not token or not isinstance(token, str):
        raise TokenDecodeError("token must be a non-empty string")
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise TokenDecodeError(str(exc)) from exc

    if expected_type is not None and payload.get("type") != expected_type:
        raise TokenDecodeError(
            f"unexpected token type: got {payload.get('type')!r}, expected {expected_type!r}"
        )
    if "sub" not in payload or not payload["sub"]:
        raise TokenDecodeError("token missing 'sub' claim")
    return payload
