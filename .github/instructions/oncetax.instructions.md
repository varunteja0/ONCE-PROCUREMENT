---
applyTo: "oncetax/**/*.{ts,tsx,sql}"
description: "OnceTax (Remix on Cloudflare Workers) — Workers runtime only, Shopify billing only, no auto-file"
---

# OnceTax — required behavior

1. **Workers runtime only.** Do not import Node-only modules: `fs`, `path`,
   `crypto` (Node), `Buffer`, `child_process`, `stream`. Use Web APIs:
   `fetch`, `Request`/`Response`, `crypto.subtle`, `ReadableStream`.
2. **Never read `process.env`.** Read secrets from
   `context.cloudflare.env` (Remix loader/action arg).
3. **Billing is Shopify Subscriptions API only.** No Stripe, Stripe Connect,
   Plaid, or any other PSP. No payment forms.
4. **No auto-filing of taxes** with any government endpoint in v0. OnceTax
   produces filing-prep PDFs only.
5. **D1 queries must be parameterized** (`?1`, `?2` placeholders). String
   concatenation of user input into SQL is a security incident.
6. **Schema changes:** update `app/schema.sql` AND add a numbered migration
   under `app/migrations/`. Apply with
   `wrangler d1 migrations apply <db> --remote`.
7. **Tax math** lives in `app/lib/tax_calc.ts` and is **pure** — no I/O, no
   `Date.now()` unless injected for testability. Rate tables are versioned
   constants. 100% unit-test coverage on this file.
8. **PDF generation** goes through `app/lib/pdf.ts`. Embed fonts at build
   time, not at request time.
9. **Multi-tenant scope:** every D1 read/write filters by the Shopify shop
   domain stored on the session. There is no admin escape hatch.
10. **TypeScript strict.** `tsc --noEmit` clean. `npm test` (Vitest) green.

## Running locally

```powershell
cd oncetax
npm run dev
npm test
npm run typecheck
```

## Never do

- Add a Node-runtime dependency or `process.env` read.
- Add Stripe / Plaid / any non-Shopify payment path.
- Auto-submit returns to IRS / state e-file systems.
- Concatenate user input into SQL.
- Bundle large binaries or fetch fonts at request time.
