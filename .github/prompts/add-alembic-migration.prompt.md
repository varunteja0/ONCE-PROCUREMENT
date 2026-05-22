---
mode: agent
description: "Generate and hand-review an Alembic migration for the most recent backend model changes."
---

# Add Alembic migration

Run after model changes under `backend/app/models/**`. Follows the rules in
[../instructions/backend-models.instructions.md](../instructions/backend-models.instructions.md).

## Steps

1. Confirm the model change(s) and summarize what schema delta is expected
   (added column / new table / index / FK).
2. Generate the migration:

   ```powershell
   cd backend
   alembic revision --autogenerate -m "<verb_object>"
   ```

3. Open the generated file under `backend/alembic/versions/` and **hand-review**:
   - PKs are `sa.String(length=36)`, not `postgresql.UUID`.
   - JSON columns are `sa.JSON()`, not `postgresql.JSONB`.
   - No partial indexes, no PG-only ops (`gin`, `gist`, `array_agg`, etc.).
   - Every FK is indexed; every tenant-scoped table has an index on
     `tenant_id`.
   - `op.create_table` ordering puts referenced tables first.
   - `downgrade()` actually reverses `upgrade()`.
4. Apply locally to confirm it works on SQLite (test DB) AND Postgres
   (dev DB if available):

   ```powershell
   cd backend
   alembic upgrade head
   pytest -q backend/tests/test_tenant_isolation.py
   ```

5. If a previously-applied migration needs adjustment, do **not** edit it —
   add a new migration that performs the correction.

## Report

End with: file path of the new migration, the schema delta in 1–2 lines,
and confirmation that `alembic upgrade head` + the smoke test passed.
