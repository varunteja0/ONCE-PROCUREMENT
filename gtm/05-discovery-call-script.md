# 30-Minute Discovery Call Script — Specialty Insurance MGAs

> Goal of the call: **diagnose**, not pitch. If pain is real and you're talking to the decision-maker, ask for $2,500 by the end. If you don't, you wasted both your time.
> Recording: ask permission ("mind if I record so I capture your workflow accurately?"). Use Otter.ai free tier (300 min/mo).
> Post-call: send the [01-one-page-pitch.md](01-one-page-pitch.md) (converted to PDF) + a Cal.com follow-up slot within 2 hours.

---

## Pre-call (5 min, day before)

- [ ] Pull up their LinkedIn, the company website, and their **carrier appointments page** (usually `/markets` or `/our-carriers`)
- [ ] Count the carrier logos. Note the top 5. **You will reference these by name in the call.**
- [ ] Pull up state licensing — NIPR.com → search the agency → note count of states they're licensed in
- [ ] Pull their LinkedIn job tenure — if <12 months at company, treat as influencer not decision-maker

---

## Call structure (30 min, hard stop)

### Min 0–2: Frame

> "Thanks for the time, {FIRST_NAME}. To stay on the 30 min — I want to spend most of this understanding how your team actually handles carrier-portal data entry today. I'll show a quick 3-minute demo at the end and we can decide together whether it's worth a follow-up. Sound good?
>
> Mind if I record so I capture your workflow accurately? Just for my notes."

### Min 2–18: Diagnose (the 8 questions — DO NOT pitch yet)

Ask, write down, summarize back ("So if I'm hearing right..."). Resist the urge to sell.

1. **"Walk me through what happens when {COMPANY} gets appointed by a new carrier — say a top-5 like {THEIR_TOP_CARRIER}. From the appointment letter arriving to the first policy bound, who does what?"**
   - *Listening for:* whether ops owns it, producer ops, or producers themselves; how long it takes; what gets re-entered.

2. **"How many carrier portals does your team actively log into in a given month?"**
   - *Score:* <20 = under-target ICP, deprioritize. 20–80 = sweet spot. 80+ = enterprise, premium pricing.

3. **"What's the breakdown between AMS-integrated carriers (Applied, Vertafore, etc.) vs direct-carrier portals you have to manually log into?"**
   - *Listening for:* the gap = the wedge. Most MGAs say "30% AMS-integrated, 70% manual." That 70% is what we automate.

4. **"When your E&O cert renews, walk me through what happens. How many portals get updated? Who does it? How long does it take?"**
   - *Listening for:* hours estimate. "10-15 hours over 2 weeks" is the typical answer = $5K of ops time per renewal.

5. **"How do you handle producer license renewals in each state? Especially when one producer is licensed in 30+ states and each carrier needs the update?"**
   - *Listening for:* recurring annual pain.

6. **"If a state DOI auditor or an E&O carrier asked you tomorrow to prove that you submitted updated cert X to carrier Y on date Z, how would you find that evidence today?"**
   - *Listening for:* "scroll through emails" or "we honestly couldn't easily" = our signed-receipt value prop just landed.

7. **"What's the biggest source of friction in this whole workflow? If you could wave a wand and fix one thing, what would it be?"**
   - *Their answer becomes your demo emphasis.*

8. **"Who else inside {COMPANY} is involved in this decision? Is this something you'd green-light yourself for a pilot, or is there a CFO / GC / IT sign-off?"**
   - *If they say "I'd need CFO sign-off" → ask for them on the next call. If "I can decide on a pilot under $X" → proceed to demo and close.*

### Min 18–25: Demo (3–5 min, screen-share)

> "Let me show you what this looks like — keep it brief."

**Demo flow (no slides, live screen):**

1. **30 seconds — the master profile.** Open your AutoApplyAI dashboard, navigate to a (pre-built) Once mockup or just use the existing extension popup. Show: producer license, E&O cert, W-9, banking, in one place. *"This is where {COMPANY}'s master data lives. Update once."*
2. **90 seconds — the autofill.** Open a recorded screen capture (Loom, free) of you logging into a real carrier portal (use a sample / sandbox or a non-production carrier like CNA's broker portal) and the extension auto-filling the 40 fields. *"This is what you'd see — 30 fields in 4 seconds, you click Submit."*
3. **45 seconds — the signed receipt.** Show the JSON: `{supplier_id, portal_id, field_hashes, timestamp, ip, ua, tos_version_hash, signature}`. *"This is what the state DOI auditor sees. Cryptographic proof we submitted exactly this on exactly this date."*
4. **45 seconds — the dashboard.** Show a Notion or hand-built screen with a list of "last 50 submissions, status, receipt link." *"Your operational view."*

> "That's the whole product."

### Min 25–28: Trial close

> "{FIRST_NAME}, based on what you described in the first 20 minutes — the 15 hours a week your team spends, the E&O renewal coming up, the DOI evidence problem — does this look like it solves a real pain at {COMPANY}?"

**Three likely answers:**

- **"Yes" / "Definitely" / "This is amazing":** Move to the ask.
- **"Looks promising, but…":** Acknowledge the objection ("totally fair — let me address that"), then move to the ask once handled.
- **"Not sure / interesting":** *They're polite-declining.* Ask: "What would have to be true for this to be a clear yes?" → either a real objection surfaces or they confirm they're not buying. Don't push past a soft no.

### Min 28–30: Ask

> "Here's what I'd propose. We're taking 5 pilots through end of July, $2,500 setup + $1,500/mo for up to 50 portals, month-to-month after the first 30 days, pilot pricing locked for 24 months.
>
> If {COMPANY} wants slot #2, I'll send the MSA tonight, we kick off Monday, you're submitting through Once by week 3.
>
> What's the call?"

**If yes:** "Great. I'll send the MSA to your email in the next hour. Can I get a P.O. number or wire confirmation by Friday so we lock the kickoff?"

**If "need to think":** "Of course. What specifically do you want to think through? Often I can address it on this call." → if real objection, handle. If "just need to discuss internally," ask for: (a) names of decision-makers, (b) a follow-up call within 7 days on your calendar before you hang up, (c) what specifically they're checking on.

**If "not now":** "Understood. Two questions before we wrap: (1) Is it timing, fit, or budget? (2) When would be the right time to circle back?" → log answer in CSV, move on. Do not chase.

---

## Post-call (within 2 hours — non-negotiable)

- [ ] Send recap email — 5 bullets of what you heard, the proposed pilot, the price, the timeline, attach the [01-one-page-pitch.md](01-one-page-pitch.md) (as PDF), and a Cal.com follow-up slot
- [ ] Update [03-icp-target-list.csv](03-icp-target-list.csv) with call outcome + next action
- [ ] If "yes": send DocuSign MSA same day
- [ ] If "need to think": calendar invite for the follow-up call + add to follow-up sequence

---

## Anti-patterns (do NOT do these)

| Anti-pattern | Why it kills the deal |
|---|---|
| Pitching in min 0 | They haven't surfaced their own pain → your pitch lands as generic noise |
| Demo before diagnosis | You demo the wrong thing; they tune out |
| Mentioning "AI" 5+ times | MGA ops leaders hear "AI" and immediately assume "buggy hallucinating thing that will get us sued" |
| Comparing yourself to Coupa / Ariba | They don't know what those are; they know Applied / Vertafore. Use their vocabulary. |
| Discounting on first call | You haven't earned the right to discount; you anchor low and stay low |
| Not asking for the sale | The single biggest cause of "great call" followed by ghost. **Always end with the ask.** |
| Calling on Friday afternoon | They want to leave the office. Wed/Thu mornings convert 3x better. |
