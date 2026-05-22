from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

from app import __version__
from app.config import settings
from app.db import engine
from app.observability import init_sentry, register_exception_handlers
from app.utils.logging import configure_logging, get_logger


def _build_limiter() -> Limiter:
    return Limiter(key_func=get_remote_address, default_limits=["120/minute"])


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "rate_limit_exceeded", "limit": str(exc.detail)},
    )


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger = get_logger("app.lifespan")
    logger.info(
        "app_startup",
        version=__version__,
        app_env=settings.app_env,
    )
    # Fail-closed secret-strength check (hard fail in production; warn otherwise).
    try:
        from app.utils.secret_strength import evaluate_secret

        for name, value in (
            ("SECRET_KEY", settings.secret_key),
            ("JWT_SECRET_KEY", settings.jwt_secret_key),
        ):
            score = evaluate_secret(name, value)
            if not score.strong:
                msg = (
                    f"weak_secret name={name} reasons={','.join(score.reasons)} "
                    f"length={score.length} entropy_bits={score.entropy_bits}"
                )
                if settings.is_production:
                    logger.error("secret_strength_fail", name=name, reasons=list(score.reasons))
                    raise RuntimeError(msg)
                logger.warning("secret_strength_weak", name=name, reasons=list(score.reasons))
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("secret_strength_check_error", error=str(exc))
    try:
        from app.db import AsyncSessionLocal
        from app.services.receipt_signer import bootstrap_signing_key

        async with AsyncSessionLocal() as session:
            try:
                await bootstrap_signing_key(session)
                await session.commit()
            except Exception as exc:  # pragma: no cover - bootstrap best-effort
                await session.rollback()
                logger.warning("signing_key_bootstrap_error", error=str(exc))
    except Exception as exc:  # pragma: no cover - bootstrap optional at boot
        logger.warning("signing_key_bootstrap_skipped", error=str(exc))
    try:
        yield
    finally:
        logger.info("app_shutdown", version=__version__)
        await engine.dispose()


def create_app() -> FastAPI:
    """Application factory wiring middleware, routes, and lifecycle hooks."""

    configure_logging()
    logger = get_logger("app.factory")

    init_sentry(
        dsn=getattr(settings, "sentry_dsn", "") or "",
        environment=getattr(settings, "env", None) or settings.app_env,
        release=getattr(settings, "app_version", __version__),
        traces_sample_rate=getattr(settings, "sentry_traces_sample_rate", 0.1),
    )

    app = FastAPI(
        title="Once Procurement API",
        version=__version__,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=_lifespan,
    )

    limiter = _build_limiter()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)

    register_exception_handlers(app)

    try:
        from app.middleware.access_log import AccessLogMiddleware
        from app.middleware.body_size import BodySizeLimitMiddleware
        from app.middleware.request_id import RequestIDMiddleware
        from app.middleware.security_headers import SecurityHeadersMiddleware
        from app.middleware.timing import TimingMiddleware

        # Order: add_middleware is LIFO (last added wraps everything else).
        # Desired execution order on the way in:
        #   RequestID -> AccessLog -> Timing -> SecurityHeaders -> BodySize
        #     -> TenantScope -> CSRF -> route
        # So we add them inside-out:
        app.add_middleware(BodySizeLimitMiddleware)
        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(TimingMiddleware)
        app.add_middleware(AccessLogMiddleware)
        app.add_middleware(RequestIDMiddleware)
    except Exception as exc:  # pragma: no cover - middleware optional at boot
        logger.warning("observability_middleware_unavailable", error=str(exc))

    if settings.backend_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.backend_cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    try:
        from app.middleware.tenant_scope import TenantScopeMiddleware

        app.add_middleware(TenantScopeMiddleware)
    except Exception as exc:  # pragma: no cover - middleware optional at boot
        logger.warning("tenant_scope_middleware_unavailable", error=str(exc))

    # --- L3.10 audit ---
    # Audit middleware must wrap routes AFTER tenant_scope (needs tenant_id)
    # and AFTER request_id (needs request_id). Because add_middleware is
    # LIFO, adding it here — AFTER TenantScope — actually places it
    # OUTSIDE TenantScope on the request path. That's intentional: we
    # only emit the audit row when the response is on its way back, and
    # by then ``request.state.tenant_id`` has been populated.
    try:
        from app.middleware.audit_middleware import AuditMiddleware

        app.add_middleware(AuditMiddleware)
    except Exception as exc:  # pragma: no cover - middleware optional at boot
        logger.warning("audit_middleware_unavailable", error=str(exc))
    # --- /L3.10 audit ---

    try:
        from app.middleware.csrf import CSRFMiddleware

        # Double-submit-cookie CSRF protection for browser/cookie clients.
        # Bypasses Bearer-authenticated calls (SPA/extension/verifier all use
        # JWT), `/v1/auth/*`, `/v1/webhooks/*`, `/v1/public/*`, `/verify/*`,
        # and health probes — see DEFAULT_BYPASS_PREFIXES.
        app.add_middleware(CSRFMiddleware)
    except Exception as exc:  # pragma: no cover - middleware optional at boot
        logger.warning("csrf_middleware_unavailable", error=str(exc))

    # API-conventions stack (B9): versioning, conditional requests,
    # idempotency. Each is opt-out-able via env so a deployment can disable
    # them independently while we roll out the contract. add_middleware is
    # LIFO so the outermost on-the-wire wrapper is the last added.
    import os as _os

    def _env_bool(name: str, default: bool) -> bool:
        raw = _os.environ.get(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    if _env_bool("ENABLE_IDEMPOTENCY_MIDDLEWARE", False):
        try:
            from app.middleware.idempotency import IdempotencyMiddleware

            app.add_middleware(IdempotencyMiddleware)
        except Exception as exc:  # pragma: no cover - optional at boot
            logger.warning("idempotency_middleware_unavailable", error=str(exc))

    if _env_bool("ENABLE_CONDITIONAL_REQUEST_MIDDLEWARE", True):
        try:
            from app.middleware.conditional_request import ConditionalRequestMiddleware

            app.add_middleware(ConditionalRequestMiddleware)
        except Exception as exc:  # pragma: no cover - optional at boot
            logger.warning("conditional_request_middleware_unavailable", error=str(exc))

    if _env_bool("ENABLE_VERSIONING_MIDDLEWARE", True):
        try:
            from app.middleware.versioning import ApiVersioningMiddleware

            app.add_middleware(ApiVersioningMiddleware)
        except Exception as exc:  # pragma: no cover - optional at boot
            logger.warning("versioning_middleware_unavailable", error=str(exc))

    try:
        from app.api.v1.openapi_customization import customize_openapi

        customize_openapi(app)
    except Exception as exc:  # pragma: no cover - optional at boot
        logger.warning("openapi_customization_unavailable", error=str(exc))

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    try:
        from app.api.v1.metrics import router as metrics_router

        # Mounted at root so Prometheus scrapes ``/metrics`` (not ``/v1/metrics``).
        app.include_router(metrics_router)
    except Exception as exc:  # pragma: no cover - metrics optional at boot
        logger.warning("metrics_endpoint_unavailable", error=str(exc))

    try:
        # `api_router` already declares prefix="/v1" — do NOT double-prefix.
        from app.api.v1.receipts import public_v1_receipt_router
        from app.api.v1.router import api_router, public_receipt_router

        app.include_router(api_router)
        # Public verifier endpoint lives at the root (no /v1 prefix) so the
        # signed-receipt URL can be shared with auditors without auth context.
        app.include_router(public_receipt_router)
        # Canonical machine-readable alias under /v1 — the external verifier
        # microservice fetches `GET /v1/public/receipts/{receipt_id}`.
        app.include_router(public_v1_receipt_router, prefix="/v1")
    except Exception as exc:  # pragma: no cover - router optional at boot
        logger.error("v1_router_unavailable", error=str(exc))

    # --- L3.3 cockpit ---
    # Founder Cockpit (operator surface). Lives OUTSIDE /v1 — separate
    # JWT secret, separate auth, separate audit trail. The act-as
    # middleware validates ``X-Operator-Acting-Tenant`` headers and
    # audits every cockpit-routed request. Both are best-effort at boot:
    # a misconfigured cockpit must not break tenant traffic.
    try:
        from app.api.cockpit.router import cockpit_router
        from app.middleware.operator_act_as import OperatorActAsMiddleware

        app.include_router(cockpit_router)
        app.add_middleware(OperatorActAsMiddleware)
    except Exception as exc:  # pragma: no cover - cockpit optional at boot
        logger.warning("cockpit_unavailable", error=str(exc))
    # --- /L3.3 cockpit ---

    # --- L3.5 stripe webhooks ---
    # Mounted at /webhooks/stripe (no /v1 prefix) so the Stripe dashboard
    # URL never has to change when the API contract revs. The endpoint
    # reads the raw request body for HMAC verification; CSRF bypasses any
    # path under ``/webhooks/`` (see DEFAULT_BYPASS_PREFIXES). The default
    # 1 MiB body-size limit is well above Stripe's ~256 KB ceiling so no
    # carve-out is needed.
    try:
        from app.api.webhooks import stripe_webhook_router

        app.include_router(stripe_webhook_router)
    except Exception as exc:  # pragma: no cover - billing optional at boot
        logger.warning("stripe_webhook_unavailable", error=str(exc))
    # --- /L3.5 stripe webhooks ---

    # --- L3.9 inbound webhooks ---
    # Postmark inbound JSON webhook. Mounted at /webhooks/postmark/inbound
    # (no /v1 prefix) so the URL we register in the Postmark dashboard is
    # stable. The route enforces its own 30 MiB cap (settings.
    # inbound_max_email_size_mb) before parsing JSON, so the framework
    # body-size middleware doesn't need a per-route carve-out at the cost
    # of a slightly higher early-reject limit. CSRF middleware already
    # bypasses any path under /webhooks/.
    try:
        from app.api.webhooks import postmark_webhook_router

        app.include_router(postmark_webhook_router)
    except Exception as exc:  # pragma: no cover - inbound optional at boot
        logger.warning("postmark_webhook_unavailable", error=str(exc))
    # --- /L3.9 inbound webhooks ---

    return app


app = create_app()
