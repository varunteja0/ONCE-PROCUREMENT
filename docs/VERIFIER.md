# Once Receipt Verifier

`verify.getonce.com` is a tiny, fully independent microservice that lets
anyone check whether a Once receipt is genuine. It has no database, no
auth, and no dependency on the main Once backend other than a single
read-only HTTP call to fetch the signed envelope.

## What it does (in one paragraph)

When a supplier submission is delivered to a buyer portal, Once writes a
**receipt**: a small JSON document recording the immutable facts of that
submission (who submitted what, where, when, and a hash of the payload).
Once then signs that document with an Ed25519 private key it controls,
producing a signed envelope. The verifier fetches an envelope by id from
the main backend's public read endpoint, re-encodes the payload using
RFC 8785 canonical JSON, and uses Once's published Ed25519 public key to
check the signature. If the math checks out the verifier shows ✓; if a
single byte has been changed anywhere in the payload it shows ✗.

## URL patterns

| URL | What you get |
| --- | --- |
| `GET /verify/{id}` (browser) | Server-rendered HTML page with a big ✓/✗ verdict, the receipt details, and code snippets to re-verify yourself. |
| `GET /verify/{id}` with `Accept: application/json` | JSON `{ verified, payload, public_key_pem, signing_key_id }`. |
| `GET /verify/{id}` with `Accept: application/jose+json` | Raw signed envelope (`{ payload, signature, signing_key_id }`) for advanced clients. |
| `GET /verify/{id}.json` | Always JSON (escape hatch for tools that can't set `Accept`). |
| `GET /verify/{id}.html` | Always HTML. |
| `GET /verify/{id}/badge.svg` | 120×31 shields-style SVG badge — green "verified", red "invalid", amber "not found". `Cache-Control: public, max-age=60, stale-while-revalidate=300` and `Access-Control-Allow-Origin: *` so you can embed it anywhere. |
| `GET /health`, `GET /healthz` | Liveness probe. |

Content negotiation follows RFC 7231 §5.3 — q-values are parsed and
respected, so `Accept: text/html;q=0.5,application/json;q=0.9` returns
JSON.

## Signing model

* **Algorithm:** Ed25519 (RFC 8032). 32-byte public keys, 64-byte
  signatures.
* **What is signed:** the **canonical-JSON** (RFC 8785) UTF-8 encoding
  of the receipt payload. Keys are sorted by UTF-16BE order, no
  insignificant whitespace, numbers in their shortest finite
  representation. The same canonicalizer ships in
  [`backend/app/utils/canonical_json.py`](../backend/app/utils/canonical_json.py)
  and [`verifier/app/canonical.py`](../verifier/app/canonical.py) — they
  are byte-for-byte identical.
* **Key rotation:** every signature includes a `signing_key_id`. The
  verifier is configured with one public key at a time via the
  `PUBLIC_KEY_PEM` env var. To rotate, deploy a new verifier instance
  with the new key and keep the old one running until all receipts
  signed with the old key have aged out of your retention window.

## Verify a receipt yourself in 3 lines of Python

```python
import base64, json, httpx
from cryptography.hazmat.primitives import serialization

env = httpx.get("https://verify.getonce.com/verify/<id>.json").json()
pub = serialization.load_pem_public_key(env["public_key_pem"].encode())
pub.verify(
    base64.b64decode(env["payload"]["signature"] if False else  # noqa
                     httpx.get(f"https://verify.getonce.com/verify/<id>",
                               headers={"Accept": "application/jose+json"}).json()["signature"]),
    json.dumps(env["payload"], sort_keys=True, separators=(",", ":")).encode(),
)  # raises InvalidSignature on mismatch
```

The cleaner version:

```python
import base64, json, httpx
from cryptography.hazmat.primitives import serialization

env = httpx.get("https://verify.getonce.com/verify/<id>",
                headers={"Accept": "application/jose+json"}).json()
pub = serialization.load_pem_public_key(PUBLIC_KEY_PEM.encode())
signed = json.dumps(env["payload"], sort_keys=True, separators=(",", ":")).encode()
pub.verify(base64.b64decode(env["signature"]), signed)
```

## Embedding the badge

Drop this in any README, dashboard, or status page:

```markdown
[![Verified by Once](https://verify.getonce.com/verify/<id>/badge.svg)](https://verify.getonce.com/verify/<id>)
```

The badge is served as `image/svg+xml`, cached for 60 seconds, and
CORS-open so it works from any origin.

## Threat model — what verification proves, and what it doesn't

**Verification proves:**

1. **Authenticity** — the receipt was signed by a private key that Once
   controls. No one else can forge a receipt that passes verification
   without stealing Once's private key.
2. **Integrity** — the payload you are looking at is byte-for-byte
   identical to the payload that was signed. Any modification, however
   small, invalidates the signature.

**Verification does *not* prove:**

1. **Legal admissibility.** A green check is strong technical evidence
   but is not by itself a legal instrument. Treat it as one input to
   your evidentiary chain, alongside whatever business records,
   timestamps, and witness logs your jurisdiction requires.
2. **Business-process correctness.** The receipt records what was
   submitted; it does not promise that the data was correct, that the
   supplier portal accepted it, or that any downstream workflow
   completed successfully. The submission status field on the receipt
   reflects Once's view at the moment of signing only.
3. **Non-repudiation of the supplier.** The signing key belongs to
   Once, not to the supplier. If you need a supplier-side signature,
   layer one in at submission time.
4. **Key compromise.** If Once's signing key is ever compromised, all
   signatures it produced become untrustworthy retroactively. The
   `signing_key_id` field lets you identify which receipts were signed
   with a compromised key during incident response.

When the stakes are high, combine verifier output with your own audit
trail.
