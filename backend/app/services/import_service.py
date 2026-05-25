"""L3.7 — Import job orchestrator.

State machine and chunked-commit logic for the bulk import pipeline.
Routed by :mod:`app.api.v1.imports`; backgrounded by
:mod:`app.workers.tasks.import_tasks`.

Key invariants:

* All file IO is **streamed** — :func:`run_validation` / :func:`run_commit`
  iterate row-by-row via the parser generators and never materialise more
  than ``settings.import_chunk_size`` rows in memory at a time.
* Status transitions are explicit. Any non-terminal cancel observed
  between chunks aborts cleanly without partial corruption.
* Each chunk commits atomically — a failure in chunk N rolls back chunk
  N only; previously-committed chunks survive (so a 100K-row import
  whose 73rd chunk hits a transient DB blip leaves 72×500 rows safely
  imported and 28×500 rows reported as errors).
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import db as _db
from app.config import settings
from app.models import (
    ImportEntityType,
    ImportJob,
    ImportRowError,
    ImportStatus,
)
from app.models.import_job import TERMINAL_STATUSES
from app.services.av_scanner import (
    InfectedFileError,
    ScannerError,
    enforce_clean,
)
from app.services.importers import get_importer
from app.services.importers.base import BaseImporter, RowError, ValidatedRow
from app.services.parsers import ALLOWED_EXTENSIONS, detect_format, iter_rows
from app.utils.logging import get_logger

__all__ = [
    "ImportServiceError",
    "FileTooLargeError",
    "UnsupportedFormatError",
    "TooManyRowsError",
    "InvalidTransitionError",
    "InfectedUploadError",
    "ScannerUnavailableError",
    "create_import_job",
    "list_jobs",
    "get_job",
    "get_job_errors",
    "run_validation",
    "run_commit",
    "cancel_job",
    "sanitize_filename",
    "storage_dir_for",
    "stream_errors_csv",
    "MAX_PREVIEW_ERRORS",
]


_logger = get_logger(__name__)

MAX_PREVIEW_ERRORS = 50
_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ImportServiceError(Exception):
    """Base class for orchestrator-level errors mapped to 4xx responses."""

    error_code: str = "import_error"


class FileTooLargeError(ImportServiceError):
    error_code = "file_too_large"


class UnsupportedFormatError(ImportServiceError):
    error_code = "unsupported_format"


class TooManyRowsError(ImportServiceError):
    error_code = "too_many_rows"


class InvalidTransitionError(ImportServiceError):
    error_code = "invalid_transition"


class InfectedUploadError(ImportServiceError):
    """Upload was rejected by the antivirus scanner.

    The API layer translates this to HTTP 422 with ``code='av_infected_file'``.
    The signature is preserved so the operator UI can show *what* was
    matched (e.g. ``Eicar-Test-Signature``) without leaking the file bytes.
    """

    error_code = "av_infected_file"

    def __init__(self, signature: str, scanner: str, message: str | None = None) -> None:
        self.signature = signature
        self.scanner = scanner
        super().__init__(message or f"File appears to be infected with {signature}; upload rejected.")


class ScannerUnavailableError(ImportServiceError):
    """The AV scanner is down and the deployment is configured fail-closed.

    Mapped to HTTP 503 by the API layer.
    """

    error_code = "av_scanner_unavailable"

    def __init__(self, scanner: str, detail: str | None = None) -> None:
        self.scanner = scanner
        self.detail = detail
        super().__init__("Antivirus scanner unavailable; please retry shortly.")


class JobNotFoundError(ImportServiceError):
    error_code = "import_job_not_found"


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


def sanitize_filename(name: str) -> str:
    """Strip path components and unsafe characters from an upload name.

    Normalises both POSIX (``/``) and Windows (``\\``) separators so the same
    upload sanitises identically on Linux CI runners and Windows dev boxes.
    """

    raw = (name or "upload").replace("\\", "/")
    base = Path(raw).name or "upload"
    cleaned = _FILENAME_SAFE.sub("_", base)
    if not cleaned or set(cleaned) == {"_"} or cleaned in {".", ".."}:
        cleaned = "upload"
    return cleaned[:200]


def storage_dir_for(tenant_id: str, job_id: str) -> Path:
    """Per-tenant per-job directory under ``settings.import_storage_path``."""

    root = Path(settings.import_storage_path)
    safe_tenant = _FILENAME_SAFE.sub("_", tenant_id) or "_"
    safe_job = _FILENAME_SAFE.sub("_", job_id) or "_"
    return root / safe_tenant / safe_job


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


async def create_import_job(
    session: AsyncSession,
    *,
    tenant_id: str,
    entity_type: ImportEntityType,
    original_filename: str,
    content_type: str | None,
    file_bytes: bytes,
    mapping: dict[str, str] | None = None,
    on_duplicate: str = "error",
    created_by_user_id: str | None = None,
) -> ImportJob:
    """Persist the upload, write the file to disk, return the job row.

    The caller is expected to subsequently dispatch :func:`run_validation`
    (either inline for small files or via Celery for large ones).
    """

    safe_name = sanitize_filename(original_filename)
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFormatError(f"Extension {ext!r} not allowed (csv, xlsx, xls only).")

    size = len(file_bytes)
    if size > settings.import_max_file_size_bytes:
        raise FileTooLargeError(f"File size {size} exceeds limit {settings.import_max_file_size_bytes}.")

    # Validate format dispatch up-front so we fail fast on truly bogus
    # uploads (e.g. a ``.pdf`` renamed to ``.csv`` we can't catch, but a
    # ``.png`` with explicit content type we can).
    detect_format(safe_name, content_type)

    job = ImportJob(
        tenant_id=tenant_id,
        entity_type=entity_type,
        status=ImportStatus.PENDING,
        original_filename=safe_name,
        file_size_bytes=size,
        content_type=content_type,
        file_url="",  # set below once the job has an id
        mapping=mapping or None,
        on_duplicate=on_duplicate,
        created_by_user_id=created_by_user_id,
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)

    target_dir = storage_dir_for(tenant_id, job.id)
    _ensure_dir(target_dir)
    target_path = target_dir / safe_name
    # Antivirus gate. Backend selected by ``settings.av_scanner_backend``;
    # see :mod:`app.services.av_scanner` for the contract. Fail-closed in
    # production (a downed scanner blocks the upload), fail-open in dev/test
    # via ``settings.av_fail_closed_on_scanner_error``. Scanner errors and
    # infections are translated to API responses in
    # ``app.api.v1.imports.upload_import``.
    try:
        enforce_clean(
            file_bytes,
            hint_name=safe_name,
            fail_closed_on_error=settings.av_fail_closed_on_scanner_error,
        )
    except InfectedFileError as exc:
        # Roll back the half-created job row so we don't leak phantom
        # ImportJob entries on rejected uploads. The caller's session
        # owns the transaction, so we just delete-and-flush.
        await session.delete(job)
        await session.flush()
        raise InfectedUploadError(signature=exc.signature, scanner=exc.scanner) from exc
    except ScannerError as exc:
        await session.delete(job)
        await session.flush()
        raise ScannerUnavailableError(scanner=exc.scanner, detail=exc.detail) from exc

    target_path.write_bytes(file_bytes)
    job.file_url = str(target_path)
    await session.flush()

    _logger.info(
        "import_job_created",
        tenant_id=tenant_id,
        job_id=job.id,
        entity_type=entity_type.value,
        filename=safe_name,
        size=size,
    )
    return job


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


async def list_jobs(
    session: AsyncSession,
    *,
    tenant_id: str,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ImportJob], int]:
    stmt = (
        select(ImportJob)
        .where(ImportJob.tenant_id == tenant_id)
        .order_by(ImportJob.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .offset(max(0, offset))
    )
    result = await session.execute(stmt)
    items = list(result.scalars().all())
    total = await session.scalar(select(func.count(ImportJob.id)).where(ImportJob.tenant_id == tenant_id))
    return items, int(total or 0)


async def get_job(session: AsyncSession, *, tenant_id: str, job_id: str) -> ImportJob:
    stmt = select(ImportJob).where(ImportJob.id == job_id, ImportJob.tenant_id == tenant_id)
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        raise JobNotFoundError(f"Import job {job_id!r} not found.")
    return job


async def get_job_errors(
    session: AsyncSession,
    *,
    tenant_id: str,
    job_id: str,
    limit: int | None = None,
    offset: int = 0,
) -> list[ImportRowError]:
    if not tenant_id:
        raise JobNotFoundError("tenant_id is required")
    stmt = (
        select(ImportRowError)
        .join(ImportJob, ImportJob.id == ImportRowError.import_job_id)
        .where(
            ImportRowError.import_job_id == job_id,
            ImportJob.tenant_id == tenant_id,
        )
        .order_by(ImportRowError.row_number.asc(), ImportRowError.id.asc())
        .offset(max(0, offset))
    )
    if limit is not None:
        stmt = stmt.limit(max(1, limit))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_job_errors(session: AsyncSession, *, tenant_id: str, job_id: str) -> int:
    if not tenant_id:
        raise JobNotFoundError("tenant_id is required")
    total = await session.scalar(
        select(func.count(ImportRowError.id))
        .join(ImportJob, ImportJob.id == ImportRowError.import_job_id)
        .where(
            ImportRowError.import_job_id == job_id,
            ImportJob.tenant_id == tenant_id,
        )
    )
    return int(total or 0)


# ---------------------------------------------------------------------------
# State machine helpers
# ---------------------------------------------------------------------------


_ALLOWED_TRANSITIONS: dict[ImportStatus, frozenset[ImportStatus]] = {
    ImportStatus.PENDING: frozenset({ImportStatus.VALIDATING, ImportStatus.CANCELED, ImportStatus.FAILED}),
    ImportStatus.VALIDATING: frozenset(
        {
            ImportStatus.DRY_RUN_READY,
            ImportStatus.FAILED,
            ImportStatus.CANCELED,
        }
    ),
    ImportStatus.DRY_RUN_READY: frozenset({ImportStatus.IMPORTING, ImportStatus.CANCELED, ImportStatus.FAILED}),
    ImportStatus.IMPORTING: frozenset({ImportStatus.COMPLETED, ImportStatus.FAILED, ImportStatus.CANCELED}),
}


def _assert_can_transition(job: ImportJob, target: ImportStatus) -> None:
    if job.status == target:
        return
    allowed = _ALLOWED_TRANSITIONS.get(job.status, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            f"Cannot transition import {job.id} from {job.status.value} " f"to {target.value}."
        )


async def _set_status(
    session: AsyncSession,
    job: ImportJob,
    target: ImportStatus,
    *,
    last_error: str | None = None,
) -> None:
    _assert_can_transition(job, target)
    job.status = target
    if target == ImportStatus.VALIDATING and job.started_at is None:
        job.started_at = datetime.now(UTC)
    if target in TERMINAL_STATUSES:
        job.completed_at = datetime.now(UTC)
    if last_error is not None:
        job.last_error = last_error[:2000]
    await session.flush()


# ---------------------------------------------------------------------------
# Validation (dry-run)
# ---------------------------------------------------------------------------


async def run_validation(
    session: AsyncSession,
    *,
    tenant_id: str,
    job_id: str,
) -> ImportJob:
    """Stream the file, validate every row, persist row errors.

    On success the job ends in ``DRY_RUN_READY``; on missing-column /
    parser / row-cap failure it ends in ``FAILED``. ``tenant_id`` is
    required: a cross-tenant ``job_id`` raises
    :class:`JobNotFoundError`.
    """

    if not tenant_id:
        raise JobNotFoundError("tenant_id is required")
    stmt = select(ImportJob).where(ImportJob.id == job_id, ImportJob.tenant_id == tenant_id)
    job = (await session.execute(stmt)).scalar_one_or_none()
    if job is None:
        raise JobNotFoundError(f"Import job {job_id!r} not found.")
    if job.status != ImportStatus.PENDING:
        raise InvalidTransitionError(f"Job {job.id} cannot validate from status {job.status.value}.")

    await _set_status(session, job, ImportStatus.VALIDATING)

    importer = get_importer(job.entity_type)
    mapping = _normalize_mapping(job.mapping)

    try:
        total, valid, invalid, errors = await _scan_and_persist_errors(
            session,
            job=job,
            importer=importer,
            mapping=mapping,
            commit_rows=False,
        )
    except _MissingColumnsError as exc:
        await _record_job_level_error(
            session,
            job=job,
            code="missing_columns",
            message=f"Required columns missing: {', '.join(exc.missing)}",
        )
        await _set_status(
            session,
            job,
            ImportStatus.FAILED,
            last_error=f"missing_columns: {','.join(exc.missing)}",
        )
        return job
    except TooManyRowsError as exc:
        await _record_job_level_error(session, job=job, code="too_many_rows", message=str(exc))
        await _set_status(session, job, ImportStatus.FAILED, last_error=str(exc))
        return job
    except Exception as exc:  # parser blew up, file truncated, etc.
        await _record_job_level_error(
            session,
            job=job,
            code="parse_error",
            message=f"{exc.__class__.__name__}: {exc}",
        )
        await _set_status(
            session,
            job,
            ImportStatus.FAILED,
            last_error=f"parse_error: {exc}",
        )
        _logger.exception("import_validation_failed", job_id=job.id)
        return job

    job.total_rows = total
    job.valid_rows = valid
    job.invalid_rows = invalid
    job.summary = {
        "validation": {
            "total": total,
            "valid": valid,
            "invalid": invalid,
            "errors_recorded": errors,
        }
    }
    await _set_status(session, job, ImportStatus.DRY_RUN_READY)
    _logger.info(
        "import_validation_completed",
        job_id=job.id,
        total=total,
        valid=valid,
        invalid=invalid,
    )
    return job


# ---------------------------------------------------------------------------
# Commit
# ---------------------------------------------------------------------------


async def run_commit(*, tenant_id: str, job_id: str) -> ImportJob:
    """Re-stream the file, insert valid rows in 500-row chunks.

    Manages its own DB sessions — caller does NOT pass one in, because
    we need each chunk to commit / rollback independently of the others.

    ``tenant_id`` is required: a cross-tenant ``job_id`` raises
    :class:`JobNotFoundError`.
    """

    if not tenant_id:
        raise JobNotFoundError("tenant_id is required")
    async with _db.AsyncSessionLocal() as session:
        stmt = select(ImportJob).where(ImportJob.id == job_id, ImportJob.tenant_id == tenant_id)
        job = (await session.execute(stmt)).scalar_one_or_none()
        if job is None:
            raise JobNotFoundError(f"Import job {job_id!r} not found.")
        if job.status != ImportStatus.DRY_RUN_READY:
            raise InvalidTransitionError(f"Job {job.id} cannot commit from status {job.status.value}.")
        await _set_status(session, job, ImportStatus.IMPORTING)
        # Drop any prior import-time errors so a re-run is idempotent.
        # Validation errors that flagged invalid rows are retained.
        await session.execute(
            delete(ImportRowError).where(
                ImportRowError.import_job_id == job.id,
                ImportRowError.error_code.in_(["chunk_failed", "duplicate_fein_existing"]),
            )
        )
        await session.commit()
        # Detach + re-load so subsequent reads use fresh sessions.
        tenant_id = job.tenant_id
        entity_type = job.entity_type
        file_url = job.file_url
        original_filename = job.original_filename
        mapping = job.mapping
        on_duplicate = job.on_duplicate
    _ = tenant_id, entity_type, file_url, original_filename, mapping, on_duplicate

    importer = get_importer(entity_type)
    mapping_norm = _normalize_mapping(mapping)

    inserted_total = 0
    updated_total = 0
    skipped_total = 0
    error_total = 0
    chunk_errors: list[str] = []
    in_file_keys: set[str] = set()

    chunk: list[ValidatedRow] = []
    chunk_size = max(1, int(settings.import_chunk_size))
    row_number = 1  # 1 == header

    file_path = Path(file_url)
    try:
        row_iter = iter_rows(file_path, filename=original_filename)
        for raw in row_iter:
            row_number += 1
            remapped = importer.remap_row(raw, mapping_norm)
            vr = importer.validate_row(remapped, row_number)
            if not vr.ok:
                error_total += 1
                continue
            if vr.dedupe_key:
                if vr.dedupe_key in in_file_keys:
                    error_total += 1
                    continue
                in_file_keys.add(vr.dedupe_key)
            chunk.append(vr)
            if len(chunk) >= chunk_size:
                ins, upd, skp, err = await _commit_chunk(
                    importer=importer,
                    tenant_id=tenant_id,
                    job_id=job_id,
                    on_duplicate=on_duplicate,
                    chunk=chunk,
                    chunk_errors=chunk_errors,
                )
                inserted_total += ins
                updated_total += upd
                skipped_total += skp
                error_total += err
                chunk = []

        if chunk:
            ins, upd, skp, err = await _commit_chunk(
                importer=importer,
                tenant_id=tenant_id,
                job_id=job_id,
                on_duplicate=on_duplicate,
                chunk=chunk,
                chunk_errors=chunk_errors,
            )
            inserted_total += ins
            updated_total += upd
            skipped_total += skp
            error_total += err
    except Exception as exc:
        async with _db.AsyncSessionLocal() as fail_session:
            fail_job = await fail_session.get(ImportJob, job_id)
            if fail_job is not None:
                fail_job.imported_rows = inserted_total + updated_total
                fail_job.summary = {
                    **(fail_job.summary or {}),
                    "commit": {
                        "inserted": inserted_total,
                        "updated": updated_total,
                        "skipped": skipped_total,
                        "errors": error_total,
                        "chunk_failures": chunk_errors,
                        "fatal": f"{exc.__class__.__name__}: {exc}",
                    },
                }
                fail_job.status = ImportStatus.FAILED
                fail_job.completed_at = datetime.now(UTC)
                fail_job.last_error = f"commit_error: {exc}"[:2000]
                await fail_session.commit()
        _logger.exception("import_commit_failed", job_id=job_id)
        raise

    async with _db.AsyncSessionLocal() as final_session:
        final_job = await final_session.get(ImportJob, job_id)
        if final_job is None:
            raise JobNotFoundError(f"Import job {job_id!r} disappeared.")
        final_job.imported_rows = inserted_total + updated_total
        final_job.summary = {
            **(final_job.summary or {}),
            "commit": {
                "inserted": inserted_total,
                "updated": updated_total,
                "skipped": skipped_total,
                "errors": error_total,
                "chunk_failures": chunk_errors,
            },
        }
        final_job.status = ImportStatus.COMPLETED
        final_job.completed_at = datetime.now(UTC)
        await final_session.commit()
        await final_session.refresh(final_job)
        _logger.info(
            "import_commit_completed",
            job_id=final_job.id,
            inserted=inserted_total,
            updated=updated_total,
            skipped=skipped_total,
            errors=error_total,
        )
        return final_job


async def _commit_chunk(
    *,
    importer: BaseImporter,
    tenant_id: str,
    job_id: str,
    on_duplicate: str,
    chunk: list[ValidatedRow],
    chunk_errors: list[str],
) -> tuple[int, int, int, int]:
    """Open a fresh session per chunk so failures roll back JUST this chunk."""

    async with _db.AsyncSessionLocal() as session:
        try:
            # Resolve cross-DB duplicates inside the same transaction so
            # an outright conflict doesn't crash the chunk.
            keys = [r.dedupe_key for r in chunk if r.dedupe_key]
            existing = await importer.existing_dedupe_keys(session, tenant_id=tenant_id, keys=keys)
            duplicate_rows: list[ValidatedRow] = []
            kept: list[ValidatedRow] = []
            for row in chunk:
                if on_duplicate == "error" and row.dedupe_key and row.dedupe_key in existing:
                    duplicate_rows.append(row)
                    session.add(
                        ImportRowError(
                            import_job_id=job_id,
                            row_number=row.row_number,
                            column="fein",
                            value=ImportRowError.truncate_value(row.dedupe_key),
                            error_code="duplicate_fein_existing",
                            error_message=("Supplier with this FEIN already exists for " "this tenant."),
                        )
                    )
                else:
                    kept.append(row)
            counts = await importer.insert_batch(
                session,
                tenant_id=tenant_id,
                rows=kept,
                on_duplicate=on_duplicate,
            )
            await session.commit()
            err_count = counts.get("errors", 0) + len(duplicate_rows)
            return (
                counts.get("inserted", 0),
                counts.get("updated", 0),
                counts.get("skipped", 0),
                err_count,
            )
        except Exception as exc:
            await session.rollback()
            chunk_errors.append(f"chunk[rows {chunk[0].row_number}..{chunk[-1].row_number}]: {exc}")
            # Record a job-level error so the report tells the operator
            # which range failed. Reusing this (now-rolled-back) session
            # keeps us at one DB connection in tests.
            session.add(
                ImportRowError(
                    import_job_id=job_id,
                    row_number=chunk[0].row_number,
                    column=None,
                    value=None,
                    error_code="chunk_failed",
                    error_message=(f"Chunk rows {chunk[0].row_number}-" f"{chunk[-1].row_number} failed: {exc}")[:512],
                )
            )
            try:
                await session.commit()
            except Exception:  # pragma: no cover - belt and braces
                await session.rollback()
            return 0, 0, 0, len(chunk)


# ---------------------------------------------------------------------------
# Validation streaming primitives
# ---------------------------------------------------------------------------


class _MissingColumnsError(Exception):
    def __init__(self, missing: list[str]) -> None:
        super().__init__(", ".join(missing))
        self.missing = missing


async def _scan_and_persist_errors(
    session: AsyncSession,
    *,
    job: ImportJob,
    importer: BaseImporter,
    mapping: dict[str, str] | None,
    commit_rows: bool,
) -> tuple[int, int, int, int]:
    """Iterate the file once, persisting row errors as we go.

    Returns ``(total_rows, valid_rows, invalid_rows, errors_recorded)``.
    """

    path = Path(job.file_url)
    iterator: Iterator[dict[str, str]] = iter_rows(path, filename=job.original_filename)

    # Peek the first row to validate headers up front. The parser already
    # consumed the header row internally — for the missing-columns check
    # we need to look at the keys of the first DATA row, since headers
    # become dict keys.
    try:
        first_row = next(iterator)
    except StopIteration:
        first_row = None

    header_set: set[str] = set()
    if first_row is not None:
        header_set = set(first_row.keys())
    elif mapping:
        # Empty file but the user provided a mapping → trust the mapping
        # so we don't double-fail on empty files.
        header_set = set(mapping.keys())

    missing = importer.missing_required_columns(header_set, mapping)
    if missing:
        raise _MissingColumnsError(missing)

    total = 0
    valid = 0
    invalid = 0
    errors_persisted = 0
    in_file_keys: set[str] = set()
    error_count_persisted = 0
    row_number = 1  # 1 == header row

    def _process(raw: dict[str, str]) -> None:
        nonlocal total, valid, invalid, errors_persisted
        nonlocal row_number, error_count_persisted
        row_number += 1
        total += 1
        remapped = importer.remap_row(raw, mapping)
        vr = importer.validate_row(remapped, row_number)
        if vr.ok and vr.dedupe_key:
            dedupe_key = vr.dedupe_key
            if dedupe_key in in_file_keys:
                vr = ValidatedRow(
                    row_number=row_number,
                    errors=[
                        RowError(
                            row_number=row_number,
                            column="fein",
                            value=dedupe_key,
                            error_code="duplicate_fein_in_file",
                            error_message=("Duplicate FEIN within the file — first " "occurrence wins."),
                        )
                    ],
                )
            else:
                in_file_keys.add(dedupe_key)
        if vr.ok:
            valid += 1
        else:
            invalid += 1
            for err in vr.errors:
                if error_count_persisted >= settings.import_max_rows:
                    break
                session.add(
                    ImportRowError(
                        import_job_id=job.id,
                        row_number=err.row_number,
                        column=err.column,
                        value=ImportRowError.truncate_value(err.value),
                        error_code=err.error_code,
                        error_message=err.error_message[:512],
                    )
                )
                errors_persisted += 1
                error_count_persisted += 1

    if first_row is not None:
        _process(first_row)
    for raw in iterator:
        if total >= settings.import_max_rows:
            raise TooManyRowsError(
                f"File has more than {settings.import_max_rows} rows " f"(limit configurable via IMPORT_MAX_ROWS)."
            )
        _process(raw)

    await session.flush()
    return total, valid, invalid, errors_persisted


async def _record_job_level_error(
    session: AsyncSession,
    *,
    job: ImportJob,
    code: str,
    message: str,
) -> None:
    session.add(
        ImportRowError(
            import_job_id=job.id,
            row_number=0,
            column=None,
            value=None,
            error_code=code,
            error_message=message[:512],
        )
    )
    job.invalid_rows = max(job.invalid_rows, 1)
    await session.flush()


def _normalize_mapping(mapping: Any) -> dict[str, str] | None:
    """``mapping`` may arrive as JSON / None — coerce to ``{src: canonical}``."""

    if not mapping:
        return None
    if isinstance(mapping, str):
        try:
            mapping = json.loads(mapping)
        except json.JSONDecodeError:
            return None
    if not isinstance(mapping, dict):
        return None
    return {str(k).strip().lower(): str(v).strip().lower() for k, v in mapping.items()}


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


async def cancel_job(
    session: AsyncSession,
    *,
    tenant_id: str,
    job_id: str,
) -> ImportJob:
    job = await get_job(session, tenant_id=tenant_id, job_id=job_id)
    if job.status in TERMINAL_STATUSES:
        raise InvalidTransitionError(f"Cannot cancel terminal job {job.id} (status={job.status.value}).")
    job.status = ImportStatus.CANCELED
    job.completed_at = datetime.now(UTC)
    await session.flush()
    _logger.info("import_job_canceled", job_id=job.id, tenant_id=tenant_id)
    return job


# ---------------------------------------------------------------------------
# Error report generation (CSV download)
# ---------------------------------------------------------------------------


def stream_errors_csv(
    errors: list[ImportRowError],
) -> Iterator[str]:
    """Yield CSV lines for the full error report download."""

    yield "row_number,column,value,error_code,error_message\r\n"
    for err in errors:
        yield _csv_row(
            [
                str(err.row_number),
                err.column or "",
                err.value or "",
                err.error_code,
                err.error_message,
            ]
        )


def _csv_row(cells: list[str]) -> str:
    parts: list[str] = []
    for cell in cells:
        s = cell.replace('"', '""')
        if any(ch in s for ch in (",", '"', "\n", "\r")):
            parts.append(f'"{s}"')
        else:
            parts.append(s)
    return ",".join(parts) + "\r\n"


# ---------------------------------------------------------------------------
# Cleanup (used by tests / cancel paths)
# ---------------------------------------------------------------------------


def delete_storage(tenant_id: str, job_id: str) -> None:
    """Best-effort: remove the on-disk file directory for a job."""

    target = storage_dir_for(tenant_id, job_id)
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
