# Once — REST API

Base URL (production): `https://api.once.io`
Base URL (local dev):  `http://localhost:8000`
Interactive docs:      `/docs` (Swagger UI) / `/redoc`

All endpoints live under `/v1`. The API is JSON-only; requests and
responses are `application/json; charset=utf-8`.

Authentication: **Bearer JWT** in the `Authorization` header for every
endpoint outside `/v1/auth/*` and `/v1/health`. Refresh flow described
in §2.

---

## 0. Conventions

- **IDs:** UUIDv4, serialized as strings (e.g.,
  `"7c5e3b7e-9d8e-4d6b-9ad1-2f1b4f4f8d12"`).
- **Timestamps:** ISO-8601 UTC with trailing `Z`
  (e.g., `"2025-01-27T15:04:05Z"`).
- **Pagination:** `?limit=50&cursor=<opaque>`. Responses include
  `next_cursor` (null if exhausted).
- **Errors:** `{ "detail": "<human-readable>", "code": "<machine-key>" }`
  with the conventional HTTP status code. `422` carries Pydantic's
  validation envelope.
- **Idempotency:** mutating endpoints accept an optional
  `Idempotency-Key` header (UUID); repeated calls with the same key
  within 24h return the original response.
- **Rate limits:** announced via `x-ratelimit-*` headers; defaults are
  60 req/min/user on read routes and 30 req/min/user on writes.
- **Request tracing:** every response carries `x-request-id`. Include
  it in any bug report.

---

## 1. Health

### `GET /v1/health`

Liveness + readiness. No auth.

```bash
curl http://localhost:8000/v1/health
```

```json
{
  "status": "ok",
  "version": "0.4.2",
  "db": "ok",
  "redis": "ok",
  "uptime_seconds": 12873
}
```

---

## 2. Auth

### `POST /v1/auth/register`

Create a new user inside a new tenant (the "owner" of the new tenant).
For inviting users into an existing tenant, see §3.

```bash
curl -X POST http://localhost:8000/v1/auth/register \
  -H 'content-type: application/json' \
  -d '{
    "email": "alice@example-mga.com",
    "password": "correct horse battery staple",
    "tenant_name": "Example Specialty MGA"
  }'
```

```json
{
  "user": {
    "id": "7c5e3b7e-9d8e-4d6b-9ad1-2f1b4f4f8d12",
    "email": "alice@example-mga.com",
    "created_at": "2025-01-27T15:04:05Z"
  },
  "tenant": {
    "id": "0c2a1f3a-9e25-4b9a-aa11-90cb18d3e8e1",
    "name": "Example Specialty MGA"
  },
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### `POST /v1/auth/login`

```bash
curl -X POST http://localhost:8000/v1/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"alice@example-mga.com","password":"correct horse battery staple"}'
```

Response shape identical to `register` minus the `tenant.name` echo.

### `POST /v1/auth/refresh`

```bash
curl -X POST http://localhost:8000/v1/auth/refresh \
  -H 'content-type: application/json' \
  -d '{"refresh_token":"eyJ..."}'
```

Returns a fresh `access_token` and a rotated `refresh_token`. The old
refresh token is invalidated server-side.

### `POST /v1/auth/logout`

```bash
curl -X POST http://localhost:8000/v1/auth/logout \
  -H 'authorization: Bearer eyJ...' \
  -H 'content-type: application/json' \
  -d '{"refresh_token":"eyJ..."}'
```

`204 No Content`. Adds the refresh token to the server-side denylist.

### `GET /v1/auth/me`

```bash
curl http://localhost:8000/v1/auth/me -H 'authorization: Bearer eyJ...'
```

```json
{
  "id": "7c5e3b7e-9d8e-4d6b-9ad1-2f1b4f4f8d12",
  "email": "alice@example-mga.com",
  "tenant_id": "0c2a1f3a-9e25-4b9a-aa11-90cb18d3e8e1",
  "roles": ["owner"]
}
```

---

## 3. Tenants

### `GET /v1/tenants/me`

Returns the caller's tenant.

### `POST /v1/tenants/me/invites`

Invite a user into the caller's tenant. Sends a magic-link email.

```bash
curl -X POST http://localhost:8000/v1/tenants/me/invites \
  -H 'authorization: Bearer eyJ...' \
  -H 'content-type: application/json' \
  -d '{"email":"bob@example-mga.com","role":"operator"}'
```

```json
{ "invite_id": "...", "expires_at": "2025-02-03T15:04:05Z" }
```

### `GET /v1/tenants/me/users`

List users in the caller's tenant.

---

## 4. Suppliers

A `Supplier` is a producer/MGA on whose behalf submissions are made.

### `GET /v1/suppliers`

```bash
curl 'http://localhost:8000/v1/suppliers?limit=20' \
  -H 'authorization: Bearer eyJ...'
```

```json
{
  "items": [
    {
      "id": "...",
      "legal_name": "Acme Producers LLC",
      "naic_number": "12345",
      "ein": "12-3456789",
      "primary_email": "ops@acme-producers.com",
      "created_at": "2025-01-10T09:11:00Z"
    }
  ],
  "next_cursor": null
}
```

### `POST /v1/suppliers`

```bash
curl -X POST http://localhost:8000/v1/suppliers \
  -H 'authorization: Bearer eyJ...' \
  -H 'content-type: application/json' \
  -d '{
    "legal_name": "Acme Producers LLC",
    "naic_number": "12345",
    "ein": "12-3456789",
    "primary_email": "ops@acme-producers.com"
  }'
```

### `GET /v1/suppliers/{supplier_id}`

### `PATCH /v1/suppliers/{supplier_id}`

### `DELETE /v1/suppliers/{supplier_id}`

Hard-delete. Cascades to associated submissions and COIs. Audit log
rows are preserved with only the FK reference.

### `GET /v1/suppliers/{supplier_id}/cois`

List Certificates of Insurance for a supplier.

### `POST /v1/suppliers/{supplier_id}/cois`

```bash
curl -X POST http://localhost:8000/v1/suppliers/$ID/cois \
  -H 'authorization: Bearer eyJ...' \
  -H 'content-type: application/json' \
  -d '{
    "policy_number": "EO-2025-0001",
    "carrier": "Hiscox",
    "coverage_type": "errors_and_omissions",
    "limit_amount_cents": 100000000,
    "effective_date": "2025-01-01",
    "expiry_date": "2026-01-01"
  }'
```

---

## 5. Portals

A `Portal` is a target carrier portal.

### `GET /v1/portals`

```json
{
  "items": [
    {
      "id": "...",
      "platform": "amtrust",
      "display_name": "AmTrust North America",
      "base_url": "https://www.amtrustfinancial.com",
      "supports_submit": true,
      "supports_sign": false,
      "risky": false
    }
  ]
}
```

`platform` is one of the `PortalPlatform` enum values (`applied_epic`,
`vertafore_ams360`, `vertafore_sircon`, `amtrust`, `markel`,
`nationwide_es`, `cna`, `guidewire`, `hawksoft`, `ezlynx`,
`nowcerts`).

### `POST /v1/portals`

Tenant-admin only. Adds a portal target into this tenant's catalogue.

### `POST /v1/portals/{portal_id}/smoke-test`

Queues a smoke test (sandbox login, no real submission). Returns
`202 Accepted` with a job id.

---

## 6. Consent

### `POST /v1/consent`

```bash
curl -X POST http://localhost:8000/v1/consent \
  -H 'authorization: Bearer eyJ...' \
  -H 'content-type: application/json' \
  -d '{
    "supplier_id": "...",
    "portal_id": "...",
    "scope": "submit_on_behalf",
    "tos_text_seen": "<carrier TOS verbatim>",
    "signed_by_name": "Alice Smith",
    "signed_by_email": "alice@example-mga.com",
    "signed_at_ip": "203.0.113.5"
  }'
```

```json
{
  "id": "...",
  "supplier_id": "...",
  "portal_id": "...",
  "scope": "submit_on_behalf",
  "tos_version_hash": "sha256:...",
  "signed_at": "2025-01-27T15:04:05Z"
}
```

### `GET /v1/consent?supplier_id=...&portal_id=...`

### `POST /v1/consent/{id}/revoke`

Revokes the consent. Future submissions for this supplier+portal will
be rejected with `409 consent_revoked`.

---

## 7. Submissions

### `POST /v1/submissions`

```bash
curl -X POST http://localhost:8000/v1/submissions \
  -H 'authorization: Bearer eyJ...' \
  -H 'content-type: application/json' \
  -H 'idempotency-key: 11111111-2222-3333-4444-555555555555' \
  -d '{
    "supplier_id": "...",
    "portal_id": "...",
    "consent_record_id": "...",
    "fields_submitted": {
      "producer_name": "Acme Producers LLC",
      "naic": "12345",
      "binder_effective_date": "2025-02-01",
      "premium_cents": 1250000
    }
  }'
```

```json
{
  "id": "...",
  "status": "queued",
  "supplier_id": "...",
  "portal_id": "...",
  "created_at": "2025-01-27T15:04:05Z"
}
```

The pipeline atomically claims the row and dispatches it.

### `GET /v1/submissions/{id}`

```json
{
  "id": "...",
  "status": "completed",
  "supplier_id": "...",
  "portal_id": "...",
  "attempts": 1,
  "last_error": null,
  "receipt_id": "...",
  "created_at": "2025-01-27T15:04:05Z",
  "completed_at": "2025-01-27T15:04:38Z"
}
```

`status` is one of: `queued`, `running`, `completed`, `failed`,
`retrying`, `blocked`, `platform_unsupported`.

### `GET /v1/submissions?status=completed&supplier_id=...&limit=50`

### `POST /v1/submissions/{id}/retry`

Resets a `failed` or `blocked` submission to `queued`. `409` if the
submission is already terminal-successful.

---

## 8. Receipts

### `GET /v1/receipts/{receipt_id}`

Returns the receipt as stored. Tenant-scoped — only callable from
inside the receipt's tenant.

```json
{
  "receipt_id": "...",
  "key_id": "20250127",
  "payload": {
    "receipt_id": "...",
    "tenant_id": "...",
    "supplier_id": "...",
    "portal": "amtrust",
    "submission_id": "...",
    "submitted_at": "2025-01-27T15:04:38Z",
    "payload_hash": "sha256:...",
    "tos_version_hash": "sha256:...",
    "consent_record_id": "..."
  },
  "sig_b64": "..."
}
```

### `GET /v1/receipts?supplier_id=...&portal_id=...`

Paginated listing scoped to the caller's tenant.

### `GET /v1/keys/{key_id}`

Returns the public key for a `key_id`. Public, no auth.

```json
{
  "key_id": "20250127",
  "algorithm": "ed25519",
  "public_key_b64url": "MCowBQYDK2VwAyEA...",
  "created_at": "2025-01-27T00:00:00Z",
  "retired_at": null
}
```

### Public verifier — `GET https://verify.once.io/verify/{receipt_id}`

Lives in the separate `verifier/` service. No auth. Returns the
receipt, signature, public key, and the verification boolean — so the
caller can re-verify offline.

```bash
curl https://verify.once.io/verify/$RECEIPT_ID
```

```json
{
  "receipt": {
    "receipt_id": "...",
    "tenant_id": "...",
    "supplier_id": "...",
    "portal": "amtrust",
    "submission_id": "...",
    "submitted_at": "2025-01-27T15:04:38Z",
    "payload_hash": "sha256:...",
    "tos_version_hash": "sha256:...",
    "consent_record_id": "..."
  },
  "sig_b64": "...",
  "public_key": {
    "key_id": "20250127",
    "algorithm": "ed25519",
    "public_key_b64url": "MCowBQYDK2VwAyEA..."
  },
  "verified": true
}
```

The verifier reconstructs `signed_bytes = canonical_json(receipt).encode()`
and runs `Ed25519.verify(public_key, sig, signed_bytes)`.

---

## 9. Error codes

| HTTP | `code`                  | Meaning |
|---|---|---|
| 400 | `validation_error`      | Generic input validation. |
| 401 | `unauthorized`          | Missing/invalid bearer token. |
| 401 | `token_expired`         | Access token TTL exceeded. Refresh. |
| 403 | `forbidden`             | Authenticated, but lacks role. |
| 404 | `not_found`             | Resource missing or not in tenant scope. |
| 409 | `consent_revoked`       | Submission rejected — consent missing/revoked. |
| 409 | `submission_terminal`   | Cannot retry a successfully-completed submission. |
| 422 | (Pydantic envelope)     | Schema validation. |
| 429 | `rate_limited`          | Slow down. |
| 500 | `internal_error`        | Bug; check `x-request-id` in Sentry. |
| 503 | `dependency_unavailable`| DB or Redis is down; retry with backoff. |

---

# Appendix A — Production Conventions (authoritative)

> The reference above documents *which* endpoints exist; this appendix
> documents *how* the API behaves at the protocol layer. New endpoints
> MUST follow this contract. Older endpoints are migrating — fields and
> envelopes here are additive and backward-compatible.

## A.1 URL conventions

- Lower-case **kebab-case** segments: `/v1/loss-runs`, `/v1/producer-licenses`.
- **Plural** resource names: `/v1/suppliers`, never `/v1/supplier`.
- **No verbs** in URLs — express the action with the HTTP method.
- Nested resources only when the child cannot exist without the parent:
  `/v1/suppliers/{supplier_id}/loss-runs`.
- Query string for filters and pagination. Never in the path.
- Stable opaque IDs (`String(36)` UUID4). Never expose sequential PKs.

## A.2 HTTP methods

| Method   | Semantics                                                          |
| -------- | ------------------------------------------------------------------ |
| `GET`    | Safe + idempotent read. Cacheable via `ETag`.                      |
| `POST`   | Create. Returns `201` with body + `Location` header.               |
| `PATCH`  | **Partial** update. JSON Merge Patch by default.                   |
| `DELETE` | Remove. `204` on success.                                          |
| `HEAD`   | Same as `GET` minus body.                                          |

> ❗ We deliberately **do not use `PUT`**. PATCH covers partial updates and
> avoids the "send the whole representation back" tax.

## A.3 Status codes

| Code  | When to use                                                             |
| ----- | ----------------------------------------------------------------------- |
| `200` | Successful read or update.                                              |
| `201` | Successful create. Include `Location`.                                  |
| `204` | Successful delete / empty-body op.                                      |
| `304` | Conditional GET cache hit (`If-None-Match`).                            |
| `400` | Malformed request.                                                      |
| `401` | Authentication missing / invalid.                                       |
| `403` | Authenticated but not authorized.                                       |
| `404` | Resource not found or not visible to your tenant.                       |
| `409` | Conflict with current resource state.                                   |
| `412` | `If-Match` / `If-None-Match` precondition failed.                       |
| `422` | Validation error. Always carries `errors[]`.                            |
| `429` | Rate limit exceeded. Include `Retry-After`.                             |
| `500` | Unhandled server error. Logged + Sentry-captured.                       |
| `503` | Dependency unavailable.                                                 |

## A.4 Error envelope — RFC 9457 Problem Details

Every 4xx / 5xx response carries the same shape:

```json
{
  "type": "https://docs.getonce.com/errors/supplier-not-found",
  "title": "Supplier not found",
  "status": 404,
  "detail": "No supplier with id 'sup_01HXY' is accessible to your tenant.",
  "instance": "/v1/suppliers/sup_01HXY",
  "trace_id": "01HXYABCDEF...",
  "errors": [
    {"loc": ["body", "ein"], "msg": "EIN must be 9 digits", "code": "value_error.ein_format"}
  ]
}
```

- `type` — stable URI under `https://docs.getonce.com/errors/`.
- `title` — short, human-readable.
- `status` — duplicate of HTTP status (per RFC 9457).
- `detail` — human-readable detail. **Transitional**: doubles as the
  legacy `{"detail": "..."}` shape FastAPI emits. New clients should read
  `type` + `title` + `errors[]`.
- `instance` — usually the request path.
- `trace_id` — matches `X-Request-ID` on the response. Quote in bug reports.
- `errors` — only on 422 responses; one entry per offending field.

Content-Type on error responses produced by the canonical handler:
`application/problem+json`. Legacy handlers continue to return
`application/json` until migrated.

## A.5 Pagination

Two modes are supported on every list endpoint that adopts the
`Page[T]` envelope (see `app.schemas.common`).

### Offset mode (default)

```
GET /v1/suppliers?limit=50&offset=100
```

- `limit` — page size, `1 ≤ limit ≤ 200`. Default `50`.
- `offset` — rows to skip, `≥ 0`. Default `0`.
- Response body:

  ```json
  {
    "items": [/* ... */],
    "total": 1342,
    "limit": 50,
    "offset": 100,
    "next_cursor": null,
    "prev_cursor": null
  }
  ```

- Out-of-range `limit` / negative `offset` → `422`.

### Cursor mode

```
GET /v1/submissions?limit=100&cursor=eyJjcmVhdGVkX2F0...
```

- `cursor` — opaque base64 returned by a prior response. **Treat as
  opaque.** Encoding may change without notice.
- `total` is `null` in cursor mode — counting is skipped to keep latency
  bounded under load.
- `next_cursor: null` ⇒ end of stream.
- Ordering is `(created_at DESC, id DESC)` — stable under inserts at the
  tail.

### Invariants

- Pagination ordering is stable within a request.
- The same `cursor` always names the same boundary row.
- Switching `limit` mid-stream is allowed; cursors remain valid.

## A.6 Idempotency

Clients may send on any mutating request:

```
Idempotency-Key: 01HXY3QF6ABCDEFGHJKMNPQRST
```

Format: UUID4 or ULID. Otherwise → `400 invalid-idempotency-key`.

- First request with key `K` → process normally, cache the response
  (status + body + safe headers + sha256 of request body) for 24h keyed
  by `(tenant_id, K)`.
- Replay with same `K` + **same body** → cached response with
  `Idempotency-Replayed: true`.
- Replay with same `K` + **different body** → `422
  idempotency-key-conflict`.
- Only `2xx` responses are cached. Errors are not — clients can safely
  retry them without rotating the key.

Some endpoints may require the key (marked in OpenAPI;
`400 idempotency-key-required` on absence).

## A.7 ETag / conditional requests

### Reads

- Every cacheable `GET` carries `ETag: W/"<sha256-hex>"`.
- `If-None-Match: W/"..."` → `304 Not Modified` with empty body when the
  tag matches.
- `If-None-Match: *` matches any existing response.

### Writes

- Routes that opt into optimistic concurrency honor `If-Match`:
  - header absent → no precondition;
  - matches resource's current ETag → proceed;
  - mismatch → `412 precondition-failed`;
  - `If-Match: *` requires the resource to exist.

## A.8 Versioning

- **URL versioning is canonical.** All current routes live under `/v1/`.
  A future `/v2/` will be added at the routing layer; `/v1/` will be
  maintained per the deprecation policy.
- **Vendor media-type negotiation** is supported as future-proofing:

  ```
  Accept: application/vnd.once.v2+json
  ```

  When v2 ships, the same URL can serve both — Accept wins. Today the
  parser accepts the header but only `v1` is registered; unknown versions
  silently fall back to `v1`.
- Every response carries `X-API-Version: v1`.

## A.9 Rate limits

Defaults (per client IP):

- `120 req / minute`, burst `30`. Configurable per environment.

Response headers:

```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 117
X-RateLimit-Reset: 42
```

On `429`:

```
Retry-After: 42
```

Auth routes have stricter account-lockout limits (see `auth_service`).

## A.10 Data formats

| Concept           | Wire format                                                       |
| ----------------- | ----------------------------------------------------------------- |
| Timestamps        | ISO 8601 UTC, `Z` suffix: `2025-01-15T12:34:56Z`.                 |
| Dates             | ISO 8601: `YYYY-MM-DD`.                                           |
| Money             | Integer **cents**; field suffix `_cents` (e.g. `amount_cents`).   |
| Currency codes    | ISO 4217 uppercase (`USD`).                                       |
| IDs               | Opaque strings (UUID4). Never sequential ints.                    |
| Booleans          | JSON `true` / `false`. No `"true"` / `"1"`.                       |
| Nullability       | Explicit. `null` ≠ field-absent.                                  |
| Empty collections | `[]` / `{}`, never `null`.                                        |

## A.11 Deprecation policy

When a field, parameter, or endpoint is deprecated:

1. **Announce** in release notes + this file's CHANGELOG.
2. Add `Sunset: <RFC 1123 date>` and `Deprecation: true` response headers
   on every affected route.
3. Honor the deprecated path for **≥ 90 days** after announcement.
4. After sunset: return `410 Gone` for one full minor release before
   removing the route entirely.

## A.12 Migration note (B1 coordination)

Routes added by Agent B1 (and any future list endpoints) should adopt
`Page[T]` from `app.schemas.common`:

```python
from app.schemas.common import Page
from app.utils.pagination import paginate

@router.get("/things", response_model=Page[ThingRead])
async def list_things(...):
    stmt = select(Thing).where(Thing.tenant_id == tenant_id)
    return await paginate(session, stmt, mode="offset", limit=limit, offset=offset)
```

Existing list endpoints (`/v1/suppliers`, `/v1/portals`,
`/v1/submissions`) keep their bespoke shapes for backward compatibility
with shipped clients. New endpoints standardize on `Page[T]` from day one.
