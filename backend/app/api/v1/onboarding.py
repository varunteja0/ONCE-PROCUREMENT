"""L3.6 — Self-serve onboarding wizard API.

All endpoints are mounted under ``/v1/onboarding`` and live outside of
:func:`app.api.deps.get_current_user`: they use a dedicated
``onboarding_session_token`` (JWT with ``scope=onboarding``) until the
user verifies their email, after which they receive a normal access /
refresh pair.

Tenant-scoped audit rows (``onboarding.<action>``) are emitted for every
state-changing endpoint.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request, status
from jwt import PyJWTError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import oauth2_scheme
from app.config import settings
from app.db import get_db
from app.models import (
    AuditLog,
    OnboardingState,
    OnboardingStep,
    Supplier,
    SupplierSubmission,
    Tenant,
    TenantUser,
    User,
)
from app.models.consent import ConsentRecord, ConsentScope
from app.models.submission import SubmissionStatus
from app.schemas.onboarding import (
    AddSupplierRequest,
    CompanyProfileRequest,
    ConnectPortalRequest,
    OnboardingCompleteResponse,
    OnboardingStartRequest,
    OnboardingStartResponse,
    OnboardingStateRead,
    RunFirstSubmissionRequest,
    SkipStepRequest,
    SubmissionPollRead,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from app.services import (
    email_dispatcher as email_dispatcher_module,
)
from app.services import (
    email_verification_service,
    onboarding_service,
)
from app.services.auth_service import issue_token_pair
from app.utils.logging import get_logger
from app.utils.password_policy import validate_password
from app.utils.security import hash_password

__all__ = ["router"]


router = APIRouter(prefix="/onboarding", tags=["onboarding"])
_logger = get_logger(__name__)


_ONBOARDING_SCOPE = "onboarding"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client_ip(request: Request) -> str | None:
    if request.client is not None and request.client.host:
        return request.client.host
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def _write_audit(
    session: AsyncSession,
    *,
    request: Request,
    action: str,
    tenant_id: str | None,
    actor_user_id: str | None,
    resource_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    meta = dict(metadata or {})
    ua = _user_agent(request)
    if ua:
        meta.setdefault("user_agent", ua[:255])
    rid = getattr(request.state, "request_id", None)
    if rid:
        meta.setdefault("request_id", rid)
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type="onboarding",
            resource_id=resource_id,
            metadata_json=meta or None,
            ip_address=_client_ip(request),
        )
    )


# ---------------------------------------------------------------------------
# Scoped session token
# ---------------------------------------------------------------------------


def _onboarding_secret() -> str:
    return settings.jwt_secret_key


def _mint_onboarding_token(*, tenant_id: str, user_id: str, email: str, email_verified: bool) -> tuple[str, int]:
    issued = _utcnow()
    expires = issued + timedelta(minutes=settings.onboarding_session_ttl_minutes)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "type": "access",
        "scope": _ONBOARDING_SCOPE,
        "email": email,
        "email_verified": email_verified,
        "iat": int(issued.timestamp()),
        "exp": int(expires.timestamp()),
    }
    token = jwt.encode(payload, _onboarding_secret(), algorithm=settings.jwt_algorithm)
    return token, settings.onboarding_session_ttl_minutes * 60


def _decode_onboarding_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, _onboarding_secret(), algorithms=[settings.jwt_algorithm])
    except PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_onboarding_token", "message": str(exc)},
        ) from exc
    if payload.get("scope") != _ONBOARDING_SCOPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "wrong_token_scope",
                "message": "Token is not scoped to onboarding.",
            },
        )
    return payload


async def _get_onboarding_context(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OnboardingContext:
    payload = _decode_onboarding_token(token)
    user_id = str(payload["sub"])
    tenant_id = str(payload["tenant_id"])
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "user_not_found", "message": "User no longer exists."},
        )
    tenant = (await session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "tenant_not_found", "message": "Tenant no longer exists."},
        )
    return OnboardingContext(
        user=user,
        tenant=tenant,
        token_payload=payload,
        email_verified=bool(payload.get("email_verified", False)),
    )


class OnboardingContext:
    __slots__ = ("user", "tenant", "token_payload", "email_verified")

    def __init__(
        self,
        *,
        user: User,
        tenant: Tenant,
        token_payload: dict[str, Any],
        email_verified: bool,
    ) -> None:
        self.user = user
        self.tenant = tenant
        self.token_payload = token_payload
        self.email_verified = email_verified


OnboardingCtx = Annotated[OnboardingContext, Depends(_get_onboarding_context)]


def _require_email_verified(ctx: OnboardingContext) -> None:
    if not ctx.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "email_not_verified",
                "message": "Verify your email before continuing onboarding.",
            },
        )


# ---------------------------------------------------------------------------
# Credential vault helpers
# ---------------------------------------------------------------------------


def _credential_key() -> bytes:
    """Derive a Fernet key from ``secret_key``.

    A throwaway derivation is sufficient here because onboarding portal
    creds are wizard-only and replaced by the real vault later.
    """

    digest = hashlib.sha256(("once-onboarding-creds:" + settings.secret_key).encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _encrypt_credentials(username: str, password: str) -> str:
    fernet = Fernet(_credential_key())
    blob = f"{username}\n{password}".encode()
    return fernet.encrypt(blob).decode("ascii")


def _decrypt_credentials(token: str) -> tuple[str, str]:  # pragma: no cover (helper)
    fernet = Fernet(_credential_key())
    try:
        raw = fernet.decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("invalid encrypted credentials") from exc
    username, _, password = raw.partition("\n")
    return username, password


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


async def _send_verification_email(*, code: str, email: str, ttl_minutes: int, company_name: str) -> None:
    dispatcher = email_dispatcher_module.get_email_dispatcher()
    subject, html, text = email_dispatcher_module.render_verify_email(
        code=code, ttl_minutes=ttl_minutes, company_name=company_name
    )
    try:
        await dispatcher.send(to=email, subject=subject, html=html, text=text)
    except email_dispatcher_module.EmailDispatcherError as exc:
        _logger.error("onboarding_verify_email_failed", error=str(exc), email=email)
        # Fallback to outbox so the user is never locked out by a misconfigured
        # email provider in production.
        fallback = email_dispatcher_module.OutboxEmailDispatcher()
        await fallback.send(to=email, subject=subject, html=html, text=text)


@router.post(
    "/start",
    response_model=OnboardingStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create pending tenant + send email verification code",
)
async def start_onboarding(
    payload: OnboardingStartRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OnboardingStartResponse:
    # Honeypot — silently accept but do nothing for obvious bots.
    if payload.website_url:
        _logger.warning("onboarding_honeypot_triggered", ip=_client_ip(request))
        # Return a plausible payload so we don't reveal that we detected the bot.
        # The token is intentionally non-functional (wrong secret).
        return OnboardingStartResponse(
            onboarding_session_token="bot",  # noqa: S106
            tenant_id="00000000-0000-0000-0000-000000000000",
            expires_in_seconds=0,
            dev_verification_code=None,
        )

    email = payload.email.lower().strip()

    policy = validate_password(payload.password, email=email, tenant_name=payload.company_name)
    if not policy.valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "password_policy_violation",
                "message": policy.first_reason or "Password failed policy checks.",
                "reasons": policy.reasons,
            },
        )

    existing_user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "email_already_registered",
                "message": "An account with that email already exists.",
            },
        )

    # Pending tenant — is_active=False blocks main-app login until verified.
    tenant = Tenant(
        name=payload.company_name.strip(),
        slug=_unique_slug(payload.company_name),
        is_active=False,
        plan="trial",
    )
    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=None,
        is_active=False,
    )
    session.add_all([tenant, user])
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "onboarding_conflict",
                "message": "Could not create account — conflict detected.",
            },
        ) from exc

    membership = TenantUser(tenant_id=tenant.id, user_id=user.id, role="owner")
    session.add(membership)
    await session.flush()

    await onboarding_service.create_state(
        session,
        tenant_id=tenant.id,
        primary_user_id=user.id,
        initial_step=OnboardingStep.EMAIL_PENDING,
    )

    # Issue verification code (rate-limited per email).
    issued = await email_verification_service.issue_code(
        session,
        email=email,
        tenant_id=tenant.id,
        ip_address=_client_ip(request),
    )

    await _send_verification_email(
        code=issued.code,
        email=email,
        ttl_minutes=settings.email_verification_code_ttl_minutes,
        company_name=tenant.name,
    )

    token, ttl = _mint_onboarding_token(tenant_id=tenant.id, user_id=user.id, email=email, email_verified=False)

    _write_audit(
        session,
        request=request,
        action="onboarding.start",
        tenant_id=tenant.id,
        actor_user_id=user.id,
        resource_id=tenant.id,
        metadata={"email": email},
    )
    _logger.info("onboarding_started", tenant_id=tenant.id, email=email)

    return OnboardingStartResponse(
        onboarding_session_token=token,
        tenant_id=tenant.id,
        expires_in_seconds=ttl,
        dev_verification_code=issued.code if settings.is_development else None,
    )


def _unique_slug(name: str) -> str:
    """Compact, URL-friendly tenant slug. Collisions resolved by uuid suffix."""

    import re
    import unicodedata
    import uuid

    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-") or "tenant"
    return f"{base[:32]}-{uuid.uuid4().hex[:6]}"


@router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
    summary="Verify the 6-digit email code; upgrade to a full session JWT",
)
async def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    ctx: OnboardingCtx,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VerifyEmailResponse:
    if ctx.email_verified:
        # Already verified — issue fresh tokens for idempotency.
        return await _finalize_email_verification(session, ctx=ctx, request=request)

    if not settings.onboarding_skip_email_verify:
        await email_verification_service.verify_code(
            session,
            email=ctx.user.email,
            tenant_id=ctx.tenant.id,
            submitted_code=payload.code,
        )

    ctx.user.is_active = True
    ctx.tenant.is_active = True
    await session.flush()

    state = await onboarding_service.advance_to(session, tenant_id=ctx.tenant.id, target=OnboardingStep.EMAIL_VERIFIED)
    # And immediately bump to PROFILE so the wizard moves forward.
    state = await onboarding_service.advance_to(session, tenant_id=ctx.tenant.id, target=OnboardingStep.PROFILE)

    _write_audit(
        session,
        request=request,
        action="onboarding.email_verified",
        tenant_id=ctx.tenant.id,
        actor_user_id=ctx.user.id,
        resource_id=ctx.tenant.id,
    )

    return await _finalize_email_verification(session, ctx=ctx, request=request, state=state)


async def _finalize_email_verification(
    session: AsyncSession,
    *,
    ctx: OnboardingContext,
    request: Request,
    state: OnboardingState | None = None,
) -> VerifyEmailResponse:
    tu_row = (
        await session.execute(
            select(TenantUser).where(TenantUser.user_id == ctx.user.id, TenantUser.tenant_id == ctx.tenant.id)
        )
    ).scalar_one()
    tokens = issue_token_pair(ctx.user, tu_row)
    if state is None:
        state = await onboarding_service.get_state(session, tenant_id=ctx.tenant.id)
    if state is None:  # pragma: no cover - get_state raises unless allow_missing=True
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="onboarding_state_not_found",
        )
    return VerifyEmailResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        tenant_id=ctx.tenant.id,
        current_step=state.current_step,
    )


# ---------------------------------------------------------------------------
# Authenticated (full-session) endpoints
# ---------------------------------------------------------------------------
#
# After verify-email the SPA holds a normal access token so we re-use the
# existing ``CurrentTenantUser`` / ``CurrentTenantId`` dependencies.

from app.api.deps import CurrentTenantId, CurrentTenantUser  # noqa: E402


@router.get(
    "/state",
    response_model=OnboardingStateRead,
    summary="Get current onboarding state for the authenticated tenant",
)
async def get_state(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OnboardingStateRead:
    state = await onboarding_service.get_state(session, tenant_id=tenant_id)
    if state is None:  # pragma: no cover - get_state raises unless allow_missing=True
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="onboarding_state_not_found",
        )
    return OnboardingStateRead.model_validate(state)


@router.post(
    "/company-profile",
    response_model=OnboardingStateRead,
    summary="Save the MGA company profile",
)
async def save_company_profile(
    payload: CompanyProfileRequest,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OnboardingStateRead:
    state = await onboarding_service.get_state(session, tenant_id=tenant_user.tenant_id)
    if state is None:  # pragma: no cover - get_state raises unless allow_missing=True
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="onboarding_state_not_found",
        )

    profile = payload.model_dump()
    state.company_profile_json = profile

    # Mirror legal_name onto the Tenant row.
    tenant = (await session.execute(select(Tenant).where(Tenant.id == tenant_user.tenant_id))).scalar_one()
    tenant.name = profile["legal_name"]

    state = await onboarding_service.advance_to(
        session,
        tenant_id=tenant_user.tenant_id,
        target=OnboardingStep.PLAN,
        step_data={"profile_saved_at": _utcnow().isoformat()},
    )

    _write_audit(
        session,
        request=request,
        action="onboarding.company_profile_saved",
        tenant_id=tenant.id,
        actor_user_id=tenant_user.user_id,
        resource_id=tenant.id,
        metadata={"primary_state": profile.get("primary_state")},
    )
    return OnboardingStateRead.model_validate(state)


@router.post(
    "/connect-portal",
    response_model=OnboardingStateRead,
    summary="Store encrypted portal credentials for the first connected carrier",
)
async def connect_portal(
    payload: ConnectPortalRequest,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OnboardingStateRead:
    # Validate the portal exists.
    from app.models import Portal

    portal = (await session.execute(select(Portal).where(Portal.id == payload.portal_id))).scalar_one_or_none()
    if portal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "portal_not_found", "message": "Portal does not exist."},
        )

    encrypted = _encrypt_credentials(payload.username, payload.password)
    state = await onboarding_service.advance_to(
        session,
        tenant_id=tenant_user.tenant_id,
        target=OnboardingStep.SUPPLIER,
        step_data={
            "connected_portal": {
                "portal_id": portal.id,
                "platform": portal.platform.value,
                "encrypted_credentials": encrypted,
                "connected_at": _utcnow().isoformat(),
            }
        },
    )
    _write_audit(
        session,
        request=request,
        action="onboarding.portal_connected",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=portal.id,
        metadata={"platform": portal.platform.value},
    )
    return OnboardingStateRead.model_validate(state)


@router.post(
    "/add-supplier",
    response_model=OnboardingStateRead,
    summary="Create the first supplier",
)
async def add_supplier(
    payload: AddSupplierRequest,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OnboardingStateRead:
    supplier = Supplier(
        tenant_id=tenant_user.tenant_id,
        legal_name=payload.legal_name,
        ein=payload.fein,
        primary_email=str(payload.primary_email) if payload.primary_email else None,
        address_json={"state": payload.state},
    )
    session.add(supplier)
    await session.flush()

    state = await onboarding_service.advance_to(
        session,
        tenant_id=tenant_user.tenant_id,
        target=OnboardingStep.SUBMISSION,
        step_data={"first_supplier_id": supplier.id},
    )
    _write_audit(
        session,
        request=request,
        action="onboarding.supplier_added",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=supplier.id,
        metadata={"legal_name": supplier.legal_name},
    )
    return OnboardingStateRead.model_validate(state)


@router.post(
    "/run-first-submission",
    response_model=SubmissionPollRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue the first portal submission",
)
async def run_first_submission(
    payload: RunFirstSubmissionRequest,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SubmissionPollRead:
    supplier = (
        await session.execute(
            select(Supplier).where(
                Supplier.id == payload.supplier_id,
                Supplier.tenant_id == tenant_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if supplier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "supplier_not_found", "message": "Supplier does not exist."},
        )

    from app.models import Portal

    portal = (await session.execute(select(Portal).where(Portal.id == payload.portal_id))).scalar_one_or_none()
    if portal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "portal_not_found", "message": "Portal does not exist."},
        )

    # Auto-grant submit-on-behalf consent (recorded in the audit trail).
    consent = ConsentRecord(
        tenant_id=tenant_user.tenant_id,
        supplier_id=supplier.id,
        scope=ConsentScope.SUBMIT_ON_BEHALF,
        portal_ids_json=[portal.id],
        granted_at=_utcnow(),
        granted_by_user_id=tenant_user.user_id,
        signed_text=(
            f"Onboarding wizard auto-consent for {supplier.legal_name} → "
            f"{portal.display_name} at {_utcnow().isoformat()}"
        ),
        signature_b64="onboarding-auto-consent",
    )
    session.add(consent)
    await session.flush()

    submission = SupplierSubmission(
        tenant_id=tenant_user.tenant_id,
        supplier_id=supplier.id,
        portal_id=portal.id,
        status=SubmissionStatus.QUEUED,
        payload_json={"source": "onboarding_wizard"},
        consent_record_id=consent.id,
    )
    session.add(submission)
    await session.flush()

    await onboarding_service.advance_to(
        session,
        tenant_id=tenant_user.tenant_id,
        target=OnboardingStep.SUBMISSION,
        step_data={"first_submission_id": submission.id},
    )
    _write_audit(
        session,
        request=request,
        action="onboarding.submission_enqueued",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=submission.id,
        metadata={"supplier_id": supplier.id, "portal_id": portal.id},
    )

    return SubmissionPollRead(submission_id=submission.id, status=submission.status.value)


@router.post(
    "/skip-step",
    response_model=OnboardingStateRead,
    summary="Skip an optional step (plan / portal / supplier / submission)",
)
async def skip_step(
    payload: SkipStepRequest,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OnboardingStateRead:
    step = OnboardingStep(payload.step)
    state = await onboarding_service.skip_step(session, tenant_id=tenant_user.tenant_id, step=step)
    _write_audit(
        session,
        request=request,
        action="onboarding.step_skipped",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=None,
        metadata={"step": step.value},
    )
    return OnboardingStateRead.model_validate(state)


@router.post(
    "/complete",
    response_model=OnboardingCompleteResponse,
    summary="Finalize onboarding; redirect to the dashboard",
)
async def complete_onboarding(
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OnboardingCompleteResponse:
    state = await onboarding_service.mark_completed(session, tenant_id=tenant_user.tenant_id)

    # Best-effort welcome email — failures must not block onboarding.
    tenant = (await session.execute(select(Tenant).where(Tenant.id == tenant_user.tenant_id))).scalar_one()
    user = (await session.execute(select(User).where(User.id == tenant_user.user_id))).scalar_one()
    try:
        dispatcher = email_dispatcher_module.get_email_dispatcher()
        subject, html, text = email_dispatcher_module.render_welcome_email(
            company_name=tenant.name, dashboard_url="https://app.getonce.com/dashboard"
        )
        await dispatcher.send(to=user.email, subject=subject, html=html, text=text)
    except Exception as exc:  # pragma: no cover - defensive
        _logger.warning("onboarding_welcome_email_failed", error=str(exc))

    _write_audit(
        session,
        request=request,
        action="onboarding.completed",
        tenant_id=tenant.id,
        actor_user_id=tenant_user.user_id,
        resource_id=tenant.id,
    )
    return OnboardingCompleteResponse(
        tenant_id=tenant.id,
        dashboard_url="/dashboard",
        current_step=state.current_step,
    )
