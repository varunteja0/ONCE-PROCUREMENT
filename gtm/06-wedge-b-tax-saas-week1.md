# Wedge B — Shopify Tax SaaS — Week 1 Plan

> **Time budget: 20 hrs/wk (evenings + Sunday).** This wedge runs in parallel with Wedge A (Procurement). Day-30 win condition: ≥3 paying Shopify merchants OR ≥50 trial signups OR (fallback if App Store review slips) app submitted + landing live + 1 paid waitlist deposit.
> Brand placeholder: **OnceTax** (or `[BRAND]Tax`). Domain target: `oncetax.com` (verify availability before purchase).
> Repo: lives at `oncetax/` inside this monorepo per CONTRACTS.md §12. Stack stays separate (Remix on Cloudflare Workers), no Python.

---

## Why this wedge (in 30 seconds)

US Shopify merchants doing >$50K/yr in revenue legally must collect + remit sales tax in every state where they have "nexus" (physical presence OR economic threshold like $100K sales / 200 transactions in 12 months). After the Wayfair decision (2018), economic nexus is enforced in 45 states + DC.

A small Shopify merchant typically owes sales tax in 5–15 states. Filing each state monthly = ~30 min per state per month. **TaxJar (acquired by Stripe, $179/mo for AutoFile) and Avalara ($99/mo + $30/state) dominate but are bloated, slow, and expensive for under-$1M merchants.**

Our angle: **$79/mo + $19/state**, undercut both, frictionless Shopify App Store install, transparent pricing, instant onboarding. Phase 0: calculation + filing-prep PDF only (no auto-file). Phase 1 (post $5K MRR): auto-file to state portals using our Playwright stack.

---

## Tech stack (decided — do not bikeshed)

- **Framework:** Remix (Shopify's official app framework — Shopify-app-template-remix from GitHub)
- **Hosting:** Cloudflare Workers + D1 (free tier covers first 100K requests/day; D1 SQLite covers first 5GB)
- **Billing:** Shopify Subscription Billing API (handles Stripe under the hood; no separate Stripe Connect needed)
- **Auth:** Shopify OAuth via the @shopify/shopify-app-remix package
- **Tax engine:** TaxJar API free tier ($0 for first 1,000 calc calls/mo — use as backstop) + our own state-rate table for CA/TX/WA in Phase 0
- **Email:** Resend free tier (3K emails/mo)
- **Analytics:** Plausible self-hosted on Workers OR Cloudflare Web Analytics (both free)

**No backend Python required for Wedge B.** This is a pure TS/Remix/Workers app. Zero overlap with `backend/` at the code level (only the *concept* of submission_pipeline + audit_service translates conceptually, not as imports).

---

## Day-by-day (Week 1)

### Day 1 (Sunday evening, ~3 hrs)

- [ ] Verify domain available: `oncetax.com` → if taken, fall back to `salestax.run` / `taxonce.app` / `niwa.tax`. **Reserve immediately on Namecheap (~$12/yr).**
- [ ] Create [Shopify Partner account](https://partners.shopify.com) (free; needs an email different from your existing Shopify shopper account if any)
- [ ] Create [Cloudflare account](https://cloudflare.com) (free tier)
- [ ] Reserve GitHub repo `varunteja0/oncetax-shopify-app` (private, single contributor for now)
- [ ] Read Shopify's "Build an app" quickstart (1 hr): https://shopify.dev/docs/apps/getting-started

### Day 2 (Monday evening, ~3 hrs)

- [ ] `npx @shopify/create-app@latest oncetax` → scaffolds the Remix template
- [ ] Push initial commit to `varunteja0/oncetax-shopify-app`
- [ ] Wire Cloudflare Workers deploy (Shopify's template is Node by default; the Workers adapter is ~30 lines — follow Cloudflare's "Remix on Workers" doc)
- [ ] Deploy "hello world" to a Workers subdomain (e.g., `oncetax-staging.varunteja.workers.dev`)
- [ ] Install the dev-tunnel locally; install your scaffold to a test Shopify dev store

### Day 3 (Tuesday evening, ~3 hrs)

- [ ] Build the **OAuth install flow** end-to-end (the Shopify template covers most of this — just verify it works in your Workers deploy)
- [ ] Wire Shopify Subscription Billing API — create one pricing plan: **$79/mo, 14-day free trial**
- [ ] Add a single page: "Connect your store" → after install, show: store name, plan status, and a stub "Configure nexus states" form

### Day 4 (Wednesday evening, ~3 hrs)

- [ ] **Static state-rate table** for CA, TX, WA (hardcoded JSON in `app/data/state-rates.json` — accurate enough for v0; refresh quarterly). Schema: `{ state, base_rate, max_local_rate, sourcing_rule: "destination"|"origin", filing_frequency_thresholds: {...} }`
- [ ] Build the **calculation endpoint**: pulls last 30 days of orders from Shopify Admin API (`orders.json`), groups by shipping-address state, calculates owed tax per state per nexus rule. Outputs a JSON summary.
- [ ] Build the **dashboard view**: table showing "State | Period | Taxable Sales | Tax Owed | Filing Due Date | Status".

### Day 5 (Thursday evening, ~3 hrs)

- [ ] Build the **filing-prep PDF generator**. Use [pdf-lib](https://pdf-lib.js.org/) (works in Workers, no Node deps). Template: standard state sales-tax return form layout, prefilled with calculated values. **Critical: PDF marked clearly "DRAFT — for your CPA / for self-filing on state portal — Once does NOT auto-file in v0."**
- [ ] Wire Resend for transactional emails: "Your CA Q2 filing prep is ready, download here"
- [ ] Add Plausible / Cloudflare Analytics for traffic tracking

### Day 6 (Friday — keep Friday evening free for Wedge A end-of-week review, OR push Wedge B 2 hrs)

- [ ] Build the **landing page** at `oncetax.com` (single HTML page on Cloudflare Pages — free). Sections: hero ("Sales tax filings prep for Shopify, $79/mo flat"), 3-step "How it works", pricing table comparing to TaxJar/Avalara, FAQ, "Install from Shopify App Store" CTA (links to App Store listing once approved).
- [ ] Set up `hello@oncetax.com` via Resend or Cloudflare Email Routing (free, forwards to your personal Gmail)

### Day 7 (Saturday morning, ~3 hrs — the big push)

- [ ] **Submit to Shopify App Store.** Required: app icon (1024×1024 — make one in Figma free in 30 min), 5 screenshots (use a dev store with seeded orders), listing copy (350 words), pricing details, privacy policy (use [iubenda](https://iubenda.com) free tier or [getterms.io](https://getterms.io) free generator), GDPR webhooks (the Shopify template scaffolds these — just verify).
- [ ] Submit. Review takes 5–7 business days typically.

### Day 7 evening / Sunday (rest or buffer)

- [ ] Buffer for whatever slipped. If everything shipped: write a draft ProductHunt launch description and a draft r/shopify "Show HN"-style post for Week 4 launch.

---

## Critical legal guardrails (DO NOT skip)

1. **Tax-calculation accuracy disclaimer.** Landing page + every PDF + every email footer: *"OnceTax provides calculation assistance and filing preparation. OnceTax is not a CPA, attorney, or licensed tax preparer. Final filing responsibility rests with the merchant. Verify all calculations with a qualified professional before filing."*
2. **No auto-filing in v0.** Auto-filing without redundancy = merchant lawsuit when CA FTB rejects a return. Auto-filing capability comes in Phase 1 (post-$5K MRR + ToS amendments + CA FTB account verification).
3. **Privacy policy** must cover Shopify's GDPR webhook obligations (`customers/data_request`, `customers/redact`, `shop/redact`). Template Shopify provides handles this.
4. **No "guaranteed tax savings" or "100% accurate" claims** — these are FTC-actionable.
5. **State-specific notes:** never service TX merchants with "physical nexus in TX" without TX SOS registration (we ourselves are not registered in TX; for v0 our calculation is informational only).

---

## Day-30 win condition (revisited)

| Outcome | What happens |
|---|---|
| App live by Day 21, 50+ installs, 3+ paid conversions | **Wedge B WINS the race.** Wedge A drops to maintenance, Tax SaaS becomes main bet. Execute report 10's full plan (add NY+FL+WA→all 50 states over months 2-4). |
| App live by Day 28, <50 installs, 0 paid | Wedge B fails. Drops to 1 day/wk maintenance; ride passive App Store discovery for 60 days. |
| App NOT live by Day 28 (Shopify review still pending or rejected) | **Fallback win:** landing page live + ≥1 paid waitlist deposit ($79 prepay via Shopify checkout link on landing page) = "signal-stage win." Wedge B continues at 20 hr/wk into Week 5. |
| Both wedges win | Best case. Procurement (Wedge A) = main bet; Tax SaaS (Wedge B) = cash-flow engine for SOC 2 + co-founder runway. |
