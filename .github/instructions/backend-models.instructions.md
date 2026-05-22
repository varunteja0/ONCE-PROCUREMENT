---
applyTo: "backend/app/models/**/*.py"
description: "Rules for SQLAlchemy 2.0 models — tenant scope, SQLite portability, migrations"
---

# Backend models — required behavior

When editing or creating files under `backend/app/models/**`:

1. **`from __future__ import annotations`** must be the first import.
2. Inherit `Base` from `app/models/base.py`. Use `TimestampMixin` for
   `created_at`/`updated_at`. Use `TenantScopedMixin` if the row belongs to a
   tenant (it almost always does).
3. **PKs are `String(36)`** with `default=lambda: str(uuid.uuid4())`.
   **Never** use the PG `UUID` type.
4. **JSON columns** use SQLAlchemy generic `JSON` — **never** `JSONB`.
5. **No partial indexes**, no PG-only functions, no `ARRAY` columns. Schema
   must run on in-memory SQLite for tests.
6. **Enums** are declared as `class XStatus(str, enum.Enum)` and used via
   `mapped_column(SQLEnum(XStatus, name="xstatus"))`.
7. **Foreign keys** must include `ondelete=` semantics (usually `"CASCADE"`
   for tenant-scoped rows, `"RESTRICT"` for referenced lookup data) and be
   `index=True`.
8. **Canonical model names** are locked in CONTRACTS.md §3. Do not rename
   `Tenant`, `User`, `Supplier`, `Portal`, `SupplierSubmission`,
   `SubmissionReceipt`, `ConsentRecord`, `CertificateOfInsurance`,
   `AuditLog`, etc.
9. Export every new model from `app/models/__init__.py`.

## After any model change

You **must** generate an Alembic migration:

```powershell
cd backend
alembic revision --autogenerate -m "<verb_object>"
```

Then **hand-review** the generated file in `backend/alembic/versions/`:

- Confirm all PKs are `sa.String(length=36)`.
- Confirm JSON columns are `sa.JSON()`, not `postgresql.JSONB()`.
- Confirm no partial indexes or PG-only ops were emitted.
- Confirm indexes exist on every FK and on `tenant_id`.

Never edit a migration that has already been applied to any shared
environment. Add a new migration instead.

## Tenant isolation

If the model uses `TenantScopedMixin`, callers must filter by `tenant_id`.
Add or update a test in `backend/tests/test_tenant_isolation.py` that proves
tenant A cannot read tenant B's rows of this model.
