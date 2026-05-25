# Cold Email Templates — Specialty Insurance MGAs

> Rules: **plaintext only, no images, no tracking pixels, no links in first email, no "AI" in subject line, no buzzwords ("synergy", "leverage", "solutions", "platform"). Send from a real Gmail/Outlook (not Mailchimp/HubSpot). Personalize line 1 every time.**
> Best send times: Tue/Wed/Thu 7:30am–9:00am recipient local time. Avoid Mon mornings (inbox triage) and Fri afternoons.
> Cap: 30 cold sends/day from one address (anything more = spam folder).

---

## §A — Pain-trigger subject (use for prospects you can verify have 30+ carrier appointments)

**Subject:** Question about your carrier portal workflow at {COMPANY}

> Hi {FIRST_NAME},
>
> Saw on your LinkedIn that you run ops at {COMPANY} — congrats on the {RECENT_CARRIER_APPOINTMENT_OR_STATE_LICENSE_OR_HEADCOUNT_GROWTH}.
>
> Quick one — how many hours a week does your team spend re-entering producer license, E&O, and W-9 data into carrier portals (Applied, Vertafore, direct carrier sites, etc.)?
>
> Asking because I just built a done-for-you service that handles those submissions across the carrier portals you're appointed at (3 production-tested today — Applied Epic, Vertafore AMS360, AmTrust — with a documented add-a-portal SDK so we ship the rest as customers request them) and emits a signed audit receipt for each one (for DOI exams and E&O defense). Price is $1,500/mo. Pilot slots open through July.
>
> If this is a real pain at {COMPANY}, worth a 20-minute call?
>
> Varun

---

## §B — Curiosity / data-question subject (use when you don't know their appointment count)

**Subject:** How {COMPANY} handles E&O recerts across carriers

> Hi {FIRST_NAME},
>
> I'm researching how mid-market MGAs handle the annual E&O + producer license recert push to each appointed carrier. Most of the ops leaders I've spoken with say it's 10–20 hours a week of clerical re-entry, fragmented across Applied, Vertafore, Sapiens, and direct carrier portals.
>
> Two questions:
>
> 1. Is that roughly your experience at {COMPANY}?
> 2. Have you tried any tooling for it, or is it all manual?
>
> I'm asking because I built something that solves it — happy to share if it's a real pain, happy to leave you alone if it isn't.
>
> Varun

---

## §C — Direct-offer subject (use for warm intros or LinkedIn-connected prospects)

**Subject:** Pilot offer for {COMPANY} — 70% off ops time on carrier portals

> Hi {FIRST_NAME},
>
> Brief: I'm running 5 pilots of a service that fills your producer license, E&O cert, COI, W-9, and banking data into every carrier portal you're appointed at — Applied, Vertafore, Sapiens, Duck Creek, plus direct carriers. Each submission gets a cryptographically signed audit receipt (for state DOI exams + E&O claims).
>
> Pilot pricing: $2,500 setup + $1,500/mo. Covers up to 50 portals. Month-to-month. Pilot pricing locked for 24 months.
>
> Compares to ~$5K/mo loaded cost of one ops FTE doing the same work.
>
> Worth 20 minutes? If yes: cal.com/varun-once/discovery
>
> Varun

---

## Follow-up #1 (send 4 business days after Day-3 email, only if no reply)

**Subject:** Re: {ORIGINAL SUBJECT LINE}

> Hi {FIRST_NAME},
>
> Bumping this in case it got buried. Two-sentence version:
>
> If your team spends 10+ hours/week re-entering MGA data into carrier portals, I have a $1,500/mo done-for-you service that takes that to under an hour. 5 pilot slots through July.
>
> Worth a 20-min call?
>
> Varun

---

## Follow-up #2 (send 5 business days after Follow-up #1, only if still no reply — LAST email)

**Subject:** Closing the loop, {FIRST_NAME}

> Hi {FIRST_NAME},
>
> Last note from me — I won't keep pinging.
>
> If carrier portal data entry isn't a meaningful pain at {COMPANY}, no worries, ignore this.
>
> If it is and the timing's just off, here's my calendar for whenever it's relevant: cal.com/varun-once/discovery
>
> Varun

---

## LinkedIn DM (send after connection accepted, 2 business days later)

> Hi {FIRST_NAME}, thanks for connecting.
>
> Quick context — I'm building a service for specialty MGAs that automates the carrier-portal recert grind (producer license, E&O, W-9, COI across Applied/Vertafore/direct carriers). Cryptographically signed receipt for each submission for DOI/E&O defense.
>
> Pilot price $1,500/mo. Curious if portal data entry is a real pain at {COMPANY} — if yes, happy to share a one-pager. If not, no worries.

---

## Reply-triggered objection handling cheat-sheet

| Objection                                                  | Reply                                                                                                                                                                                                                                   |
| ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| _"We use Applied Epic for this already"_                   | Applied stores the data but doesn't push it to carrier portals on your behalf — your team still does the submission. We're the layer between your AMS and the 80+ external portals. Happy to show a 5-min demo.                         |
| _"How is this different from Vertafore Producer Manager?"_ | Vertafore PM handles license tracking + producer onboarding. We handle the outbound submission of that data to every carrier portal you're appointed at, plus the signed audit receipt for DOI defense. Complementary, not competitive. |
| _"We need to evaluate security/compliance first"_          | Absolutely — we're targeting SOC 2 Type I in H2 2026, GLBA-aligned today, never store unencrypted PII, never share data across MGA customers. Happy to send the security questionnaire response we've prepared.                         |
| _"Send me more info, I'll review"_                         | Attached the one-pager. The fastest way to know if it's a fit is a 20-min call — I can show you a live demo against a portal you actually use. Pick any slot: cal.com/varun-once/discovery                                              |
| _"Pricing seems high / can you discount"_                  | Pilot pricing IS the discount — $1,500/mo locked for 24 months. Standard pricing in August is $2,500/mo. The economics: one ops FTE costs ~$5K/mo loaded; we replace 70% of that bandwidth. Happy to walk through ROI on the call.      |
| _"Not now / try us in 6 months"_                           | Understood. Two things: (1) pilot slots are 5 total and 24-month price lock; if you wait you're at standard pricing. (2) Can I send a 60-second check-in in Q4?                                                                         |

---

## Tracking — log every send in [03-icp-target-list.csv](03-icp-target-list.csv)

Required columns to fill on every send:

- `email_sent_at` (ISO datetime)
- `email_variant` (A / B / C / F1 / F2)
- `linkedin_connected_at`
- `linkedin_dm_at`
- `replied_at`
- `call_booked_at`
- `outcome` (no_reply / not_interested / call_booked / not_decision_maker / pilot_won / pilot_lost)

Weekly Friday review: aggregate reply rate by variant; double down on the winning variant Week 2.
