# PUBLIC_TRUST_KEYS.md — DNS-TXT publication of Once signing keys

> Runbook for operators. Publishing public keys in DNS adds an
> independent trust anchor: an attacker who compromises the Once backend
> still cannot silently substitute a key, because the canonical fingerprints
> live in DNS controlled by a separate account.

## Why DNS

Three properties matter:

1. **Out-of-band** — DNS is not the Once backend. A backend compromise alone
   cannot rewrite a DNS record.
2. **Cacheable** — TTL gives auditors a deterministic propagation window.
3. **Verifiable by anyone with `dig`** — no SDK required.

The TXT records we publish under `_once-keys.getonce.com` are the
**canonical truth** about which Once signing keys are currently active. The
`/v1/public/keys` API endpoint is a convenience; if the two ever disagree,
DNS wins.

## Record format

```
_once-keys.getonce.com.  3600  IN  TXT  "v=once-key1; kid=<key_id>; alg=ed25519; sha256=<base64-of-sha256-of-DER-public-key>"
```

One TXT record per active key. Revoked keys are removed from DNS within
24 hours of revocation (matching the cache TTL).

## Publishing procedure

### 1. Pull the active keys from the API

```bash
curl -sf https://getonce.com/v1/public/keys.txt > /tmp/once-keys.pem
```

Output is one `key_id: <id>` header line followed by a PEM block, blank
line separated. Revoked keys are NOT emitted.

### 2. Generate the TXT-record body for each active key

```bash
awk '
  /^key_id:/ { kid = $2; next }
  /-----BEGIN/ { pem = $0 "\n"; in_pem = 1; next }
  /-----END/   { pem = pem $0; in_pem = 0
                 # Hash the DER form of the SubjectPublicKeyInfo
                 cmd = "printf \"%s\\n\" \"" pem "\" | openssl pkey -pubin -outform DER 2>/dev/null | openssl dgst -sha256 -binary | openssl base64 -A"
                 cmd | getline hash; close(cmd)
                 printf "\"v=once-key1; kid=%s; alg=ed25519; sha256=%s\"\n", kid, hash
                 pem = ""; next }
  in_pem { pem = pem $0 "\n" }
' /tmp/once-keys.pem
```

Each line of output is one TXT-record value, ready to paste into your DNS
provider.

### 3. Publish via your DNS provider

Use whichever tool your registrar exposes. With Cloudflare:

```bash
# Replace ZONE_ID and API_TOKEN with your own.
curl -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "TXT",
    "name": "_once-keys",
    "content": "v=once-key1; kid=key_2026_01; alg=ed25519; sha256=<base64>",
    "ttl": 3600
  }'
```

### 4. Confirm propagation

```bash
dig +short TXT _once-keys.getonce.com @1.1.1.1
dig +short TXT _once-keys.getonce.com @8.8.8.8
dig +short TXT _once-keys.getonce.com @9.9.9.9
```

All three resolvers must return the same set of records before announcing the
key rotation to customers.

## Rotation procedure

A rotation is two changes, in this order:

1. **Add the new key** to the backend AND publish its TXT record. The new key
   is now trusted but not yet used for signing. Wait one TTL window
   (default 1 hour) for caches to converge.
2. **Promote the new key to active-signing** in the backend and **revoke the
   old key** at the end of its grace period. Remove the old TXT record only
   _after_ the grace period has elapsed — auditors still verifying
   historical receipts need the public key to be reachable.

## Revocation procedure

1. Mark the key `revoked_at = now` in the backend. The key is immediately
   removed from `/v1/public/keys.txt` but remains in `/v1/public/keys`
   (with `include_revoked=true`) so historical receipts can still be
   verified.
2. Remove the corresponding TXT record from DNS.
3. Note the rotation in `docs/SECRET_ROTATION.md` and in the next customer
   release notes.

## Verifying a published receipt against the DNS anchor

This is the procedure auditors should follow:

```bash
# 1. Pull the receipt
curl -sf https://getonce.com/v1/verify/<receipt_id>.json > /tmp/receipt.json
KID=$(jq -r .receipt.signing_key_id /tmp/receipt.json)

# 2. Fetch the public key from DNS
EXPECTED=$(dig +short TXT _once-keys.getonce.com | grep "kid=$KID" | head -1)
echo "DNS says: $EXPECTED"

# 3. Fetch the same key from the API and compare fingerprints
curl -sf "https://getonce.com/v1/public/keys?include_revoked=true" \
  | jq -r --arg k "$KID" '.keys[] | select(.key_id==$k) | .public_key_pem' \
  | openssl pkey -pubin -outform DER \
  | openssl dgst -sha256 -binary | openssl base64 -A
```

If the SHA-256 from step 3 does not match the `sha256=` field from step 2,
**stop and contact security@getonce.com**.

## See also

- [verifier/README.md](../verifier/README.md) — standalone microservice.
- [docs/VERIFIER.md](./VERIFIER.md) — operator runbook for the verifier service.
- [docs/SECRET_ROTATION.md](./SECRET_ROTATION.md) — companion rotation runbook.
- [docs/MOAT.md](./MOAT.md) — why we publish at all.
