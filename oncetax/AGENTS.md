# oncetax/ — Agent rules (Wedge B)

> Authoritative rules: [CONTRACTS.md](../CONTRACTS.md) §11, §12 (row 24).
> This is a **separate product** from the main supplier-portal autopilot —
> Remix-on-Workers Shopify app for tax filing prep.

## Stack snapshot

- **Remix on Cloudflare Workers** (no Node runtime!)
- D1 SQLite · R2 object storage · KV sessions
- Shopify Subscription Billing API (**NO Stripe Connect**)
- `pdf-lib` in the Worker for filing-prep PDFs
- Resend for transactional email · Plausible analytics · Sentry
- Wrangler 3 · TypeScript strict · Tailwind

## Layout

```
app/
  root.tsx, entry.server.tsx, entry.client.tsx
  routes/
    _index.tsx                 # landing
    oauth.callback.tsx         # Shopify OAuth
    billing.tsx                # subscription mgmt
    dashboard.tsx              # tenant dashboard
    api.calc.tsx               # tax calc endpoint
  lib/
    shopify.ts                 # OAuth + Admin GraphQL
    tax_calc.ts                # pure functions, fully unit-tested
    pdf.ts                     # pdf-lib helpers
    d1.ts                      # query helpers (parameterized!)
    sessions.ts                # KV-backed session store
  schema.sql                   # D1 schema — keep canonical
```

## Hard rules (oncetax)

1. **Workers runtime only.** No Node APIs (`fs`, `path`, `crypto.randomBytes`,
   Buffer). Use Web Crypto, `Request`/`Response`, `fetch`.
2. **No auto-filing in v0.** OnceTax generates filing-prep PDFs; users file
   manually. Do not add IRS/state e-file integrations without explicit ask.
3. **Billing = Shopify Subscriptions only.** Never call Stripe, Stripe
   Connect, or any other PSP from this app.
4. **D1 queries are always parameterized** (`?1`, `?2`). String concatenation
   in SQL = security incident.
5. **Schema changes** go in `app/schema.sql` AND a numbered migration file
   under `app/migrations/` (create the folder on first migration). Apply with
   `wrangler d1 migrations apply <db> --remote`.
6. **Secrets** live in `.dev.vars` (local) and Wrangler secrets (deployed).
   Read via `context.cloudflare.env`. Never via `process.env`.
7. **Tax math** in `lib/tax_calc.ts` is **pure** and exhaustively unit-tested.
   No I/O, no Date.now() unless injected. Rates are versioned constants.
8. **PDF generation** goes through `lib/pdf.ts`. Embedded fonts are
   pre-bundled; do not fetch fonts at runtime.
9. **Multi-tenant:** every query scopes to the Shopify shop domain from the
   session. No cross-shop reads.
10. **TypeScript strict**, `tsc --noEmit` clean, `npm test` (Vitest) green.

## Running locally

```powershell
cd oncetax
npm install
# one-time
cp .dev.vars.example .dev.vars   # then edit secrets
wrangler d1 create oncetax-dev   # update wrangler.toml with the id
wrangler d1 execute oncetax-dev --local --file app/schema.sql
# dev
npm run dev                       # remix + wrangler
npm test                          # vitest
npm run typecheck
# deploy
wrangler deploy
```

## Never do

- Call Node-only APIs or `process.env`.
- Add Stripe / Plaid / any non-Shopify billing path.
- Concatenate user input into SQL.
- Auto-file taxes with any government endpoint.
- Read another shop's data via session manipulation.
- Bundle fonts or large binaries at request time — bundle at build time.
