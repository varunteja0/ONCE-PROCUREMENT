---
applyTo: "verifier/**/*.py"
description: "Public Ed25519 verifier — stateless, no auth, canonical-JSON byte-match with backend"
---

# Verifier — required behavior

1. **Stateless.** No database, no persistent cache. Bounded in-memory LRU
   for public keys is OK.
2. **Public by design.** No JWT, no API key. CORS allows `*` on
   `/verify/*` and `/healthz`.
3. **Single responsibility:** verify a receipt. Do not add unrelated
   endpoints without explicit approval.
4. **Canonical-JSON encoding must byte-match** `backend/app/utils/canonical_json.py`.
   If you change one, change both, and add a pinned-bytes test in each.
5. **Failure semantics:** verification failure returns
   `{verified: false, reason: "<short_code>"}` with HTTP 200. Use 5xx only
   when the verifier itself is broken (network, key fetch failure, etc.).
6. **Rate limit** with slowapi per IP.
7. **`from __future__ import annotations`** at the top of every module.
   structlog logger only. No `print`.

## Tests

Any change to verification logic requires a test in
`verifier/test_verify.py`. Pin a known-good canonical-JSON byte output so
silent encoder drift fails CI.

Run: `cd verifier && pytest -q`.
