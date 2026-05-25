# Once — Landing site (`getonce.com`)

Static one-pager that lives at the root of `getonce.com`. The app (React/Vite)
lives at `app.getonce.com` and the verifier at `verify.getonce.com` — this
folder is intentionally static HTML so the marketing root deploys in ~2 seconds
and never blocks on the app build.

## Stack

- Static HTML pages: landing page plus lightweight trust/legal pages.
- Tailwind via the `cdn.tailwindcss.com` script (no build step).
- Inter from Google Fonts.
- Calendly inline embed (`varun-once/discovery`) — provision the slug at
  https://calendly.com before first launch, or the iframe will show "page
  not found".

## Trust pages

- `/security` — security overview and buyer review packet.
- `/privacy` — plain-English pilot privacy policy.
- `/terms` — pilot terms summary.
- `/dpa` — data processing addendum summary and subprocessors.

These pages are intentionally conservative. Do not claim SOC 2, GLBA, HIPAA,
legal admissibility, or production carrier coverage unless the artifact exists
and the implementation is verified.

## Local preview

Any static server works:

```bash
cd landing
python -m http.server 8000
# open http://localhost:8000
```

## Deploy (Vercel) — fastest path

```bash
cd landing
npx vercel login                # one-time
npx vercel --prod               # creates project on first run, then deploys
```

That's it. Subsequent pushes to `main` deploy automatically via Vercel's
native Git integration (no GitHub Actions needed for the static site).

### 1. Point the apex + `www` at Vercel (one-time, after first deploy)

In Cloudflare DNS, add:

| Name          | Type  | Value                  | Proxy    |
| ------------- | ----- | ---------------------- | -------- |
| `getonce.com` | CNAME | `cname.vercel-dns.com` | DNS-only |
| `www`         | CNAME | `cname.vercel-dns.com` | DNS-only |

Cloudflare supports CNAME flattening at the apex; otherwise use Vercel's A
record `76.76.21.21`.

Then attach the domain in Vercel:

```bash
npx vercel domains add getonce.com
npx vercel domains add www.getonce.com
npx vercel alias getonce.com
```

### 2. Project settings (set once in the Vercel dashboard)

- **Root directory**: `landing`
- **Framework preset**: Other
- **Build command**: (leave blank)
- **Output directory**: `.` (root)
- **Install command**: (leave blank)
- **Production branch**: `main`

### CI/CD note

The repo-level GitHub workflow `deploy-frontend.yml` only handles the **app**
project. The landing site uses Vercel's native Git integration — push to
`main` with changes under `landing/**` and it auto-deploys.

If you'd rather drive it from GitHub Actions, mirror `deploy-frontend.yml`
with `working-directory: landing` and a separate `VERCEL_PROJECT_ID_LANDING`
secret.
