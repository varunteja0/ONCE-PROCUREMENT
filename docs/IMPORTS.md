# Bulk Imports (L3.7)

The bulk-import pipeline ingests CSV / XLSX spreadsheets of business
records (suppliers, COIs, loss runs, producer licenses) in a two-phase
flow: a streaming **dry-run** that validates the file and surfaces errors,
followed by an operator-confirmed **commit** that inserts rows in 500-row
chunks.

> Endpoints live under `POST/GET /v1/imports`. UI: `/imports`.

---

## Architecture

```
┌──────────────┐  upload   ┌────────────────────┐  validate  ┌───────────────┐
│ Drag-drop UI │──────────▶│ POST /v1/imports   │───────────▶│ ImportService │
└──────────────┘           └────────────────────┘            │  · CsvParser  │
       ▲                            │                        │  · XlsxParser │
       │       errors_preview       │ run_validation()       │  · Importer   │
       │◀───────────────────────────┘                        │  · ErrorBuf   │
       │                                                     └───────┬───────┘
       │       commit confirmed                                       │
       │                                                              ▼
       │                          ┌──────────────────┐   per-chunk   ┌──────────┐
       │◀─── progress polling ────│ run_commit       │──────────────▶│ chunks    │
       │                          │  AsyncSessionLocal│   500 rows   │ (atomic) │
       │                          └──────────────────┘               └──────────┘
```

Key design decisions:

1. **Streaming parsers.** `CsvParser` (chardet-sniffed encoding + UTF-8 BOM
   stripping) and `XlsxParser` (openpyxl `read_only=True`) yield rows
   lazily, so a 100K-row file never lives in memory at once.
2. **Per-chunk session isolation.** `run_commit` opens its own
   `AsyncSessionLocal()` per 500-row chunk so any one row failure rolls
   back at most 500 rows. A chunk-failure row is written to the same
   transaction (rolled back, then reused) to keep error reporting durable.
3. **Two-phase commit + audit.** Validation never writes domain rows; the
   operator must POST `/commit { confirmed: true }` after reviewing the
   error preview. Every state transition emits an `AuditLog` entry.

---

## Entities & columns

Column metadata is exposed via `GET /v1/imports/columns/{entity}` and
drives both the UI mapper and the CSV template download. Below are the
column tables today.

### Suppliers (`entity_type=supplier`)

| Field           | Required | Aliases                                          | Description                       |
| --------------- | -------- | ------------------------------------------------ | --------------------------------- |
| `name`          | yes      | `company`, `supplier`, `supplier_name`, `legal_name` | Supplier legal name           |
| `fein`          | yes      | `ein`, `tax_id`, `federal_id`                    | EIN, format `XX-XXXXXXX`          |
| `state`         | yes      | `primary_state`                                  | 2-letter US state code            |
| `email`         | no       | `primary_email`, `contact_email`                 | Primary email                     |
| `phone`         | no       | `primary_phone`, `contact_phone`                 | Primary phone (any format)        |
| `address_line1` | no       | `address1`, `street`, `street1`                  | Street address line 1             |
| `address_line2` | no       | `address2`, `street2`                            | Street address line 2             |
| `city`          | no       | `town`                                           | City                              |
| `zip`           | no       | `postal_code`, `zipcode`, `zip_code`             | ZIP / postal code                 |
| `naic_code`     | no       | `naics`, `naics_code`, `naic`                    | NAICS industry code               |
| `gwp_band`      | no       | `premium_band`, `size_band`                      | Free-form GWP / premium tier band |
| `notes`         | no       | `comments`, `memo`                               | Free-form internal notes          |

### COIs, Loss Runs, Producer Licenses

These entity importers reuse the same `Importer` protocol — see
`backend/app/services/importers/__init__.py` and the registry. Add new
columns inline in each importer's `_COLUMNS` tuple; the UI auto-discovers
them via `/imports/columns/{entity}`.

---

## API

| Method | Path                                | Purpose                                       |
| ------ | ----------------------------------- | --------------------------------------------- |
| POST   | `/v1/imports`                       | Upload file + start validation                |
| GET    | `/v1/imports`                       | List tenant's import jobs                     |
| GET    | `/v1/imports/{id}`                  | Detail + first 50 row errors                  |
| GET    | `/v1/imports/{id}/errors.csv`       | Streamed full error report                    |
| POST   | `/v1/imports/{id}/commit`           | `{ "confirmed": true }` — flip DRY_RUN→COMMIT |
| POST   | `/v1/imports/{id}/cancel`           | Abort in any non-terminal state               |
| GET    | `/v1/imports/template/{entity}`     | Download a starter CSV template               |
| GET    | `/v1/imports/columns/{entity}`      | Column metadata for the UI mapper             |

### Upload form fields

| Field          | Required | Description                                         |
| -------------- | -------- | --------------------------------------------------- |
| `file`         | yes      | `multipart/form-data` file (CSV or XLSX, ≤ 25 MB)   |
| `entity_type`  | yes      | One of `supplier`, `coi`, `loss_run`, `producer_license` |
| `mapping`      | no       | JSON object `{ target_field: source_header }`       |
| `on_duplicate` | no       | `error` (default), `update`, `skip`                 |

### State machine

```
pending ─▶ validating ─▶ dry_run_ready ─▶ importing ─▶ completed
   │             │             │             │
   └──▶ failed   └──▶ failed   └──▶ failed   └──▶ failed
   └──▶ canceled └──▶ canceled └──▶ canceled └──▶ canceled
```

Terminal states: `completed`, `failed`, `canceled`. Once terminal, the job
record is immutable; uploads create a new job.

### Error codes

Error rows (`/v1/imports/{id}/errors.csv` and `errors_preview`) carry a
machine-readable `error_code`:

| Code                  | Meaning                                                                 |
| --------------------- | ----------------------------------------------------------------------- |
| `missing_required`    | A required column is blank.                                             |
| `invalid_format`      | Value failed format validation (e.g. EIN not `XX-XXXXXXX`).             |
| `invalid_state`       | State code isn't a known 2-letter US state.                             |
| `invalid_email`       | Email failed RFC syntax check.                                          |
| `duplicate_in_file`   | Same key seen twice in the same upload.                                 |
| `duplicate_in_db`     | Row matches an existing record and `on_duplicate=error`.                |
| `chunk_failed`        | Whole 500-row chunk rolled back (DB constraint error during commit).    |
| `unknown_column`      | Mapping referenced a header not in the file.                            |

HTTP-level codes:

| Code                       | HTTP | Meaning                                            |
| -------------------------- | ---- | -------------------------------------------------- |
| `unsupported_format`       | 400  | File extension/MIME not CSV or XLSX.               |
| `file_too_large`           | 413  | Exceeds `IMPORT_MAX_FILE_SIZE_BYTES`.              |
| `invalid_mapping_json`     | 400  | `mapping` form field is not a JSON object.         |
| `unknown_entity_type`      | 400  | `entity_type` not in the registry.                 |
| `commit_not_confirmed`     | 400  | Missing `confirmed: true` body on `/commit`.       |
| `invalid_transition`       | 409  | E.g. committing a `failed` or `completed` job.     |
| `import_job_not_found`     | 404  | Job id not visible to this tenant.                 |

---

## Settings

```ini
# backend/app/config.py — L3.7
IMPORT_MAX_FILE_SIZE_BYTES = 26_214_400  # 25 MiB
IMPORT_MAX_ROWS            = 100_000
IMPORT_CHUNK_SIZE          = 500
IMPORT_STORAGE_PATH        = "/var/lib/once/imports"
```

`IMPORT_STORAGE_PATH` is only used when the operator opts in to deferred
background validation via Celery (`app.workers.tasks.import_tasks`); the
default inline path keeps the bytes in-memory and writes nothing.

---

## Adding a new importer

1. **Define the column schema** in
   `backend/app/services/importers/<entity>_importer.py`:
   ```python
   _COLUMNS = (
       ColumnSpec(field="number", required=True, aliases=("policy_no",),
                  description="Policy number"),
       ...
   )
   ```
2. **Implement `Importer`**:
   ```python
   class CoiImporter:
       entity_type = ImportEntityType.coi
       columns = _COLUMNS

       async def validate_row(self, normalised: dict[str, str]) -> list[RowError]: ...
       async def commit_rows(self, session, rows: list[dict[str, str]]) -> int: ...
       async def find_duplicates(self, session, tenant_id, rows) -> set[int]: ...
   ```
3. **Register** in `app/services/importers/__init__.py`:
   ```python
   _REGISTRY[ImportEntityType.coi] = CoiImporter()
   ```
4. **Add the `ImportEntityType` enum value** in `app/models/import_job.py`
   if not already present.
5. **Frontend** picks it up automatically — `ENTITY_OPTIONS` in
   `frontend/src/pages/imports/ImportNew.tsx` already lists the four
   first-class entities; add new ones there if you ship more.

No DB migration is needed unless the new importer writes to a new table.

---

## Test fixtures

`backend/tests/fixtures/imports/` — CSVs used by `test_imports_pipeline.py`:

| File                          | Purpose                                         |
| ----------------------------- | ----------------------------------------------- |
| `suppliers_valid.csv`         | Happy-path, all rows valid                      |
| `suppliers_mixed.csv`         | Mix of valid + invalid rows                     |
| `suppliers_duplicate.csv`     | In-file duplicate exercising `duplicate_in_file`|
| `suppliers_missing_columns.csv` | Missing a required column                     |
| `suppliers_utf8_bom.csv`      | UTF-8 with BOM (header dequote test)            |
| `suppliers_cp1252.csv`        | CP-1252 / Windows-encoded (chardet path)        |

Sample templates for download: `docs/imports/supplier_template.csv`,
`docs/imports/supplier_template.xlsx`.
