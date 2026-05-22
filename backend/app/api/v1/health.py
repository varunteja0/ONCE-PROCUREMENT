from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["health"])

CheckResult = Literal["ok", "fail", "skipped"]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


async def _check_db(session: AsyncSession) -> CheckResult:
    try:
        result = await session.execute(text("SELECT 1"))
        result.scalar_one()
        return "ok"
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("health.db_failed", error=str(exc))
        return "fail"


async def _check_redis() -> CheckResult:
    redis_url = getattr(settings, "redis_url", "") or ""
    if not redis_url.strip():
        return "skipped"
    try:
        import redis.asyncio as redis_asyncio
    except ImportError:
        logger.debug("health.redis_client_unavailable")
        return "skipped"

    client = None
    try:
        client = redis_asyncio.from_url(
            redis_url, socket_connect_timeout=1.0, socket_timeout=1.0
        )
        await asyncio.wait_for(client.ping(), timeout=1.0)
        return "ok"
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("health.redis_failed", error=str(exc))
        return "fail"
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception as exc:  # pragma: no cover - close best-effort
                logger.debug("health.redis_close_failed", error=str(exc))


@router.get("/health/live", summary="Liveness probe (process alive only)")
async def health_live() -> dict[str, str]:
    """Always 200 while the process is alive. Suitable for Fly liveness."""

    return {"status": "ok", "time": _utc_now_iso()}


@router.get("/health", summary="Readiness probe (DB + Redis checks)")
async def health(session: AsyncSession = Depends(get_db)) -> JSONResponse:
    db_status, redis_status = await asyncio.gather(
        _check_db(session),
        _check_redis(),
    )

    checks: dict[str, CheckResult] = {"db": db_status, "redis": redis_status}
    all_ok = db_status == "ok" and redis_status in ("ok", "skipped")

    body: dict[str, Any] = {
        "status": "ok" if all_ok else "fail",
        "version": getattr(settings, "app_version", "0.0.0"),
        "time": _utc_now_iso(),
        "checks": checks,
    }
    return JSONResponse(
        body,
        status_code=(
            status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
    )


@router.get("/ready", summary="Readiness alias (DB only) — back-compat")
async def ready(session: AsyncSession = Depends(get_db)) -> JSONResponse:
    db_status = await _check_db(session)
    if db_status != "ok":
        return JSONResponse(
            {"status": "not_ready", "database": "unavailable"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return JSONResponse({"status": "ready", "database": "ok"})


__all__ = ["router"]
