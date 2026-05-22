# AUDIT — Tamper-Evident Audit Trail (L3.10)

> **Status:** production. New parallel system. Coexists with the legacy
> `audit_logs` table (kept untouched for backwards compatibility) under the
> new table `audit_trail` + the worker-rendered, signed export pipeline.

This document describes the **append-only, chain-hashed, Ed25519-signed**
per-tenant audit trail used by Once Procurement for compliance evidence
(SOC 2 CC4.1 / CC4.2 / CC7.2 / CC7.3 / CC7.4) and tenant-facing forensics.

---

## 1. Goals

1. **Tamper evidence** — any unauthorized mutation of historical rows can
   be detected by re-computing the SHA-256 chain.
2. **Cryptographic export proof** — every PDF/JSON export bundle is signed
   with the tenant's Ed25519 key, so the customer can verify months later
   without trusting our running system.
3. **Best-effort, never-on-the-critical-path** — failing to persist an
   audit row never breaks the user request that triggered it.
4. **Per-tenant isolation** — every row is `WHERE tenant_id = :t`-scoped at
   the API, ORM, and chain-verification layers.

---

## 2. Schema

Table `audit_trail` (Alembic migration
`backend/app/alembic/versions/20260521_07_audit_trail.py`).

| Column           | Type        | Notes                                              |
|------------------|-------------|----------------------------------------------------|
| `id`             | ULID (str)  | PK. Time-sortable; safe to expose.                 |
| `tenant_id`      | str         | FK → `tenants.id`. Indexed.                        |
| `chain_position` | int         | Monotonic per tenant, starts at 1.                 |
| `prev_hash`      | char(64)    | Previous row's `this_hash`; `"0"*64` for row #1.   |
| `this_hash`      | char(64)    | `sha256(canonical(row_without_hashes) ‖ prev_hash)`|
| `occurred_at`    | timestamptz | Server clock at ingress.                           |
| `actor_type`     | enum        | `user / operator / system / inbound_email / webhook / worker` |
| `actor_id`       | str?        | Internal id when available.                        |
| `actor_email`    | str?        | Denormalized for human-readable timeline.          |
| `action_verb`    | str         | e.g. `created`, `updated`, `signed`, `exported`.   |
| `resource_type`  | str         | e.g. `supplier`, `submission`.                     |
| `resource_id`    | str?        |                                                    |
| `request_id`     | str?        | Echoed from `X-Request-ID`.                        |
| `ip_address`     | str?        |                                                    |
| `user_agent`     | str?        |                                                    |
| `before_redacted`| JSONB?      | PII-redacted snapshot.                             |
| `after_redacted` | JSONB?      | PII-redacted snapshot.                             |
| `metadata`       | JSONB?      | Free-form scalar context.                          |

**Append-only enforcement:**
- Postgres: `REVOKE UPDATE, DELETE` from app role; trigger raises on any
  UPDATE/DELETE.
- SQLite (tests/dev): `CHECK (length(this_hash) = 64 AND length(prev_hash)
  = 64)` + an `AFTER UPDATE`/`AFTER DELETE` trigger that raises.

A companion `audit_exports` table records every export request (status,
hash of the rendered PDF, hash of the signed envelope, ed25519 signature,
key id, output path / blob key).

---

## 3. Chain hash specification

For each new row `N` belonging to tenant `T`:

```
canonical = canonical_json({
  id, tenant_id, chain_position, occurred_at, actor_type, actor_id,
  actor_email, action_verb, resource_type, resource_id, request_id,
  ip_address, user_agent, before_redacted, after_redacted, metadata
})  # NB: hashes themselves are NOT in the canonical input
this_hash = sha256(canonical || prev_hash).hexdigest()
```

`canonical_json` is RFC-8785-style: keys sorted, no insignificant
whitespace, `ensure_ascii=False`, integers preserved.

**Verification** is implemented in
`backend/app/services/audit_chain.py::verify_chain(...)`. It streams rows
in `(tenant_id, chain_position)` order, recomputes each row's hash, and
returns:

```json
{
  "valid": true,
  "rows_checked": 12345,
  "head_hash": "ab12…",
  "breaks": []
}
```

A break is `{ "position": N, "id": "01H…", "expected": "…", "actual": "…" }`.

A nightly Celery beat task (`audit.verify_nightly_hash`, pre-existing)
calls `verify_chain` for every tenant and pages the on-call if `valid:
false`.

---

## 4. Signed export envelope

Bundle endpoint: `POST /v1/audit/exports` → 202 with the export row
(status `pending`). The worker (`audit.generate_export`) renders a PDF
with the events for the requested scope and produces a JSON envelope:

```json
{
  "version": "audit-export.v1",
  "tenant_id": "01H…",
  "scope_type": "tenant | supplier | submission | date_range",
  "scope_params": { "...": "..." },
  "rows": [ /* AuditLogRead-shaped objects, in chain order */ ],
  "chain": {
    "head_hash": "abcd…",
    "rows_checked": 42,
    "valid": true
  },
  "pdf_sha256": "…hex…",
  "rendered_at": "2026-05-21T12:00:00Z",
  "signing_key_id": "tenant-01H…-ed25519-v1"
}
```

The envelope is **canonicalized** and signed with the tenant's Ed25519
private key (managed by the existing `signing_key` service). The
signature, public key, key id, `envelope_sha256`, and `pdf_sha256` are
returned alongside the export row. The PDF and the signed-envelope JSON
are both downloadable at `GET /v1/audit/exports/{id}/download` and
`GET /v1/audit/exports/{id}/envelope.json`.

### Verifying an export offline

```python
import hashlib, json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from app.utils.canonical_json import canonical_json_bytes

envelope = json.loads(open("envelope.json", "rb").read())
signature = bytes.fromhex(envelope.pop("signature"))
pubkey_b64 = envelope.pop("public_key_b64")

# 1. PDF hash matches.
assert hashlib.sha256(open("export.pdf", "rb").read()).hexdigest() \
       == envelope["pdf_sha256"]

# 2. Signature verifies over the canonical envelope.
import base64
pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(pubkey_b64))
pub.verify(signature, canonical_json_bytes(envelope))

# 3. Re-replay the chain locally.
prev = "0" * 64
for row in envelope["rows"]:
    h = row.pop("this_hash"); p = row.pop("prev_hash")
    assert p == prev
    body = canonical_json_bytes(row) + prev.encode()
    assert hashlib.sha256(body).hexdigest() == h
    prev = h
```

### `curl` cookbook

```bash
# List events
curl -H "Authorization: Bearer $TOKEN" \
     "$BASE/v1/audit?limit=50&actor_type=user"

# Verify chain
curl -H "Authorization: Bearer $TOKEN" "$BASE/v1/audit/chain/verify"

# Request export
curl -X POST -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     "$BASE/v1/audit/exports" \
     -d '{"scope_type":"tenant"}'

# Poll, then download
curl -H "Authorization: Bearer $TOKEN" \
     "$BASE/v1/audit/exports/$ID" | jq .status
curl -OJ -H "Authorization: Bearer $TOKEN" \
     "$BASE/v1/audit/exports/$ID/download"
```

---

## 5. Ingress: `AuditMiddleware`

`backend/app/middleware/audit_middleware.py` is mounted ahead of the
router. For every authenticated `POST/PUT/PATCH/DELETE` to non-skipped
paths it extracts:

- tenant id, actor id/email (from `request.state`, populated by the
  auth middleware),
- request id (echo of `X-Request-ID`),
- `action_verb` (derived from the HTTP method + route name),
- `resource_type` / `resource_id` (derived from the path),
- IP + user agent,

…then calls `record_audit_event(...)` from `app/services/audit_logger.py`.

**Write strategy:** *inline `await record_audit_event(...)`*, **not**
`loop.create_task`. The service swallows every exception, so a database
hiccup never breaks the request; the inline write was chosen because
fire-and-forget tasks did not complete reliably under
`httpx.ASGITransport` (test fixture) and the latency cost is
sub-millisecond on a healthy DB.

Skipped path prefixes: `/health`, `/metrics`, `/docs`, `/openapi`,
`/static`, `/v1/audit` (the read endpoints).

---

## 6. REST API

| Method | Path                                  | Notes                                |
|--------|---------------------------------------|--------------------------------------|
| GET    | `/v1/audit`                           | Cursor/offset-paginated list.        |
| GET    | `/v1/audit/{id}`                      | Single row.                          |
| GET    | `/v1/audit/by-resource/{rt}/{rid}`    | Resource-scoped timeline.            |
| GET    | `/v1/audit/chain/verify`              | On-demand chain replay.              |
| POST   | `/v1/audit/exports`                   | Enqueue an export (202).             |
| GET    | `/v1/audit/exports`                   | List recent exports.                 |
| GET    | `/v1/audit/exports/{id}`              | Poll export status.                  |
| GET    | `/v1/audit/exports/{id}/download`     | Stream the PDF.                      |
| GET    | `/v1/audit/exports/{id}/envelope.json`| Stream the signed JSON envelope.     |

Rate-limit: one active (`pending`/`generating`) export per tenant.

---

## 7. Frontend

- `/audit` — paginated timeline + actor/resource filters +
  `ChainVerificationBadge` (refetches every 60s).
- `/audit/:id` — full event detail (before/after diff, request metadata).
- `/audit/exports` — list + "New export" dialog (`ExportDialog`),
  download buttons.

All three pages live under `frontend/src/pages/audit/`. The hook layer
(`frontend/src/hooks/useAudit.ts`) wraps `auditApi` with React Query so
the badge and timeline auto-revalidate after a mutation elsewhere in the
app invalidates the `['audit']` key.

---

## 8. SOC 2 evidence map

| Control  | Evidence                                                                                          |
|----------|---------------------------------------------------------------------------------------------------|
| CC4.1    | `audit_trail` rows for every mutating API call; nightly `verify_chain` beat task with pager alert.|
| CC4.2    | Signed export envelopes (Ed25519 + tenant key id + canonical JSON) are admissible compliance evidence. |
| CC7.2    | Chain-break detection ⇒ on-call page within 5 min; runbook in `docs/RUNBOOK.md#audit-chain-break`. |
| CC7.3    | Append-only triggers + revoked `UPDATE/DELETE` make unauthorized modification observable.         |
| CC7.4    | Operator (`actor_type='operator'`) events are recorded with the operator id for impersonation audits. |

---

## 9. Design decisions

1. **Parallel table (`audit_trail`), not extending `audit_logs`.** The
   legacy `audit_logs` is a wide, mutable, business-log table used by
   billing reconciliation. Mixing in a tamper-evident chain would risk
   breaking either contract; we keep them isolated and migrate readers
   over time.
2. **ULID primary keys, not UUIDv4.** ULIDs are time-sortable, which
   makes the `(tenant_id, chain_position)` index naturally aligned with
   insertion order and lets the chain-replay query stream from disk
   without an extra sort.
3. **Inline best-effort writes, not background tasks.** Fire-and-forget
   tasks are operationally appealing but fragile under ASGI shutdown and
   in test harnesses. The middleware now awaits `record_audit_event`
   directly; the service contract guarantees it never raises and never
   takes more than a few ms on the happy path.

---

## 10. Known limitations

- **`envelope_sha256` is not embedded in the PDF footer.** The envelope
  hash depends on `pdf_sha256`, which can only be computed after the PDF
  is rendered. The current PDF renderer uses a `"0"*64` placeholder in
  the footer; downstream verifiers should rely on the JSON envelope, not
  the PDF text, for the envelope hash. A future revision can use a
  two-pass render (`/Length` patch) to backfill the footer.
- **PDF content streams are zlib-compressed** by reportlab, so
  substring assertions on PDF text are unreliable; tests assert
  structural invariants (size diff under input mutation, `%PDF-` magic).
- **One active export per tenant.** Hard limit to prevent worker
  starvation when a tenant requests many overlapping date-range
  exports; lifted by the `/audit/exports/{id}/cancel` (TODO) endpoint.
