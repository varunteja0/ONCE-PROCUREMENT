---
mode: agent
description: "Add support for a new ACORD form (schema, service mapping, tests)."
---

# New ACORD form support

You will add support for a new ACORD form variant in the backend, wired into
`acord_form_service`. Follow [../../backend/AGENTS.md](../../backend/AGENTS.md)
and the existing patterns in:

- `backend/app/models/acord_form.py`
- `backend/app/services/acord_form_service.py`
- `backend/app/schemas/` (matching schema file if present)
- `backend/tests/test_acord_forms.py`

## Inputs to gather

- ACORD form **number** and **version** (e.g. ACORD 125 2016/03).
- Whether this is a **new form type** or a **new version** of an existing
  form (different model row vs. enum value).
- Field map: ACORD field code → canonical submission field name.
- Whether the form participates in the submission pipeline (it usually does).

## Plan

1. **Enum / lookup**: add the form variant to the relevant enum or seed data.
   Do NOT rename existing values.
2. **Model**: only if a new persistent shape is needed — add fields to
   `acord_form.py` and generate a migration:
   `cd backend && alembic revision --autogenerate -m "acord_<num>_<version>"`.
   Hand-review (no JSONB, no UUID, String(36) PKs).
3. **Schema**: extend the Pydantic schemas in `app/schemas/`.
4. **Service mapping**: extend `app/services/acord_form_service.py` with the
   new field map. Keep mapping data in a constant table, not branching
   `if/else` chains.
5. **Submission integration**: if the form feeds submitters, update the
   relevant `BaseSubmitter` subclasses to consume the new fields.
6. **Tests**: extend `backend/tests/test_acord_forms.py` with:
   - A canonicalization test (input → expected canonical dict).
   - A round-trip test (canonical dict → form payload → parse back).
   - Tenant isolation test if the form is persisted per tenant.

## Quality gates

```powershell
cd backend
ruff check .
pytest -q backend/tests/test_acord_forms.py
```
