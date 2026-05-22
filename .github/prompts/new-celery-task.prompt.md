---
mode: agent
description: "Scaffold a new Celery background task: file, idempotent body, schedule, test."
---

# New Celery task

You will add a new Celery task to `backend/app/workers/tasks/`. Follow
[../instructions/backend-workers.instructions.md](../instructions/backend-workers.instructions.md)
and CONTRACTS.md §12 row 11.

## Inputs to gather

- **Area** (`submission`, `renewal`, `sanctions`, `smoke_test`, or a new one
  — discuss with user before inventing).
- **Trigger:** enqueued from an endpoint, fired by Celery beat, or both.
- **Inputs:** primitive args only (ids, strings, timestamps). No ORM objects.
- **Effects:** what external systems / tables it touches; how it is made
  idempotent.
- **Failure policy:** which exceptions trigger retry, max retries, backoff.

## Plan

1. **File:** add to existing `app/workers/tasks/<area>_tasks.py` if the
   area exists. Otherwise create a new file and update
   `app/workers/tasks/__init__.py`.
2. **Decorator:** use the shared celery app and these flags by default:

   ```python
   @celery_app.task(
       bind=True,
       acks_late=True,
       autoretry_for=(TransientError,),
       retry_backoff=True,
       retry_jitter=True,
       max_retries=5,
   )
   ```

3. **Body:**
   - Open a fresh async session (do not accept one as an argument).
   - Re-fetch the entity by id.
   - Make the operation idempotent — check current state first, no-op if
     the work is already done.
   - Structured logs at start, success, failure with `task_id`,
     `tenant_id`, primary entity id.
4. **Pipeline interaction:** if the task is processing a `SupplierSubmission`,
   call `submission_pipeline.process_submission` — do **not** reimplement
   the atomic-claim pattern (CONTRACTS.md §5).
5. **Schedule** (only if periodic): add to `celery_app.beat_schedule` with a
   comment explaining the cadence rationale.
6. **Test:** add `backend/tests/test_<area>_tasks.py` (or extend an existing
   one). Invoke the task **function**, not `.delay()`. Run it twice with the
   same input and assert observable state is identical (idempotency proof).
   Add a retry test that raises `TransientError` once and asserts success.

## Quality gates

```powershell
cd backend
ruff check .
pytest -q backend/tests/test_<area>_tasks.py
```

Both must pass before the task ships.
