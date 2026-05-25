"""Orchestrator for the L3.8 PDF-extraction pipeline.

Responsibilities:

1. Resolve a source document (COI / E&O / producer license) to its PDF
   bytes via a pluggable loader. Phase 3 wires real loaders against the
   existing models' ``file_url`` / ``file_id`` columns; a default
   in-memory loader is provided for tests.
2. Run text-layer extraction via
   :mod:`app.services.pdf_extraction.text_extractor`.
3. Dispatch the right entity extractor and persist an
   :class:`~app.models.extraction_result.ExtractionResult` row with
   honest per-field confidence scores.
4. Compute final status (succeeded / partial / failed) from the
   extractor's ``required_fields``.

The Celery task wrapper lives in
:mod:`app.workers.tasks.extraction_tasks`; HTTP entry points live in
:mod:`app.api.v1.extractions`. This module is intentionally HTTP- and
Celery-agnostic.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.extraction_result import (
    ExtractionResult,
    ExtractionSourceType,
    ExtractionStatus,
)
from app.services.pdf_extraction import (
    BasePdfExtractor,
    PdfEncryptedError,
    PdfParseError,
    PdfTooLargeError,
    extract_pages,
    get_extractor,
)
from app.utils.logging import get_logger

__all__ = [
    "ExtractionService",
    "ExtractionNotFoundError",
    "PdfLoaderError",
    "PdfLoader",
    "InMemoryPdfLoader",
    "create_extraction_record",
    "run_extraction",
    "accept_extraction",
    "reject_extraction",
    "get_extraction",
    "list_extractions",
]


_logger = get_logger(__name__)


class ExtractionNotFoundError(Exception):
    pass


class PdfLoaderError(Exception):
    pass


# ---------------------------------------------------------------------------
# PDF loader plumbing
# ---------------------------------------------------------------------------
#
# Production swaps in a real loader (S3 / disk / WebDAV). Tests use the
# in-memory loader so they never touch the filesystem.


PdfLoader = Callable[[str, str, str], Awaitable[bytes]]
"""Async callable: ``(tenant_id, source_type, source_id) -> bytes``."""


class InMemoryPdfLoader:
    """Test-friendly loader. Indexed by ``(tenant_id, type, id)``."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str, str], bytes] = {}

    def put(
        self,
        *,
        tenant_id: str,
        source_type: str | ExtractionSourceType,
        source_id: str,
        blob: bytes,
    ) -> None:
        key = (
            tenant_id,
            source_type.value if isinstance(source_type, ExtractionSourceType) else source_type,
            source_id,
        )
        self._store[key] = blob

    async def __call__(self, tenant_id: str, source_type: str, source_id: str) -> bytes:
        try:
            return self._store[(tenant_id, source_type, source_id)]
        except KeyError as exc:
            raise PdfLoaderError(f"no pdf for tenant={tenant_id} type={source_type} id={source_id}") from exc


# Module-level default loader so the worker + API can share the same one.
_default_loader: PdfLoader = InMemoryPdfLoader()


def set_default_loader(loader: PdfLoader) -> None:
    global _default_loader
    _default_loader = loader


def get_default_loader() -> PdfLoader:
    return _default_loader


# ---------------------------------------------------------------------------
# Service entry points
# ---------------------------------------------------------------------------


async def create_extraction_record(
    session: AsyncSession,
    *,
    tenant_id: str,
    document_type: ExtractionSourceType,
    document_id: str,
) -> ExtractionResult:
    """Insert a fresh PENDING row and return it."""
    extractor = get_extractor(document_type)
    row = ExtractionResult(
        tenant_id=tenant_id,
        source_document_type=document_type.value,
        source_document_id=document_id,
        extractor_version=extractor.version,
        status=ExtractionStatus.PENDING.value,
    )
    session.add(row)
    await session.flush()
    return row


def _classify_status(
    extractor: BasePdfExtractor,
    fields: dict[str, Any],
    confidences: dict[str, float],
) -> ExtractionStatus:
    required = set(extractor.required_fields)
    have = required & set(fields.keys())
    if not have:
        return ExtractionStatus.FAILED
    if have != required:
        return ExtractionStatus.PARTIAL
    low_conf = [k for k in required if confidences.get(k, 0.0) < 0.6]
    if low_conf:
        return ExtractionStatus.PARTIAL
    return ExtractionStatus.SUCCEEDED


async def run_extraction(
    session: AsyncSession,
    *,
    extraction_id: str,
    loader: PdfLoader | None = None,
) -> ExtractionResult:
    """Load the PDF, run the extractor, persist + return the row.

    Always commits its own changes (caller may still wrap in a tx).
    Never raises - failures are recorded on the row as ``status=failed``.
    """
    row = await session.get(ExtractionResult, extraction_id)
    if row is None:
        raise ExtractionNotFoundError(extraction_id)

    if not getattr(settings, "pdf_extraction_enabled", True):
        row.status = ExtractionStatus.FAILED.value
        row.error = "pdf_extraction_disabled"
        await session.commit()
        return row

    pdf_loader = loader or get_default_loader()

    try:
        blob = await pdf_loader(row.tenant_id, row.source_document_type, row.source_document_id)
    except PdfLoaderError as exc:
        row.status = ExtractionStatus.FAILED.value
        row.error = f"loader: {exc}"
        await session.commit()
        return row
    except Exception as exc:
        _logger.exception("extraction_loader_failed", extraction_id=extraction_id)
        row.status = ExtractionStatus.FAILED.value
        row.error = f"loader: {exc}"
        await session.commit()
        return row

    try:
        # Run the (CPU-bound) parser in a thread so we don't block the loop.
        timeout = getattr(settings, "extractor_timeout_seconds", 30)
        pages = await asyncio.wait_for(asyncio.to_thread(extract_pages, blob), timeout=timeout)
    except PdfEncryptedError:
        row.status = ExtractionStatus.FAILED.value
        row.error = "pdf_encrypted"
        await session.commit()
        return row
    except PdfTooLargeError as exc:
        row.status = ExtractionStatus.FAILED.value
        row.error = f"pdf_too_large: {exc}"
        await session.commit()
        return row
    except PdfParseError as exc:
        row.status = ExtractionStatus.FAILED.value
        row.error = f"pdf_parse: {exc}"
        await session.commit()
        return row
    except TimeoutError:
        row.status = ExtractionStatus.FAILED.value
        row.error = "extractor_timeout"
        await session.commit()
        return row

    extractor = get_extractor(row.source_document_type)
    try:
        result = await asyncio.to_thread(extractor.extract, pages)
    except Exception as exc:
        _logger.exception("extractor_crashed", extraction_id=extraction_id)
        row.status = ExtractionStatus.FAILED.value
        row.error = f"extractor: {type(exc).__name__}: {exc}"
        await session.commit()
        return row

    row.extracted_fields = result.fields
    row.field_confidences = result.confidences
    row.warnings = result.warnings or None
    row.status = _classify_status(extractor, result.fields, result.confidences).value
    await session.commit()
    return row


async def get_extraction(session: AsyncSession, *, tenant_id: str, extraction_id: str) -> ExtractionResult | None:
    """Load an extraction with a single tenant-filtered SELECT.

    Cross-tenant ids return ``None`` (caller treats as 404). The previous
    ``session.get`` + post-check pattern violated repo policy and was fragile
    under refactors.
    """

    return await session.scalar(
        select(ExtractionResult).where(
            ExtractionResult.id == extraction_id,
            ExtractionResult.tenant_id == tenant_id,
        )
    )


async def list_extractions(
    session: AsyncSession,
    *,
    tenant_id: str,
    document_type: ExtractionSourceType | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ExtractionResult], int]:
    stmt = select(ExtractionResult).where(ExtractionResult.tenant_id == tenant_id)
    if document_type is not None:
        stmt = stmt.where(ExtractionResult.source_document_type == document_type.value)
    total_stmt = stmt.with_only_columns(ExtractionResult.id)
    total_rows = (await session.execute(total_stmt)).all()
    total = len(total_rows)
    stmt = stmt.order_by(ExtractionResult.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), total


async def accept_extraction(
    session: AsyncSession,
    *,
    tenant_id: str,
    extraction_id: str,
    user_id: str | None,
    fields: dict[str, Any],
) -> ExtractionResult:
    row = await get_extraction(session, tenant_id=tenant_id, extraction_id=extraction_id)
    if row is None:
        raise ExtractionNotFoundError(extraction_id)
    # Merge user overrides over the extractor output.
    merged = dict(row.extracted_fields or {})
    merged.update(fields or {})
    row.extracted_fields = merged
    row.status = ExtractionStatus.ACCEPTED.value
    row.reviewed_by_user_id = user_id
    await session.commit()
    return row


async def reject_extraction(
    session: AsyncSession,
    *,
    tenant_id: str,
    extraction_id: str,
    user_id: str | None,
    reason: str | None,
) -> ExtractionResult:
    row = await get_extraction(session, tenant_id=tenant_id, extraction_id=extraction_id)
    if row is None:
        raise ExtractionNotFoundError(extraction_id)
    row.status = ExtractionStatus.REJECTED.value
    row.reviewed_by_user_id = user_id
    if reason:
        warnings = list(row.warnings or [])
        warnings.append(f"rejected: {reason}")
        row.warnings = warnings
    await session.commit()
    return row


class ExtractionService:
    """Thin object wrapper for code that prefers methods over module-level
    functions. All work delegates to the free functions above."""

    def __init__(self, loader: PdfLoader | None = None) -> None:
        self._loader = loader

    async def create(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        document_type: ExtractionSourceType,
        document_id: str,
    ) -> ExtractionResult:
        return await create_extraction_record(
            session,
            tenant_id=tenant_id,
            document_type=document_type,
            document_id=document_id,
        )

    async def run(self, session: AsyncSession, *, extraction_id: str) -> ExtractionResult:
        return await run_extraction(session, extraction_id=extraction_id, loader=self._loader)
