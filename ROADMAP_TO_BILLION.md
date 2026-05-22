# ROADMAP_TO_BILLION.md — From "production-grade local repo" → $1B company

> Synthesis as of 2026-05-20, post-L2 hardening. Local-only mode still in
> effect; deploy/sales/raise phases below are blueprints, not actions.
>
> Read order: this doc (the map) → `PLAN.md` (strategy) → `LOCAL-BUILD.md`
> (L2/L3 build details) → `ROADMAP.md` (company-formation execution) →
> `CONTRACTS.md` (code contracts).

---

## Where we are: phase-by-phase status

| # | Phase | Mode | Status | Confidence |
|---|---|---|---|---|
| L1 | Repo skeleton (25-agent v1 build) | local | ✅ done | high |
| **L2** | **Production hardening (10 + 3 agents)** | **local** | **✅ done** | **medium — needs your `pytest` run** |
| L3 | 30-day dogfood (you operate it daily) | local | ⏳ next | — |
| 0 | Foundation: DE C-corp, brand, infra, sales stack | cloud | blocked (your call) | — |
| 1 | Deploy + first 30 cold emails | cloud | blocked | — |
| 2 | 2 paid pilots ($3K MRR) | cloud | blocked | — |
| 3 | 5–7 logos + Vanta + self-serve ($10–15K MRR) | cloud | blocked | — |
| 4 | Real Playwright submitters + cofounder ($20–28K MRR) | cloud | blocked | — |
| 5 | SOC 2 Type I + raise prep ($35–45K MRR) | cloud | blocked | — |
| 6 | Scale: Series A or bootstrap-to-PMF ($80–120K MRR) | cloud | blocked | — |
| 7 | Category leader / $1B path ($1M+ MRR) | cloud | blocked | — |

**Net**: L2 closed today. **9 phases remain.** Local-only constraint = we
can ship L3 next; everything from Phase 0 onward needs you to pull the
trigger on cloud/legal/cash.

---

## The 9 remaining phases — what each one *actually* requires

### L3 — Dogfood (local only, 30 days, your laptop)
**Why**: every product worth $1B was used daily by its founders before
anyone paid. We have 270+ passing tests + a clickable demo, but you have
never actually used it. L3 surfaces the UX paper-cuts no test can find.

**Done when**:
- You run `make up && make seed && make demo` every working day for 30
  days.
- You file ≥10 "fake" submissions per day against the local portal
  fixtures.
- You log every paper-cut in `docs/UX_LOG.md` (I'll scaffold).
- We close ≥80% of papered cuts before Phase 0.
- A 90-second screencast of the happy path exists (you record once,
  reuse forever for cold outreach + cofounder pitch + investor decks).

**Subphases I'd dispatch agents for during L3**:
- L3.1 — Fix every paper-cut you log (rolling 10-agent batches).
- L3.2 — Replace fixture-driven seed with **realistic 3-month
  transcript** (50 suppliers, 800 submissions, 5 carriers, mixed
  outcomes, expiring COIs). Makes the demo *look like a real customer*.
- L3.3 — Build the **founder cockpit**: a separate React route at
  `/cockpit` you'd use to operate the product on a customer's behalf
  in Phase 2 (done-for-you era). Reuses the same backend; different UX.
- L3.4 — **Receipt verifier polish**: branded HTML, share-card
  metadata (OG tags, Twitter cards), QR code variant for printed
  receipts.
- L3.5 — **Pricing page + pricing logic** wired (Stripe Checkout in
  test mode; webhook handlers; tenant billing state machine). Critical
  before Phase 2 wires hit.
- L3.6 — **Onboarding wizard** (your future self-serve, but offline):
  signup → vault unlock → first portal connection → first submission.
  Today the only way in is via seed script.
- L3.7 — **CSV/Excel bulk import** for suppliers (every MGA has them
  in a spreadsheet today; no import = no demo).
- L3.8 — **PDF document parser** (COI/license metadata extraction via
  PyMuPDF + simple regex; defer Vision-LLM to Phase 4). Buys us "we
  read your existing COI PDFs" in the pitch.
- L3.9 — **Email ingestion** (forward `submissions@yourtenant.once.com`
  → backend parses → creates draft submission). Massive pitch unlock.
- L3.10 — **Audit-trail page**: every action ever taken in the system
  for a given supplier, exportable to PDF, signed. Auditor catnip.

**Estimate**: 1 week your time (daily use + UX log) + 2 sessions
my time (dispatching agents to fix what you log).

---

### Phase 0 — Foundation (Week 0–2, ~$2.7K spend)
The first cash phase. **Trigger**: L3 demo screencast you'd be proud to
send a stranger.

**What we do**:
- File **Delaware C-corp via Stripe Atlas** ($500 + $100/yr).
  - Issue 10M founder shares; sign 83(b) and **certified-mail within 30
    days** (missing this is a 5-figure tax mistake).
- Open **Mercury** ($0), **Carta** free tier, **Wise Business** for INR
  wires, **OpenPhone** ($15/mo US number).
- Buy `getonce.com` (or upgrade to `once.io` ~$2K if cash allows).
- Stand up **landing page** on Vercel (single page, Cal.com embed,
  pitch from `docs/PITCH.md`).
- Sales stack: **Sales Nav Core** ($99), **Apollo Basic** ($49),
  **Instantly.ai** ($37), **Hunter** free.
- GitHub org `once-inc` (private) + Sentry free + Plausible ($9) +
  1Password Teams ($8/seat) + Resend (free until 3K emails) +
  Cloudflare (DNS).

**Exit gate**: EIN issued, domain live, repo CI green, landing page
Google-indexable.

**Risk lever**: skip Apollo + Sales Nav if cash-constrained; do
LinkedIn-manual + Hunter free for first 30 prospects.

---

### Phase 1 — Deploy + first 30 cold emails (Week 3–6)
First cloud deploy. Still $0 MRR.

**Deploy**:
- Backend + worker + beat → **Fly.io** (2 machines, ~$15/mo).
- Verifier → Fly (1 machine).
- Frontend → **Vercel** (free tier).
- Postgres → **Fly Postgres** or **Neon** free tier.
- Redis → Fly Redis (~$5/mo) or **Upstash** free.
- Signing key generated locally, pushed via `fly secrets set`.
- Sentry + Plausible wired.
- Smoke test in prod: register → supplier → submission → receipt
  verifies. All 4 pass.
- `BUILD.md` 5 follow-ups closed (3 already done in L2 via B11).

**Outbound**:
- Build **200-prospect ICP CSV** from Target Markets Program
  Administrators directory + WSIA member directory. Filter:
  US, $20–150M GWP, 8–25 carriers, visible "Producer Login" link.
- Warm `founder@getonce.com` via Instantly (5–7 days).
- Send 30 personalized cold emails Weeks 5–6.

**Exit gate**: 30 emails sent, ≥1 discovery call booked, CI green,
prod URLs respond.

---

### Phase 2 — Land 2 paid pilots (Week 7–12) — $3K MRR
**The single most important phase of the company.** Real wires =
proof-of-life.

- ~10 cold emails/day × 6 weeks = ~200 sends → 6–10 discovery calls →
  2 closes (1.5–3% close rate, honest 2026 benchmark).
- Offer: **$2.5K setup + $1.5K/mo**, ≤50 portals, 30-day money-back.
- 2-page MSA via DocuSign. Invoice via Stripe (NOT Connect).
- **Done-for-you ops**: you operate the codebase as their private
  cockpit. Each completed submission → signed receipt → emailed to
  customer. **50–100 receipts by end of phase = the moat**.
- Cofounder hunt starts: 5–8% equity, 4-yr/1-yr cliff, 90-day paid
  trial at $3–5K/mo *before* equity.

**Exit gate**: 2 wires received, $3K MRR, 50+ signed receipts in
production.

---

### Phase 3 — Productize + compliance start (Month 4–6) — $10–15K MRR
- **Self-serve onboarding** live. Move pilot #1 from white-glove to
  self-serve (higher margin); keep pilot #2 white-glove for case study.
- Add 3 portals: **Vertafore AMS360, Sircon, Markel** (already
  mocked in L2, real Playwright now).
- **Vanta Startup** starts Month 3 ($585/mo).
- Auditor engaged: **Prescient Assurance** or **A-LIGN** ($7–10K Type
  I).
- **Cyber insurance** binder Month 4 ($2.5–5K/yr, Coalition or At-Bay).
- Part-time SDR Month 5 once MRR > $8K (LATAM/Philippines, $1.5–2K/mo).
- 1 LinkedIn post/wk + 1 blog/mo + 1 podcast pitch/mo.

**Exit gate**: 5–7 logos, $10–15K MRR, Vanta observation period
started.

---

### Phase 4 — Real submitters + cofounder (Month 7–9) — $20–28K MRR
**The technical moat phase.** Replace 4 mock submitters with battle-
hardened Playwright against real portals.

- Applied Epic (M7) — unlocks IVANS path to ~25 carriers.
- AmTrust producer portal (M7).
- Markel (M8).
- Vertafore AMS360 (M9).
- Sircon (M9).
- Each: ~2 wk dev + 1 wk selector hardening + 1 wk soak test.
- **Portal smoke-test workflow** every 15 min → Slack alert on drift.
- Cofounder trial → equity signed; vesting retroactive to trial start.
- **WSIA Annual** (San Diego, Sep) + **Target Markets Summit**
  (Scottsdale, Oct). 15 pre-booked meetings each.

**Exit gate**: $20–28K MRR, 4 portals fully automated, cofounder signed.

---

### Phase 5 — SOC 2 Type I + raise prep (Month 10–12) — $35–45K MRR
- SOC 2 audit closes; report issued M11. **This unlocks enterprise
  deals** ($5K+/mo).
- Type II observation starts immediately (closes M23).
- **Pre-seed deck** (12 slides). Target $1.5–2.5M @ $10–15M post,
  17–25% dilution.
- Investor list: Brewer Lane, MTech Capital, Eos (InsurTech specialists);
  Hustle Fund, Maple, Bling, Pear, Susa (B2B pre-seed); Plug & Play +
  Lloyd's Lab (strategic).
- 6-week process. Open Mon, close 6 weeks later.
- **Alt path**: skip raise if $35K+ MRR + 18mo runway + one >$8K
  enterprise pilot. Push to Series A at $5–10M ARR at much better
  dilution.

**Exit gate**: SOC 2 Type I report issued; signed term sheet OR
documented 18-mo runway.

---

### Phase 6 — Scale (Month 13–18) — $80–120K MRR
**First time the company can lose to execution risk, not market risk.**

- **Hires (in order)**:
  1. Sr full-stack engineer (M13) — submitter velocity.
  2. AE #1 (M14) — enterprise.
  3. CSM (M16) — onboarding + churn.
- **Portals #6–10**: GuideWire, HawkSoft, EzLynx, NowCerts, CNA.
- **COI auto-renewal monitor** as paid add-on ($300/mo).
- **Verify API** public, free-tier + paid >10K calls/mo.
- **2nd-vertical PoC** with 1 design partner: healthcare GPO suppliers
  (Vizient, Premier) OR DIB commercial subs (NIST 800-171).

**Exit gate**: $80–120K MRR, 3 FTE hired, 2nd vertical PoC live.

---

### Phase 7 — Category leader / billion-dollar path (Month 19+)
This is where the math gets to $1B. Honest path:

**Year 2 (M13–24)**: $1.5M → $5M ARR. Series A: $8–12M at $30–50M post.
**Year 3 (M25–36)**: $10–15M ARR. Series B: $20–35M at $100–200M post.
**Year 4 (M37–48)**: $25–40M ARR. Strategic options open ($200–500M).
**Year 5–7 (M49–84)**: $80–150M ARR @ best-in-class 80% NDR + 100%
logo retention in regulated SaaS = **$1.2–3B comp** (Toast 12× ARR
at IPO; Vertafore acquired for $5.4B on ~$500M ARR; Coupa $8B on
~$700M ARR).

**The 4 levers that get us there**:

1. **OSS the Supplier Identity Protocol** (Q2 2027, M10–12).
   Apache-2.0 receipt schema + reference verifier. Plaid Auth play —
   become the *default* trust primitive carriers + brokers + buyers
   point at. Without this, we're a tool; with it, we're a category.
2. **Buyer-side monetization** (M18+). Today suppliers pay. When
   buyers (carriers, brokers, MGUs) start paying to *verify*
   incoming receipts at scale, ACV jumps 5–10× per logo.
3. **EU GDPR/CSRD wedge** (M30+, Year 3). London office once US ARR
   > $5M. EU AI Act + CSRD = forced AI auditability = our exact
   pitch in a market with no incumbent. Doubles TAM.
4. **Adjacent verticals**: insurance (Year 1–2) → healthcare GPOs
   (Year 2) → DIB subcontractors (Year 3) → manufacturing/Tier-2
   automotive (Year 4) → professional services (Year 5). Same
   technical substrate; different forms + compliance overlays. Each
   vertical doubles TAM at ~10× engineering reuse.

**Exit options at each milestone** (so you can choose, not be forced):
- $5–10M ARR (~M30): strategic acquisition $50–150M (SAP / Coupa /
  Workday / OneTrust). **Default: pass.**
- $25M ARR (~M48): private equity rollup $250–500M. **Default: pass.**
- $80–150M ARR (~M72–84): **IPO** at $1B+ OR private-equity LBO at
  10–14× ARR. **This is the $1B+ outcome.**

---

## What can kill this between today and $1B (and how we mitigate)

| # | Kill risk | Phase it strikes | Mitigation |
|---|---|---|---|
| 1 | **Cofounder ghosts** after 60-day trial | Phase 2 | Hunt starts Day 1 of Phase 0; 70% of trials fail; treat finding cofounder as a 9-month sales cycle |
| 2 | **Selector drift** breaks 2+ portals in 1 week | Phase 4 | 15-min smoke tests + Slack alerts (scaffolded). Carrier-specific selector libraries versioned + rolled forward weekly |
| 3 | **Customer concentration** > 30% any single logo | Phase 3 | Cap intake at 30%; refuse new revenue from top logo above the cap until others catch up |
| 4 | **"India founder"** objection on calls | Phase 2 | US 1-800 (OpenPhone), Cal.com on US hours, cofounder cover for ~M9+ |
| 5 | **SOC 2 timeline slip** past M14 | Phase 5 | Vanta from M3, audit start no later than M10, Type I report a board-level commitment |
| 6 | **Carrier portal TOS strike** (cease-and-desist) | Phase 4 | We never scrape Coupa/Ariba/Jaggaer; carrier portals = our customer's own credentials, used by them with our help (agency law shield); legal opinion from Cooley M10 |
| 7 | **Competitor enters from above** (Vertafore ships AI auto-fill) | Phase 6 | Receipt protocol moat (OSS Q2 2027); buyer-side network effects; vertical depth |
| 8 | **AI commodity pressure** drops underwriting prices to $0 | Phase 7 | We're the audit trail layer, not the underwriting layer — regulatory tailwind (EU AI Act, NAIC bulletin) makes us *more* valuable as AI gets cheaper |
| 9 | **Fundraise market collapses** at Phase 5 | Phase 5 | Default = bootstrap to Series A at $5–10M ARR; raise is opportunistic, never required |
| 10 | **Founder health / India ops fail** | any | Hyderabad CA for transfer pricing M3, US payroll via Deel from cofounder onboarding, 1 day/week deep-work block locked in calendar |

---

## What to do *right now* (this week, in priority order)

1. **You**: run the L2 test suite on your machine (the 4 commands at the
   bottom of my last summary). Confirm the 270+ pass count.
2. **You**: spend 1 hour clicking through `make demo`. Log every
   friction point in a text file. Send to me.
3. **Me**: dispatch L3.1 (paper-cut fixes) + L3.2 (realistic seed) +
   L3.3 (founder cockpit) as a 10-agent parallel batch on your signal.
4. **You**: book 30 days on your calendar for L3 dogfood. Even 30 mins
   a day. Discipline > velocity here.
5. **Me**: scaffold `docs/UX_LOG.md` template + `docs/SCREENCAST_SHOTLIST.md`
   so when L3 finishes you can record the 90-second video in one take.

Phase 0 (cash, legal, deploy) waits until L3 is done. **Don't form the
company before you're proud of the product.**

---

*Document version: 1.0 · 2026-05-20 · Authored by Claude (AI cofounder).
Re-read first Monday of every month and at every phase exit gate.*
