"""L3.7 — REST API for the bulk-import pipeline.

Endpoints:

* ``POST   /v1/imports``                     — upload + kick off validation
* ``GET    /v1/imports``                     — list tenant's jobs
* ``GET    /v1/imports/{id}``                — detail + first 50 errors
* ``GET    /v1/imports/{id}/errors.csv``     — full error report (CSV)
* ``POST   /v1/imports/{id}/commit``         — flip DRY_RUN_READY → IMPORTING
* ``POST   /v1/imports/{id}/cancel``         — abort in any non-terminal state
* ``GET    /v1/imports/template/{entity}``   — downloadable starter CSV
* ``GET    /v1/imports/columns/{entity}``    — column metadata for UI mapper

Validation runs inline at upload time (the orchestrator is fully
streaming so even a 100K-row file fits within request budget on the
small / medium files we see in pilots). Production deployments may
re-route validation to Celery by toggling
``settings.enable_in_process_processor`` — see
:mod:`app.workers.tasks.import_tasks`.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi import (
    Path as PathParam,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentTenantUser
from app.db import get_db
from app.models import AuditLog, ImportEntityType
from app.schemas.imports import (
    ImportColumnSpec,
    ImportColumnsResponse,
    ImportCommitRequest,
    ImportJobDetail,
    ImportJobListItem,
    ImportJobRead,
    ImportRowErrorRead,
    OnDuplicateMode,
)
from app.services import import_service
from app.services.importers import get_importer
from app.utils.logging import get_logger

__all__ = ["router"]


router = APIRouter(prefix="/imports", tags=["imports"])
_logger = get_logger(__name__)


_VALID_ON_DUPLICATE: frozenset[str] = frozenset({"error", "update", "skip"})


def _client_ip(request: Request) -> str | None:
    if request.client is not None and request.client.host:
        return request.client.host
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return None


def _audit(
    session: AsyncSession,
    *,
    action: str,
    tenant_id: str,
    actor_user_id: str | None,
    resource_id: str | None,
    ip_address: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type="import_job",
            resource_id=resource_id,
            metadata_json=metadata,
            ip_address=ip_address,
        )
    )


def _problem(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def _entity(entity_type: str) -> ImportEntityType:
    try:
        return ImportEntityType(entity_type)
    except ValueError as exc:
        raise _problem(
            "unknown_entity_type",
            f"Unknown entity_type {entity_type!r}.",
            status.HTTP_400_BAD_REQUEST,
        ) from exc


# ---------------------------------------------------------------------------
# Upload + state-transition endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ImportJobRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a CSV/XLSX and start dry-run validation.",
)
async def upload_import(
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
    entity_type: str = Form(...),
    mapping: str | None = Form(default=None),
    on_duplicate: OnDuplicateMode = Form(default="error"),
) -> ImportJobRead:
    if on_duplicate not in _VALID_ON_DUPLICATE:
        raise _problem(
            "invalid_on_duplicate",
            f"on_duplicate must be one of {sorted(_VALID_ON_DUPLICATE)}.",
            status.HTTP_400_BAD_REQUEST,
        )
    entity = _entity(entity_type)

    mapping_dict: dict[str, str] | None = None
    if mapping:
        try:
            parsed = json.loads(mapping)
        except json.JSONDecodeError as exc:
            raise _problem(
                "invalid_mapping_json",
                f"mapping must be valid JSON: {exc}",
                status.HTTP_400_BAD_REQUEST,
            ) from exc
        if not isinstance(parsed, dict):
            raise _problem(
                "invalid_mapping_json",
                "mapping JSON must be an object.",
                status.HTTP_400_BAD_REQUEST,
            )
        mapping_dict = {str(k): str(v) for k, v in parsed.items()}

    file_bytes = await file.read()

    try:
        job = await import_service.create_import_job(
            session,
            tenant_id=tenant_user.tenant_id,
            entity_type=entity,
            original_filename=file.filename or "upload",
            content_type=file.content_type,
            file_bytes=file_bytes,
            mapping=mapping_dict,
            on_duplicate=on_duplicate,
            created_by_user_id=tenant_user.user_id,
        )
    except import_service.InfectedUploadError as exc:
        # Drop the rolled-back half-job before raising — without an
        # explicit rollback the deletion sits as a pending change in the
        # session and survives the HTTPException unwind.
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "av_infected_file",
                "message": str(exc),
                "signature": exc.signature,
                "scanner": exc.scanner,
            },
        ) from exc
    except import_service.ScannerUnavailableError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "av_scanner_unavailable",
                "message": str(exc),
                "scanner": exc.scanner,
            },
        ) from exc
    except import_service.UnsupportedFormatError as exc:
        raise _problem("unsupported_format", str(exc), status.HTTP_400_BAD_REQUEST) from exc
    except import_service.FileTooLargeError as exc:
        raise _problem("file_too_large", str(exc), status.HTTP_413_REQUEST_ENTITY_TOO_LARGE) from exc

    _audit(
        session,
        action="import.uploaded",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=job.id,
        ip_address=_client_ip(request),
        metadata={
            "entity_type": entity.value,
            "filename": job.original_filename,
            "size": job.file_size_bytes,
        },
    )

    # Inline validation. For very large files the operator can opt in
    # to background execution via the Celery task (which calls the same
    # ``run_validation`` function) — see import_tasks.process_import_job.
    await session.commit()
    try:
        job = await import_service.run_validation(
            session, tenant_id=tenant_user.tenant_id, job_id=job.id
        )
    except import_service.ImportServiceError as exc:
        raise _problem(exc.error_code, str(exc), status.HTTP_400_BAD_REQUEST) from exc

    return ImportJobRead.model_validate(job)


@router.get(
    "",
    response_model=list[ImportJobListItem],
    summary="List import jobs for the current tenant.",
)
async def list_imports(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    response: Response,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ImportJobListItem]:
    items, total = await import_service.list_jobs(
        session, tenant_id=tenant_id, limit=limit, offset=offset
    )
    response.headers["X-Total-Count"] = str(total)
    return [ImportJobListItem.model_validate(item) for item in items]


@router.get(
    "/template/{entity_type}",
    summary="Download a starter CSV template for ``entity_type``.",
    response_class=Response,
)
async def download_template(
    _tenant: CurrentTenantId,
    entity_type: str = PathParam(...),
) -> Response:
    entity = _entity(entity_type)
    importer = get_importer(entity)
    headers = [c.field for c in importer.columns]
    example_row = [c.example or "" for c in importer.columns]
    body = (
        ",".join(headers) + "\r\n"
        + ",".join(_csv_escape(c) for c in example_row) + "\r\n"
    )
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{entity.value}_template.csv"'
            )
        },
    )


@router.get(
    "/columns/{entity_type}",
    response_model=ImportColumnsResponse,
    summary="Column metadata for the UI mapper.",
)
async def get_columns(
    _tenant: CurrentTenantId,
    entity_type: str = PathParam(...),
) -> ImportColumnsResponse:
    entity = _entity(entity_type)
    importer = get_importer(entity)
    return ImportColumnsResponse(
        entity_type=entity,
        columns=[
            ImportColumnSpec(
                field=c.field,
                required=c.required,
                aliases=list(c.aliases),
                description=c.description,
                example=c.example,
            )
            for c in importer.columns
        ],
    )


@router.get(
    "/{job_id}",
    response_model=ImportJobDetail,
    summary="Job status + first 50 row errors.",
)
async def get_import(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    job_id: str = PathParam(...),
) -> ImportJobDetail:
    try:
        job = await import_service.get_job(
            session, tenant_id=tenant_id, job_id=job_id
        )
    except import_service.JobNotFoundError as exc:
        raise _problem(
            "import_job_not_found", str(exc), status.HTTP_404_NOT_FOUND
        ) from exc
    errors = await import_service.get_job_errors(
        session, tenant_id=tenant_id, job_id=job.id, limit=import_service.MAX_PREVIEW_ERRORS
    )
    total_errors = await import_service.count_job_errors(
        session, tenant_id=tenant_id, job_id=job.id
    )
    return ImportJobDetail(
        **ImportJobRead.model_validate(job).model_dump(),
        errors_preview=[ImportRowErrorRead.model_validate(e) for e in errors],
        error_count=total_errors,
    )


@router.get(
    "/{job_id}/errors.csv",
    summary="Download the full validation error report (CSV).",
    response_class=StreamingResponse,
)
async def download_errors(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    job_id: str = PathParam(...),
) -> StreamingResponse:
    try:
        job = await import_service.get_job(
            session, tenant_id=tenant_id, job_id=job_id
        )
    except import_service.JobNotFoundError as exc:
        raise _problem(
            "import_job_not_found", str(exc), status.HTTP_404_NOT_FOUND
        ) from exc
    errors = await import_service.get_job_errors(
        session, tenant_id=tenant_id, job_id=job.id
    )
    return StreamingResponse(
        import_service.stream_errors_csv(errors),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="import_{job.id}_errors.csv"'
            )
        },
    )


@router.post(
    "/{job_id}/commit",
    response_model=ImportJobRead,
    summary="Commit a dry-run-ready import to the DB.",
)
async def commit_import(
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    payload: ImportCommitRequest,
    job_id: str = PathParam(...),
) -> ImportJobRead:
    if not payload.confirmed:
        raise _problem(
            "commit_not_confirmed",
            "Set `confirmed: true` to commit the import.",
            status.HTTP_400_BAD_REQUEST,
        )

    try:
        job = await import_service.get_job(
            session, tenant_id=tenant_user.tenant_id, job_id=job_id
        )
    except import_service.JobNotFoundError as exc:
        raise _problem(
            "import_job_not_found", str(exc), status.HTTP_404_NOT_FOUND
        ) from exc

    _audit(
        session,
        action="import.commit_requested",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=job.id,
        ip_address=_client_ip(request),
    )
    await session.commit()

    try:
        job = await import_service.run_commit(
            tenant_id=tenant_user.tenant_id, job_id=job.id
        )
    except import_service.InvalidTransitionError as exc:
        raise _problem(
            "invalid_transition", str(exc), status.HTTP_409_CONFLICT
        ) from exc
    except import_service.ImportServiceError as exc:
        raise _problem(exc.error_code, str(exc), status.HTTP_400_BAD_REQUEST) from exc

    return ImportJobRead.model_validate(job)


@router.post(
    "/{job_id}/cancel",
    response_model=ImportJobRead,
    summary="Cancel an in-flight import.",
)
async def cancel_import(
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    job_id: str = PathParam(...),
) -> ImportJobRead:
    try:
        job = await import_service.cancel_job(
            session, tenant_id=tenant_user.tenant_id, job_id=job_id
        )
    except import_service.JobNotFoundError as exc:
        raise _problem(
            "import_job_not_found", str(exc), status.HTTP_404_NOT_FOUND
        ) from exc
    except import_service.InvalidTransitionError as exc:
        raise _problem(
            "invalid_transition", str(exc), status.HTTP_409_CONFLICT
        ) from exc
    _audit(
        session,
        action="import.canceled",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=job.id,
        ip_address=_client_ip(request),
    )
    return ImportJobRead.model_validate(job)


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _csv_escape(cell: str) -> str:
    s = (cell or "").replace('"', '""')
    if any(ch in s for ch in (",", '"', "\n", "\r")):
        return f'"{s}"'
    return s
