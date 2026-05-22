"""L3.10 — Audit middleware.

Observes every non-GET HTTP request that has resolved through the
tenant-scope middleware (i.e. ``request.state.tenant_id`` is set) and
emits one chain-linked audit row per request. Writes happen in the
background after the response is dispatched so a slow audit append never
blocks the user-facing response. Best-effort by contract — failures
warn-log without affecting the response.

Skipped paths (out-of-band by design):

* ``/v1/health``
* ``/metrics``
* ``/webhooks/*`` (handlers write their own attributed audit rows)
* ``GET *`` (read traffic; explicit view audits go through the API)

Resource extraction is heuristic but deterministic: it walks the URL
path looking for ``/v1/{collection}/{id}[/…]`` and maps the collection
back to a singular resource type via :data:`_COLLECTION_TO_RESOURCE`.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable, Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app import db as _app_db  # access AsyncSessionLocal via module to honour test patches
from app.models.audit_log import AuditActorType
from app.services.audit_logger import record_audit_event
from app.utils.logging import get_logger

_background_tasks: set[asyncio.Task] = set()


_logger = get_logger(__name__)


_DEFAULT_SKIP_PREFIXES: tuple[str, ...] = (
    "/v1/health",
    "/health",
    "/metrics",
    "/webhooks/",
    "/v1/auth/login",
    "/v1/auth/refresh",
    "/v1/auth/register",
    "/verify/",
    "/docs",
    "/openapi.json",
    "/redoc",
)


# Maps the URL collection segment back to a domain resource type. The
# collection-level grain is the right granularity: `/v1/suppliers/{id}/cois`
# is recorded as `resource_type="supplier"` with the supplier id; deeper
# entity audits should be emitted explicitly by the service layer.
_COLLECTION_TO_RESOURCE: dict[str, str] = {
    "suppliers": "supplier",
    "submissions": "submission",
    "receipts": "receipt",
    "portals": "portal",
    "tenants": "tenant",
    "loss-runs": "loss_run",
    "producer-licenses": "producer_license",
    "eo-certificates": "eo_certificate",
    "acord-forms": "acord_form",
    "risk-schedules": "risk_schedule",
    "imports": "import_job",
    "extractions": "extraction",
    "inbound": "inbound_email",
    "onboarding": "onboarding",
    "billing": "billing",
    "exports": "audit_export",
    "audit": "audit",
    "cois": "coi",
    "consents": "consent",
    "verifier-keys": "verifier_api_key",
}


# HTTP method → action verb. Any future verbs (e.g. "signed", "exported")
# are emitted explicitly by the service layer when they apply.
ACTION_VERBS: dict[str, str] = {
    "POST": "created",
    "PUT": "updated",
    "PATCH": "updated",
    "DELETE": "deleted",
}


_PATH_RE = re.compile(r"^/v1/(?P<collection>[a-z0-9_\-]+)(?:/(?P<id>[^/]+))?")


def extract_resource(path: str) -> tuple[str, str | None]:
    """Return ``(resource_type, resource_id)`` for an HTTP path."""

    m = _PATH_RE.match(path)
    if not m:
        return ("http_request", None)
    collection = m.group("collection")
    resource_type = _COLLECTION_TO_RESOURCE.get(collection, collection.replace("-", "_"))
    raw_id = m.group("id")
    if not raw_id:
        return resource_type, None
    # Filter sub-collection / action segments masquerading as ids.
    if raw_id in {
        "new",
        "reorder",
        "verify",
        "download",
        "envelope",
        "rules",
        "exports",
        "chain",
        "by-resource",
        "me",
    }:
        return resource_type, None
    return resource_type, raw_id


class AuditMiddleware(BaseHTTPMiddleware):
    """Emit one audit-trail row per state-changing authenticated request."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        skip_prefixes: Iterable[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._skip_prefixes: tuple[str, ...] = (
            tuple(skip_prefixes) if skip_prefixes is not None else _DEFAULT_SKIP_PREFIXES
        )

    def _should_skip(self, path: str, method: str) -> bool:
        if method.upper() not in ACTION_VERBS:
            return True
        for prefix in self._skip_prefixes:
            if path == prefix or path.startswith(prefix):
                return True
        return False

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)

        try:
            method = request.method.upper()
            path = request.url.path

            if self._should_skip(path, method):
                return response

            tenant_id = getattr(request.state, "tenant_id", None)
            if not tenant_id:
                # Unauthenticated traffic doesn't belong in the tenant chain.
                return response

            user_id = getattr(request.state, "user_id", None)
            request_id = getattr(request.state, "request_id", None)
            operator_tenant = request.headers.get("X-Operator-Acting-Tenant")

            actor_type = (
                AuditActorType.OPERATOR if operator_tenant else AuditActorType.USER
            )
            resource_type, resource_id = extract_resource(path)
            action_verb = ACTION_VERBS[method]
            client_ip = (
                request.client.host if request.client is not None else None
            )
            user_agent = request.headers.get("user-agent")

            payload_summary = {
                "method": method,
                "path": path,
                "status_code": response.status_code,
            }

            # Fire-and-forget: schedule the write on the running loop so the
            # response returns immediately. The write opens its own session
            # because the request-scoped session is already closed.
            # Write the audit row inline (still best-effort): all exceptions
            # are caught by ``_append_async`` so the response never 500s on
            # audit failure. We previously used ``loop.create_task`` for true
            # fire-and-forget semantics, but that left ordering and
            # observability ambiguous under TestClient/ASGI transports. The
            # inline write adds a few ms but is exactly-once-per-request and
            # observable in tests.
            await _append_async(
                tenant_id=str(tenant_id),
                actor_type=actor_type,
                actor_id=str(user_id) if user_id else None,
                action_verb=action_verb,
                resource_type=resource_type,
                resource_id=resource_id,
                request_id=request_id,
                ip=client_ip,
                user_agent=user_agent,
                payload_summary=payload_summary,
            )
        except Exception as exc:  # noqa: BLE001 - never break the response
            _logger.warning(
                "audit_middleware_dispatch_error",
                error_type=type(exc).__name__,
                error=str(exc),
            )

        return response


async def _append_async(
    *,
    tenant_id: str,
    actor_type: AuditActorType,
    actor_id: str | None,
    action_verb: str,
    resource_type: str,
    resource_id: str | None,
    request_id: str | None,
    ip: str | None,
    user_agent: str | None,
    payload_summary: dict,
) -> None:
    try:
        async with _app_db.AsyncSessionLocal() as session:
            try:
                await record_audit_event(
                    session,
                    tenant_id=tenant_id,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    action_verb=action_verb,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    request_id=request_id,
                    ip=ip,
                    user_agent=user_agent,
                    payload_summary=payload_summary,
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    except Exception as exc:  # noqa: BLE001
        _logger.warning(
            "audit_middleware_write_failed",
            tenant_id=tenant_id,
            resource_type=resource_type,
            error_type=type(exc).__name__,
            error=str(exc),
        )
