"""Append-only cockpit audit writer.

Every cockpit-routed request, and every "act-as" request, produces exactly
one row here. Writes are best-effort: a failure to record an audit row is
warn-logged but never propagates to a 500 (so a transient DB hiccup cannot
break the operator surface). Operators who deliberately suppress audit
records are still caught by the structlog ``security.cockpit_login`` /
``security.cockpit_request`` stream which is independent.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

import app.db as app_db
from app.models import CockpitAudit
from app.utils.logging import get_logger

__all__ = [
    "redact_payload",
    "write_audit",
    "write_audit_async",
    "REDACTED",
]


_logger = get_logger(__name__)
REDACTED: str = "[REDACTED]"

_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "x-csrf-token",
        "password",
        "totp_code",
        "refresh_token",
        "access_token",
        "secret",
        "api_key",
    }
)


def redact_payload(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Recursively redact sensitive keys.

    Returns ``None`` when input is ``None`` so callers can pass it
    through directly to the JSON column.
    """

    if payload is None:
        return None

    def _walk(value: Any) -> Any:
        if isinstance(value, Mapping):
            out: dict[str, Any] = {}
            for k, v in value.items():
                if str(k).lower() in _SENSITIVE_KEYS:
                    out[str(k)] = REDACTED
                else:
                    out[str(k)] = _walk(v)
            return out
        if isinstance(value, list):
            return [_walk(v) for v in value]
        if isinstance(value, tuple):
            return [_walk(v) for v in value]
        return value

    walked = _walk(dict(payload))
    if isinstance(walked, dict):
        return walked
    return {"value": walked}


async def write_audit(
    session: AsyncSession,
    *,
    operator_id: str | None,
    tenant_id_acted_as: str | None,
    action: str,
    resource_type: str = "cockpit",
    resource_id: str | None = None,
    request_id: str | None = None,
    method: str | None = None,
    path: str | None = None,
    status_code: int | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    payload: Mapping[str, Any] | None = None,
) -> None:
    """Append one row to ``cockpit_audit`` on the given session.

    The caller owns the surrounding transaction; this function only
    ``add()``s and ``flush()``es so that a downstream rollback wipes the
    half-written audit too.
    """

    try:
        session.add(
            CockpitAudit(
                operator_id=operator_id,
                tenant_id_acted_as=tenant_id_acted_as,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                request_id=request_id,
                method=method,
                path=(path or "")[:512] or None,
                status_code=status_code,
                ip=ip,
                user_agent=(user_agent or "")[:512] or None,
                payload_redacted=redact_payload(payload),
            )
        )
        await session.flush()
    except Exception as exc:  # pragma: no cover - defensive: audit must not break the request
        _logger.warning("cockpit_audit_write_failed", error=str(exc), action=action)


async def write_audit_async(
    *,
    operator_id: str | None,
    tenant_id_acted_as: str | None,
    action: str,
    **kwargs: Any,
) -> None:
    """Fire-and-forget audit write using a fresh session.

    Used by middleware where the request session is already committed /
    closed by the time we're ready to record the audit row.
    """

    try:
        async with app_db.AsyncSessionLocal() as session:
            await write_audit(
                session,
                operator_id=operator_id,
                tenant_id_acted_as=tenant_id_acted_as,
                action=action,
                **kwargs,
            )
            await session.commit()
    except Exception as exc:  # pragma: no cover - audit best-effort
        _logger.warning("cockpit_audit_async_failed", error=str(exc), action=action)
