from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentTenantUser
from app.db import get_db
from app.models import AuditLog, SubmissionReceipt
from app.schemas.receipt import (
    PublicReceiptRead,
    PublicReceiptVerifyResponse,
    ReceiptRead,
)
from app.utils.logging import get_logger

router = APIRouter(prefix="/receipts", tags=["receipts"])
public_receipt_router = APIRouter(tags=["receipts-public"])
# Public verifier alias mounted under /v1 — the canonical path expected by the
# ``verifier`` microservice. Same handler as ``/verify/{id}`` below.
public_v1_receipt_router = APIRouter(
    prefix="/public/receipts", tags=["receipts-public"]
)
_logger = get_logger(__name__)

__all__ = ["router", "public_receipt_router", "public_v1_receipt_router"]

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50


def _client_ip(request: Request) -> str | None:
    if request.client is not None and request.client.host:
        return request.client.host
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return None


def _write_audit(
    session: AsyncSession,
    *,
    action: str,
    tenant_id: str | None,
    actor_user_id: str | None,
    resource_id: str | None,
    ip_address: str | None,
    metadata: dict[str, Any] | None,
) -> None:
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type="receipt",
            resource_id=resource_id,
            metadata_json=metadata,
            ip_address=ip_address,
        )
    )


def _verify_url(request: Request, receipt_id: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/verify/{receipt_id}"


def _receipt_to_read(request: Request, r: SubmissionReceipt) -> ReceiptRead:
    """Build a ReceiptRead from an ORM row, injecting verify_url first.

    ``ReceiptRead.verify_url`` is required, so calling ``model_validate(r)``
    directly on the ORM row 500s. Constructing the dict — with the URL —
    before validation keeps the response-only field a hard requirement.
    """

    return ReceiptRead.model_validate(
        {
            "id": r.id,
            "tenant_id": r.tenant_id,
            "supplier_id": r.supplier_id,
            "submission_id": r.submission_id,
            "portal_platform": r.portal_platform,
            "submitted_at": r.submitted_at,
            "payload_hash": r.payload_hash,
            "tos_version_hash": r.tos_version_hash,
            "consent_record_id": r.consent_record_id,
            "signing_key_id": r.signing_key_id,
            "signature_b64": r.signature_b64,
            "public_payload_json": dict(r.public_payload_json or {}),
            "created_at": r.created_at,
            "updated_at": r.updated_at,
            "verify_url": _verify_url(request, r.id),
        }
    )


async def _load_receipt_for_tenant(
    session: AsyncSession, *, tenant_id: str, receipt_id: str
) -> SubmissionReceipt:
    stmt = select(SubmissionReceipt).where(
        SubmissionReceipt.id == receipt_id,
        SubmissionReceipt.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    receipt = result.scalar_one_or_none()
    if receipt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "receipt_not_found", "message": "Receipt does not exist."},
        )
    return receipt


@router.get(
    "",
    response_model=list[ReceiptRead],
    summary="List receipts for the current tenant",
)
async def list_receipts(
    request: Request,
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    response: Response,
    supplier_id: Annotated[str | None, Query(max_length=36)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ReceiptRead]:
    stmt = select(SubmissionReceipt).where(SubmissionReceipt.tenant_id == tenant_id)
    count_stmt = select(func.count(SubmissionReceipt.id)).where(
        SubmissionReceipt.tenant_id == tenant_id
    )
    if supplier_id is not None:
        stmt = stmt.where(SubmissionReceipt.supplier_id == supplier_id)
        count_stmt = count_stmt.where(SubmissionReceipt.supplier_id == supplier_id)
    stmt = stmt.order_by(
        SubmissionReceipt.submitted_at.desc(), SubmissionReceipt.id.desc()
    )
    stmt = stmt.limit(min(max(limit, 1), _MAX_LIMIT)).offset(max(offset, 0))

    result = await session.execute(stmt)
    receipts = list(result.scalars().all())
    total_result = await session.execute(count_stmt)
    total = int(total_result.scalar_one() or 0)
    response.headers["X-Total-Count"] = str(total)

    return [_receipt_to_read(request, r) for r in receipts]


@router.get(
    "/{receipt_id}",
    response_model=ReceiptRead,
    summary="Fetch a single receipt (tenant-scoped)",
)
async def get_receipt(
    receipt_id: str,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ReceiptRead:
    receipt = await _load_receipt_for_tenant(
        session, tenant_id=tenant_user.tenant_id, receipt_id=receipt_id
    )
    _write_audit(
        session,
        action="receipt.viewed",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=receipt.id,
        ip_address=_client_ip(request),
        metadata={"submission_id": receipt.submission_id},
    )
    return _receipt_to_read(request, receipt)


# ---------------------------------------------------------------------------
# Public verifier endpoint — NOT mounted under /receipts, no auth required.
# ---------------------------------------------------------------------------


async def _verify_receipt_public(
    receipt_id: str,
    request: Request,
    session: AsyncSession,
) -> PublicReceiptVerifyResponse:
    """Shared implementation for the public verifier routes."""

    result = await session.execute(
        select(SubmissionReceipt).where(SubmissionReceipt.id == receipt_id)
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "receipt_not_found", "message": "Receipt does not exist."},
        )

    verified = False
    public_key_b64: str | None = None
    reason: str | None = None
    try:
        from app.services.receipt_signer import verify_receipt as _verify
    except Exception as exc:  # pragma: no cover - signer optional in some test envs
        reason = f"signer_unavailable: {exc.__class__.__name__}"
        _logger.warning("receipt_signer_unavailable", error=str(exc))
    else:
        try:
            verification = await _verify(session, receipt.id)
            verified = bool(verification.get("verified", False))
            public_key_pem = verification.get("public_key_pem") or ""
            if public_key_pem:
                # The verifier and downstream clients accept either a raw PEM
                # or its base64 wire form. We return PEM directly under the
                # ``public_key_b64`` field (kept for backwards compatibility);
                # base64-armoring an already-armored PEM would just double-wrap.
                public_key_b64 = public_key_pem
            if not verified:
                reason = "signature_invalid_or_unknown_key"
        except Exception as exc:
            reason = f"verification_error: {exc}"
            _logger.exception(
                "receipt_verification_failed", receipt_id=receipt_id
            )

    _write_audit(
        session,
        action="receipt.verified_public",
        tenant_id=None,
        actor_user_id=None,
        resource_id=receipt.id,
        ip_address=_client_ip(request),
        metadata={"verified": verified, "reason": reason},
    )

    public_payload = dict(receipt.public_payload_json or {})
    public = PublicReceiptRead(
        receipt_id=receipt.id,
        portal_platform=receipt.portal_platform,
        submitted_at=receipt.submitted_at,
        payload_hash=receipt.payload_hash,
        tos_version_hash=receipt.tos_version_hash,
        signing_key_id=receipt.signing_key_id,
        signature_b64=receipt.signature_b64,
        public_payload_json=public_payload,
    )
    return PublicReceiptVerifyResponse(
        receipt=public,
        verified=verified,
        public_key_b64=public_key_b64,
        reason=reason,
        # Top-level aliases so the standalone verifier service can verify
        # without unwrapping ``receipt``. Byte-identical to the nested fields.
        payload=public_payload,
        signature=receipt.signature_b64,
    )


@public_receipt_router.get(
    "/verify/{receipt_id}",
    response_model=PublicReceiptVerifyResponse,
    summary="Publicly verify a signed submission receipt",
)
async def verify_receipt_public(
    receipt_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PublicReceiptVerifyResponse:
    return await _verify_receipt_public(receipt_id, request, session)


@public_v1_receipt_router.get(
    "/{receipt_id}",
    response_model=PublicReceiptVerifyResponse,
    summary="Publicly verify a signed submission receipt (v1 alias)",
)
async def verify_receipt_public_v1(
    receipt_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PublicReceiptVerifyResponse:
    """Canonical alias for the public verifier at ``/v1/public/receipts/{id}``.

    Returns the same envelope as ``GET /verify/{receipt_id}``; the verifier
    microservice consumes this path by default.
    """

    return await _verify_receipt_public(receipt_id, request, session)
