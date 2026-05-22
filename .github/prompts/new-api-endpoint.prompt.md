---
mode: agent
description: "Scaffold a new backend FastAPI endpoint end-to-end: schema, service, router, registration, tests."
---

# New backend API endpoint

You will add a new FastAPI endpoint to the `backend/` project following the
rules in [../../backend/AGENTS.md](../../backend/AGENTS.md) and
[../../CONTRACTS.md](../../CONTRACTS.md).

## Inputs to gather (ask once, in one message)

- HTTP **method** and **path** (e.g. `POST /v1/suppliers/{supplier_id}/notes`).
- One-line **purpose**.
- Whether the endpoint is **tenant-scoped** (default: yes).
- Whether it requires **auth** (default: yes).
- Request body shape and response shape (sketch).
- Whether it triggers a **Celery task** or a **submission**.

## Plan to follow

1. **Pydantic schemas** in `backend/app/schemas/<area>.py` (request + response).
2. **Service function** in `backend/app/services/<area>_service.py` —
   - accepts `session: AsyncSession`, `tenant_id: str`, primitives;
   - returns ORM/domain object or raises a typed exception from
     `app/services/exceptions.py`;
   - includes `.where(Model.tenant_id == tenant_id)` defense-in-depth.
3. **Router** in `backend/app/api/v1/<area>.py`:
   - inject `session = Depends(get_db)` and `tenant_id = Depends(get_current_tenant_id)`;
   - call the service; map typed exceptions to `HTTPException`;
   - structured log with `tenant_id` + primary id.
4. **Register** the router in `backend/app/api/v1/router.py`.
5. **Tests** in `backend/tests/test_<area>.py` covering: happy path, 401, 422,
   cross-tenant 404, and any error path the service can raise.
6. **Migration**: only if the change adds/edits a model — `cd backend && alembic revision --autogenerate -m "<verb_object>"` and hand-review.

## Quality gates (run before declaring done)

```powershell
cd backend
ruff check .
pytest -q
```

Both must be green. Report any failure with the offending file + line.
