---
applyTo: "backend/app/services/**/*.py"
description: "Rules for service layer — typed errors, no HTTP, transactional discipline"
---

# Backend services — required behavior

1. **`from __future__ import annotations`** at top of every module.
2. **No FastAPI / HTTP types in services.** Services accept primitive args
   and a `session: AsyncSession`, return ORM models or domain dataclasses,
   and raise typed exceptions from `app.services.exceptions`. The API layer
   maps exceptions to HTTP.
3. **Tenant scope is the caller's responsibility _and_ the service's
   defense-in-depth.** Every query inside the service must include
   `.where(Model.tenant_id == tenant_id)` even if the caller already
   restricted scope.
4. **Transactions:** rely on `get_db`'s autocommit at the request boundary.
   Inside a service, use `async with session.begin_nested():` for SAVEPOINTs
   when needed. Never call `session.commit()`.
5. **Pipeline contract (CONTRACTS.md §5):** the atomic-claim UPDATE in
   `submission_pipeline.process_submission` must keep `rowcount == 1` semantics.
   Do not refactor it into a separate SELECT-then-UPDATE.
6. **Receipts (CONTRACTS.md §6):** sign through
   `app.services.receipt_signer.sign()`, which canonical-JSON-encodes the
   payload first. Never mutate a signed receipt; produce a new one with a new
   `receipt_id`.
7. **External I/O** (HTTP, Playwright, Celery enqueues) goes inside the
   service, never the router. Wrap in retries with explicit timeouts.
8. **Logging:** structured `log.info("event.name", key=value, ...)`. Include
   `tenant_id` and the primary entity id in every event line.
9. **Dependency direction:** `api → services → models / utils`. Services
   must not import from `api/`.

## Tests

Each new public service function needs at least:

- One happy-path test.
- One error-path test exercising the typed exception it raises.
- For tenant-scoped functions, a cross-tenant test proving isolation.

Run: `cd backend && pytest -q backend/tests/test_<area>*.py`.
