# backend/ — Agent rules

> Authoritative stack & naming rules: [CONTRACTS.md](../CONTRACTS.md) §2–§8, §11–§13.
> This file = backend-only working rules and recipes.

## Stack snapshot

- Python **3.12** · FastAPI · SQLAlchemy 2.0 **async** (`Mapped[...]`)
- Alembic · Celery (Redis broker) · Playwright **sync** bridged via
  `asyncio.to_thread`
- Pydantic v2 + pydantic-settings · structlog · slowapi
- DB: Postgres (prod) / SQLite in-memory (tests, StaticPool). **Schema must be
  SQLite-portable** — see CONTRACTS.md §2.

## Layout (do not invent new top-level dirs)

```
app/
  api/v1/         # Routers. Register in api/v1/router.py.
  automation/     # Playwright submitters + portal detector.
  middleware/     # tenant_scope, csrf, etc.
  models/         # SQLAlchemy 2.0 models. One file per aggregate.
  schemas/        # Pydantic v2 request/response models.
  services/       # Business logic. Routers call services, not models directly.
  utils/          # logging, security, crypto, canonical_json.
  workers/        # Celery app + tasks/.
```

File ownership per module is locked in CONTRACTS.md §12 — match it.

## Hard rules (backend)

1. **`from __future__ import annotations`** at the top of every `.py` file.
2. **Models:** inherit `Base` (and `TimestampMixin` / `TenantScopedMixin` from
   `app/models/base.py` when applicable). PKs are `String(36)` with
   `default=lambda: str(uuid.uuid4())`. Status fields use a
   `class XStatus(str, enum.Enum)`.
3. **Tenant scope:** every tenant-scoped row has
   `tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)`.
   Every query filtering tenant data MUST include
   `.where(Model.tenant_id == tenant_id)`. The
   `app.middleware.tenant_scope` middleware exposes the active id at
   `request.state.tenant_id`; access it via `Depends(get_current_tenant_id)`.
4. **Schema change ⇒ Alembic migration.** Run
   `alembic revision --autogenerate -m "<verb_object>"`, hand-review, commit.
5. **Routes:** inject `session: AsyncSession = Depends(get_db)` (autocommits on
   success). Routers stay thin — call into `app/services/`.
6. **Logging:** `from app.utils.logging import get_logger; log = get_logger(__name__)`.
   No `print`. Structured kwargs only: `log.info("submission.claimed", submission_id=..., tenant_id=...)`.
7. **Errors:** raise `HTTPException` at the API boundary; raise typed
   exceptions from `app.services.exceptions` inside services.
8. **Config:** `from app.config import settings`. Never read `os.environ`
   directly outside `config.py`.
9. **Receipts:** sign via `app.services.receipt_signer`. Canonical-JSON the
   payload (`app.utils.canonical_json`) before signing. Never mutate a signed
   receipt — add a new one.
10. **Submission pipeline:** atomic claim pattern is locked
    (CONTRACTS.md §5). Do not bypass `process_submission()` for new portals;
    add a `BaseSubmitter` subclass under `app/automation/submitters/` and wire
    it via the dispatcher.

## Tests

- Pytest async via `pytest-asyncio`. In-memory SQLite + StaticPool
  (`backend/tests/conftest.py`).
- Every new endpoint → request/response test.
- Every new service path → at least one happy + one error test.
- Multi-tenant code paths require an explicit isolation test (a tenant must
  not be able to read another tenant's rows).
- Run: `cd backend && pytest -q` (must be green before commit).
- Lint: `cd backend && ruff check .` (must be green).

## Common recipes

### Add a new model
1. Create `app/models/<thing>.py` (inherit `Base`, mixins as needed).
2. Export from `app/models/__init__.py`.
3. Generate migration: `alembic revision --autogenerate -m "add_<thing>"`.
4. Hand-review the generated file (drop PG-only types, confirm `String(36)`
   PKs, indexes on FKs and `tenant_id`).
5. Add Pydantic schemas in `app/schemas/<thing>.py`.
6. Add service in `app/services/<thing>_service.py`.
7. Add router in `app/api/v1/<thing>s.py` and register in
   `app/api/v1/router.py`.
8. Add tests in `backend/tests/test_<thing>*.py` (CRUD + tenant isolation).

### Add a new portal submitter
1. Add the enum value to `PortalPlatform` (CONTRACTS.md §4) **only** if not
   already present.
2. Create `app/automation/submitters/<platform>.py` subclassing `BaseSubmitter`.
3. Wire it in the dispatcher in `app/services/submission_pipeline.py`.
4. Add fixtures under `fixtures/portals/<platform>/` (mirror existing layout).
5. Add Playwright test + a pipeline integration test.

### Add a Celery task
1. File goes under `app/workers/tasks/<area>_tasks.py`.
2. Decorate with the shared celery app from `app/workers/celery_app.py`.
3. Long-running / external I/O → `acks_late=True`, idempotent body.
4. Add a unit test that calls the task function directly (not via Celery).

## Running locally

```powershell
cd backend
# one-time
pip install -r requirements.txt
# dev
uvicorn app.main:app --reload --port 8000
# worker
celery -A app.workers.celery_app worker -l info
# migration
alembic upgrade head
alembic revision --autogenerate -m "<message>"
```

## Things to never do

- Use `UUID`, `JSONB`, partial indexes, or any PG-only construct in models.
- Skip the `tenant_id` filter on a tenant-scoped query.
- Mutate an applied Alembic migration. Add a new one.
- Add `print()` or bare `logging` calls.
- Bypass `process_submission()` or `receipt_signer.sign()` for "just this once".
- Commit `.env`, signing keys, or real customer fixtures.
