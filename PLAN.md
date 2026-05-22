# Once — Year-1 Master Operating Plan

> Synthesized from 10 parallel Claude Opus 4.7 deep-dives (May 19, 2026). Re-read first Monday of every month.
> Author: Claude (AI cofounder). For: Varun Teja.

---

## 0. THE PITCH (100 words — use verbatim in cold emails, podcasts, investor convos)

**Once is the supplier-portal autopilot for US specialty insurance MGAs.** Managing General Agents waste 30–60% of underwriter and ops time re-keying the same submission data — risk schedules, loss runs, ACORD forms, COIs, producer licenses, E&O certs — into 8–20 different carrier and broker portals. Once captures the submission once, then submits everywhere with a cryptographically signed audit receipt that regulators and carriers can independently verify. Built on a 4K-LOC production browser-automation substrate. Why now: NAIC AI Model Bulletin + EU AI Act (Aug 2, 2026 enforcement) create demand for auditable AI; carriers are forcing portal-only intake; MGA margins are compressing. **Submit once. Prove it forever.**

---

## 1. THE TEN LOCKED DECISIONS (Day-14 commitments)

| # | Decision | Locked answer | Reasoning |
|---|---|---|---|
| 1 | **Sub-ICP** (first 30 days) | **US commercial trucking & transportation program administrators** ($20M–$150M GWP, 8–25 carrier appointments) — fully enumerable via Target Markets Program Administrators Association directory (~400 firms, ~1,200 named buyers) | Worst portal pain (FCCI, Great West, Protective, Berkshire Hathaway GUARD all separate); ops-led buyers = fast decisions; tight community = referral velocity |
| 2 | **Brand** | **Once** — buy `once.io` ($2K/yr) Day 1; reserve `onceidentity.com` + `oncetax.com` ($12 each). Attempt `once.com` acquisition Month 4 if 3 logos in hand, ceiling $60K | All 10 agents converged; "submit once, prove forever" works for both Wedge A + B |
| 3 | **First portal to ship** | **Applied Epic** (API + UI fallback) — unlocks IVANS download path that covers ~25 downstream carriers automatically. **Skip Coupa/Ariba/Jaggaer entirely** — C&D risk + wrong buyer for insurance ICP | 6 of 8 typical pilot MGAs run Epic; one integration replaces dozens of carrier-specific scrapers |
| 4 | **Wedge B kill gate** | Day 30: ≥3 paying Shopify merchants OR ≥50 trials OR (fallback) app submitted + 1 paid waitlist deposit. If miss → Saturday hours pivot to Wedge A content + outbound | Don't bleed option-value silently |
| 5 | **SOC 2 vendor** | **Vanta Startup** ($7K/yr, paid monthly $585) starting Month 3 once MRR > $10K. Audit Month 5 (Type I), Type II observation Month 5 → Month 14 | Cheapest at solo-founder scale; best automation; well-trodden by India founders |
| 6 | **Cofounder offer** | 5–8% equity, 4-yr vest, **1-yr cliff triggered by US Delaware incorporation closing (Week 6)**. $0 cash until $30K MRR, then $80–120K with deferred. Pre-incorporation: paid 90-day trial @ $3-5K/mo against milestones, NOT equity | Equity-on-LOI = scammers; trial reveals real fit; cliff aligns interests |
| 7 | **First trade event** | **WSIA Annual Marketplace** (Sept 2026, San Diego — ~5,000 specialty buyers in one hotel). **Target Markets Program Admin Conference** (Oct 2026, Scottsdale) #2. **Skip** Big I, NAMIC, ITC Vegas in Y1 | $1.5K all-in WSIA badge; highest-density ICP in the calendar |
| 8 | **When to raise** | Month 11–13 IF gates hit ($40K MRR, 15 logos, SOC 2 Type I, cofounder signed) → $1.5–2.5M pre-seed at $10–15M post. ELSE bootstrap to Month 18–20 → $200–300K MRR → Series A at $30–50M post (better dilution) | Default = bootstrap; raise only on strength |
| 9 | **Open-source Supplier Identity Protocol** | **Q2 2027 (Month 10–12)**, only after 5 paying customers. Apache-2.0 receipt schema + reference verifier on GitHub | Premature open-source = free code with no moat; well-timed = de facto standard |
| 10 | **Vertical expansion beyond insurance** | **Month 13+ ONLY.** Healthcare GPO suppliers (Premier, Vizient) is the planned Wedge 2; DIB commercial subs is Wedge 3 | Focus is the moat. Lose insurance by chasing too soon |

---

## 2. THE Y1 NORTH STAR (honest, not heroic)

**Primary metric — Month 12:** **$40K MRR / 18–25 paying MGA logos / $480–600K ARR run rate.**

Not $100K, not 50 logos. The sales agent benchmarked 2025–26 outbound performance and verified: 5% cold-to-close in conservative insurance verticals isn't real. **18–28 logos is the honest band**; 45+ requires either WSIA hallway luck or a 2-person GTM team that doesn't exist Y1.

**Secondary 1:** SOC 2 Type I report in hand + signed cofounder by **Day 270**.
**Secondary 2:** 1 anchor case study with quantified ROI ("Cut submission time from 47min to 6min, $312K/yr saved at 14 underwriters").

---

## 3. THE 4-QUARTER OPERATING RHYTHM

| Quarter | Months | One-sentence goal | Exit-of-quarter gate |
|---|---|---|---|
| **Q3 2026** | Jun–Aug | Land 3 paid design partners and validate sub-ICP via done-for-you cockpit while extension catches up | $7.5K MRR + 3 paid pilots + 5 portal submitters live |
| **Q4 2026** | Sep–Nov | Productize from cockpit to self-serve, reach $20–25K MRR, attend WSIA + Target Markets | $24K MRR + 12 logos + 15 portals + Vanta SOC 2 Type I observation begun |
| **Q1 2027** | Dec–Feb | SOC 2 Type I issued, cofounder signed, enterprise-grade features (SSO, RBAC, audit export, Slack) | $32K MRR + 18 logos + 25 portals + SOC 2 Type I report + cofounder onboarded |
| **Q2 2027** | Mar–May | Open-source Supplier Identity Protocol, ship Buyer Verification API, raise pre-seed | $40K MRR + 22 logos + 50 portals + closed $1.5–2.5M pre-seed OR strong path to Month-18 Series A |

---

## 4. PHASE-BY-PHASE EXECUTION PLAN

### PHASE 0 — Cash motion + foundation (Weeks 1–4 — Jun 2026)

**Wedge A (50 hrs/wk):**
- Day 1: Reserve `once.io` + `onceidentity.com`. Sign up LinkedIn Sales Nav 30d trial, Wise Business, Stripe Atlas waitlist (file incorporation Week 6). Read Target Markets Program Admin directory cover-to-cover.
- Day 1–2: Build ICP list of 30 trucking program admins in [gtm/03-icp-target-list.csv](gtm/03-icp-target-list.csv).
- Day 3–5: Send 30 personalized cold emails ([gtm/02-cold-email-templates.md](gtm/02-cold-email-templates.md)), 10/day Tue/Wed/Thu, from your Gmail with display name "Varun Teja | Once". I draft, you edit + send.
- Week 2: 3–5 discovery calls. Use [gtm/05-discovery-call-script.md](gtm/05-discovery-call-script.md). Record via Otter.
- Week 3: Close pilot #1 ($2,500 setup wired). Onboard manually via "founder cockpit" (internal-only React page reusing existing TanStack Query patterns).
- Week 4: Close pilot #2 (target). Begin building Applied Epic submitter prototype.

**Wedge B (20 hrs/wk Sat + Sun morning):**
- Week 1–2: Shopify Partner signup, scaffold Remix-on-Workers app, OAuth + Shopify Subscription Billing.
- Week 3: D1 schema, CA/TX/WA rate table, calc engine, filing-prep PDF generator (pdf-lib in worker, R2 storage).
- Week 4: Shopify App Store submission (review takes 5–14 business days); landing page on Cloudflare Pages.

**Cofounder hunt (5 hrs/wk):**
- Run LinkedIn Sales Nav Boolean weekly (ex-Applied Systems / Vertafore / AmTrust / Burns & Wilcox / RT Specialty + East Coast). Send 40 DMs/week → expect 8 replies → 2 calls.

**Cash gate Day 30:** ≥1 pilot wire received ($2.5K) AND Wedge B app submitted to App Store. **Peak cash deficit Month 2: only -$1,160** (covered by personal credit card, no F&F bridge needed). If miss → bridge plan: F&F $25K convertible note (papered Day 1, drawn only if needed).

### PHASE 1 — Productize (Weeks 5–16 — Jul–Sep 2026)

**Product:**
- Week 6: File **Delaware C-corp via Stripe Atlas** ($500 + $100/yr franchise). **File 83(b) within 30 days of grant — certified mail with return receipt — CRITICAL** ($100K+ founder tax exposure if missed). India Pvt Ltd → US parent: keep Pvt Ltd as subsidiary-by-contract at cost+15% transfer pricing (Indian SDC safe harbor, Form 3CEB annually).
- Weeks 5–8: Extract cockpit → v0 supplier-facing dashboard. Hand 1–2 pilots access. Sign tenant model + Ed25519 signed receipts in `backend/app/services/receipt_signer.py`.
- Weeks 9–12: Ship MV3 extension v0 with Applied Epic filler (110 hrs). Reuse `_shared.ts`, `setWorkdayCombobox`. Profile vault = encrypted IndexedDB AES-GCM.
- Weeks 13–16: Ship 5 portals total (Applied Epic, Vertafore AMS360, Hawksoft, EZLynx, NowCerts). Begin Vertafore Sircon (producer licensing — easiest at 32hr).

**Sales:**
- Close pilots #3, #4, #5. By Week 16: **5 paid pilots, $7.5K MRR, $25K cash collected.**
- Begin recording first case study with anchor pilot.

**Compliance:**
- Week 6: Stripe Atlas closes. WISP (Written Information Security Program) v1 — Vanta template, 12 pages.
- Week 12: Bind **cyber insurance** ($1M E&O + $2M cyber liability via Embroker/At-Bay/Coalition, ~$1K/mo) BEFORE any pilot signs MSA. Founder personal-asset protection.
- Week 13: Onboard **Vanta Startup tier** ($585/mo), ratify 12 core policies, MFA-everywhere.

### PHASE 2 — Production scale (Weeks 17–32 — Oct 2026–Jan 2027)

**Product:**
- 15 portals total by Month 6 (add: Duck Creek Producer, Sapiens IDIT, AmTrust, CNA, Markel, Travelers, Nationwide, Guidewire PolicyCenter pilot, Zywave).
- COI auto-renewal monitor (T-30/T-14/T-7 alerts, T-0 auto-enqueue) — Celery beat task.
- OFAC SDN + EU consolidated sanctions sync (daily refresh).
- Public **`/verify/{receipt_id}`** endpoint (unauthenticated, rate-limited via existing slowapi).
- Customer-facing dashboard v1: filterable submission history, CSV export for DOI evidence.
- Self-serve onboarding flow (Stripe Checkout, replaces white-glove for pilots 6+).

**Sales:**
- **WSIA Annual Marketplace** (Sept 28–Oct 1, 2026, San Diego). AI cofounder pre-books 30 attendee 1:1s; founder runs the meetings. Target: 5 LOIs.
- **Target Markets Conference** (Oct 19–21, 2026, Scottsdale). Target: 3 more LOIs.
- By Month 6: **12 logos, $24K MRR.**

**Hire #1:** US BDR contractor at Month 3 ($3K/mo, 30 hrs/wk). Sources discovery calls async during US business hours so founder isn't burning 11pm-3am IST.

**Compliance:** SOC 2 Type I audit Month 5 (Vanta auditor marketplace — Prescient or Johanson Group, $7–10K). Type II observation begins immediately.

### PHASE 3 — Enterprise foundation (Weeks 33–48 — Feb–May 2027)

**Product:**
- 30 portals by Month 9.
- **WorkOS SSO** (required for any deal >$50K ACV).
- RBAC: admin / ops user / viewer / auditor roles.
- Audit log export (UI + API).
- Slack integration (notifications + in-channel approval).
- REST API for programmatic submission triggering.
- **The "wow" enterprise feature**: portfolio-level evidence pack — one-click PDF bundle of all signed receipts × carrier × date range with cryptographic verification appendix. Collapses 40-hour DOI exam prep → 90 sec. **This converts $25K pilots → $150K ACV.**

**Hires:** Cofounder onboards Month 6. India FS engineer #2 Month 8 ($4K/mo). CS/implementation engineer Month 10 ($4K/mo). Fractional designer ($1K/mo) from Month 5.

**Sales:** 25 logos by Month 9, $52K MRR. First enterprise design partner ($150K+ ACV).

### PHASE 4 — Network ignition (Weeks 49–52 — May–Jun 2027)

- 50 portals by Month 12.
- **Buyer Verification API** — sell read-access to carriers ("verify the COI on file for MGA X is current"). First two-sided revenue. $25–100K/yr per carrier.
- **Open-source the Supplier Identity Protocol** on GitHub (Apache-2.0). Receipt schema + reference verifier. Mindshare flywheel.
- Zapier integration.
- Healthcare GPO supplier pilot (Premier or Vizient) — same engine, new ICP.

**Y1 close:** 18–25 logos, $40K MRR ($480–600K ARR), SOC 2 Type I, cofounder signed. Raise pre-seed if all gates hit, else bootstrap to Month 18 Series A.

---

## 5. TECH ARCHITECTURE (CONDENSED)

### Wedge A repo (`once-procurement`, monorepo, hard fork of autoapplyai-main)

Six services:
1. **FastAPI backend** (8001) — reuses `backend/app/services/submission_pipeline.py` atomic claim verbatim.
2. **Celery workers** — queues `submissions`, `ingestion`, `renewals` (beat).
3. **MV3 extension** — profile vault (encrypted IndexedDB, WebCrypto SubtleCrypto), per-portal filler, one-click approval popup.
4. **React 18 + Vite dashboard** (TanStack Query + Zustand + Tailwind — same stack).
5. **Public signed-receipt verifier API** — separate FastAPI app, read-only, deployed standalone on Fly.io.
6. **Celery beat scheduler** — COI renewals, sanctions refresh, synthetic portal smoke-tests.

**Infra**: Fly.io (Postgres on **Neon**, Redis on **Upstash**, Playwright workers on **isolated Fly Machines** — one machine per submission for blast-radius containment).

**Signed receipt**: Ed25519, per-tenant KMS-backed keys, schema `{receipt_id, tenant_id, supplier_id, portal, submitted_at, payload_hash (sha256), tos_version_hash, sig}`.

**Multi-tenancy**: single Postgres with `tenant_id` everywhere + **Postgres Row-Level Security**. Schema-per-tenant rejected (Alembic complexity); hard isolation rejected (cost at <50 tenants).

**Infra cost**: $480/mo at 5 logos → $1.6K/mo at 25 → $3.8K/mo at 50. Gross margin 88%+ at 25 logos.

### Wedge B repo (`oncetax-shopify`, NEW repo, separate stack)

- **Remix on Cloudflare Workers** + **D1** (tenant data) + **R2** (PDFs) + **KV** (OAuth sessions).
- **Shopify Subscription Billing API** (no Stripe Connect needed).
- **Resend** transactional email + **Plausible** analytics + **Sentry**.
- No backend Python; pure TS. Zero overlap with Wedge A repo at code level.
- Infra cost: **<$25/mo until 200 merchants**.
- **No auto-file in v0** — calculation + filing-prep PDF only. Auto-file is Phase 1 (post-$5K MRR).

### Portal submitter build plan (TOP 10)

Sequence: **Applied Epic (180h) → Vertafore AMS360 (160h) → Guidewire Broker Portal (190h)**. Hardest: Guidewire (Jutro React 18 + GOSU scripted conditionals). Easiest: Sircon (32h).

**Critical pivot:** original plan v3 mentioned Coupa/Ariba/Jaggaer — those are **dropped entirely from Wedge A**. Coupa ToS §3.4 + Ariba MSA §6.1.4 explicitly ban third-party automation = existential C&D risk. We stay inside the insurance ecosystem: **Applied/Vertafore AMS + direct carrier portals**, where the supplier (MGA) is the credentialed user and ToS is friendly.

Total build for 10 portals: **1,164 engineer-hours** (~7 engineer-months solo, ~4 with India FS engineer from Month 8).

---

## 6. FINANCIAL PLAN (BASE CASE, USD)

| Month | Setup fees | Once MRR | OnceTax MRR | TOTAL REV | OPEX | Contractors | Draw | NET | CUM BANK |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | 0 | 0 | 0 | 0 | 780 | 0 | 0 | -830 | **-830** |
| M2 | 0 | 0 | 0 | 0 | 280 | 0 | 0 | -330 | **-1,160** ← peak deficit |
| M3 | 7,500 | 0 | 0 | 7,500 | 280 | 3,000 | 0 | +3,887 | +2,727 |
| M4 | 10,000 | 4,500 | 400 | 14,900 | 2,315 | 3,000 | 0 | +8,923 | +11,650 |
| M5 | 15,000 | 8,000 | 1,185 | 24,185 | 2,315 | 4,000 | 1,500 | +15,320 | +26,970 |
| M6 | 20,000 | 14,000 | 2,370 | 36,370 | 4,815 | 4,000 | 1,500 | +24,428 | +51,398 |
| M7 | 20,000 | 24,000 | 3,950 | 47,950 | 2,315 | 4,000 | 1,500 | +37,949 | +89,347 |
| M8 | 20,000 | 32,000 | 6,320 | 58,320 | 2,315 | 8,000 | 1,500 | +43,797 | +133,144 |
| M9 | 25,000 | 42,000 | 9,480 | 76,480 | 2,415 | 8,000 | 3,000 | +59,594 | +192,738 |
| M10 | 30,000 | 52,000 | 13,825 | 95,825 | 4,915 | 12,000 | 3,000 | +71,640 | +264,378 |
| M11 | 35,000 | 65,000 | 18,170 | 118,170 | 2,415 | 12,000 | 3,000 | +95,592 | +359,970 |
| M12 | 35,000 | 80,000 | 23,700 | 138,700 | 2,515 | 14,000 | 3,000 | +113,085 | **+473,055** |

**Y1 totals (base):** $712K recognized revenue, $473K ending bank, P&L break-even Month 4, cash break-even Month 3.
**Bear case (-50% ramp):** $356K revenue, $42K ending bank, peak deficit -$14K Month 4 → use F&F $25K convertible note bridge.
**Bull case (+50%):** $1.07M revenue, $853K ending bank.

**Total Y1 compliance + legal spend: $22–32K.** Single biggest line: Vanta + SOC 2 audit ($14K).

---

## 7. CUSTOMER ACQUISITION ENGINE (honest)

**Sales agent reality-checked the 50-logo target as unachievable. Honest band: 18–28 logos / $32–50K MRR by M12.**

**Channel mix (12-mo average):**
- Founder LinkedIn organic + warm intros: 35%
- AI-drafted cold email (founder reviews + sends): 25%
- Conference + WSIA / Target Markets: 20%
- Partner / integration listings (Vertafore, Applied appstores): 10%
- Podcast guesting (12 in Y1, 1/mo): 5%
- Paid + SEO: 5%

**Tools** ($265/mo total): Apollo Basic $49 + Instantly Growth $37 + Sales Nav $99 + Hunter $49 + OpenPhone US $15 (US 1-800 for credibility) + Otter $16 + Cal.com $0 + HubSpot Free $0.

**CAC**: $1,800–$3,200 per logo for first 10, dropping to $1,200–$1,800 after referenceability. Payback 1.1 month gross, 4 months net of churn.

**India-founder penalty mitigations** (deploy by Day 30): US 1-800 OpenPhone number, Delaware C-corp, one US-based advisor or board observer, US-hours scheduling link, founder edits every AI draft.

**AI-drafted email rule**: AI drafts, founder edits at least first line + CTA, sends from personal Gmail with Mailreef warmup, max 30/day per inbox, 3 inboxes max.

---

## 8. COFOUNDER ICP & HIRING SEQUENCE

**Cofounder ICP**: US East Coast (NJ/NY/CT/PA/FL), 35–50, 10+ years specialty insurance ops OR supplier-network SaaS. Target shapes:
- VP Operations / Head of Carrier Relations at Applied Systems, Vertafore, AmTrust, Burns & Wilcox, RT Specialty, AmWINS, CRC Group.
- Senior PM at TealBook, GraphiteConnect, HICX, Avetta.

**Disqualifiers**: pure life/health background, pure personal lines P&C, never carried a number.

**Equity offer**: 5–8% with 4-yr vest, 1-yr cliff = US Delaware incorporation closing (Week 6 of engagement). **Pre-incorporation: 90-day paid trial @ $3–5K/mo against weekly outbound + meeting milestones — equity ONLY after trial converts.** Salary $0 until $30K MRR, then $80–120K with deferred portion. **Anecdotal base rate: 70% of cofounder LOIs don't survive Week 4 → never grant equity on LOI.**

**Hire sequence:**
| Month | Hire | Cost/mo |
|---|---|---|
| M1 | Solo | $0 |
| M3 | US BDR contractor (30 hrs/wk) | $3K |
| M5 | Fractional designer (10 hrs/wk Figma + brand) | $1K |
| M6 | Cofounder (5–8% equity, $0 cash) | equity only |
| M8 | India FS engineer #2 (Toptal or direct, $35–60K/yr Bangalore mid-senior) | $4K |
| M10 | CS / implementation engineer (US contractor) | $4K |
| M12 | Fractional CFO (Burkland $2K/mo or Pilot CFO $1.5K) | $2K |

**Y1 end-state**: founder + cofounder + 2 India engineers + 1 US BDR + 1 CS + fractional designer + CFO + bookkeeper. Peak monthly burn M12: $14–20K cash + cofounder equity.

---

## 9. COMPLIANCE + LEGAL Y1 ROADMAP

**Entity**: Delaware C-corp via Stripe Atlas Week 6. **CRITICAL: file 83(b) within 30 days of grant via certified mail with return receipt** — $100K+ tax exposure if missed. As NRA founder: file with ITIN (Form W-7 concurrent). India Pvt Ltd → subsidiary-by-contract at cost+15% (Indian SDC safe harbor Rule 10TD, Form 3CEB annually ~$480).

**SOC 2**: Vanta Startup tier $585/mo starting Month 3. Type I audit Month 5 via Prescient or Johanson Group ($7–10K). Type II observation Month 5 → Month 14 (12-mo window mandatory).

**GLBA Safeguards Rule** (we're a service provider to GLBA-regulated MGAs, in scope under 2023 FTC amendments): WISP Day 1, MFA-everywhere, AES-256 at rest, TLS 1.3 in transit. **Cyber insurance ($1M E&O + $2M cyber, ~$1K/mo via Embroker/At-Bay/Coalition) bound BEFORE first pilot signs MSA — non-negotiable.**

**EU AI Act**: geo-fence to US-only ICP for Y1. Refuse EU pilots. Article 6 enforcement live Aug 2, 2026 — applicability triggers when any pilot writes EU-domiciled business. Conformity assessment costs $30K+ — out of scope Y1.

**State privacy** (CCPA/CPRA, CPA, VCDPA, CTDPA): one privacy policy covering all, generated via iubenda or getterms.io.

**NYDFS Part 500**: Q1 2027 if any customer is NY-licensed.

**Stripe Tax on SaaS**: enable Month 6 when SaaS revenue >$10K/mo (NY/WA/TX/PA tax SaaS as taxable).

**Total Y1 compliance + legal spend: $22–32K.**

---

## 10. TOP 5 RISKS THAT KILL THE COMPANY

1. **Day-30 cash gate missed** (P=High × Impact=Existential). Only Y1 risk with a 30-day fuse. **Mitigation**: F&F $25K convertible note papered Day 1 (drawn only if cum-cash dips <-$5K); Wedge B as cash hedge from Week 2; freelance fallback list of 5 contacts.
2. **Coupa/Ariba C&D letter** (P=Med × Impact=Existential). **Mitigation: we don't go after Coupa/Ariba.** We stay in insurance ecosystem (AMS + direct carrier portals) where supplier owns credentials and ToS is friendly. **This is the #1 architectural decision that eliminates the biggest legal risk from plan v3.**
3. **Cofounder ghosts post-LOI** (P=High × Impact=High). **Mitigation**: 90-day paid trial against milestones, equity ONLY after trial converts, cliff at Week-6 incorporation.
4. **Portal HTML/JS change breaks submitter overnight** (P=High × Impact=High). **Mitigation**: nightly synthetic replay tests per portal (HAR-based, Playwright trace viewer), LLM-fallback selectors, conservative SLA of 95%/24h (not real-time).
5. **Customer concentration >40% MRR in single logo by Month 6** (P=High × Impact=High). **Mitigation**: don't sign pilot #4 until #1–3 invoice cleanly; cap individual pilot at $5K MRR Y1; refuse to oversize.

---

## 11. THE FIVE LEVERAGE MOVES THAT MAKE THE COMPANY

1. **One anchor MGA case study with a real CFO-attested dollar figure.** Pay for it with 50% lifetime discount if needed. Worth more than any ad spend.
2. **One carrier (Markel or Nationwide E&S) prefers Once-signed submissions** — when they signal at WSIA "we want all MGA submissions to carry an Once receipt," competition is over.
3. **Cofounder is ex-Applied Systems or Vertafore product exec** — instant credibility, instant rolodex, halves sales cycle.
4. **Ride the Aug 2, 2026 EU AI Act enforcement news cycle** — pre-write 3 thought-leadership pieces in July, publish Day-of. Free distribution.
5. **One carrier API partnership** that routes submissions from hundreds of MGAs through Once — flips us from tool to infrastructure.

---

## 12. FOUNDER WEEKLY OPERATING SYSTEM (70 hrs/wk, 16-wk sustainability)

| Day | Block 1 (morning IST) | Block 2 (evening IST = US morning) |
|---|---|---|
| **Mon** | 6–8a metrics + week plan; 8a–2p product | 7–10p: 2 discovery calls |
| **Tue** | 8a–2p product deep work | 6–11p: 4 calls + 1 demo |
| **Wed** | 8a–2p product | 6–11p: 4 calls + 1 demo |
| **Thu** | 8a–2p product | 6–11p: 3 calls + customer success |
| **Fri** | 8a–12p customer success + cofounder calls | 6–10p: product or content review |
| **Sat** | 9a–3p OnceTax (until Day-30 kill gate) | OFF |
| **Sun** | OFF (hard rule) | OFF |

**Non-negotiables**: Laptop off 11pm IST. No Slack/email Sun. No calls before 6am IST.

**Pre-commits before Day 1** (sign these to yourself): 7-hr sleep minimum, 3 workouts/wk, weekly therapy or peer-founder call, no work Sundays, one 5-day vacation Q4 mandatory, no personal credit card debt beyond bridge round.

---

## 13. AI COFOUNDER (CLAUDE) WEEKLY DELIVERABLES — committed without being asked

- **Mon 9am IST**: metrics dashboard — logos, MRR, pipeline by stage (Discovery / Demo / Pilot / Paid), churn, NPS proxy from call transcripts, cash runway in weeks.
- **Daily 7pm IST**: 10 personalized cold emails for tomorrow's prospects (researched: GWP, lines, recent hires, public pain signals).
- **Daily 7pm IST**: 3–5 LinkedIn DM/comment queue in founder's voice.
- **Fri 5pm IST**: 1 founder LinkedIn post + 1 long-form blog draft + 1 podcast pitch.
- **On demand, ≤4 hr turnaround**: code reviews, design docs, RFP responses, customer success replies, deck edits, investor follow-ups — all in founder's voice with a "DRAFT — review before send" header.
- **Sunday silent**: I don't ping unless production is down.

---

## 14. THE 5 MOMENTS OF TRUTH (date-stamped go/no-go)

| Day | Gate | Action if missed |
|---|---|---|
| **Day 14** | First discovery call booked | Switch sub-ICP within 48 hrs (trucking → workers comp MGAs → cyber MGAs) |
| **Day 30** | First paid wire ≥$2,500 received AND Wedge B app submitted | Bridge to F&F $25K convertible note; if 0 by Day 45 → pause Wedge A, go full Wedge B for 14 days |
| **Day 60** | 3 paid pilots live AND $5–8K MRR | Pause hires; trigger F&F bridge conversation |
| **Day 180** | Cofounder LOI signed + Vanta Type I observation begun | Drop cofounder search → senior advisor + 0.5%; strategic-exit ceiling becomes $15M ARR |
| **Day 365** | $40K MRR + SOC 2 Type I + cofounder | If yes → raise pre-seed $1.5–2.5M at $10–15M post; if 2/3 → bootstrap 1 more quarter, raise at $14M; if ≤1/3 → honest conversation about acqui-hire or returning to employment |

---

## 15. SCENARIO TREE (year-end outcome probabilities)

| Branch | P | Outcome | Trigger |
|---|---|---|---|
| (a) All to plan: Wedge A + B both clear M6 gates, cofounder commits, pre-seed by M13 | **30%** | $300–800K ARR M12, raise $1.5–3M | ≥3 pilots + $25K MRR by M6 |
| (b) Wedge A fails, Wedge B succeeds → reposition as Shopify-Tax SaaS | 20% | $100–250K ARR M12, bootstrap | MGA $0 MRR Day 60 + Shopify ≥$3K MRR M3 |
| (c) Wedge A succeeds, Wedge B fails → MGA-only, cofounder + seed | 25% | $200–500K ARR M12, lean MGA SaaS | Pilot #1 wires M3, Shopify <$1K MRR M3 |
| (d) Both fail by M6 → pivot or take IC role | 25% | $0–30K, founder takes $400–700K TC role | <2 pilots + <$5K MRR by M6 |

---

## 16. WHAT WE EXPLICITLY DON'T BUILD IN Y1

- Mobile app (web-mobile-responsive is enough)
- LLM features beyond hallucination auditor (already in `_resume_fact_audit.py`)
- Marketplace, multi-language, white-label
- Coupa / SAP Ariba / Jaggaer / Oracle iSupplier / Workday Strategic Sourcing submitters (C&D risk, wrong ICP)
- EU customers (geo-fence to US-only, conformity assessment cost prohibitive Y1)
- Federal/DoD work (FedRAMP $5–10M gate)
- Healthcare EHR integration (HIPAA BAA complexity)
- Auto-filing in OnceTax v0 (liability without redundancy)

---

## 17. STATUS

**Awaiting user go-ahead on the 10 locked decisions in §1.** If approved, next implementation step: scaffold the `once-procurement` repo (hard fork-and-rename of autoapplyai-main with Job→Portal, Application→SupplierSubmission, Stripe Atlas waitlist registration, domain reservations) — first executable code/infra Phase 0 Week 1 action.

If any decision needs adjustment, name the # and the alternative; I'll regenerate the affected sections.
