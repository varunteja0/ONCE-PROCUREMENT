"""Once Receipt Verifier — public Ed25519 verification microservice.

Independent of the main backend. Fetches a signed receipt envelope from the
main backend's public read endpoint, then verifies its Ed25519 signature using
a configured public key (PEM). Intended to be auditable / runnable by anyone.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import httpx
import structlog
from app.api_key import enforce_api_key_or_rate_limit
from app.canonical import verify_canonical_match
from app.content_negotiation import negotiate
from app.observability import init_sentry
from app.views import _render_html
from app.views import router as views_router
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

logger = structlog.get_logger(__name__)


class VerifierSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    backend_base_url: str = "http://localhost:8000"
    backend_receipt_path: str = "/v1/public/receipts/"
    backend_key_path: str = "/v1/keys/"
    signing_key_id: str = "default"
    public_key_pem: str = ""
    public_key_cache_ttl_sec: int = 3600
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
    # Narrow allow_headers to the exact set the verifier consumes. Avoids
    # advertising arbitrary header acceptance from a wildcard origin.
    allow_headers=["accept", "content-type", "x-verify-api-key"],
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


@dataclass(slots=True)
class CachedPublicKey:
    pem: str
    expires_at: float


_PUBLIC_KEY_CACHE: dict[str, CachedPublicKey] = {}
_PUBLIC_KEY_CACHE_MAX = 64


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


def _extract_signing_key_id(envelope: dict[str, Any], payload: dict[str, Any]) -> str:
    candidates: list[Any] = [
        envelope.get("signing_key_id"),
        envelope.get("key_id"),
        payload.get("signing_key_id"),
    ]
    receipt_obj = envelope.get("receipt")
    if isinstance(receipt_obj, dict):
        candidates.append(receipt_obj.get("signing_key_id"))
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return settings.signing_key_id


def _static_public_key_for(signing_key_id: str) -> str | None:
    pem = settings.public_key_pem.strip()
    if pem and signing_key_id == settings.signing_key_id:
        return pem
    return None


def _cache_get(signing_key_id: str) -> str | None:
    cached = _PUBLIC_KEY_CACHE.get(signing_key_id)
    if cached is None:
        return None
    if cached.expires_at <= time.monotonic():
        _PUBLIC_KEY_CACHE.pop(signing_key_id, None)
        return None
    return cached.pem


def _cache_put(signing_key_id: str, pem: str) -> None:
    if len(_PUBLIC_KEY_CACHE) >= _PUBLIC_KEY_CACHE_MAX:
        oldest_key = min(
            _PUBLIC_KEY_CACHE, key=lambda key_id: _PUBLIC_KEY_CACHE[key_id].expires_at
        )
        _PUBLIC_KEY_CACHE.pop(oldest_key, None)
    _PUBLIC_KEY_CACHE[signing_key_id] = CachedPublicKey(
        pem=pem,
        expires_at=time.monotonic() + max(60, settings.public_key_cache_ttl_sec),
    )


def _public_key_url(signing_key_id: str) -> str:
    base = settings.backend_base_url.rstrip("/")
    path = settings.backend_key_path.rstrip("/")
    return f"{base}{path}/{signing_key_id}"


async def _resolve_public_key_pem(signing_key_id: str) -> str:
    static_pem = _static_public_key_for(signing_key_id)
    if static_pem is not None:
        return static_pem

    cached = _cache_get(signing_key_id)
    if cached is not None:
        return cached

    url = _public_key_url(signing_key_id)
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_sec) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        logger.warning(
            "public_key_backend_unreachable",
            key_id=signing_key_id,
            url=url,
            error=str(exc),
        )
        raise HTTPException(
            status_code=503,
            detail="Public key registry is temporarily unavailable",
        ) from exc

    if resp.status_code == 404:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown signing key id: {signing_key_id}",
        )
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Backend returned {resp.status_code} fetching public key",
        )
    try:
        body = resp.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Backend returned non-JSON public key response",
        ) from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=502, detail="Malformed public key response")
    public_key_pem = body.get("public_key_pem")
    algorithm = body.get("algorithm")
    if not isinstance(public_key_pem, str) or not public_key_pem.strip():
        raise HTTPException(status_code=502, detail="Public key response missing PEM")
    if isinstance(algorithm, str) and algorithm.lower() != "ed25519":
        raise HTTPException(status_code=502, detail="Public key is not Ed25519")
    _load_public_key(public_key_pem)
    _cache_put(signing_key_id, public_key_pem)
    return public_key_pem


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
    public_key_pem: str = ""
    signing_key_id: str = ""


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

    # Accept the real backend envelope shape (PublicReceiptVerifyResponse):
    # ``{ receipt: { public_payload_json, signature_b64, ... }, ... }``.
    if (not isinstance(payload, dict)) or (not isinstance(signature_str, str)):
        receipt_obj = envelope.get("receipt")
        if isinstance(receipt_obj, dict):
            if not isinstance(payload, dict):
                candidate = receipt_obj.get("public_payload_json")
                if isinstance(candidate, dict):
                    payload = candidate
            if not isinstance(signature_str, str):
                candidate_sig = receipt_obj.get("signature_b64")
                if isinstance(candidate_sig, str):
                    signature_str = candidate_sig

    if not isinstance(payload, dict) or not isinstance(signature_str, str):
        return VerificationResult(
            status="error",
            verified=False,
            http_status=422,
            envelope=envelope if isinstance(envelope, dict) else {},
            error_detail="Receipt envelope missing 'payload' or 'signature'",
        )

    signing_key_id = _extract_signing_key_id(envelope, payload)
    try:
        public_key_pem = await _resolve_public_key_pem(signing_key_id)
        public_key = _load_public_key(public_key_pem)
    except HTTPException as exc:
        return VerificationResult(
            status="error",
            verified=False,
            http_status=exc.status_code,
            payload=payload,
            envelope=envelope,
            error_detail=str(exc.detail),
            signing_key_id=signing_key_id,
        )

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
            signing_key_id=signing_key_id,
            public_key_pem=public_key_pem,
        )

    internal_error: BaseException | None = None

    def _verify_bytes(signed_bytes: bytes) -> bool:
        nonlocal internal_error
        try:
            public_key.verify(signature, signed_bytes)
            return True
        except InvalidSignature:
            return False
        except Exception as exc:  # noqa: BLE001
            internal_error = exc
            return False

    verified = verify_canonical_match(payload, _verify_bytes)
    if internal_error is not None:
        # Per verifier.instructions.md §7: a 5xx is only allowed when the
        # verifier itself is broken. A bug in `cryptography` or an
        # unexpected payload type is exactly that case — surface it as a
        # 503 "error" result instead of silently degrading to
        # "invalid", which would be indistinguishable from a real bad
        # signature for callers.
        log.error(
            "verify_internal_error",
            error=str(internal_error),
            error_type=type(internal_error).__name__,
        )
        return VerificationResult(
            status="error",
            verified=False,
            http_status=503,
            payload=payload,
            envelope=envelope,
            error_detail="Verifier internal error during signature verification",
            signing_key_id=signing_key_id,
            public_key_pem=public_key_pem,
        )

    log.info("verify_complete", verified=verified)
    return VerificationResult(
        status="verified" if verified else "invalid",
        verified=verified,
        http_status=200,
        payload=payload,
        envelope=envelope,
        signing_key_id=signing_key_id,
        public_key_pem=public_key_pem,
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
        envelope = result.envelope or {"error": result.error_detail or "unavailable"}
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
        public_key_pem=result.public_key_pem,
        signing_key_id=result.signing_key_id,
    )
    return JSONResponse(body.model_dump(), status_code=result.http_status)
