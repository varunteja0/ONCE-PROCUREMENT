# OnceTax — Sales tax filing prep for Shopify (Wedge B)

> **Status:** Phase 1 — parallel-run, 30 days.
> The primary Once product is OnceProc (supplier-portal autopilot). OnceTax is
> a separate Shopify app on a different stack (Cloudflare Workers + D1 +
> Remix). It is intentionally minimal in v0: **state-level sales-tax
> filing-prep PDFs only, no auto-filing to state portals.**

## Stack

- Cloudflare Workers (runtime: V8 isolates, `nodejs_compat` flag)
- D1 (SQLite) for shops, order cache, filings
- R2 for generated filing-prep PDFs (gated by `ENABLE_PDF_GENERATION`)
- KV for Shopify session storage
- Remix on Vite (`@remix-run/cloudflare` adapter) for the merchant UI
- TypeScript strict, Tailwind, Zod, `pdf-lib`

## Layout

```
oncetax/
  worker.ts             Cloudflare Worker entry (serves /health, delegates rest to Remix)
  wrangler.toml         Cloudflare bindings: DB, PDF_BUCKET, SESSIONS
  vite.config.ts        Remix Cloudflare build
  vitest.config.ts      Node-runtime smoke test config
  smoke.test.ts         /health smoke test
  app/
    root.tsx, entry.{server,client}.tsx
    tailwind.css
    routes/             _index, oauth.callback, billing, dashboard, api.calc
    lib/                shopify, d1, sessions, tax_calc, pdf
    schema.sql          D1 schema (idempotent CREATE TABLE IF NOT EXISTS)
  .dev.vars.example     Local secrets template
```

## Install

```bash
cd oncetax
npm install
cp .dev.vars.example .dev.vars        # fill in real Shopify keys
```

Create Cloudflare resources once, then update `wrangler.toml` with the IDs:

```bash
npx wrangler d1 create oncetax
npx wrangler kv namespace create SESSIONS
npx wrangler r2 bucket create oncetax-pdfs
```

## Develop

```bash
npm run dev           # wrangler dev — Worker + Remix on http://localhost:8788
npm run test          # vitest run — smoke test
npm run typecheck     # tsc --noEmit
```

The `/health` endpoint is served directly by `worker.ts` (no Remix dependency),
so it works the moment the Worker starts.

## D1 schema / migrations

The schema lives at `app/schema.sql` and is idempotent (every statement uses
`IF NOT EXISTS`). Apply it:

```bash
# Local D1 (miniflare)
npm run db:migrate:local

# Remote D1 (deployed)
npm run db:migrate:remote
```

Tables: `shops`, `orders_cache`, `filings`.

## Deploy

```bash
npm run deploy        # vite build → wrangler deploy
```

Set production secrets:

```bash
npx wrangler secret put SHOPIFY_API_KEY
npx wrangler secret put SHOPIFY_API_SECRET
npx wrangler secret put SESSION_SECRET
npx wrangler secret put RESEND_API_KEY
# Optional:
npx wrangler secret put TAXJAR_API_KEY
```

## Wedge B status — parallel-run, 30 days

OnceTax is a side-bet, not the main product. Phase 1 goal is narrow:

1. Code compiles (`npm run typecheck`, `npm run build`).
2. Smoke test passes (`npm run test` — `/health` returns 200).
3. The Worker deploys (`wrangler deploy`) and accepts an OAuth install handshake
   from a development Shopify store (`/oauth/callback`).

Anything beyond that — district-level rates, auto-filing, multi-currency,
non-US support — is **out of scope** until OnceProc Phase 2 ships. See the
Wedge B TODO at the bottom of `ROADMAP.md` (or this repo's planning notes).

## Constraints

- Cloudflare Workers runtime only — no Node `fs`, no `child_process`, no
  native modules. Use `crypto.subtle`, `fetch`, Web Streams.
- PDF generation is behind the `ENABLE_PDF_GENERATION` flag (default `"false"`
  in `wrangler.toml`); PDFs are written to R2 — never the filesystem.
- D1 = SQLite — no Postgres-only types (`UUID`, `JSONB`, partial indexes).
