# Once â€” Landing site (`getonce.com`)

Static one-pager that lives at the root of `getonce.com`. The app (React/Vite)
lives at `app.getonce.com` and the verifier at `verify.getonce.com` â€” this
folder is intentionally just `index.html` + `vercel.json` so the marketing
root deploys in ~2 seconds and never blocks on the app build.

## Stack
- Single HTML file.
- Tailwind via the `cdn.tailwindcss.com` script (no build step).
- Inter from Google Fonts.
- Cal.com embed placeholder (`data-cal-link="once/demo"`) â€” wire up once the
  Cal.com booking page exists.

## Local preview
Any static server works:

```bash
cd landing
python -m http.server 8000
# open http://localhost:8000
```

## Deploy (Vercel)

This is a **separate Vercel project** from `frontend/` so the marketing
homepage and the app deploy independently.

### One-time setup

```bash
cd landing
vercel link               # create a new project, e.g. "once-landing"
vercel domains add getonce.com
vercel domains add www.getonce.com
vercel alias getonce.com
```

Then in the Vercel dashboard for the `once-landing` project:

- **Root directory**: `landing`
- **Framework preset**: Other
- **Build command**: (leave blank)
- **Output directory**: `.` (root)
- **Install command**: (leave blank)
- **Production branch**: `main`

### CI/CD

The repo-level GitHub workflow `deploy-frontend.yml` only handles the **app**
project. The landing project deploys via Vercel's native Git integration
(push to `main` with changes in `landing/**` â†’ auto-deploy).

If you'd rather drive it from GitHub Actions, mirror `deploy-frontend.yml`
with `working-directory: landing` and a separate `VERCEL_PROJECT_ID_LANDING`
secret.

## DNS

In Cloudflare, point the apex and `www` at Vercel:

| Name           | Type  | Value                  | Proxy   |
| -------------- | ----- | ---------------------- | ------- |
| `getonce.com`  | CNAME | `cname.vercel-dns.com` | DNS-only |
| `www`          | CNAME | `cname.vercel-dns.com` | DNS-only |

Cloudflare supports CNAME flattening at the apex; otherwise use Vercel's A
records (76.76.21.21).