# Secret Rotation Runbook

This runbook covers every long-lived secret in the Once platform.  All
rotations target **zero customer-visible downtime**.  Run them quarterly
or immediately on suspected compromise.

## Conventions

- All commands assume you are logged into Fly (`fly auth login`) and have
  `flyctl` v0.2+ installed.
- Treat each rotation as a Sev-3 change unless triggered by suspected
  compromise (then Sev-1).
- Tag the corresponding change in the audit log (`secret.rotated`).
- Use `python -c "import secrets; print(secrets.token_urlsafe(48))"` for
  generic high-entropy strings, or `python backend/scripts/gen_signing_key.py`
  for Ed25519 receipt-signing keys, or `python backend/scripts/gen_secret.py`
  if you want a length-validated SECRET_KEY / JWT_SECRET_KEY.

## 1. JWT signing secret (`JWT_SECRET_KEY`)

Tokens are short-lived (15 min access, 30 d refresh), so the grace window
only needs to span the refresh-token lifetime.

**Future plural-secret support**: the auth layer currently reads
`JWT_SECRET_KEY` (single).  A future change will introduce
`JWT_SECRET_KEYS` (comma-separated, leftmost = primary) so decoders can
accept old keys during rotation.  Until that lands, the procedure below
forces all users to re-login after rotation — communicate accordingly.

Procedure (once plural keys ship):

1. Generate a new secret:
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`
2. Set `JWT_SECRET_KEYS="<new>,<old>"` on backend (`fly secrets set ...`).
3. Wait full refresh-token lifetime (30 d) + 1 day buffer.
4. Set `JWT_SECRET_KEYS="<new>"` (drop the old key).
5. Verify with `GET /v1/security/self-check` → `jwt_secret_strength = strong`.

Until plural support: schedule a 5-min maintenance window, rotate, accept
that everyone re-logins.  Document in customer changelog.

## 2. Receipt signing key (Ed25519)

This is the most security-critical secret: receipts signed with the old
key MUST remain verifiable forever.  The `SigningKey` registry already
supports this.

Procedure:

1. `python backend/scripts/gen_signing_key.py` → produces a new PEM and
   a suggested `key_id`.
2. Insert as **inactive** via admin task:
   ```sql
   INSERT INTO signing_keys (id, key_id, private_key_pem, public_key_pem,
                             status, created_at)
   VALUES (gen_random_uuid(), '<new_id>', '<pem>', '<pub_pem>',
           'inactive', now());
   ```
3. Promote to **dual-sign** for 7 days — backend signs every receipt with
   both keys; verifier accepts either.  (Implementation hook: set
   `RECEIPT_SIGNING_DUAL_KEY_IDS=<new_id>,<old_id>`.)
4. After 7 days, promote `<new_id>` to **primary** and demote `<old_id>`
   to **verify-only**:
   ```sql
   UPDATE signing_keys SET status='primary' WHERE key_id='<new_id>';
   UPDATE signing_keys SET status='verify_only' WHERE key_id='<old_id>';
   ```
5. Never delete the old key row — verifier needs it for historical
   receipts.

## 3. `SECRET_KEY` (cookie / CSRF signing)

Used to sign the CSRF cookie value and any future signed cookies.

1. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
2. `fly secrets set SECRET_KEY="<new>" --app once-api`
3. Outstanding CSRF cookies become invalid — users will re-acquire one
   on the next safe-method request (transparent).

## 4. Database credentials

Postgres on Fly (or external).  Use the connection-string format
`postgres://user:pass@host/db?sslmode=require`.

1. Create a new role in Postgres: `CREATE ROLE once_app_v2 WITH LOGIN PASSWORD '<new>' INHERIT;`
2. Grant it the same privileges as the current role: `GRANT once_app TO once_app_v2;`
3. `fly secrets set DATABASE_URL="postgres://once_app_v2:<new>@..."`
4. Deploy.  Connections from old role drain over 5 min.
5. `REVOKE once_app FROM <connections>; DROP ROLE once_app;` after 24 h.

## 5. Third-party API keys

### Stripe

1. Stripe dashboard → API keys → **Roll restricted key**.
2. `fly secrets set STRIPE_SECRET_KEY="<new>" STRIPE_PUBLISHABLE_KEY="<new>"`
3. Stripe keeps the old key valid for 12 h — no downtime.

### Sentry

1. Sentry → Project settings → Client Keys → **Generate New Key**.
2. Set `SENTRY_DSN` on backend, frontend, extension, verifier — all four.
3. Revoke old DSN after 7 days.

### OFAC consolidated list mirror

1. No "key" per se; if the mirror URL or token changes, update
   `OFAC_LIST_URL` and `OFAC_LIST_TOKEN`.
2. Bounce workers so the cache is refreshed on next fetch.

## 6. Webhook signing secrets

Stripe → set new webhook signing secret in Stripe dashboard, then
`fly secrets set STRIPE_WEBHOOK_SECRET="<new>"`.  Stripe rotates atomically
on save.

## 7. Cleanup checklist

After any rotation:

- [ ] Confirm `GET /v1/security/self-check` shows `*_strength: strong`.
- [ ] Tail logs for 30 min looking for `auth_login_failed` spikes.
- [ ] Update internal password manager.
- [ ] Note in the security changelog (`docs/CHANGELOG-SECURITY.md`).
- [ ] Close the change ticket.
