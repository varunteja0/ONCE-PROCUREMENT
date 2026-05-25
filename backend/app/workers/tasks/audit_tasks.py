"""Audit-chain Celery tasks.

The nightly verifier task computes a SHA-256 digest of yesterday's
``audit_logs`` rows for every active tenant, persisting an
:class:`AuditHashDigest` row that chains to the previous day's digest.

On idempotent re-runs the existing digest is preserved untouched; if
re-verification fails the row is left alone and the task returns a
``mismatch`` summary plus structured-log alert.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

import app.db as app_db
from app.config import settings
from app.models import Tenant
from app.services.audit_hash_service import (
    AuditHashMismatch,
    ensure_daily_digest,
    previous_utc_day,
    verify_daily_digest,
)
from app.utils.logging import get_logger
from app.workers.celery_app import celery_app

__all__ = ["verify_nightly_audit_hash_task"]


_logger = get_logger(__name__)


async def _run_for_all_tenants() -> dict[str, Any]:
    day_utc = previous_utc_day()
    summary: dict[str, Any] = {
        "day_utc": str(day_utc),
        "tenants_total": 0,
        "tenants_new": 0,
        "tenants_verified": 0,
        "tenants_mismatched": 0,
        "tenants_failed": 0,
        "mismatches": [],
    }
    async with app_db.AsyncSessionLocal() as session:
        result = await session.execute(select(Tenant.id))
        tenant_ids = [str(t) for t in result.scalars().all()]
        summary["tenants_total"] = len(tenant_ids)

        for tenant_id in tenant_ids:
            try:
                # If a digest already exists, verify_daily_digest will compare
                # against it; otherwise we persist a fresh digest below.
                try:
                    await verify_daily_digest(session, tenant_id=tenant_id, day_utc=day_utc)
                    summary["tenants_verified"] += 1
                    continue
                except AuditHashMismatch as exc:
                    if exc.context.get("reason") != "missing":
                        # Real tampering signal — DO NOT overwrite. Log + record.
                        summary["tenants_mismatched"] += 1
                        summary["mismatches"].append(
                            {
                                "tenant_id": tenant_id,
                                "stored_digest": exc.context.get("stored_digest"),
                                "recomputed_digest": exc.context.get("recomputed_digest"),
                            }
                        )
                        _logger.error(
                            "audit_hash_mismatch",
                            tenant_id=tenant_id,
                            day_utc=str(day_utc),
                            **{k: v for k, v in exc.context.items() if k not in {"tenant_id", "day_utc"}},
                        )
                        continue

                # No digest yet — compute and persist.
                row = await ensure_daily_digest(session, tenant_id=tenant_id, day_utc=day_utc)
                summary["tenants_new"] += 1
                _logger.info(
                    "audit_hash_digest_new",
                    tenant_id=tenant_id,
                    day_utc=str(day_utc),
                    digest=row.digest_sha256,
                    row_count=row.row_count,
                )
            except Exception as exc:  # noqa: BLE001 — per-tenant resilience
                summary["tenants_failed"] += 1
                _logger.exception(
                    "audit_hash_tenant_error",
                    tenant_id=tenant_id,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )

        await session.commit()

    return summary


@celery_app.task(
    bind=False,
    name="audit.verify_nightly_hash",
    acks_late=True,
)
def verify_nightly_audit_hash_task() -> dict[str, Any]:
    """Compute / verify yesterday's audit-hash digest for every tenant.

    Idempotent: re-runs on the same UTC day do not duplicate digest rows.
    On chain mismatch the task does NOT mutate the stored digest; it logs
    a structured ``audit_hash_mismatch`` event so an alerting layer can
    page the on-call.
    """

    started_at = datetime.now(tz=UTC)
    _logger.info("audit_hash_job_started", at=started_at.isoformat())
    try:
        summary = asyncio.run(_run_for_all_tenants())
    except Exception as exc:  # pragma: no cover - top-level safety net
        _logger.exception(
            "audit_hash_job_unhandled_error",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return {
            "status": "failed",
            "error_type": type(exc).__name__,
            "message": str(exc),
        }

    finished_at = datetime.now(tz=UTC)
    summary.update(
        {
            "status": "ok" if summary["tenants_mismatched"] == 0 and summary["tenants_failed"] == 0 else "alert",
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_sec": (finished_at - started_at).total_seconds(),
        }
    )
    _logger.info("audit_hash_job_completed", **summary)
    return summary


# --- L3.10 audit export ---
# Production-grade audit-trail PDF export. Runs in worker because PDF
# rendering is CPU-bound. Exposes ``generate_audit_export_task`` (Celery)
# and ``generate_audit_export_sync`` (test / local dev path).


async def _generate_export(export_id: str) -> dict[str, Any]:
    import hashlib
    import json as _json
    import os as _os
    import tempfile
    from datetime import timedelta

    from app.models.audit_export import (
        AuditExport,
        AuditExportScope,
        AuditExportStatus,
    )
    from app.models.audit_log import AuditLogEntry
    from app.models.tenant import Tenant
    from app.services.audit_chain import verify_chain
    from app.services.audit_pdf_exporter import render_audit_pdf
    from app.services.audit_signer import sign_envelope
    from app.utils.canonical_json import canonical_json_bytes

    async with app_db.AsyncSessionLocal() as session:
        export = await session.get(AuditExport, export_id)
        if export is None:
            return {"status": "missing", "export_id": export_id}

        export.status = AuditExportStatus.GENERATING
        await session.commit()

        try:
            # Resolve scope → row filter.
            stmt = select(AuditLogEntry).where(AuditLogEntry.tenant_id == export.tenant_id)
            params = export.scope_params or {}
            if export.scope_type == AuditExportScope.SUPPLIER and params.get("supplier_id"):
                stmt = stmt.where(
                    AuditLogEntry.resource_type == "supplier",
                    AuditLogEntry.resource_id == str(params["supplier_id"]),
                )
            elif export.scope_type == AuditExportScope.SUBMISSION and params.get("submission_id"):
                stmt = stmt.where(
                    AuditLogEntry.resource_type == "submission",
                    AuditLogEntry.resource_id == str(params["submission_id"]),
                )
            elif export.scope_type == AuditExportScope.DATE_RANGE:
                if params.get("from"):
                    stmt = stmt.where(AuditLogEntry.occurred_at >= _parse_iso(params["from"]))
                if params.get("to"):
                    stmt = stmt.where(AuditLogEntry.occurred_at < _parse_iso(params["to"]))

            stmt = stmt.order_by(AuditLogEntry.chain_position.asc())
            rows = list((await session.execute(stmt)).scalars().all())

            # Refuse to export a tampered chain.
            chain = await verify_chain(session, tenant_id=export.tenant_id)
            if not chain.valid:
                export.status = AuditExportStatus.FAILED
                export.error = f"chain_invalid: {len(chain.breaks)} break(s) detected"
                export.completed_at = datetime.now(tz=UTC)
                await session.commit()
                return {
                    "status": "failed",
                    "reason": "chain_invalid",
                    "breaks": len(chain.breaks),
                }

            tenant = await session.get(Tenant, export.tenant_id)
            tenant_name = tenant.name if tenant is not None else None

            generated_at = datetime.now(tz=UTC)
            row_summaries = [
                {
                    "id": r.id,
                    "chain_position": r.chain_position,
                    "this_hash": r.this_hash,
                    "occurred_at": r.occurred_at,
                    "actor_type": r.actor_type.value if hasattr(r.actor_type, "value") else str(r.actor_type),
                    "actor_id": r.actor_id,
                    "action_verb": r.action_verb,
                    "resource_type": r.resource_type,
                    "resource_id": r.resource_id,
                    "payload_summary": r.payload_summary,
                }
                for r in rows
            ]

            envelope: dict[str, Any] = {
                "version": "1.0",
                "tenant_id": export.tenant_id,
                "scope": {
                    "type": export.scope_type.value,
                    "params": params,
                },
                "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
                "row_count": len(rows),
                "rows": [
                    {
                        "id": r["id"],
                        "chain_position": r["chain_position"],
                        "this_hash": r["this_hash"],
                        "occurred_at": r["occurred_at"]  # type: ignore[union-attr]
                        .astimezone(UTC)
                        .isoformat()
                        .replace("+00:00", "Z")
                        if r["occurred_at"] is not None
                        else None,
                        "actor_type": r["actor_type"],
                        "actor_id": r["actor_id"],
                        "action_verb": r["action_verb"],
                        "resource_type": r["resource_type"],
                        "resource_id": r["resource_id"],
                    }
                    for r in row_summaries
                ],
                "pdf_sha256": "",  # placeholder — set after rendering
                "first_chain_hash": rows[0].this_hash if rows else None,
                "last_chain_hash": rows[-1].this_hash if rows else None,
            }

            # Render with a placeholder envelope sha so the footer renders;
            # we re-derive deterministic hashes after.
            pdf_bytes = render_audit_pdf(
                tenant_id=export.tenant_id,
                tenant_name=tenant_name,
                scope=envelope["scope"],
                rows=row_summaries,
                generated_at=generated_at,
                signing_key_id=settings.receipt_signing_key_id,
                envelope_sha256="0" * 64,
            )
            pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
            envelope["pdf_sha256"] = pdf_sha256

            sign_envelope(envelope)
            envelope_bytes = (
                canonical_json_bytes(envelope)
                if False
                else _json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
            )
            envelope_sha256 = hashlib.sha256(envelope_bytes).hexdigest()

            # Write to a temp dir owned by the process; expires_at is recorded
            # so a janitor sweep can clean up after 7 days.
            base = _os.environ.get("AUDIT_EXPORT_DIR") or tempfile.gettempdir()
            base_dir = _os.path.join(base, "once-audit-exports", export.tenant_id)
            _os.makedirs(base_dir, exist_ok=True)
            pdf_path = _os.path.join(base_dir, f"{export.id}.pdf")
            env_path = _os.path.join(base_dir, f"{export.id}.envelope.json")
            with open(pdf_path, "wb") as fh:
                fh.write(pdf_bytes)
            with open(env_path, "wb") as fh:
                fh.write(envelope_bytes)

            export.file_path = pdf_path
            export.file_sha256 = pdf_sha256
            export.signed_envelope_path = env_path
            export.envelope_sha256 = envelope_sha256
            export.row_count = len(rows)
            export.expires_at = generated_at + timedelta(days=7)
            export.status = AuditExportStatus.READY
            export.completed_at = generated_at
            export.error = None
            await session.commit()
            return {
                "status": "ready",
                "export_id": export.id,
                "row_count": len(rows),
                "pdf_sha256": pdf_sha256,
            }
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            export = await session.get(AuditExport, export_id)
            if export is not None:
                export.status = AuditExportStatus.FAILED
                export.error = f"{type(exc).__name__}: {exc}"
                export.completed_at = datetime.now(tz=UTC)
                await session.commit()
            _logger.exception("audit_export_failed", export_id=export_id, error=str(exc))
            return {"status": "failed", "export_id": export_id, "error": str(exc)}


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


async def generate_audit_export_sync(export_id: str) -> dict[str, Any]:
    """Test / local-dev entry point — awaits the export generation directly."""

    return await _generate_export(export_id)


@celery_app.task(
    bind=False,
    name="audit.generate_export",
    acks_late=True,
    max_retries=2,
)
def generate_audit_export_task(export_id: str) -> dict[str, Any]:
    """Celery task that renders + signs an audit export."""

    try:
        return asyncio.run(_generate_export(export_id))
    except Exception as exc:  # pragma: no cover - defensive
        _logger.exception("audit_export_unhandled", export_id=export_id)
        return {
            "status": "failed",
            "export_id": export_id,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


__all__ = list(
    set(__all__)
    | {
        "generate_audit_export_task",
        "generate_audit_export_sync",
    }
)
# --- /L3.10 audit export ---
