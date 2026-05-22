---
applyTo: "backend/tests/**/*.py"
description: "Backend tests — async pytest, in-memory SQLite, tenant isolation"
---

# Backend tests — required behavior

When editing or creating files under `backend/tests/**`:

1. **`from __future__ import annotations`** at the top of every module.
2. **Async tests** are the default. Use `pytest.mark.asyncio` (or rely on
   `asyncio_mode = "auto"` if set in `pytest.ini`).
3. **Database** comes from `backend/tests/conftest.py` — in-memory SQLite
   (`sqlite+aiosqlite:///:memory:`) with `StaticPool`. Do not connect to
   Postgres in unit tests; do not create your own engine.
4. **Use the provided fixtures:** `db_session`, `client` (httpx `AsyncClient`
   bound to the FastAPI app), `tenant_factory`, `user_factory`,
   `auth_headers`. Add new factories to `conftest.py` rather than recreating
   them per test.
5. **Tenant isolation is a first-class test type.** Any change to a
   tenant-scoped service or endpoint requires a test that creates two
   tenants and proves tenant A cannot read tenant B's rows. Put these in
   `backend/tests/test_tenant_isolation.py` when they cut across modules.
6. **Endpoint test coverage**: at minimum 200/201, 401 (no token), 422
   (validation), and cross-tenant 404/403.
7. **Service test coverage**: at minimum one happy path + one error path
   that exercises the typed exception in `app/services/exceptions.py`.
8. **Receipts / signing tests** must pin the canonical-JSON byte output.
   The verifier has the symmetric test — if you change one, change the
   other in the same PR.
9. **Test naming:** `test_<area>_<behavior>` for functions,
   `test_<area>.py` for files. Match the area name in CONTRACTS.md §12.
10. **No real network calls.** Mock with `respx` (httpx) or `pytest-mock`.
    Playwright bots run against captured fixtures from `fixtures/portals/`,
    never live portals.
11. **No `print`.** Use `caplog` to assert structured log events.

## Running

```powershell
cd backend
pytest -q                              # full suite
pytest -q backend/tests/test_<area>.py # single file
pytest -q -k "<keyword>"               # by name
ruff check .                           # must also pass
```

## Adding a new test module

If the module crosses an existing area, add to the existing file. Only
create `test_<new_area>.py` when there is no natural home. Update
`backend/tests/__init__.py` only if the test framework needs it (usually
not).
