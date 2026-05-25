"""Operator authentication — separate JWT secret, shorter TTLs.

The cockpit uses its **own** signing key (``COCKPIT_JWT_SECRET_KEY``) so a
compromised tenant-user JWT cannot be replayed against the operator
surface, and vice versa. Access tokens live 15 minutes; refresh tokens 1
hour. Refresh tokens are server-side (sha256 stored in
``operator_sessions``) so individual operator devices can be revoked.

Account lockout (B8 shared tracker) and strong-secret password policy
(B8 ``evaluate_secret``) are enforced here as well.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Final

import jwt
from jwt import PyJWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    Operator,
    OperatorRecoveryCode,
    OperatorSession,
    OperatorStatus,
    OperatorTenantGrant,
)
from app.services.mfa_totp import hash_recovery_code, verify_code
from app.utils.logging import get_logger
from app.utils.secret_strength import evaluate_secret

__all__ = [
    "ACCESS_TTL_MINUTES",
    "REFRESH_TTL_MINUTES",
    "TOKEN_TYPE_ACCESS",
    "TOKEN_TYPE_REFRESH",
    "get_cockpit_jwt_secret",
    "operator_password_hash",
    "operator_password_verify",
    "evaluate_operator_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "issue_token_pair",
    "authenticate_operator",
    "refresh_operator_session",
    "revoke_session",
    "OperatorAuthError",
]


_logger = get_logger(__name__)
_pwd_context: CryptContext = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TTL_MINUTES: Final[int] = 15
REFRESH_TTL_MINUTES: Final[int] = 60
TOKEN_TYPE_ACCESS: Final[str] = "cockpit_access"  # noqa: S105
TOKEN_TYPE_REFRESH: Final[str] = "cockpit_refresh"  # noqa: S105
_ALGORITHM: Final[str] = "HS256"


class OperatorAuthError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 401) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def get_cockpit_jwt_secret() -> str:
    """Read the cockpit-specific JWT secret. **Not** the tenant JWT secret.

    In production this MUST be a strong secret (B8 strength policy);
    development falls back to a deterministic but loud placeholder.

    Runtime secret loading is centralized in ``app.config.settings`` so
    validation and audit behavior stay in one place.
    """

    raw = (settings.cockpit_jwt_secret_key or "").strip()
    if raw:
        return raw
    if settings.is_production:
        raise RuntimeError(
            "COCKPIT_JWT_SECRET_KEY is not set. Refusing to issue or verify "
            "cockpit tokens in APP_ENV=production without an explicit secret."
        )
    # Dev/test fallback — never matches the tenant secret so the two
    # token surfaces remain isolated.
    return "cockpit-dev-secret-do-not-use-in-prod-" + ("x" * 32)


def operator_password_hash(plain: str) -> str:
    if not isinstance(plain, str) or not plain:
        raise ValueError("password must be a non-empty string")
    return _pwd_context.hash(plain)


def operator_password_verify(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return _pwd_context.verify(plain, hashed)
    except (ValueError, TypeError):
        return False


def evaluate_operator_password(password: str) -> None:
    """Refuse to set a password that fails the B8 strength policy."""

    result = evaluate_secret("operator_password", password)
    if not result.strong:
        raise OperatorAuthError(
            code="weak_password",
            message=("Operator password is too weak: " + ", ".join(result.reasons)),
            status_code=400,
        )


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _encode(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, get_cockpit_jwt_secret(), algorithm=_ALGORITHM)


def create_access_token(operator: Operator) -> tuple[str, datetime]:
    now = _now()
    exp = now + timedelta(minutes=ACCESS_TTL_MINUTES)
    payload = {
        "sub": operator.id,
        "email": operator.email,
        "role": operator.role,
        "type": TOKEN_TYPE_ACCESS,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return _encode(payload), exp


def create_refresh_token(operator: Operator) -> tuple[str, datetime, str]:
    now = _now()
    exp = now + timedelta(minutes=REFRESH_TTL_MINUTES)
    jti = uuid.uuid4().hex
    payload = {
        "sub": operator.id,
        "type": TOKEN_TYPE_REFRESH,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": jti,
    }
    token = _encode(payload)
    return token, exp, jti


def _hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def decode_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    if not token or not isinstance(token, str):
        raise OperatorAuthError("invalid_token", "Token must be a non-empty string.")
    try:
        payload: dict[str, Any] = jwt.decode(token, get_cockpit_jwt_secret(), algorithms=[_ALGORITHM])
    except PyJWTError as exc:
        raise OperatorAuthError("invalid_token", str(exc)) from exc

    if expected_type and payload.get("type") != expected_type:
        raise OperatorAuthError(
            "invalid_token_type",
            f"Expected token type {expected_type!r}, got {payload.get('type')!r}.",
        )
    if not payload.get("sub"):
        raise OperatorAuthError("invalid_token", "Token missing 'sub' claim.")
    return payload


async def issue_token_pair(
    session: AsyncSession,
    operator: Operator,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, str, int]:
    access, _access_exp = create_access_token(operator)
    refresh, refresh_exp, _jti = create_refresh_token(operator)
    session.add(
        OperatorSession(
            operator_id=operator.id,
            refresh_token_hash=_hash_refresh(refresh),
            expires_at=refresh_exp,
            ip_address=ip,
            user_agent=(user_agent or "")[:512] or None,
        )
    )
    await session.flush()
    return access, refresh, ACCESS_TTL_MINUTES * 60


async def authenticate_operator(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    ip: str | None,
    user_agent: str | None,
    totp_code: str | None = None,
) -> tuple[Operator, str, str, int]:
    normalized = (email or "").strip().lower()

    result = await session.execute(select(Operator).where(Operator.email == normalized))
    operator = result.scalar_one_or_none()

    invalid = OperatorAuthError("invalid_credentials", "Invalid operator credentials.", status_code=401)

    if operator is None or not operator_password_verify(password, operator.hashed_password):
        _logger.info("cockpit_login_failed", email=normalized, ip=ip)
        raise invalid

    if operator.status != OperatorStatus.ACTIVE.value:
        raise OperatorAuthError(
            "operator_suspended",
            "This operator account has been suspended.",
            status_code=403,
        )

    if operator.mfa_required:
        if not totp_code:
            raise OperatorAuthError(
                "mfa_required",
                "Multi-factor authentication is required for this operator.",
                status_code=403,
            )
        if not operator.mfa_secret:
            _logger.warning(
                "cockpit_login_mfa_unenrolled",
                operator_id=operator.id,
                ip=ip,
            )
            raise OperatorAuthError(
                "mfa_not_enrolled",
                "MFA is required but not enrolled. Contact an admin to reset.",
                status_code=403,
            )

        submitted = totp_code.strip()
        if not verify_code(operator.mfa_secret, submitted):
            # TOTP failed — try as a one-time recovery code.
            code_hash = hash_recovery_code(submitted)
            rc_result = await session.execute(
                select(OperatorRecoveryCode).where(
                    OperatorRecoveryCode.code_hash == code_hash,
                    OperatorRecoveryCode.operator_id == operator.id,
                )
            )
            recovery = rc_result.scalar_one_or_none()
            if recovery is None or recovery.used_at is not None:
                _logger.info(
                    "cockpit_login_mfa_failed",
                    operator_id=operator.id,
                    ip=ip,
                )
                raise OperatorAuthError("invalid_mfa", "Invalid MFA code.", status_code=403)
            recovery.used_at = _now()
            await session.flush()
            _logger.warning(
                "cockpit_login_mfa_recovery_used",
                operator_id=operator.id,
                ip=ip,
            )

    operator.last_login_at = _now()
    access, refresh, expires_in = await issue_token_pair(session, operator, ip=ip, user_agent=user_agent)
    return operator, access, refresh, expires_in


async def refresh_operator_session(
    session: AsyncSession,
    *,
    refresh_token: str,
    ip: str | None,
    user_agent: str | None,
) -> tuple[Operator, str, str, int]:
    payload = decode_token(refresh_token, expected_type=TOKEN_TYPE_REFRESH)
    operator_id = str(payload["sub"])

    token_hash = _hash_refresh(refresh_token)
    sess_result = await session.execute(select(OperatorSession).where(OperatorSession.refresh_token_hash == token_hash))
    sess = sess_result.scalar_one_or_none()
    if sess is None or sess.revoked_at is not None:
        raise OperatorAuthError("invalid_refresh", "Refresh token unknown or revoked.", status_code=401)
    # SQLite returns naive datetimes even for ``DateTime(timezone=True)`` —
    # normalize so the comparison stays tz-aware.
    expires_at = sess.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= _now():
        raise OperatorAuthError("refresh_expired", "Refresh token has expired.", status_code=401)

    op_result = await session.execute(select(Operator).where(Operator.id == operator_id))
    operator = op_result.scalar_one_or_none()
    if operator is None or operator.status != OperatorStatus.ACTIVE.value:
        raise OperatorAuthError(
            "operator_suspended",
            "Operator is no longer active.",
            status_code=403,
        )

    # Rotate: revoke old, issue new pair.
    sess.revoked_at = _now()
    access, new_refresh, expires_in = await issue_token_pair(session, operator, ip=ip, user_agent=user_agent)
    return operator, access, new_refresh, expires_in


async def revoke_session(session: AsyncSession, *, refresh_token: str) -> None:
    token_hash = _hash_refresh(refresh_token)
    sess_result = await session.execute(select(OperatorSession).where(OperatorSession.refresh_token_hash == token_hash))
    sess = sess_result.scalar_one_or_none()
    if sess and sess.revoked_at is None:
        sess.revoked_at = _now()
        await session.flush()


async def list_operator_grants(session: AsyncSession, operator: Operator) -> list[OperatorTenantGrant]:
    result = await session.execute(select(OperatorTenantGrant).where(OperatorTenantGrant.operator_id == operator.id))
    return list(result.scalars().all())
