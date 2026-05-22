# Inbound email

> **Note**: This file exists because some code paths and runbooks reference `docs/inbound/README.md`. The full feature documentation lives in [`../INBOUND_EMAIL.md`](../INBOUND_EMAIL.md). This is just a stable redirect.

See [`docs/INBOUND_EMAIL.md`](../INBOUND_EMAIL.md) for:

- Dual ingestion paths: Postmark webhook + IMAP polling
- Authoritative-source resolution and dedup by `Message-ID`
- Attachment storage (`backend/app/services/inbound_attachment_storage.py`)
- Routing rules (allow/deny lists, supplier auto-match, fallback-to-review)
- Spam / phishing classification
- Per-tenant inbox addresses (`{tenant_slug}@inbound.getonce.com`)
- API endpoints (`GET /v1/inbox`, `POST /v1/inbox/{id}/route`, `POST /v1/inbox/{id}/spam`)
- Antivirus scan wiring (ClamAV sidecar — see [`docs/SECURITY.md`](../SECURITY.md))

For the bulk-upload companion feature (CSV / XLSX uploaded via the UI or API), see [`docs/imports/README.md`](../imports/README.md).
