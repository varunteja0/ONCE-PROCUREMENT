"""Cockpit MFA enrollment / confirmation / disable / recovery routes.

All routes require an authenticated operator. The login flow itself
(``/cockpit/auth/login``) is what *consumes* TOTP / recovery codes — the
routes here only manage the operator's MFA state.

Recovery codes are returned ONCE (at enrollment or regeneration time);
they are stored hashed and cannot be recovered after that response.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cockpit import CurrentOperator
from app.db import get_db
from app.models import OperatorRecoveryCode
from app.schemas.operator import (
    MfaConfirmRequest,
    MfaConfirmResponse,
    MfaDisableRequest,
    MfaEnrollResponse,
    MfaStatusResponse,
)
from app.services import mfa_totp
from app.services.cockpit_audit import write_audit
from app.utils.logging import get_logger

__all__ = ["router"]

router = APIRouter(prefix="/mfa", tags=["cockpit-mfa"])
_logger = get_logger(__name__)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _client_ip(request: Request) -> str | None:
    if request.client is not None and request.client.host:
        return request.client.host
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip() or None
    return None


async def _verify_totp_or_recovery(
    session: AsyncSession,
    *,
    operator_id: str,
    secret: str,
    submitted: str,
) -> bool:
    """Return True if ``submitted`` is a live TOTP OR an unused recovery code.

    On recovery-code success the row is marked ``used_at`` (single-use)
    and flushed.
    """

    if mfa_totp.verify_code(secret, submitted):
        return True
    code_hash = mfa_totp.hash_recovery_code(submitted)
    result = await session.execute(
        select(OperatorRecoveryCode).where(
            OperatorRecoveryCode.code_hash == code_hash,
            OperatorRecoveryCode.operator_id == operator_id,
        )
    )
    rc = result.scalar_one_or_none()
    if rc is None or rc.used_at is not None:
        return False
    rc.used_at = _now()
    await session.flush()
    return True


@router.post(
    "/enroll",
    response_model=MfaEnrollResponse,
    summary="Start MFA enrollment: generate secret + QR. Idempotent-safe (409 if already enrolled).",
)
async def enroll(
    request: Request,
    operator: CurrentOperator,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MfaEnrollResponse:
    if operator.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "mfa_already_enrolled",
                "message": "MFA is already enrolled for this operator. Disable first to re-enroll.",
            },
        )

    secret = mfa_totp.generate_secret()
    operator.mfa_secret = secret
    await session.flush()

    uri = mfa_totp.provisioning_uri(secret, account_name=operator.email)
    qr_svg = mfa_totp.provisioning_qr_svg(uri)

    await write_audit(
        session,
        operator_id=operator.id,
        tenant_id_acted_as=None,
        action="cockpit.mfa.enroll_started",
        resource_type="operator",
        resource_id=operator.id,
        request_id=getattr(request.state, "request_id", None),
        method=request.method,
        path=request.url.path,
        status_code=200,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _logger.info("cockpit_mfa_enroll_started", operator_id=operator.id)
    return MfaEnrollResponse(secret=secret, provisioning_uri=uri, qr_svg=qr_svg)


@router.post(
    "/confirm",
    response_model=MfaConfirmResponse,
    summary="Confirm MFA enrollment with a TOTP code; activates MFA and returns recovery codes (ONCE).",
)
async def confirm(
    payload: MfaConfirmRequest,
    request: Request,
    operator: CurrentOperator,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MfaConfirmResponse:
    if not operator.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "mfa_not_started",
                "message": "MFA enrollment has not been started. Call /enroll first.",
            },
        )
    if not mfa_totp.verify_code(operator.mfa_secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_mfa", "message": "Invalid MFA code."},
        )

    operator.mfa_required = True

    # Wipe any stale recovery codes from a prior partial enrollment.
    await session.execute(
        delete(OperatorRecoveryCode).where(
            OperatorRecoveryCode.operator_id == operator.id
        )
    )
    plain = mfa_totp.generate_recovery_codes()
    for code in plain:
        session.add(
            OperatorRecoveryCode(
                operator_id=operator.id,
                code_hash=mfa_totp.hash_recovery_code(code),
            )
        )
    await session.flush()

    await write_audit(
        session,
        operator_id=operator.id,
        tenant_id_acted_as=None,
        action="cockpit.mfa.enrolled",
        resource_type="operator",
        resource_id=operator.id,
        request_id=getattr(request.state, "request_id", None),
        method=request.method,
        path=request.url.path,
        status_code=200,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _logger.info("cockpit_mfa_enrolled", operator_id=operator.id)
    return MfaConfirmResponse(recovery_codes=plain)


@router.post(
    "/disable",
    summary="Disable MFA after verifying a TOTP or recovery code.",
)
async def disable(
    payload: MfaDisableRequest,
    request: Request,
    operator: CurrentOperator,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    if not operator.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "mfa_not_enrolled",
                "message": "MFA is not enrolled for this operator.",
            },
        )
    ok = await _verify_totp_or_recovery(
        session,
        operator_id=operator.id,
        secret=operator.mfa_secret,
        submitted=payload.code,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_mfa", "message": "Invalid MFA code."},
        )

    operator.mfa_required = False
    operator.mfa_secret = None
    await session.execute(
        delete(OperatorRecoveryCode).where(
            OperatorRecoveryCode.operator_id == operator.id
        )
    )
    await session.flush()

    await write_audit(
        session,
        operator_id=operator.id,
        tenant_id_acted_as=None,
        action="cockpit.mfa.disabled",
        resource_type="operator",
        resource_id=operator.id,
        request_id=getattr(request.state, "request_id", None),
        method=request.method,
        path=request.url.path,
        status_code=200,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _logger.info("cockpit_mfa_disabled", operator_id=operator.id)
    return {"status": "ok"}


@router.post(
    "/recovery-codes/regenerate",
    response_model=MfaConfirmResponse,
    summary="Replace all recovery codes after verifying a TOTP. Returns new codes ONCE.",
)
async def regenerate_recovery_codes(
    payload: MfaConfirmRequest,
    request: Request,
    operator: CurrentOperator,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MfaConfirmResponse:
    if not operator.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "mfa_not_enrolled",
                "message": "MFA is not enrolled for this operator.",
            },
        )
    if not mfa_totp.verify_code(operator.mfa_secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_mfa", "message": "Invalid MFA code."},
        )

    await session.execute(
        delete(OperatorRecoveryCode).where(
            OperatorRecoveryCode.operator_id == operator.id
        )
    )
    plain = mfa_totp.generate_recovery_codes()
    for code in plain:
        session.add(
            OperatorRecoveryCode(
                operator_id=operator.id,
                code_hash=mfa_totp.hash_recovery_code(code),
            )
        )
    await session.flush()

    await write_audit(
        session,
        operator_id=operator.id,
        tenant_id_acted_as=None,
        action="cockpit.mfa.recovery_regenerated",
        resource_type="operator",
        resource_id=operator.id,
        request_id=getattr(request.state, "request_id", None),
        method=request.method,
        path=request.url.path,
        status_code=200,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _logger.info("cockpit_mfa_recovery_regenerated", operator_id=operator.id)
    return MfaConfirmResponse(recovery_codes=plain)


@router.get(
    "/status",
    response_model=MfaStatusResponse,
    summary="Report MFA enrollment + unused recovery-code count for the current operator.",
)
async def mfa_status(
    operator: CurrentOperator,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MfaStatusResponse:
    result = await session.execute(
        select(func.count()).select_from(OperatorRecoveryCode).where(
            OperatorRecoveryCode.operator_id == operator.id,
            OperatorRecoveryCode.used_at.is_(None),
        )
    )
    unused = int(result.scalar_one() or 0)
    return MfaStatusResponse(
        mfa_required=bool(operator.mfa_required),
        enrolled=operator.mfa_secret is not None,
        unused_recovery_count=unused,
    )
