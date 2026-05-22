---
applyTo: "backend/app/workers/**/*.py"
description: "Celery workers — idempotency, structured logging, async-bridge discipline"
---

# Backend workers — required behavior

When editing or creating files under `backend/app/workers/**`:

1. **`from __future__ import annotations`** at the top of every module.
2. **Single Celery app:** import from `app.workers.celery_app`. Do not create
   a second `Celery(...)` instance anywhere.
3. **Task file layout:** one file per area under `app/workers/tasks/` (e.g.
   `submission_tasks.py`, `renewal_tasks.py`, `sanctions_tasks.py`,
   `smoke_test_tasks.py`). Match the names in CONTRACTS.md §12 row 11.
4. **Task signatures take primitives**, not ORM objects. Re-fetch entities
   inside the task using a fresh session.
5. **Idempotency is mandatory.** Tasks may be retried at-least-once. Every
   task body must produce the same observable state if run twice with the
   same input.
6. **`acks_late=True`** for any task that performs external I/O or DB writes.
   Pair with bounded `max_retries` + exponential backoff (`autoretry_for=(...)`,
   `retry_backoff=True`, `retry_jitter=True`).
7. **DB sessions:** Celery runs sync. Open an async session with
   `asyncio.run(_async_body(...))` or use the project's session helper that
   bridges sync→async. Never share a session across tasks.
8. **Submission tasks** must go through `submission_pipeline.process_submission`
   (CONTRACTS.md §5). Do not bypass the atomic claim — even "just to retry".
9. **Structured logging:** `from app.utils.logging import get_logger`. Every
   task logs `task.started` / `task.completed` / `task.failed` with
   `task_id`, `tenant_id`, and the primary entity id.
10. **No `print`, no bare `logging`.** No long blocking calls without an
    explicit timeout.
11. **Schedules** live in `celery_app.beat_schedule`. Adding a periodic task
    requires a comment with the cadence rationale.

## Tenant scope

Tasks that operate on tenant-scoped data must accept `tenant_id` as a
parameter and pass it through to every service call. Do not infer
`tenant_id` from request state — there is no request.

## Tests

Unit-test the task **function body directly** (not via `.delay()`). Use the
in-memory SQLite fixture. For retry behavior, test the wrapped callable
twice and assert idempotency.

Run: `cd backend && pytest -q backend/tests/test_*tasks*.py` (when present).
