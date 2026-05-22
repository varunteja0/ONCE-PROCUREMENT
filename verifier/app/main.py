"""Once Receipt Verifier — public Ed25519 verification microservice.

Independent of the main backend. Fetches a signed receipt envelope from the
main backend's public read endpoint, then verifies its Ed25519 signature using
a configured public key (PEM). Intended to be auditable / runnable by anyone.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import httpx
import structlog
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.api_key import enforce_api_key_or_rate_limit
from app.content_negotiation import negotiate
from app.observability import init_sentry
from app.views import _render_html, router as views_router

logger = structlog.get_logger(__name__)


class VerifierSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    backend_base_url: str = "http://localhost:8000"
    backend_receipt_path: str = "/v1/public/receipts/"
    signing_key_id: str = "default"
    public_key_pem: str = ""
    request_timeout_sec: float = 10.0
    app_name: str = "once-verifier"
    sentry_dsn: str = ""
    env: str = "development"
    app_version: str = "0.1.0"
    sentry_traces_sample_rate: float = 0.1
    # L6.1 — API-key monetization
    backend_internal_token: str = ""
    unauth_rate_limit: str = "100/day;20/hour;5/minute"


settings = VerifierSettings()

init_sentry(
    dsn=settings.sentry_dsn,
    environment=settings.env,
    release=settings.app_version,
    traces_sample_rate=settings.sentry_traces_sample_rate,
)

app = FastAPI(title="Once Receipt Verifier", version="0.1.0")
app.middleware("http")(enforce_api_key_or_rate_limit)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

_APP_DIR = Path(__file__).resolve().parent
_TEMPLATES_DIR = _APP_DIR / "templates"
_STATIC_DIR = _APP_DIR / "static"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
templates.env.autoescape = True

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
app.include_router(views_router)


class VerifyResponse(BaseModel):
    verified: bool
    payload: dict[str, Any]
    public_key_pem: str
    signing_key_id: str


def _load_public_key(pem: str) -> Ed25519PublicKey:
    if not pem.strip():
        raise HTTPException(
            status_code=503,
            detail="Verifier not configured: PUBLIC_KEY_PEM is empty",
        )
    try:
        key = serialization.load_pem_public_key(pem.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503, detail=f"Invalid public key PEM: {exc}"
        ) from exc
    if not isinstance(key, Ed25519PublicKey):
        raise HTTPException(
            status_code=503, detail="Configured public key is not Ed25519"
        )
    return key


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _decode_signature(sig: str) -> bytes:
    try:
        return base64.b64decode(sig, validate=True)
    except Exception:  # noqa: BLE001
        try:
            return bytes.fromhex(sig)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=422,
                detail="Signature is neither valid base64 nor hex",
            ) from exc


async def _fetch_receipt(receipt_id: str) -> dict[str, Any]:
    url = (
        f"{settings.backend_base_url.rstrip('/')}"
        f"{settings.backend_receipt_path.rstrip('/')}/{receipt_id}"
    )
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_sec) as client:
            resp = await client.get(url)
    except httpx.HTTPError as exc:
        logger.warning(
            "backend_unreachable", url=url, error=str(exc), receipt_id=receipt_id
        )
        raise HTTPException(
            status_code=404,
            detail=f"Receipt {receipt_id} not found (backend unreachable)",
        ) from exc

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Backend returned {resp.status_code} fetching receipt",
        )

    try:
        return resp.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502, detail="Backend returned non-JSON receipt"
        ) from exc


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@dataclass
class VerificationResult:
    """Outcome of attempting to verify a receipt.

    Distinct from :class:`VerifyResponse` so non-JSON callers (HTML view,
    badge endpoint) can render error states without us having to raise and
    catch HTTPExceptions across module boundaries.
    """

    status: Literal["verified", "invalid", "not_found", "error"]
    verified: bool
    http_status: int
    payload: dict[str, Any] | None = None
    envelope: dict[str, Any] = field(default_factory=dict)
    error_detail: str | None = None


async def perform_verification(receipt_id: str) -> VerificationResult:
    """Fetch a receipt and try to verify its Ed25519 signature.

    Never raises HTTPException — returns a :class:`VerificationResult` so
    HTML and badge views can render every failure mode without try/except.
    """

    log = logger.bind(receipt_id=receipt_id)
    try:
        envelope = await _fetch_receipt(receipt_id)
    except HTTPException as exc:
        status_str: Literal["not_found", "error"] = (
            "not_found" if exc.status_code == 404 else "error"
        )
        return VerificationResult(
            status=status_str,
            verified=False,
            http_status=exc.status_code,
            error_detail=str(exc.detail),
        )

    payload = envelope.get("payload")
    signature_str = envelope.get("signature") or envelope.get("sig")
    if not isinstance(payload, dict) or not isinstance(signature_str, str):
        return VerificationResult(
            status="error",
            verified=False,
            http_status=422,
            envelope=envelope if isinstance(envelope, dict) else {},
            error_detail="Receipt envelope missing 'payload' or 'signature'",
        )

    try:
        public_key = _load_public_key(settings.public_key_pem)
    except HTTPException as exc:
        return VerificationResult(
            status="error",
            verified=False,
            http_status=exc.status_code,
            payload=payload,
            envelope=envelope,
            error_detail=str(exc.detail),
        )

    signed_bytes = _canonical_json_bytes(payload)
    try:
        signature = _decode_signature(signature_str)
    except HTTPException as exc:
        return VerificationResult(
            status="error",
            verified=False,
            http_status=exc.status_code,
            payload=payload,
            envelope=envelope,
            error_detail=str(exc.detail),
        )

    verified = False
    try:
        public_key.verify(signature, signed_bytes)
        verified = True
    except InvalidSignature:
        verified = False
    except Exception as exc:  # noqa: BLE001
        log.warning("verify_error", error=str(exc))
        verified = False

    log.info("verify_complete", verified=verified)
    return VerificationResult(
        status="verified" if verified else "invalid",
        verified=verified,
        http_status=200,
        payload=payload,
        envelope=envelope,
    )


@app.get("/verify/{receipt_id}")
async def verify(receipt_id: str, request: Request):  # noqa: ANN201
    """Content-negotiated verification endpoint.

    * ``Accept: text/html`` (browsers) → server-rendered HTML page.
    * ``Accept: application/json`` (or no Accept / ``*/*``) → JSON
      ``VerifyResponse`` — preserves back-compat with API clients and
      with the prior pre-content-negotiation contract.
    * ``Accept: application/jose+json`` → raw signed envelope from backend.

    Browsers always send an explicit ``text/html`` in their Accept header,
    so they reliably get HTML; tooling like ``curl`` and ``httpx`` (which
    send ``Accept: */*``) reliably get JSON. The dedicated
    ``/verify/{id}.html`` route is the escape hatch for forcing HTML from
    a non-browser context.
    """

    fmt = negotiate(request, default="json")
    result = await perform_verification(receipt_id)

    if fmt == "html":
        return _render_html(request, receipt_id, result, result.http_status)

    if fmt == "jose":
        envelope = result.envelope or {
            "error": result.error_detail or "unavailable"
        }
        return JSONResponse(
            envelope,
            status_code=result.http_status,
            media_type="application/jose+json",
        )

    # JSON path — preserve the original VerifyResponse shape for back-compat.
    if result.status in {"not_found", "error"}:
        return JSONResponse(
            {"detail": result.error_detail or result.status},
            status_code=result.http_status,
        )
    body = VerifyResponse(
        verified=result.verified,
        payload=result.payload or {},
        public_key_pem=settings.public_key_pem,
        signing_key_id=settings.signing_key_id,
    )
    return JSONResponse(body.model_dump(), status_code=result.http_status)
