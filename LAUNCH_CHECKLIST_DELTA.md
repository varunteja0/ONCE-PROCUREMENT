# LAUNCH_CHECKLIST_DELTA.md

> Things only **you** can do. The code is green. These are the human / billing /
> ops steps required before production traffic. Do them in order.

## 1. Secrets (must be set BEFORE the first deploy)

### Backend (Fly / wherever FastAPI runs)

- [ ] `COCKPIT_JWT_SECRET_KEY` — 64+ random chars (`openssl rand -hex 32`).
      Distinct from `JWT_SECRET_KEY`. **No default** in production: app refuses to
      boot without it.
- [ ] Confirm `JWT_SECRET_KEY` (tenant) is rotated if it was ever in a dev
      `.env` that leaked.
- [ ] `RECEIPT_SIGNING_PRIVATE_KEY_PEM` already set? If yes, leave it. If no,
      generate Ed25519 PEM and set it. Public key goes to verifier.

### OnceTax (Cloudflare Workers)

- [ ] `WORKER_DATA_KEY` — `openssl rand -base64 32 | tr -d '=' | tr '/+' '_-'`
      then `wrangler secret put WORKER_DATA_KEY --env production` (and staging).
      **BACK THIS KEY UP IN A PASSWORD MANAGER.** Losing it = unrecoverable shop
      data (access tokens encrypted with it).
- [ ] `SHOPIFY_API_SECRET`, `SHOPIFY_API_KEY` already wired from Partner
      dashboard? Re-verify in `wrangler secret list --env production`.

## 2. Database migrations (must run BEFORE first deploy)

### Backend (Postgres)

- [ ] Staging: `cd backend && alembic upgrade head`
- [ ] Production: same, off-hours or with brief read-only window. New table
      this wave: `revoked_refresh_tokens`.
- [ ] Verify: `\d revoked_refresh_tokens` shows `jti, tenant_id, user_id,
revoked_at, expires_at`.

### OnceTax (D1)

- [ ] `wrangler d1 execute oncetax-d1 --env staging --file=app/migrations/0001_encrypt_access_token.sql`
- [ ] Same on `--env production`.
- [ ] **Pre-existing shops will fail to decrypt** after this migration because
      their `access_token` was stored plaintext, not GCM-sealed. Two options:
  1. (Easiest) Force-reinstall on all existing shops (uninstall → reinstall
     OAuth flow re-seals the token). Acceptable if shop count < 20.
  2. Write a one-off seal script: read each row, if token starts with
     `shpat_` plaintext → re-seal with `seal()` and `UPDATE`. Skip if already
     base64-GCM length.

## 3. CI / GitHub

- [ ] **Fix GitHub Actions billing** at
      https://github.com/settings/billing/spending_limit — CI cannot run on PRs
      until this is unblocked.
- [ ] Once CI is green again: batch-review 20+ open Dependabot PRs. Merge
      patch/minor in groups, hold majors until you have time to test.
- [ ] Verify `Verify CI` status check is required on `main` branch
      protection.

## 4. Shopify Partner dashboard (OnceTax)

- [ ] App URL points at your production Workers domain.
- [ ] Allowed redirect URLs include `https://<your-domain>/auth/callback`.
- [ ] Mandatory GDPR webhook endpoints registered:
  - `/webhooks/customers/data_request`
  - `/webhooks/customers/redact`
  - `/webhooks/shop/redact`
- [ ] App listing copy mentions: **"Filing-prep worksheets only — not
      tax-of-record. Review every figure before filing."** (Mirrors in-app
      disclaimer; required to avoid app-review rejection / merchant complaints.)

## 5. Legal / compliance (cannot be code)

- [ ] Stand up a one-page Terms + Privacy at your apex domain. The disclaimer
      shipped in-app helps but does not replace ToS.
- [ ] Decide insurance: E&O policy quote before you take real $ from a real
      customer. ($1–3k/yr typical for solo SaaS, tax-adjacent.)
- [ ] CPA review of the 5-state base-rate logic. One paid hour from any
      state-tax CPA is worth it.

## 6. Final deploy gate

- [ ] All 5 quality suites green locally (✅ verified this session):
  - Backend: 76/76 auth + onboarding + 57 verifier tests pass
  - Frontend: 175/175 vitest pass, lint clean, tsc clean
  - Extension: 84/84 vitest pass
  - OnceTax: 3/3 smoke pass, tsc clean
- [ ] `git status` clean. No `_logs_*`, `_wave*`, `_final_*`, `ptlog*`,
      `*.new` files committed (delete them now if so).
- [ ] Tag the commit: `git tag v0.1.0-pre-launch && git push --tags`.
- [ ] Deploy backend → run smoke against `/healthz` and one authed endpoint.
- [ ] Deploy verifier → POST a known-good receipt, expect 200.
- [ ] Deploy frontend → manually walk signup → onboarding → dashboard.
- [ ] Deploy OnceTax → install on a dev store, run one tax calc, verify the
      `disclaimer` field is in the JSON response.

## 7. The bet itself (the part code can't fix)

Pick **one** wedge. Get **five** discovery calls this week. Sign **one** paid
pilot in 30 days. If you can't, the problem isn't the code — it's the ICP or
the pitch, and you need to fix that before writing another feature.

The code is solid. Go sell.
