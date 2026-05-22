# Deploy Runbook — Once (`getonce.com`)

End-to-end runbook for taking the repo from a green CI to a live production
stack on **`getonce.com`** (root marketing) + **`app.getonce.com`** (frontend)
+ **`api.getonce.com`** (backend) + **`verify.getonce.com`** (verifier).

> One-time setup: ~90 minutes. Steady-state: every push to `main` deploys
> automatically.

---

## 0. Provider accounts you must own first

| Provider | Plan | Purpose |
|---|---|---|
| **Fly.io** | Hobby (free) → scale up | `once-backend` (FastAPI + Celery) and `once-verifier` (FastAPI) |
| **Vercel** | Hobby → Pro when you cross 100GB bandwidth | `once-app` (React) and `once-landing` (static) |
| **Cloudflare** | Free | DNS for `getonce.com` + future R2/Workers |
| **GitHub** | org `once-inc` | source, Actions, secrets |
| **Neon** or **Fly Postgres** | free tier OK to start | Postgres for backend |
| **Upstash Redis** or Fly Redis | free | Celery broker |
| **Sentry** | free | error tracking |
| **Slack** (optional) | free | smoke-test alerts |

---

## 1. GitHub Secrets — full required list

Set these at **repo** scope (Settings → Secrets and variables → Actions).
Workflows guard on token presence and skip cleanly if missing, so PRs from
forks stay green.

| Secret name | Used by | Source |
|---|---|---|
| `FLY_API_TOKEN` | `deploy-backend.yml`, `deploy-verifier.yml` | `fly tokens create deploy -x 8760h` (org-scoped) |
| `VERCEL_TOKEN` | `deploy-frontend.yml` | https://vercel.com/account/tokens |
| `VERCEL_ORG_ID` | `deploy-frontend.yml` | `cat frontend/.vercel/project.json` after `vercel link` |
| `VERCEL_PROJECT_ID_APP` | `deploy-frontend.yml` | same `project.json` (the `projectId` field) |
| `VERCEL_PROJECT_ID_LANDING` | (only if you wire landing into Actions; default is Vercel-Git auto-deploy) | run `vercel link` inside `landing/` |
| `SENTRY_DSN_BACKEND` | (optional) backend Fly secret, not GH | `Sentry → backend project` |
| `SENTRY_DSN_FRONTEND` | (optional) Vercel env var, not GH | `Sentry → frontend project` |
| `SLACK_WEBHOOK_SMOKE` | (optional) backend Fly secret, not GH | Slack incoming webhook for portal drift alerts |

> Sentry DSNs and Slack webhooks are **runtime** secrets — set them on Fly
> (backend) and Vercel (frontend) directly. They do not need to be GitHub
> secrets.

---

## 2. Fly.io — create the two apps

```bash
fly auth login
fly orgs create once-inc                     # if not already
fly apps create once-backend --org once-inc
fly apps create once-verifier --org once-inc
```

### 2a. Provision Postgres + Redis

Either Fly-managed (cheapest, region-locked) or external:

```bash
# Postgres
fly postgres create --name once-pg --org once-inc --region iad \
  --initial-cluster-size 1 --vm-size shared-cpu-1x --volume-size 10
fly postgres attach once-pg --app once-backend     # injects DATABASE_URL

# Redis (or use Upstash and paste the URL into secrets)
fly redis create --name once-redis --org once-inc --region iad --no-replicas
fly redis status once-redis                        # copy the URL
```

### 2b. Backend secrets

```bash
fly secrets set --app once-backend \
  APP_ENV="production" \
  SECRET_KEY="$(openssl rand -hex 32)" \
  JWT_SECRET_KEY="$(openssl rand -hex 32)" \
  REDIS_URL="redis://default:PASS@HOST:6379/0" \
  RECEIPT_SIGNING_KEY_ID="prod-2026-01" \
  RECEIPT_SIGNING_PRIVATE_KEY_PEM="$(base64 -w0 ed25519_priv.pem)" \
  BACKEND_CORS_ORIGINS='["https://app.getonce.com","https://getonce.com"]' \
  SENTRY_DSN="https://...@sentry.io/..." \
  SLACK_WEBHOOK_SMOKE="https://hooks.slack.com/services/..."
```

> Generate the Ed25519 keypair once and store the **private** key only in Fly
> secrets. Commit nothing. The public key is served by the backend at
> `/v1/keys/{key_id}`.

### 2c. Verifier secrets

```bash
fly secrets set --app once-verifier \
  ENV="production" \
  BACKEND_BASE_URL="https://api.getonce.com" \
  SIGNING_KEY_ID="prod-2026-01"
```

### 2d. First manual deploy (optional sanity check)

```bash
fly deploy --remote-only --config fly.toml --app once-backend
fly deploy --remote-only --config verifier/fly.toml --app once-verifier
```

The backend `[deploy] release_command` runs `alembic upgrade head`
automatically.

---

## 3. Vercel — two projects

### 3a. App (`once-app`) — the React/Vite frontend

```bash
cd frontend
vercel link            # create new project "once-app", scope to your team
vercel env add VITE_API_BASE_URL production   # → https://api.getonce.com
vercel env add VITE_VERIFY_BASE_URL production # → https://verify.getonce.com
vercel env add VITE_SENTRY_DSN production      # → from Sentry
```

Project settings (Vercel dashboard → `once-app` → Settings → General):

- **Root directory**: `frontend`
- **Framework preset**: Vite (auto-detected from `vercel.json`)
- **Build command**: `npm run build`
- **Output directory**: `dist`
- **Production branch**: `main`
- **Domains**: add `app.getonce.com` (production), keep auto-generated
  `*.vercel.app` for previews.

Copy `orgId` and `projectId` from `frontend/.vercel/project.json` into the
GitHub secrets `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID_APP`. From here on,
`deploy-frontend.yml` owns deploys.

### 3b. Landing (`once-landing`) — static marketing root

```bash
cd landing
vercel link            # create new project "once-landing"
```

Project settings:

- **Root directory**: `landing`
- **Framework preset**: Other
- **Build command**: *(empty)*
- **Output directory**: `.` (or `landing` if the root setting doesn't apply)
- **Install command**: *(empty)*
- **Production branch**: `main`
- **Domains**: add `getonce.com` (apex) and `www.getonce.com`.

Easiest path: **leave landing on Vercel's native Git integration** — every
push to `main` touching `landing/**` auto-deploys. If you'd rather route it
through GitHub Actions, copy `deploy-frontend.yml`, change
`working-directory` to `landing`, and reference
`secrets.VERCEL_PROJECT_ID_LANDING`.

---

## 4. Cloudflare DNS

Zone: `getonce.com`. Records:

| Name        | Type  | Value                          | Proxy     | TTL | Notes |
|-------------|-------|--------------------------------|-----------|-----|-------|
| `@` (apex)  | CNAME | `cname.vercel-dns.com`         | DNS only  | Auto | Landing. CF flattens CNAME at apex. |
| `www`       | CNAME | `cname.vercel-dns.com`         | DNS only  | Auto | Landing alias. |
| `app`       | CNAME | `cname.vercel-dns.com`         | DNS only  | Auto | React app. |
| `api`       | CNAME | `once-backend.fly.dev`         | DNS only  | Auto | Backend. |
| `verify`    | CNAME | `once-verifier.fly.dev`        | DNS only  | Auto | Verifier. |
| `_acme-challenge.*` | TXT | (Vercel/Fly will instruct)   | DNS only  | Auto | Issued automatically. |

> **Keep proxy = DNS only** for everything Vercel and Fly own — both manage
> their own TLS via Let's Encrypt and the orange-cloud proxy breaks cert
> issuance. You can flip it on later only after both providers confirm a
> compatible setup.

Custom domain registration on Fly:

```bash
fly certs add api.getonce.com     --app once-backend
fly certs add verify.getonce.com  --app once-verifier
fly certs show api.getonce.com    --app once-backend     # wait for "Issued"
fly certs show verify.getonce.com --app once-verifier
```

Custom domain registration on Vercel: add via dashboard (Project →
Settings → Domains). Vercel emits the DNS instructions; for both `app` and
the landing apex the CNAME above is what they want.

---

## 5. First-deploy order

Order matters because the frontend won't build cleanly if the backend isn't
reachable for its OpenAPI fetch (if you wire that), and DNS propagation
takes minutes.

1. **Secrets** — set every Fly secret listed in §2b/§2c, every Vercel env
   var listed in §3a, every GitHub secret listed in §1.
2. **Backend** — push to `main` (or run `fly deploy` manually). Wait for
   `release_command` (alembic upgrade) to succeed. Hit
   `https://once-backend.fly.dev/v1/health/live`.
3. **Verifier** — same.
4. **DNS** — add Cloudflare records, then `fly certs add` on both Fly apps.
   Wait until certs report `Issued` (1–10 min).
5. **Frontend (app)** — push to `main`. Vercel build runs via Actions.
   Smoke: `https://app.getonce.com` loads → login round-trips against
   `api.getonce.com`.
6. **Landing** — push to `main`. Vercel auto-deploys. Smoke:
   `https://getonce.com` returns the hero in <500 ms.
7. **End-to-end smoke**: register user → create supplier → trigger
   submission → fetch receipt → hit `verify.getonce.com/verify/{id}` and
   confirm `verified: true`.

---

## 6. Steady-state CI/CD

| Trigger | Workflow | Action |
|---|---|---|
| PR to `main` | `ci.yml` | backend pytest, frontend tsc+lint+build, verifier pytest, extension vitest+build |
| PR to `main`, `frontend/**` changed | `deploy-frontend.yml` | preview deploy on Vercel |
| Push `main`, `backend/**` or `fly.toml` changed | `deploy-backend.yml` | `fly deploy` → `once-backend` |
| Push `main`, `verifier/**` changed | `deploy-verifier.yml` | `fly deploy` → `once-verifier` |
| Push `main`, `frontend/**` changed | `deploy-frontend.yml` | `vercel deploy --prod` → `once-app` |
| Push `main`, `landing/**` changed | Vercel Git integration | static deploy → `once-landing` |
| Push `main`, `extension/**` changed | `extension.yml` | build + upload `.zip` artifact |

---

## 7. Rotating secrets

- **JWT / app secret keys**: `fly secrets set JWT_SECRET_KEY="$(openssl rand -hex 32)"` quarterly. Forces re-login.
- **Receipt signing key**: roll annually. Bump `RECEIPT_SIGNING_KEY_ID` to a new value (e.g. `prod-2027-01`), keep the old public key reachable at `/v1/keys/{old_id}` so historical receipts still verify.
- **Fly token**: `fly tokens create deploy -x 8760h` once a year; update `FLY_API_TOKEN` in GH.
- **Vercel token**: rotate annually; update `VERCEL_TOKEN` in GH.

---

## 8. Rollback

- **Backend / verifier**: `fly releases --app once-backend` → `fly deploy --image registry.fly.io/once-backend:deployment-<sha>` to redeploy a prior image.
- **Frontend**: in Vercel dashboard, find the previous production deployment → "Promote to Production". Zero-downtime.
- **Landing**: same as frontend.
- **Database**: Fly Postgres snapshots daily; `fly postgres backup restore` for catastrophic recovery. For schema-level rollback, write an explicit Alembic downgrade migration and ship it.

---

## 9. Cutover checklist (the day you point `getonce.com` for real)

- [ ] All GitHub secrets in §1 set.
- [ ] `fly apps list` shows `once-backend` and `once-verifier` both `deployed`.
- [ ] `fly secrets list --app once-backend` includes `SECRET_KEY`, `JWT_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `RECEIPT_SIGNING_KEY_ID`, `RECEIPT_SIGNING_PRIVATE_KEY_PEM`.
- [ ] `fly secrets list --app once-verifier` includes `SIGNING_KEY_ID`, `BACKEND_BASE_URL`.
- [ ] Both Vercel projects exist; production domains added (`app.getonce.com`, `getonce.com`, `www.getonce.com`).
- [ ] Cloudflare zone `getonce.com` has the 5 records from §4, all `DNS only`.
- [ ] `fly certs show` reports `Issued` for `api.getonce.com` and `verify.getonce.com`.
- [ ] `https://api.getonce.com/v1/health/live` returns 200.
- [ ] `https://verify.getonce.com/health` returns 200.
- [ ] `https://app.getonce.com` loads the login screen, login succeeds.
- [ ] `https://getonce.com` loads the landing hero.
- [ ] End-to-end: register → submit → receipt verifies at `verify.getonce.com`.
- [ ] Sentry receives a test error from both backend and frontend.
- [ ] Slack receives a test smoke-test alert (if wired).
- [ ] CI is green on `main`.
