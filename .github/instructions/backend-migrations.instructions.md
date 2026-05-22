---
applyTo: "backend/alembic/versions/**/*.py"
description: "Applied Alembic migrations — portability rules + never edit applied files"
---

# Alembic migrations — required behavior

> Files in `backend/alembic/versions/` are normally **read-only** (enforced
> via `.vscode/settings.json`). Editing one already applied to a shared
> environment will break every other environment. The correct response is
> almost always **add a new migration** that performs the correction.

When generating or reviewing a migration file:

1. **`from __future__ import annotations`** at the top.
2. **Portable types only** — schema must apply to both Postgres and
   in-memory SQLite:
   - PKs: `sa.String(length=36)` — **never** `postgresql.UUID`.
   - JSON: `sa.JSON()` — **never** `postgresql.JSONB`.
   - No partial indexes. No PG-only functions (`gin`, `gist`, `array_agg`,
     `tsvector`, `to_tsvector`, etc.). No `ARRAY` columns.
3. **Indexes:** every foreign key column gets an index. Every tenant-scoped
   table gets an index on `tenant_id`. Composite indexes for the
   most-common WHERE clauses (often `(tenant_id, status)` for submissions).
4. **Ordering:** in `upgrade()`, create parent tables before children.
   In `downgrade()`, drop children before parents.
5. **`downgrade()` is a real inverse** of `upgrade()`. If a downgrade is
   genuinely impossible (e.g. data loss), `raise NotImplementedError` with
   a comment explaining why — do not silently leave it empty.
6. **No data migrations mixed with schema migrations.** If you need to
   backfill, generate two migrations: one schema-only, one data-only that
   depends on it. Data migrations must be idempotent.
7. **Naming:** revision message uses `<verb>_<object>` snake_case
   (`add_supplier_notes`, `index_submissions_tenant_status`). Do not edit
   `down_revision` / `revision` IDs by hand.
8. **No raw SQL** unless the schema operation cannot be expressed through
   `op.*`. When raw SQL is unavoidable, wrap it in
   `op.execute(sa.text("..."))` and confirm it parses on both dialects.
9. **Foreign keys** always specify `ondelete=` semantics
   (usually `"CASCADE"` for tenant-scoped tables, `"RESTRICT"` for lookup
   data).

## Editing an applied migration

Don't. Add a new migration. Acceptable exceptions (require explicit user
approval in the PR):

- Fixing a typo in a docstring/comment that has no functional effect.
- Adding a missing `op.create_index` that was forgotten in the same PR,
  **before** the migration has been applied to any shared environment.

Anything else → new migration.

## Quality gate

```powershell
cd backend
alembic upgrade head
pytest -q backend/tests/test_tenant_isolation.py
```

Both must pass before the migration ships.
