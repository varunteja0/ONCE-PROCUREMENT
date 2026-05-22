---
applyTo: "backend/app/api/**/*.py"
description: "Rules for FastAPI routers — DI, tenant scope, errors, registration"
---

# Backend API — required behavior

When editing or creating files under `backend/app/api/**`:

1. **`from __future__ import annotations`** must be the first import.
2. Inject the DB session: `session: AsyncSession = Depends(get_db)`.
   `get_db` autocommits on success — do not call `session.commit()` at the
   end of a successful request.
3. **Tenant-scoped endpoints** must depend on `get_current_tenant_id`
   (re-exported from `app/api/deps.py`) and pass `tenant_id` to every service
   call. Never trust a `tenant_id` from the request body.
4. **Auth-required endpoints** depend on `get_current_user`. Public endpoints
   must be explicitly listed in code review.
5. **Routers stay thin.** Business logic lives in `app/services/<thing>_service.py`.
   Routers only: parse request → call service → shape response.
6. **Request/response models** are Pydantic v2 models in
   `app/schemas/<thing>.py`. No raw dict responses.
7. **Errors:** raise `HTTPException` at the API layer with a stable status
   code and a short, non-leaky `detail`. Catch typed exceptions from
   `app.services.exceptions` and map them to HTTP codes — do not let stack
   traces leak.
8. **Logging:** `from app.utils.logging import get_logger; log = get_logger(__name__)`.
   Log structured kwargs at info on success and at warning on
   client-visible errors.
9. **Rate limiting:** use the slowapi limiter from `app.main` on
   authentication, signup, and any expensive endpoint.
10. **CSRF:** state-changing routes for browser clients go through the CSRF
    middleware (`app/middleware/csrf.py`). Do not bypass.
11. **Register every new router in `app/api/v1/router.py`.** A router not
    registered is dead code.

## Tests

Every new endpoint requires a `backend/tests/test_<area>.py` covering:

- Happy path (200/201).
- Auth failure (401).
- Tenant isolation (404 or 403 when crossing tenants).
- Validation failure (422).

Run before commit: `cd backend && ruff check . && pytest -q`.
