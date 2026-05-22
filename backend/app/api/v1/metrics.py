"""Prometheus exposition endpoint.

Gated by ``METRICS_ENABLED`` (default ``true`` in development; recommended
``true`` in all environments). When ``METRICS_TOKEN`` is set, the endpoint
requires ``Authorization: Bearer <token>`` — production deployments MUST set a
token to prevent anonymous scraping. The default registry (which includes the
process + platform collectors registered in ``observability_extras``) is
exposed in standard Prometheus text format.
"""

from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.observability_extras import DEFAULT_REGISTRY, sample_db_pool

router = APIRouter(tags=["meta"])


def _metrics_enabled() -> bool:
    raw = os.environ.get("METRICS_ENABLED", "true").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _expected_token() -> str:
    return (os.environ.get("METRICS_TOKEN") or "").strip()


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        return ""
    scheme, _, token = authorization.partition(" ")
    if scheme.strip().lower() != "bearer":
        return ""
    return token.strip()


@router.get("/metrics", include_in_schema=False)
async def metrics(authorization: str | None = Header(default=None)) -> Response:
    if not _metrics_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="metrics_disabled")

    expected = _expected_token()
    if expected:
        provided = _extract_bearer(authorization)
        if not provided or not hmac.compare_digest(expected, provided):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="metrics_unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Snapshot SQLAlchemy pool gauges right before serialization.
    sample_db_pool()

    payload = generate_latest(DEFAULT_REGISTRY)
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


__all__ = ["router"]
