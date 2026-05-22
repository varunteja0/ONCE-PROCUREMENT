# verifier/ — Agent rules

> Authoritative rules: [CONTRACTS.md](../CONTRACTS.md) §6, §12 (row 24).
> Tiny public service. **Keep it tiny.**

## Purpose

Single responsibility: given a `receipt_id`, fetch the signed payload + public
key, verify the Ed25519 signature, and return `{payload, sig, public_key, verified: bool}`.

## Stack

- FastAPI · `cryptography` (Ed25519) · Pydantic v2
- Stateless. Reads from the backend's public `/v1/keys/{key_id}` and
  `/v1/receipts/{id}/payload` endpoints. **No DB of its own.**
- Deployed standalone on Fly.io (see `fly.toml`).

## Layout

```
app/
  main.py            # FastAPI app, /healthz + /verify/{receipt_id}
  canonical.py       # canonical-JSON encoder (must match backend exactly)
  observability.py   # structlog + Sentry
```

## Hard rules (verifier)

1. **Canonical JSON must byte-match the backend's `app/utils/canonical_json.py`.**
   Any divergence breaks every existing receipt. Update both in lockstep, with
   tests that pin the byte output.
2. **No persistence.** No DB, no cache writes. In-memory LRU for public keys
   is allowed but must be size-bounded and TTL-bounded. Per-key monthly
   usage counters are tracked in the **main backend**
   (`verifier_api_key_usage` table); the verifier merely POSTs a charge call
   per request — it does not own the counter row.
3. **Public verification stays unauthenticated.** `GET /verify/{id}` MUST
   remain callable without any header — receipts are publicly verifiable by
   design. The optional `X-Verify-API-Key` header lifts the per-IP burst
   limit and enables monetization (free tier monthly cap, paid tier
   metered), but absence of the header is **not** an error.
4. **CORS:** allow `*` on `/verify/*` and `/healthz` only. Do not allow
   credentials.
5. **Rate limit** (in-process `limits` MovingWindowRateLimiter, per remote
   IP, configurable via `unauth_rate_limit`, default
   `100/day;20/hour;5/minute`). Applied only when no `X-Verify-API-Key` is
   present; keyed requests skip the IP limit and are bounded by the
   per-key monthly cap enforced by the backend charge endpoint.
6. **API-key flow:** when `X-Verify-API-Key` is set, the middleware POSTs
   to the backend `/v1/internal/verifier-keys/charge` endpoint with the
   shared `X-Internal-Token` (`backend_internal_token` setting). 200 →
   attach `request.state.api_key_id` / `api_key_tenant_id` and pass.
   401 → `{detail: {code: "invalid_api_key"}}`. 402 → forward the
   `quota_exceeded` body verbatim. Anything else → 503 (backend
   unreachable; do not silently fail-open with a key present).
7. **Errors:** return `{verified: false, reason: "<short_code>"}` rather than
   500 when verification simply fails. 5xx only for the verifier being broken.
8. **No new endpoints** without explicit ask. This service stays single-purpose.

## Tests

`pytest -q` must pass. Add a test for any new failure mode in `test_verify.py`
and pin a known-good canonical-JSON output in `test_health.py` / a new
canonical test.

## Running locally

```powershell
cd verifier
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
pytest -q
```

## Never do

- Add a database, queue, or persistent cache.
- Add authentication / authorization.
- Diverge canonical-JSON encoding from the backend.
- Expand scope beyond verifying receipts.
