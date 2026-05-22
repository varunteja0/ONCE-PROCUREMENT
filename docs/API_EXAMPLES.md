# Once API — curl Examples

Placeholder host: `https://api.getonce.com`. Local: `http://localhost:8000`.
Replace `$TOKEN` with a valid JWT access token obtained from
`POST /v1/auth/login`.

## Auth

### Register a tenant + owner

```bash
curl -X POST https://api.getonce.com/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"owner@acme.com","password":"S3cret-Pass!","full_name":"Jane Owner","tenant_name":"Acme MGA"}'
# → 201 {"access_token":"...","refresh_token":"...","token_type":"bearer"}
```

### Login

```bash
curl -X POST https://api.getonce.com/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"owner@acme.com","password":"S3cret-Pass!"}'
```

### Login — bad credentials (error envelope)

```bash
curl -X POST https://api.getonce.com/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"owner@acme.com","password":"wrong"}'
# → 401
# {
#   "type": "https://docs.getonce.com/errors/unauthorized",
#   "title": "Unauthorized",
#   "status": 401,
#   "detail": {"code": "invalid_credentials", "message": "..."},
#   "instance": "/v1/auth/login",
#   "trace_id": "01HXY..."
# }
```

### Refresh

```bash
curl -X POST https://api.getonce.com/v1/auth/refresh \
  -H 'Content-Type: application/json' \
  -d '{"refresh_token":"..."}'
```

## Tenants

### Read my tenant

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://api.getonce.com/v1/tenants/me
```

## Suppliers

### Create

```bash
curl -X POST https://api.getonce.com/v1/suppliers \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: 01HXY3QF6ABCDEFGHJKMNPQRST' \
  -d '{"legal_name":"Bob'\''s Trucking LLC","ein":"12-3456789","naics_code":"484110"}'
```

### Replay the same create (idempotent)

```bash
curl -X POST https://api.getonce.com/v1/suppliers \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: 01HXY3QF6ABCDEFGHJKMNPQRST' \
  -d '{"legal_name":"Bob'\''s Trucking LLC","ein":"12-3456789","naics_code":"484110"}'
# → 201 with header: Idempotency-Replayed: true
```

### Idempotency-Key reused with different body → 422

```bash
curl -X POST https://api.getonce.com/v1/suppliers \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: 01HXY3QF6ABCDEFGHJKMNPQRST' \
  -d '{"legal_name":"Different Co"}'
# → 422 idempotency-key-conflict
```

### List (offset pagination)

```bash
curl -H "Authorization: Bearer $TOKEN" \
  'https://api.getonce.com/v1/suppliers?limit=25&offset=0'
```

### List (cursor pagination)

```bash
curl -H "Authorization: Bearer $TOKEN" \
  'https://api.getonce.com/v1/suppliers?limit=25&cursor=eyJjcmVhdGVkX2F0...'
```

### List with bad limit → 422

```bash
curl -H "Authorization: Bearer $TOKEN" \
  'https://api.getonce.com/v1/suppliers?limit=9999'
# → 422 validation error
```

### Get one (conditional GET)

```bash
ETAG=$(curl -sI -H "Authorization: Bearer $TOKEN" \
  https://api.getonce.com/v1/suppliers/sup_123 | awk -F': ' '/^ETag/ {print $2}' | tr -d '\r')

curl -i -H "Authorization: Bearer $TOKEN" \
  -H "If-None-Match: $ETAG" \
  https://api.getonce.com/v1/suppliers/sup_123
# → 304 Not Modified (empty body)
```

### Partial update with If-Match (optimistic concurrency)

```bash
curl -X PATCH https://api.getonce.com/v1/suppliers/sup_123 \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H "If-Match: $ETAG" \
  -d '{"naics_code":"484121"}'
# → 412 precondition-failed if the resource was modified since you read it
```

### Delete

```bash
curl -X DELETE https://api.getonce.com/v1/suppliers/sup_123 \
  -H "Authorization: Bearer $TOKEN"
# → 204 No Content
```

### Get one — not found

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://api.getonce.com/v1/suppliers/sup_does_not_exist
# → 404 {"type":".../not-found","title":"Not found","status":404,"detail":"...","instance":"/v1/suppliers/sup_does_not_exist","trace_id":"..."}
```

## Portals

### List supported portals

```bash
curl -H "Authorization: Bearer $TOKEN" \
  'https://api.getonce.com/v1/portals?is_supported=true'
```

## Submissions

### Create a submission

```bash
curl -X POST https://api.getonce.com/v1/submissions \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: 11111111-2222-3333-4444-555555555555' \
  -d '{"supplier_id":"sup_123","portal_id":"prt_amtrust","payload":{"line_of_business":"workers_comp"}}'
```

### List submissions

```bash
curl -H "Authorization: Bearer $TOKEN" \
  'https://api.getonce.com/v1/submissions?limit=50&offset=0'
```

### Get one submission

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://api.getonce.com/v1/submissions/sub_abc
```

### Cancel (returns 409 if already running)

```bash
curl -X POST https://api.getonce.com/v1/submissions/sub_abc/cancel \
  -H "Authorization: Bearer $TOKEN"
# → 409 {"type":".../conflict","title":"Conflict","status":409,...}
```

## Receipts

### Get a receipt (auth required for tenant context)

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://api.getonce.com/v1/receipts/rec_abc
```

### Public verifier (no auth)

```bash
curl https://api.getonce.com/verify/rec_abc
# → {"payload":{...},"signature":"...","public_key":"...","verified":true}
```

### Machine-readable public alias

```bash
curl https://api.getonce.com/v1/public/receipts/rec_abc
```

## Consents

### Create a consent record

```bash
curl -X POST https://api.getonce.com/v1/suppliers/sup_123/consents \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"portal_id":"prt_amtrust","scope":"submit_on_behalf"}'
```

## Loss runs

### Upload metadata

```bash
curl -X POST https://api.getonce.com/v1/loss-runs \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"supplier_id":"sup_123","carrier":"AmTrust","policy_period_start":"2024-01-01","policy_period_end":"2024-12-31"}'
```

## Producer licenses

### List for a supplier

```bash
curl -H "Authorization: Bearer $TOKEN" \
  'https://api.getonce.com/v1/producer-licenses?supplier_id=sup_123'
```

## EO certificates

### Create

```bash
curl -X POST https://api.getonce.com/v1/eo-certificates \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"supplier_id":"sup_123","carrier":"Hiscox","expires_on":"2026-03-31","limit_per_claim_cents":100000000}'
```

## ACORD forms

### Create an ACORD form record

```bash
curl -X POST https://api.getonce.com/v1/acord-forms \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"supplier_id":"sup_123","form_code":"125","payload":{}}'
```

## Risk schedules

### Create a schedule of vehicles

```bash
curl -X POST https://api.getonce.com/v1/risk-schedules \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"supplier_id":"sup_123","schedule_type":"vehicles","rows":[{"vin":"1HGCM82633A004352","year":2022,"make":"Ford","model":"Transit"}]}'
```

## Meta

### Health

```bash
curl https://api.getonce.com/health
# → {"status":"ok"}
```

### Negotiate API version (future-proofing)

```bash
curl -i -H 'Accept: application/vnd.once.v1+json' \
  https://api.getonce.com/v1/portals
# Response header: X-API-Version: v1
```

### Unknown API version → silent fallback to v1

```bash
curl -i -H 'Accept: application/vnd.once.v99+json' \
  https://api.getonce.com/v1/portals
# Response header: X-API-Version: v1
```

## Rate limiting

```bash
# Burst >120/min from one IP
for i in $(seq 1 200); do
  curl -s -o /dev/null -w '%{http_code}\n' \
    -H "Authorization: Bearer $TOKEN" \
    https://api.getonce.com/v1/suppliers
done | sort -u
# → 200
# → 429
```

## CSRF (browser/cookie clients only)

```bash
# 1. GET to receive the csrftoken cookie
curl -i -c cookies.txt https://api.getonce.com/v1/tenants/me

# 2. State-changing call: echo cookie value into X-CSRF-Token
TOKEN_VAL=$(awk '$6=="csrftoken"{print $7}' cookies.txt)
curl -X POST https://api.getonce.com/v1/suppliers \
  -b cookies.txt \
  -H "X-CSRF-Token: $TOKEN_VAL" \
  -H 'Content-Type: application/json' \
  -d '{"legal_name":"Cookie Co"}'
```
