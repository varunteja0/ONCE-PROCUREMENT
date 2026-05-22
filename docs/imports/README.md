# Bulk imports (CSV / XLSX)

> **Note**: This file exists because some code paths and runbooks reference `docs/imports/README.md`. The full feature documentation lives in [`../IMPORTS.md`](../IMPORTS.md). This is just a stable redirect.

See [`docs/IMPORTS.md`](../IMPORTS.md) for:

- Supported file formats (CSV with auto-detected delimiter/encoding, XLSX via openpyxl)
- Streaming upload contract (chunked, ≤200MB per job)
- Column mapping & header inference
- Validation pipeline (per-row errors persisted, partial-success allowed)
- Duplicate handling strategies (`skip`, `update`, `replace`, `error`)
- API endpoints (`POST /v1/imports`, `GET /v1/imports/{id}`, `GET /v1/imports/{id}/errors`)
- Antivirus scan wiring (ClamAV sidecar — see [`docs/SECURITY.md`](../SECURITY.md))
- Storage layout (`{tenant_id}/{job_id}/{sha256}.{ext}`)

For the inbound-email companion feature (PDFs and CSVs arriving via Postmark/IMAP), see [`docs/inbound/README.md`](../inbound/README.md).
