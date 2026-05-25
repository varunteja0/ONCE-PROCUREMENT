# Once — Launch Checklist (founder pre-flight)

> Use this like a pilot's pre-flight checklist. Tick boxes in order. Do not skip Phase 0.
> Engineering is **done**. Everything below is sales, legal, and banking — none of which can be agent-automated.

---

## 1. Phase 0 — Legal & Banking (week 1, ~$600 one-time, ~10 hrs)

- [ ] **Stripe Atlas** — file Delaware C-Corp + obtain EIN. https://stripe.com/atlas — $500, 2–3 weeks turnaround.
- [ ] **Form 83(b) election** — file within 30 days of stock issuance (Stripe Atlas walks you through this).
- [ ] **Mercury Bank** — open operating + reserve business accounts. https://mercury.com — $0, ~5 days after EIN.
- [ ] **Buy `getonce.com`** (or fallback `onceidentity.com`). Cloudflare Registrar preferred. ~$12/yr. Lock auto-renew.
- [ ] **Google Workspace** — `varun@onceidentity.com`. https://workspace.google.com — $7/mo.
- [ ] **OpenPhone US business line** — https://openphone.com — $15/mo.
- [ ] **Calendly Pro** — set 30-min discovery slots, EST 9–11am only. `cal.com/varun-once/discovery` — $12/mo.
- [ ] **LinkedIn Sales Navigator (Core)** — $99/mo. Use the 30-day free trial for week 1.
- [ ] **Vercel** — deploy `landing/` to `getonce.com`. `npx vercel --prod`.
- [ ] **Delaware Franchise Tax** — calendar reminder for March 1 (annual).
- [ ] **MSA template review** — read `gtm/04-msa-template.md` once with fresh eyes.

## 2. Phase 1 — First customer (weeks 2–10, ~30 hrs/wk)

- [ ] Wire **25 real ICP MGAs** from `gtm/03-icp-target-list.csv` into Sales Navigator. Criteria: 15–200 headcount, ≥30 carrier appointments, licensed in ≥10 states.
- [ ] Send **30 cold emails/week** using `gtm/02-cold-email-templates.md`. Send between IST 6:30–8:00am (US East 9–10:30pm prior day — top of inbox at 7am EST).
- [ ] Track in Sales Nav: opens, replies, clicks. Target: 3–5 replies per 30 emails.
- [ ] Run **discovery calls** at IST 6:30–9:00pm using script in `gtm/05-discovery-call-script.md`.
- [ ] Send **MSA + order form** within 24 hrs of a "yes" — `gtm/04-msa-template.md`.
- [ ] Wire **$2,500 setup fee** to Mercury → kickoff the following Monday.
- [ ] **Concierge onboard customer #1** over 2 weeks (master profile → 10 portals → 50 portals).
- [ ] Capture a 60-second testimonial video.
- [ ] Repeat 9 more times → 10 paying logos.

## 3. Phase 2 — Conferences (book by JULY or lose the slot)

- [ ] **WSIA Annual Marketplace** — San Diego, late Sept 2026. Registration + booth.
- [ ] **Target Markets Program Admin Summit** — Scottsdale, Oct 2026. Registration.
- [ ] **B1 US visitor visa** — apply at Hyderabad/Chennai consulate. 4–8 wk wait. Book NOW.
- [ ] Pre-conference: schedule **15 in-person meetings** via Sales Nav warm intros for each show.
- [ ] Print **200 one-pagers** from `gtm/01-one-page-pitch.md`.
- [ ] **Demo laptop** loaded with offline fixtures (`fixtures/portals/`) — runs without WiFi.
- [ ] Budget cap: **≤ $30K combined** for both trips (flights + hotel + booth + dinners). Plan: `gtm/08-wsia-2026-meeting-plan.md` + `gtm/09-target-markets-2026-plan.md`.

## 4. Phase 3 — Post-launch tech debt (defer; address only when triggered)

- [ ] Customer-onboarding self-serve flow — when concierge bandwidth tops out (~customer #15).
- [ ] Public status page at `status.getonce.com` — when first paying customer asks.
- [ ] **SOC 2 Type I** via Vanta or Drata (~$15K Year 1) — when first prospect asks for it.
- [ ] Audit log export UX in cockpit — when first auditor requests.
- [ ] Migrate ops alerts email → PagerDuty — when first prod outage at 2am IST.

## 5. Emergency contacts / incident runbook

- **On-call**: Varun · OpenPhone US number · `varun@onceidentity.com`
- **Full runbook**: [docs/RUNBOOK.md](RUNBOOK.md)
- **Secret rotation**: [docs/SECRET_ROTATION.md](SECRET_ROTATION.md)
- **Threat model**: [docs/THREAT_MODEL.md](THREAT_MODEL.md)
- **Backend on-call commands**: [backend/AGENTS.md](../backend/AGENTS.md)
- **Verifier**: [docs/VERIFIER.md](VERIFIER.md)

---

## What is intentionally NOT being done before launch (and why)

| Deferred item                        | Defer until              | Why it's safe to defer                                                                         |
| ------------------------------------ | ------------------------ | ---------------------------------------------------------------------------------------------- |
| JWT → httpOnly cookies migration     | Customer #3              | Current header-bearer is audited; no XSS surface in operator-only cockpit                      |
| HS256 → RS256 JWT                    | Customer #5              | Single-issuer + rotated secret is sufficient for one-tenant-per-token model                    |
| Speculative-service full quarantine  | Customer #2              | Audit confirmed no orphaned services; every service has a worker or API importer               |
| `oncetax/` spin-off into its own org | OnceTax ARR > $50K/mo    | Zero runtime code shared with Wedge A; spin out only when there's revenue to justify the split |
| Performance optimization             | First customer complaint | No customer at scale yet; optimizing without a signal is waste                                 |
| Expanding test surface beyond 1,451  | First prod incident      | The first incident teaches you what's actually under-tested                                    |

---

## Done = customer #1 wires $2,500.

Engineering will not block this. Code is shipped. The bottleneck is **you sending the first 30 cold emails**.

Document version: 1.0 · Owner: Founder · Last updated: 2026-05-25
