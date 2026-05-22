# Target Markets Program Administrators Summit 2026 — Plan

> **Conference:** Target Markets Program Administrators Association Summit,
> Scottsdale, **October 2026** (exact dates: <<TM_DATES>>).
> **Owner:** <<MEETING_OWNER>>. **Target:** 15 pre-booked meetings →
> $35K MRR pipeline within 30 days. **Sibling doc:**
> [gtm/08-wsia-2026-meeting-plan.md](08-wsia-2026-meeting-plan.md).

Target Markets is where program-business MGAs gather. Program MGAs run
deep on producer licensing (Sircon-heavy) and on AMS360 / Applied Epic for
operations. This is where the Sircon submitter earns its keep.

## 1. Why this show (separate from WSIA)

WSIA = wholesale brokers + open-market specialty. Target Markets = program
administrators — niche-specific MGAs with delegated underwriting authority.
Different buyer, different pain mix:

- **Sircon producer-licensing volume is high** (one program MGA can run
  thousands of state appointments per month).
- **AMS360 lock-in** for the back office.
- **Smaller buying committees** — usually founder/CEO + ops lead.

Single-call close probability is materially higher than WSIA. Pipeline
target is lower but **close rate target is higher**.

## 2. Goals

| Metric | Target |
|---|---|
| Pre-booked meetings | 15 |
| On-site walk-up demos | 8 |
| Post-show pipeline created | $35K MRR (≈ $420K ARR) |
| Signed paid pilots within 30 days | 3 |
| Logos confirmed for program-MGA reference calls | 2 |

ICP: program MGA, ≥ $25M GWP, ≥ 50 appointed producers, today re-keying
into Sircon + AMS360.

## 3. Pre-show plan (staggered one month after WSIA)

### T-10 weeks (immediately after WSIA wrap)
- Carve the WSIA learnings into a "what we shipped this month" one-pager
  to send to the Target Markets list. Use real numbers from the WSIA
  pipeline (no vanity metrics).
- Pull the Target Markets attendee list. Enrich on GWP and program lines
  (workers' comp, transportation, professional liability, etc.).

### T-6 weeks
- Outbound sequence (same structure as WSIA §2 but Sircon-centric subject
  lines). Owner: <<OUTBOUND_OWNER>>.
- Reset the `demo.once-procurement.app` tenant with a program-MGA fixture
  (high producer count, multi-state appointments, AMS360 export sample).

### T-3 weeks
- Confirm meeting blocks. Calendly: Mon + Tue 7am–10am and 4pm–8pm.
- Pre-record a 90-second Sircon submission demo as the cold-email video.

### T-1 week
- Dry-run all 5 submitters. Confirm the **Sircon submitter** specifically
  handles 3-state and 10-state requests cleanly. This is the differentiator.
- Brief the team on objection handling (§5).

## 4. The 20-minute meeting script (Sircon-focused)

| Minutes | What we do |
|---|---|
| 0–2 | Ask about producer-licensing volume and current re-key process. |
| 2–10 | **Live demo:** submit a 5-state appointment via Sircon end-to-end. Show the signed receipt and the time saved. |
| 10–15 | Pricing + program-MGA-specific terms (volume discount above <<VOLUME_THRESHOLD>> submissions/mo). |
| 15–20 | Next step: paid pilot ($<<PILOT_PRICE_USD>>, 30 days, Sircon + one carrier portal of their choice). |

Note the difference from WSIA: at Target Markets we lead with **Sircon**,
not with carrier portals. Sircon volume is the entry wedge for program MGAs.

## 5. Objection bank

- "We already automate Sircon with macros." → Macros break weekly. Show
  the smoke-test workflow + 15-minute drift detection.
- "Will it scale to 5,000 appointments a month?" → Yes — show the soak
  harness output (`backend/tests/integration/test_submitter_soak.py`).
- "Where does the data live?" → Tenant-isolated Postgres, signed receipts,
  no cross-tenant queries (see `CONTRACTS.md`).
- "Compliance is going to kill this." → Walk through `docs/SECURITY.md`
  and the public verifier (`verifier/`).

## 6. On-show cadence

| Slot | Activity |
|---|---|
| 07:00–10:00 | Pre-booked meetings |
| 10:00–16:00 | Show floor + sessions + Sircon walk-up demos at our table |
| 16:00–19:00 | After-floor meetings |
| 19:00–22:00 | 1 hosted dinner (max 6 program-MGA founders) |
| 22:30 | Daily HubSpot sync |

## 7. Post-show 14-day playbook

Mirrors WSIA (see §7 of [08-wsia-2026-meeting-plan.md](08-wsia-2026-meeting-plan.md))
with one addition: at +7, run a **joint review with the WSIA pipeline** so
we can prioritize the joint addressable accounts (firms that appeared at
both shows) — they convert at a materially higher rate.

## 8. Budget

| Line item | Amount |
|---|---|
| Registration (2 attendees) | $<<REG_COST_USD>> |
| Hotel + travel (2 attendees, 3 nights) | $<<TRAVEL_COST_USD>> |
| Tabletop / sponsor slot | $<<TABLE_COST_USD>> |
| Hosted dinner (1 night × 6 guests) | $<<DINNER_COST_USD>> |
| Print + swag | $<<PRINT_COST_USD>> |
| **Total** | **≤ $18,000** |

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Sircon UI changes pre-show | Re-run integration tests T-3 and T-1 |
| Lower attendance than WSIA → fewer walk-ups | Pre-book 18 to net 15 |
| Buyer thinks Once = WSIA wholesaler tool | Lead every conversation with Sircon, not carrier portals |
| Program MGA wants on-prem | Politely decline; we are cloud-only by design |

## 10. Success metric

By <<MEASUREMENT_DATE>> Target Markets 2026 is a success if (a) ≥ $35K MRR
pipeline created, and (b) ≥ 3 paid pilots signed (target close rate is
intentionally higher than WSIA). If we miss both, we re-evaluate program-MGA
ICP fit before booking 2027.

---

Document version: 0.1 · Owner: Founder/GTM · Last updated: 2026-05-20
