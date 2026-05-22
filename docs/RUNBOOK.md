# Once — Operations Runbook

The on-call playbook. Keep it short, keep it executable. If you're
reading this during an incident, search for the symptom — every section
starts with one.

Engineering threat model: [`SECURITY.md`](./SECURITY.md).
Compliance map: [`COMPLIANCE.md`](./COMPLIANCE.md).

---

## 0. On-call basics

- **Pager:** PagerDuty service `once-backend`. Primary on-call
  rotates weekly; secondary follows by 12 hours.
- **War room:** `#once-incidents` in Slack. Open a thread per
  incident; pin the timestamps.
- **Status page:** statuspage.once.io. Post within 5 minutes of
  paging if customer-visible.
- **Severity scale:**
  - **SEV1** — receipts cannot be signed, OR cross-tenant data leak
    suspected. Page founders immediately.
  - **SEV2** — API down or DB unavailable for >5 min.
  - **SEV3** — single portal submitter broken; degraded UX.

After every SEV1/SEV2 incident, a public postmortem is written
within 5 business days and posted at `docs/postmortems/`.

---

## 1. Deploying

### 1.1 Backend (Fly.io)

Normal path:

```bash
# from repo root
fly deploy --config fly.toml --app once-backend
```

`fly.toml`'s `[deploy] release_command = "alembic upgrade head"` runs
migrations automatically before the new image goes live. If the
migration fails, the deploy aborts and the old image keeps serving.

Rollback:

```bash
fly releases --app once-backend
fly deploy --image registry.fly.io/once-backend:<sha-from-list> --app once-backend
```

### 1.2 Frontend (operator console)

```bash
cd frontend
npm ci && npm run build
# Push to Cloudflare Pages via the connected GitHub branch — autodeploys.
```

### 1.3 Extension (Chrome Web Store)

Drop the artifact from
[`.github/workflows/extension.yml`](../.github/workflows/extension.yml)
into the Web Store dashboard. Promotion to "Public" requires a second
maintainer to approve in the dashboard.

### 1.4 OnceTax (Cloudflare Workers)

```bash
cd oncetax
pnpm install
pnpm wrangler deploy
```

---

## 2. Rotating the receipt signing key

This is the highest-stakes routine operation in the system. Old public
keys MUST remain queryable forever or historical receipts become
unverifiable.

Pre-flight:

- Pick a new `key_id`. Convention: `YYYYMMDD` (e.g., `20250127`).
- Generate the new key offline:
  ```bash
  python - <<'PY'
  from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
  from cryptography.hazmat.primitives import serialization as s
  k = Ed25519PrivateKey.generate()
  print(k.private_bytes(s.Encoding.PEM, s.PrivateFormat.PKCS8, s.NoEncryption()).decode())
  print(k.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw).hex())
  PY
  ```
- Record the public key + `key_id` in the `signing_keys` table:
  ```sql
  INSERT INTO signing_keys (key_id, public_key_raw, created_at, retired_at)
  VALUES ('20250127', decode('<hex>', 'hex'), now(), NULL);
  ```

Cutover:

1. Set the new private key as a Fly secret:
   ```bash
   fly secrets set --app once-backend \
     RECEIPT_SIGNING_PRIVATE_KEY_PEM="$(cat new_key.pem)" \
     RECEIPT_SIGNING_KEY_ID="20250127"
   ```
2. Fly will roll the `worker` and `beat` processes. New receipts will
   carry the new `key_id`.
3. Mark the old key retired (do **not** delete its row):
   ```sql
   UPDATE signing_keys SET retired_at = now() WHERE key_id = '<old>';
   ```
4. Verify a fresh submission produces a verifiable receipt:
   ```bash
   curl https://verify.once.io/verify/<new-receipt-id> | jq .verified
   # → true
   ```
5. Verify an old submission still verifies under the old key:
   ```bash
   curl https://verify.once.io/verify/<old-receipt-id> | jq .verified
   # → true
   ```

If step 4 or 5 returns `false`, abort and roll back the Fly secret to
the previous key. Then open a SEV1.

---

## 3. Running an Alembic migration

```bash
# Author a migration
cd backend
alembic revision --autogenerate -m "add foo column"
# inspect the generated file under alembic/versions/, hand-edit as needed
# (autogenerate is a starting point, not a finished migration)

# Apply locally
alembic upgrade head

# Apply in production — automatic on `fly deploy`
# (release_command in fly.toml). To run manually:
fly ssh console --app once-backend -C "alembic upgrade head"

# Roll back one revision
fly ssh console --app once-backend -C "alembic downgrade -1"
```

Rules:

- **Migrations must be SQLite-portable.** No `JSONB`, no `UUID`, no
  partial indexes. See `CONTRACTS.md` §2.
- **Migrations must be reversible** unless explicitly documented in
  the migration's docstring. CI runs `alembic downgrade base` on a
  freshly-upgraded SQLite to enforce this.
- **No data migrations in the same revision as a schema migration.**
  Split them.

---

## 4. Restoring from backup

Fly Postgres takes a base backup every 24h and ships WAL continuously.
Retention is 35 days.

```bash
# List available restore points
fly postgres backup list --app once-backend-db

# Restore into a new app (NEVER restore into the live app)
fly postgres restore --app once-backend-db \
   --backup-id <backup-id> \
   --new-app-name once-backend-db-restore

# Once verified, attach to a new backend app for cutover
fly postgres attach --app once-backend-restore once-backend-db-restore
```

Quarterly restore drill:

1. Restore yesterday's backup into a sandbox app.
2. Run `pytest backend/tests/test_restore_smoke.py` against the
   restored DB.
3. Check that the most recent receipt verifies through the verifier
   service pointed at the sandbox.
4. Destroy the sandbox app.

A drill that doesn't verify a receipt doesn't count.

---

## 5. On-call response

### 5.1 SEV1 — receipts not signing

Symptom: `/v1/health` returns 200 but `submission_pipeline` logs
`ReceiptSigningError` for every completed submission.

Triage:

1. Check `RECEIPT_SIGNING_PRIVATE_KEY_PEM` is set on the worker:
   ```bash
   fly ssh console --app once-backend -s --process worker \
     -C "python -c 'from app.config import settings; print(bool(settings.receipt_signing_private_key_pem))'"
   ```
2. If false → restore the secret from your password manager. Roll the
   worker process.
3. If true → check the key parses:
   ```bash
   fly ssh console --app once-backend -s --process worker \
     -C "python -c 'from app.services.receipt_signer import _signer; _signer()'"
   ```
4. If the parser raises → key is corrupt. **Do not rotate** under
   pressure; restore the previous secret.
5. Once signing recovers, replay the stuck submissions:
   ```bash
   fly ssh console --app once-backend -s --process worker \
     -C "python -m app.scripts.replay_stuck_submissions --since 1h"
   ```

### 5.2 SEV1 — cross-tenant data suspected

If a customer reports seeing another tenant's data:

1. **Do not** issue a credit or write a status page note until you
   have evidence. Wrong-blame is worse than silence here.
2. Capture: tenant ID, user ID, request ID (from `x-request-id`
   header), exact URL, timestamp.
3. Pull the request from Sentry/Fly logs. Look for `tenant_id` in
   the structured log line.
4. If the served `tenant_id` != the user's JWT `tenant_id` → SEV1
   confirmed. Page founders.
5. Freeze: deploy a kill switch that 503s the affected route:
   ```bash
   fly secrets set --app once-backend KILL_ROUTE_<NAME>=1
   fly deploy --strategy immediate
   ```
6. Begin formal incident response per
   [`COMPLIANCE.md`](./COMPLIANCE.md) §2 (24-hour controller
   notification).

### 5.3 SEV2 — API down

1. Check `fly status --app once-backend`.
2. If machines are crashing on boot — `fly logs` will show the
   stacktrace. Most common: bad env var, failed migration.
3. If DB is unreachable — `fly postgres status --app once-backend-db`.
4. Roll back to last green release (see §1.1).

### 5.4 SEV3 — single portal submitter broken

Submitters are isolated. A broken `amtrust` submitter affects only
amtrust submissions.

1. Set `ENABLE_TOS_RISKY_PLATFORMS=False` if the breakage is on a
   gated platform — submissions to it will route to `BLOCKED` instead
   of `FAILED`.
2. Pause new submissions via the operator console (per-portal toggle).
3. Open a ticket against `backend/app/automation/submitters/`. The
   playwright trace is captured automatically on failure under
   `/var/log/playwright/<submission_id>/`.

---

## 6. Routine ops

| Cadence | Task | Owner |
|---|---|---|
| Daily | Verify nightly audit-log hash job succeeded (Sentry breadcrumb). | On-call |
| Weekly | Review Dependabot PRs. Merge security ones within 7 days. | On-call |
| Weekly (Mon 04:00 UTC) | Celery beat `keys.warn_jwt_secret_age` — Sentry alert if last `jwt_secret_key` `KeyRotationLog` is >90 days. **Response:** rotate JWT secret per §6.1 and log via `POST /cockpit/compliance/key-rotations`. | On-call |
| Weekly (Mon 04:15 UTC) | Celery beat `keys.warn_db_password_age` — Sentry alert if last `db_password` `KeyRotationLog` is >180 days. **Response:** rotate DB password per §6.1 and log it. | On-call |
| Monthly | Smoke-test all portal submitters against fixture sandboxes. | Backend lead |
| Quarterly | Restore drill (§4). | On-call |
| Quarterly | Receipt-signing key health check (sign + verify a canary). | Backend lead |
| Annual (Jan 1, 03:00 UTC) | Celery beat `keys.rotate_signing_key` — auto-rotates the active `SigningKey` and writes a `KeyRotationLog` row. **Response:** verify in Sentry breadcrumb; confirm new `signing_key_id` is live; old key stays in the registry for historical verification. Manual rotation procedure in §2. | Backend lead |

### 6.1 What to do when a rotation-age alert fires

1. Confirm the alert in Sentry (`key_rotation_age_warning`).
2. Mint a new secret out-of-band (e.g. `python -c "import secrets; print(secrets.token_urlsafe(64))"` for JWT; cloud-provider console for DB).
3. Update the secret in Fly (`fly secrets set JWT_SECRET_KEY=...` or `DATABASE_URL=...`) and roll the relevant service.
4. Mint a short-lived founder token (§7.2), then:
   ```bash
   curl -s -X POST https://once.example/cockpit/compliance/key-rotations \
     -H "Authorization: Bearer $(cat /tmp/cockpit.token)" \
     -H 'Content-Type: application/json' \
     -d '{"key_name":"jwt_secret_key","notes":"Quarterly rotation per alert"}'
   ```
5. The next weekly beat run will see the fresh `KeyRotationLog` row and the alert clears automatically.

---

## 7. Quarterly SOC 2 Type I evidence drill

**Symptom:** "Auditor is asking for last quarter's access review + audit
trail + key-rotation log + chain-of-custody hashes for tenant X."

Every quarter (on or before the 5th business day of Jan/Apr/Jul/Oct) the
founder on-call runs the evidence export script for every active tenant
and uploads the resulting bundles to the SOC 2 evidence drive.

### 7.1 Prerequisites

- A **founder** operator account exists in the cockpit (`OperatorRole.FOUNDER`).
  Verify with `python -m scripts.create_operator --email <you> --role founder`
  if you are bootstrapping.
- The nightly `audit.verify_nightly_hash` Celery beat job has been running
  for the full reporting window. Check Sentry breadcrumbs (or query
  `SELECT covers_date, COUNT(*) FROM audit_hash_digests GROUP BY 1
  ORDER BY 1 DESC LIMIT 10`) to confirm a contiguous chain.
- You have write access to the SOC 2 evidence drive
  (`s3://once-soc2-evidence/<quarter>/`).

### 7.2 Mint a short-lived founder token

```bash
curl -s -X POST https://once.example/cockpit/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"email":"founder@once.dev","password":"<your-pw>"}' \
     | jq -r .access_token > /tmp/cockpit.token
```

The token expires in 15 minutes; re-mint as needed.

### 7.3 Run the export for every active tenant

```bash
# from repo root
TENANTS=$(psql "$DATABASE_URL" -At -c \
  "SELECT id FROM tenants WHERE is_active = true ORDER BY slug")

cd backend
for tid in $TENANTS; do
  python -m scripts.soc2_evidence_export \
      --cockpit-url   https://once.example \
      --cockpit-token "$(cat /tmp/cockpit.token)" \
      --tenant-id     "$tid" \
      --start         2026-01-01T00:00:00Z \
      --end           2026-04-01T00:00:00Z \
      --output        "evidence/2026Q1/${tid}.zip"
done
```

Each `.zip` contains:

- `manifest.json` — schema version, generation timestamp, window,
  cockpit URL, and a `sha256` + `bytes` for every artifact.
- `audit_logs.jsonl` — every `AuditLog` row for the tenant in the
  window, one JSON object per line, sorted by `(occurred_at, id)`.
- `access_review.json` — current users + roles + last-login for the
  tenant (point-in-time snapshot).
- `audit_hash_digests.json` — every nightly chain-of-custody digest
  ever recorded for the tenant (paginated transparently).
- `key_rotations.json` — every secret-rotation log entry (global,
  not tenant-scoped).

### 7.4 Upload + ticket

1. Upload every `.zip` to `s3://once-soc2-evidence/<quarter>/`.
2. Open a Jira ticket on the SOC 2 board titled
   `SOC2 evidence — <quarter>` and attach the manifest hashes as a
   table (auditor uses these to byte-match the archive on download).
3. Tag a founder; close out within 2 business days.

### 7.5 If `audit_hash_digests.json` shows gaps or a mismatch

A gap (missing `covers_date`) means the nightly Celery job did not run
that day — investigate the worker logs for `audit_hash_job_started` /
`audit_hash_job_completed` events.

A `tenants_mismatched > 0` Sentry alert from
`audit_hash_job_completed` (status=`alert`) means an `audit_logs` row
was mutated after its digest was stored. **Treat this as a SEV1**:
file an incident, freeze the affected tenant from new writes, and page
founders. The mismatched digest row is preserved unmodified so the
forensic baseline remains intact.

---

## 8. Verifier API key issuance (Verify API monetization)

External buyers (carriers, brokers) call the public verifier
(`verify.once.io`) programmatically to verify receipts at scale. Each
tenant can mint per-buyer API keys from the cockpit. Free-tier keys
are capped at `VERIFIER_FREE_TIER_MONTHLY_CAP` calls/month (default
10,000); uncapped keys are reserved for the paid metered tier (Stripe
wiring is a follow-up; the schema supports it today).

### 8.1 Issue a key (cockpit UI)

1. Sign in as an owner/admin operator and open **Verifier Keys** in
   the sidebar (`/verifier-keys`).
2. Click **Issue key**, give it a buyer-facing name (e.g., "ACME
   Reinsurance — prod"), and set **Monthly call cap**:
   - blank → use the platform default (`10000` for free tier);
   - `0`   → uncapped (paid/metered tier, requires explicit billing
     agreement);
   - any positive integer → hard cap per calendar month.
3. The plaintext key (format `vk_live_…`) is shown **exactly once**.
   Copy it and send it to the buyer over a trusted channel. We only
   store the SHA-256 hash; we cannot recover it later.

### 8.2 Issue a key via API (operator JWT)

```bash
curl -s -X POST https://once.example/v1/admin/verifier-keys \
     -H "Authorization: Bearer $OPERATOR_JWT" \
     -H 'Content-Type: application/json' \
     -d '{"name":"ACME Reinsurance — prod","monthly_call_cap":10000}'
# → 201 {"id":"...","key_prefix":"vk_live_...","plaintext":"vk_live_...","monthly_call_cap":10000,...}
```

The buyer then calls:

```bash
curl -H "X-Verify-API-Key: vk_live_xxxxxxxxxxxx..." \
     https://verify.once.io/verify/<receipt-id>
```

Without a key the request is subject to per-IP burst limits
(`VERIFIER_UNAUTH_RATE_LIMIT`, default `100/day;20/hour;5/minute`).
With a valid key the per-IP limit is skipped and the per-key monthly
counter (`verifier_api_key_usage`) is incremented on the backend; once
`count > monthly_call_cap` the verifier returns `402 {detail: {code:
"quota_exceeded", limit, used, reset_at}}`.

### 8.3 Raise or lower a cap

Caps are immutable on the existing key. To change the cap, revoke
the current key (§8.4) and issue a fresh one with the new cap. This
forces the buyer to confirm the new contract envelope and leaves a
clean `verifier_api_key.revoked` + `verifier_api_key.created` pair in
`AuditLog`.

### 8.4 Revoke a key

In the cockpit, click **Revoke** on the row and confirm. Or:

```bash
curl -s -X DELETE https://once.example/v1/admin/verifier-keys/<key-id> \
     -H "Authorization: Bearer $OPERATOR_JWT"
# → 204
```

Revocation is idempotent (re-issuing DELETE on a revoked key returns
204) and writes a `verifier_api_key.revoked` `AuditLog` row capturing
the operator. The verifier picks up the revocation on the next charge
call (no cache — charge is per-request).

### 8.5 If a buyer reports `402 quota_exceeded`

1. Confirm via `GET /v1/admin/verifier-keys` that the key still exists
   and is not revoked.
2. Inspect the `verifier_api_key_usage` row for the current
   `period_month` to see actual call volume.
3. If the cap raise is contractually approved, revoke and re-issue
   with the new cap (§8.3). The counter resets implicitly on the 1st
   of the next month.

### 8.6 If the verifier returns `503` on every keyed request

The verifier could not reach the backend's `/v1/internal/verifier-keys/charge`
endpoint (network or auth failure). Check:

1. `BACKEND_INTERNAL_TOKEN` on the verifier Fly app matches
   `VERIFIER_INTERNAL_TOKEN` on the backend.
2. The backend is healthy (`/v1/health` 200).
3. Verifier logs for `verifier_api_key_charge_failed` events.

Unauthenticated `/verify/{id}` traffic is unaffected by this failure
mode; only requests carrying `X-Verify-API-Key` 503 when the charge
call cannot complete (we intentionally do **not** fail-open when a key
is present, to preserve metering integrity).


