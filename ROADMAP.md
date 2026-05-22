# ROADMAP.md — From Code Repo → Real Company

> **Operational companion to `PLAN.md`** (which holds the year-1 strategic
> plan from the 10-subagent deep dive). This doc is **what we do, in what
> order, to turn 115 files into a Delaware C-corp generating real ARR.**
> Read PLAN.md first for strategy. Read this for execution sequencing.
>
> Companion files: `BUILD.md` (verify commands), `CONTRACTS.md` (code
> contracts), `gtm-procurement/README.md` (Week-1 outbound checklist).

---

## 0. North-star outcome

**Day 365**: $40K MRR · 18–25 paying logos · Delaware C-corp · SOC 2 Type I
done · US cofounder signed · either pre-seed closed @ $10–15M or
bootstrapped to PMF.

**Probability-weighted EV ~$60–120M with a fat right tail to $1B+** (per
the 10-subagent synthesis in PLAN.md).

## 1. The 7 phases (overview)

| #   | Phase                                            | Calendar | Cash gate at exit | Headline KPI                                     |
| --- | ------------------------------------------------ | -------- | ----------------- | ------------------------------------------------ |
| 0   | **Foundation** — entity, brand, infra            | Wk 0–2   | $-2.7K spent      | DE C-corp filed, domains owned, repo green       |
| 1   | **Code production-ready + first 30 cold emails** | Wk 3–6   | $0 MRR            | CI green; 30 prospects emailed                   |
| 2   | **Services-first: land 2 paid pilots**           | Wk 7–12  | $3K MRR           | 2 wires received; private cockpit running        |
| 3   | **Productize → 5–7 logos**                       | M4–6     | $10–15K MRR       | Self-serve UI live; Vanta started                |
| 4   | **Real Playwright submitters + cofounder**       | M7–9     | $20–28K MRR       | 4 portals automated; cofounder LOI signed        |
| 5   | **SOC 2 Type I + raise prep**                    | M10–12   | $35–45K MRR       | SOC 2 audit complete; term sheet OR 18-mo runway |
| 6   | **Scale: Series A or bootstrap-to-PMF**          | M13–18   | $80–120K MRR      | 3 hires; 2nd vertical scoped                     |
| 7   | **Category leader**                              | M19+     | —                 | Receipt protocol OSS'd; network effects live     |

---

## Phase 0 — Foundation (Week 0–2)

**Goal**: be a real legal entity with a real name, real infra, and a green
CI pipeline. **No customer work yet.**

### 0.1 Legal & finance

- File **DE C-corp via Stripe Atlas** ($500 + $100/yr franchise). Standard
  10M-share split. Issue founder stock immediately — **84(b) election
  within 30 days, non-negotiable** (else you owe US tax on vested value as
  income).
- Open **Mercury** business banking ($0/mo).
- **Carta free tier** for cap table.
- **Wise Business** or Atlas invoicing for receiving first US wires.
- **OpenPhone** ($15/mo) — kills the "India solo" objection on calls.
- **Cal.com** booking page on US hours (8am–5pm ET = 5:30pm–2:30am IST).

### 0.2 Brand & domains

- Lock name **Once** (placeholder — confirm in decisions below).
- Buy `once.io` (~$2K/yr) **or** fallback `getonce.com` (~$12/yr).
- Logo: Fiverr Pro or self-design in Figma (1 day, indigo brand palette
  already in `frontend/tailwind.config.js`).
- Single-page landing (Framer or Next.js on Vercel) — pitch from
  `docs/PITCH.md` + Cal.com embed.

### 0.3 Infra & ops

- **GitHub org `once-inc`** (private repos), push current code, enable CI.
- **Sentry** free tier (errors), **Plausible** ($9/mo, analytics).
- **1Password Teams** ($8/seat) for secrets.
- **Resend** ($0 until 3K emails/mo) for transactional.
- **Cloudflare** (DNS + R2 for OnceTax PDFs).
- **Fly.io** account (backend + verifier hosting).

### 0.4 Sales stack

- **LinkedIn Sales Navigator Core** ($99/mo, free trial available).
- **Apollo.io Basic** ($49/mo) for email finding + cold sequences.
- **Instantly.ai** ($37/mo) for cold-email warmup + sending.
- **Hunter.io** free tier for verification.

### 0.5 Decisions to lock this week

- [ ] Final brand: **Once** vs alt (Verite / Pactly / Onceledger)
- [ ] Domain: `once.io` ($2K) vs `getonce.com` ($12) vs other
- [ ] OK burning **~$2.7K Month 1** on credit card (Atlas + domain +
      sales stack)?
- [ ] Cofounder hunt: start Day 1 or Day 60?

**Exit gate**: DE C-corp EIN issued · domains live · repo CI green ·
landing page Google-indexable. **Week 2.**

---

## Phase 1 — Code production-ready + first 30 cold emails (Week 3–6)

**Goal**: real CI passes, first cold outbound starts. Still $0 MRR.

### 1.1 Code → production-ready

| Task                                                            | Done when                                     |
| --------------------------------------------------------------- | --------------------------------------------- |
| `pytest -q` green vs in-memory SQLite                           | `.github/workflows/ci.yml` green              |
| `tsc --noEmit` + `eslint --max-warnings 0` clean (frontend)     | CI green                                      |
| `vitest run` green (extension)                                  | CI green                                      |
| Fix the 5 follow-ups in `BUILD.md`                              | All checked off                               |
| Deploy backend to **Fly.io**                                    | `https://api.once.io/docs` responds           |
| Deploy verifier to Fly                                          | `https://verify.once.io/verify/{id}` responds |
| Deploy frontend to **Vercel**                                   | `app.once.io` loads, login works              |
| Generate Ed25519 signing key into Fly secrets                   | `fly secrets list` shows key                  |
| Postgres on **Fly Postgres** or **Neon** free tier              | `alembic upgrade head` succeeds in prod       |
| Sentry wired (backend + frontend)                               | Test error reaches Sentry                     |
| Smoke test: register → supplier → submission → receipt verifies | All 4 pass via Postman                        |

### 1.2 ICP target list (200 prospects)

- Source: **Target Markets Program Administrators** directory (~400 firms)
  - WSIA member directory (~700 surplus-lines wholesalers).
- Filter: US-based, $20–150M GWP, 8–25 carrier partners, "Producer Login"
  link visible on website (= proxy for portal pain).
- Drop into `gtm-procurement/03-icp-target-list.csv` (scaffolded). 200 rows
  × (company, contact, title, LinkedIn, email, phone, GWP, # portals,
  source).

### 1.3 Outbound machine warmed up

- 5–7 day Instantly warmup on `founder@once.io`.
- Cold email V1 (drafted in `gtm-procurement/02-cold-email-templates.md`).
- A/B subject lines on first 30 sends.
- 30 personalized first-touches sent Wk 5–6. 2 LinkedIn follow-ups each.

### 1.4 Discovery call ready

- Script in `gtm-procurement/05-discovery-call-script.md`.
- Loom recording: extension filling a fake AmTrust portal (60 sec).
- PDF of `01-one-page-pitch.md`.

**Exit gate**: 30 cold emails sent · ≥1 discovery call booked · CI fully
green · prod deployed. **Week 6.**

---

## Phase 2 — Services-first: land 2 paid pilots (Week 7–12)

**Goal**: 2 paying logos at $1.5K/mo each = **$3K MRR**, $5K wired upfront
(setup fees). Cash break-even in sight.

### 2.1 Sales motion

- ~10 cold emails/day → ~200 sends over the phase → realistic 6–10
  discovery calls → 2 closes (1.5–3% close rate is the honest 2026
  benchmark).
- Offer: **$2.5K setup + $1.5K/mo, ≤50 portals managed, 30-day money-back**.
- Contract: 2-page MSA (already in `gtm-procurement/04-msa-template.md`)
  via DocuSign.
- Invoice via **Stripe** (NOT Stripe Connect). USD wire or ACH.

### 2.2 Done-for-you operations

For pilots #1 & #2: **YOU operate the codebase as a private cockpit**.
Login as the supplier, run extension on their machine via screen share,
or run server-side Playwright on their behalf with credentials in vault.
Each completed submission → signed receipt → forwarded to supplier as
proof. **This is the moat building in real time**: 50–100 signed
receipts by end of Phase 2 = audit trail no Series-A competitor can match.

### 2.3 Customer-success loop

- Weekly 15-min check-in per pilot.
- Every painful manual fill = 1 product backlog ticket. By M3 the
  backlog drives self-serve UI priorities.

### 2.4 Cofounder hunt: start now

- Target: US-based ex-Coupa/Ariba/Zip ICP analyst **or** ex-MGA COO.
- **5–8% equity, 4-yr vest, 1-yr cliff**.
- **90-day paid trial at $3–5K/mo BEFORE equity** (70% of LOIs ghost —
  protect dilution).
- Outreach: 10 named candidates via Sales Nav, 2 intros via
  WSIA/Target Markets community.

**Exit gate**: 2 wires received · $3K MRR · 50+ signed receipts emitted.
**Week 12.**

---

## Phase 3 — Productize → 5–7 logos (Month 4–6)

**Goal**: $10–15K MRR, self-serve product live, SOC 2 observation begun.

### 3.1 Product

- Self-serve onboarding flow (frontend already has all pages — wire
  signup → vault unlock → first portal connection).
- Move 1 of the 2 pilots from done-for-you → self-serve (higher margin).
- Other pilot stays on white-glove (testimonials, case study).
- Add 3 more portals: **Vertafore AMS360, Sircon, Markel**. Submitters
  already mocked — replace with real Playwright in Phase 4.

### 3.2 Compliance

- **Vanta Startup** ($585/mo) starting Month 3. Policy templates,
  evidence collection, GitHub/Linear/AWS connectors.
- Pick auditor: **Prescient Assurance** or **A-LIGN** ($7–10K Type I).
- **Cyber insurance binder** Month 4 ($2.5–5K/yr, Coalition or At-Bay).

### 3.3 Sales scale-up

- Hire **part-time SDR** (Filipino or LATAM, $1.5–2K/mo) Month 5 once
  MRR > $8K. They source + send first-touch; founder takes every demo.
- Aim 5–7 logos by end of M6 = $7.5–10.5K MRR base + done-for-you adders.

### 3.4 Brand

- 1 LinkedIn post/week (I draft, you edit + post from your account).
- 1 blog post/month on `once.io/blog` (SEO: "supplier onboarding portal
  fatigue", "specialty insurance MGA carrier portals list").
- 1 podcast pitch/month (insurance + InsurTech podcasts).

**Exit gate**: 5–7 logos · $10–15K MRR · Vanta observation period
started. **Month 6.**

---

## Phase 4 — Real Playwright submitters + cofounder (Month 7–9)

**Goal**: $20–28K MRR, automation moat real, cofounder closed.

### 4.1 Playwright submitters (the hard part)

Sequence (per portal priority in `PLAN.md`):

1. **Applied Epic** (M7) — biggest leverage (unlocks IVANS download to ~25
   carriers via single integration).
2. **AmTrust producer portal** (M7).
3. **Markel** (M8).
4. **Vertafore AMS360** (M9).
5. **Sircon** (M9).

Each submitter: ~2 wk dev + 1 wk selector hardening + 1 wk soak test with
5 real submissions. **Reuse `_shared.ts` patterns from extension** — the
React tracked-input native-setter trick is already battle-tested.

Add **portal smoke-test workflow** (scaffolded in
`workers/tasks/smoke_test_tasks.py`) — every 15 min, alerts Slack on
selector drift.

### 4.2 Cofounder closed

- 90-day trial concludes; if mutual fit → sign cofounder agreement,
  vesting starts **retroactive to trial start**, 5–8% equity per locked
  decision.
- Cofounder owns sales + customer success. Founder owns product + eng.

### 4.3 First events

- **WSIA Annual Conference**, San Diego, Sep 2026 — booth-adjacent
  meeting room (~$2.5K). Pre-book 15 meetings via Sales Nav.
- **Target Markets Summit**, Scottsdale, Oct 2026 — sponsorship ~$5K.
- Goal: 5 SQLs per event → 1–2 logos in 90 days post-event.

**Exit gate**: $20–28K MRR · 4 portals fully automated · cofounder
signed · 2 events booked. **Month 9.**

---

## Phase 5 — SOC 2 Type I + raise prep (Month 10–12)

**Goal**: SOC 2 audit complete; either pre-seed term sheet **or**
18-month runway from revenue.

### 5.1 SOC 2 Type I audit (M10–11)

- Auditor on-site observation period closes.
- Report issued ~M11. **This unlocks enterprise deals** ($5K+/mo).
- Type II observation starts immediately (12 mo of evidence → completes
  M23).

### 5.2 Pre-seed raise prep (M11–12)

**Trigger to raise**: $35K+ MRR · ≥3 logos with >$3K MRR each · SOC 2 in
hand · cofounder signed.

**Trigger to skip raise**: same except 1 pilot >$8K MRR (means we have a
real enterprise wedge; bootstrap path more dilution-friendly).

- Deck: 12 slides (problem → wedge → traction → moat → ask).
- Target: **$1.5–2.5M @ $10–15M post**, 17–25% dilution.
- Investor list (research-validated):
  - **InsurTech specialists**: Brewer Lane, MTech Capital, Eos.
  - **B2B SaaS pre-seed**: Hustle Fund, Maple VC, Bling, Pear, Susa.
  - **Strategics**: Plug & Play InsurTech, Lloyd's Lab (London).
- 6-week process. Open round Mon, close 6 weeks later.

### 5.3 Alt: bootstrap-to-PMF

If gates not hit OR market dry: extend runway via revenue, hire freeze,
push to **Series A from $5–10M ARR ~Month 24** at $30–50M (better
dilution).

**Exit gate**: SOC 2 Type I report issued · either signed term sheet
OR documented 18-mo runway. **Month 12.**

---

## Phase 6 — Scale: Series A or bootstrap-to-PMF (Month 13–18)

**Goal**: $80–120K MRR, 3 hires made, 2nd vertical scoped.

### 6.1 Hires (in order)

1. **Sr Full-stack engineer** (M13) — owns submitter velocity, $140K US
   base **or** $4–6K/mo senior Indian contractor.
2. **Account Executive #1** (M14) — US-based, $80K base + commission,
   targets enterprise ($5K+/mo).
3. **Customer Success Manager** (M16) — onboarding + churn, $70K base.

### 6.2 Product expansion

- **Portal #6–10**: GuideWire, HawkSoft, EzLynx, NowCerts, CNA portal.
- **COI auto-renewal monitor** (scaffolded in `coi_monitor_service.py`)
  becomes a paid add-on ($300/mo).
- **Verify API** — public-facing, buyers hit
  `verify.once.io/api/v1/receipts/{id}` programmatically. Free tier +
  paid for >10K calls/mo.

### 6.3 2nd vertical scoping

**Don't pivot — extend.** Most natural:

- **Healthcare GPO suppliers** (Vizient, Premier vendor onboarding) —
  same technical pattern, different forms.
- **DIB commercial subcontractors** (NIST 800-171 questionnaires) —
  high-value, slower sales cycle.

**Exit gate**: $80–120K MRR · 3 FTE hired · 2nd vertical PoC live with
1 design partner. **Month 18.**

---

## Phase 7 — Category leader path (Month 19+)

- **OSS the receipt protocol** (Q2 2027) — only after 5 paying customers
  validate the schema. Adopt-by-default play (Plaid Auth / Stripe
  Checkout pattern).
- **Buyer Verification API** monetized — buyers pay to confirm supplier
  data is fresh + receipts are valid.
- **EU GDPR/CSRD wedge** — open London office Year 3 once US revenue
  > $5M ARR.
- **Strategic exit option opens** at $5–10M ARR (~M30–36) to SAP /
  Coupa / Workday / OneTrust for $50–150M. **Don't take it.** Push to
  Series B and category leader at $100M ARR (~Year 5–7) for $1B+
  outcome.

---

## Cross-cutting workstreams (always-on, every phase)

### Security & compliance

- Quarterly pen-test (initially HackerOne triage, later dedicated firm).
- Dependency scan: Dependabot + Snyk free tier.
- Secret rotation every 90 days (signing key, JWT secret, DB password).
- Customer data: Postgres encrypted at rest (Fly Postgres default).
  Vault data client-side encrypted via PBKDF2-310k + AES-GCM (already
  shipped).

### Legal

- Privacy policy + ToS drafted by **Stripe Atlas templates** modified by
  an India-licensed lawyer ($500 one-time). US lawyer review at
  Series A.
- DPA template for EU customers (Phase 5+).
- IP assignment from cofounder + every contractor at signing.

### Finance & ops

- Monthly P&L from Mercury exports + Google Sheets (M1–12).
- Move to **Pilot.com** bookkeeping at $25K MRR.
- Indian operating entity: keep current sole-prop until US C-corp wires
  Indian salary as service payment. **Get a Hyderabad CA to set up
  transfer pricing before first cofounder paycheck.**

### Brand & content

- 1 LinkedIn post/week.
- 1 blog post/month.
- 1 podcast appearance/month from M6.
- Newsletter ($0 → Beehiiv) starts M3 with first 10 prospects.

### Risk monitoring (review weekly with me)

**Top 5 kill risks** with mitigations:

1. **Cofounder ghosts after 60 days** → start hunt Day 1.
2. **Selector drift breaks 1+ portal** → 15-min smoke tests + Slack alerts.
3. **Customer concentration > 30%** → cap at 30% until $25K MRR.
4. **India-founder objection on calls** → 1-800 + Cal.com on US hours.
5. **SOC 2 timeline slip** → Vanta from M3, audit start no later than M10.

---

## The 8 decisions I need from you to unblock Phase 0

1. [ ] **Brand**: lock "Once" or pick alt (Verite / Pactly / Onceledger /
       other)?
2. [ ] **Domain**: pay ~$2K for `once.io` or take `getonce.com` for $12?
3. [ ] **$2.7K Month-1 spend** on credit card OK?
4. [ ] **Cofounder hunt**: start Day 1 or Day 60?
5. [ ] **Wedge B (OnceTax Shopify)**: parallel-run for 30 days or fold
       now?
6. [ ] **First ICP**: trucking MGAs (recommended) or open to alt (E&S
       surplus, healthcare MGUs)?
7. [ ] **Repo license**: keep BSL 1.1 (current) or go MIT + closed-source
       server?
8. [ ] **My commitment cadence**: confirm Mon 9am IST metrics / daily
       7pm IST outbound / Fri 5pm IST content / Sunday silent?

---

## What I'll do this week once decisions land (Phase 0, Week 1)

- [ ] Update `CONTRACTS.md` + `ROADMAP.md` with locked decisions
- [ ] Draft Stripe Atlas application (you submit + pay $500)
- [ ] Reserve domain + set up Cloudflare DNS
- [ ] Generate Ed25519 signing keypair (Fly secrets format)
- [ ] Set up GitHub org + push current repo, wire CI
- [ ] Draft 30-prospect Target Markets shortlist
- [ ] Draft v1 landing page copy
- [ ] Draft first 3 cold-email subject lines + bodies for Wk 5 send

**Your only tasks this week**: answer the 8 decisions, sign Stripe Atlas
docs, wire $500 + $12 for domain. **~2 hours of your time.**

---

_Document version: 1.0 · 2026-05-19 · Authored by AI cofounder, owned by
the founder._
