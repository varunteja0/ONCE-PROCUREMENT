# WSIA Annual Marketplace 2026 — Meeting Plan

> **Conference:** Wholesale & Specialty Insurance Association (WSIA) Annual
> Marketplace, San Diego, **September 2026** (exact dates: <<WSIA_DATES>>).
> **Owner:** <<MEETING_OWNER>>. **Target:** 15 pre-booked meetings →
> $50K MRR of pipeline within 30 days post-show.

WSIA is the wholesale broker / MGA event of the year. ICP for Once is
mid-market MGAs and wholesale brokers running multi-portal carrier
submission pipelines today. This document is the operating plan.

## 1. Goals

| Metric | Target |
|---|---|
| Pre-booked qualified meetings | 15 |
| On-site walk-up demos | 10 |
| Post-show pipeline created | $50K MRR (≈ $600K ARR) |
| Signed paid pilots within 30 days | 2 |
| Logos confirmed for case-study calls | 3 |

A meeting is "qualified" when (a) the attendee runs or owns submission
operations at an MGA or wholesaler, (b) the firm has ≥ 10 producers, and
(c) we have a named portal pain point on file.

## 2. Pre-show plan (T-12 weeks → T-1 week)

### T-12 weeks
- Pull the WSIA attendee list (<<ATTENDEE_LIST_SOURCE>>); enrich with
  Clearbit + LinkedIn Sales Navigator. Target list ≤ 250 firms.
- Tag each firm by portal mix (AmTrust, Markel, AMS360, Applied Epic,
  Sircon). This drives the demo script for each meeting.

### T-8 weeks
- Launch a 4-email outbound sequence to the top 80 firms. Cadence: intro,
  value, social proof, "WSIA meeting?". Owner: <<OUTBOUND_OWNER>>.
- Spin up a dedicated WSIA tenant at `demo.once-procurement.app` seeded
  with the carrier mix above.

### T-4 weeks
- Confirm meeting blocks. Use Calendly with WSIA-only availability:
  Mon evening, Tue + Wed 7am–9am and 4pm–7pm (around the show floor).
- Print 100 leave-behinds (2-pager — see §6).
- Confirm booth / lounge slot (<<BOOTH_OR_LOUNGE_LOCATION>>).

### T-1 week
- Dry-run all 5 portal demos against the live demo tenant. Record a
  fallback screen-capture of each in case Wi-Fi fails.
- Brief everyone on talk-track + objection handling (§5).

## 3. On-show daily cadence

| Slot | Activity |
|---|---|
| 06:30 | Breakfast: open day prep, confirm meetings via Slack |
| 07:00–09:00 | Pre-show meetings (coffee at <<HOTEL_NAME>>) |
| 09:00–16:00 | Show floor + sponsor sessions + walk-ups |
| 16:00–19:00 | After-floor meetings + party-circuit drop-ins |
| 19:00–22:00 | Hosted dinner (max 8 invitees, 2 per night) |
| 22:30 | End-of-day sync: log every meeting into HubSpot |

Hard rule: every conversation gets a HubSpot record by midnight the same
day. No "I'll log it later." Logged = exists.

## 4. The 20-minute meeting script

| Minutes | What we do |
|---|---|
| 0–2 | Context: ask about their current submission pain (open question). Confirm portal mix. |
| 2–10 | **Live demo** of the relevant carrier portal automation in the demo tenant. Submit a real test application end-to-end. Show the signed receipt. |
| 10–15 | Pricing: $X/seat/month + $Y/submission, annual contract, 30-day cancellation. (Exact pricing: <<PRICING_SHEET_REF>>.) |
| 15–20 | Next step: paid pilot ($<<PILOT_PRICE_USD>> for 30 days, 2 portals), signed before end of show or by EOD next Friday. |

If the prospect cannot do a paid pilot, we ask for a calendar slot 14 days
post-show with the operations owner and 2 named carriers they want
automated first.

## 5. Talk-track and objection bank

- "We already use <competitor>." → "What is the moment in their flow you
  re-key data?" (We win on the receipt layer + Sircon/AMS360 coverage.)
- "We tried automation — selectors keep breaking." → Show the 15-min
  smoke-test workflow + Slack drift alerts. This is our moat.
- "Compliance says no scraping." → Show signed Ed25519 receipts +
  CONTRACTS.md + SECURITY.md. Tenant-isolated. SOC2 in <<SOC2_TARGET_DATE>>.
- "Send me a deck." → No deck. We do a 5-minute live demo right now.

## 6. Leave-behind (2-pager)

- Side A: one-line pitch, the 5 supported portals with logos, signed
  receipt diagram, founder photo + email.
- Side B: pilot offer + QR code → `https://once-procurement.app/wsia2026`
  (UTM-tagged landing page; Vercel-hosted; A/B test optional).

## 7. Post-show 14-day playbook

| Day | Action |
|---|---|
| +1 | Personalized recap email to every meeting (HubSpot template, hand-edited intro) |
| +3 | Calendar invite for the agreed next step. If no time held, push to +7. |
| +5 | Send signed pilot SOW (see `gtm/04-msa-template.md`) to confirmed warm leads. |
| +7 | Internal pipeline review — drop anything cold, double down on the rest. |
| +10 | Hand off live pilots to onboarding (CSV + first carrier in 5 days). |
| +14 | Retrospective doc + numbers vs §1 targets. |

## 8. Budget (do not exceed without founder approval)

| Line item | Amount |
|---|---|
| WSIA registration (2 attendees) | $<<REG_COST_USD>> |
| Hotel + travel (2 attendees, 4 nights) | $<<TRAVEL_COST_USD>> |
| Booth / lounge slot | $<<BOOTH_COST_USD>> |
| Hosted dinners (2 nights × 8 guests) | $<<DINNER_COST_USD>> |
| Print leave-behind + swag | $<<PRINT_COST_USD>> |
| **Total** | **≤ $25,000** |

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Demo fails on conference Wi-Fi | MiFi + recorded fallback screen-capture |
| Key prospect cancels last minute | Maintain 5-person standby list, offer dinner |
| Selector drift mid-conference | Beat task + Slack alerts; rollback script on laptop |
| Competitor counter-pitch on floor | Public differentiator sheet (signed receipts + Sircon) |

## 10. Success metric

By <<MEASUREMENT_DATE>> we declare WSIA 2026 a success if and only if
both are true: (a) ≥ $50K of net-new MRR pipeline, and (b) ≥ 2 paid
pilots signed. Anything less and we cut the conference budget for 2027.

---

Document version: 0.1 · Owner: Founder/GTM · Last updated: 2026-05-20
