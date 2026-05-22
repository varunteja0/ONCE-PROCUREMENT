# UX Log — Once Dogfood Journal

**Purpose**: Capture every papercut, slow path, confusing label, missing affordance, or "I expected X but got Y" moment encountered while using Once daily for 30 days. This log is the *only* legitimate input to the `l3-1-papercut-fixes` batch — no opinions, no speculation, no design-team fantasies. Only things observed during real use.

## How to use this log

1. **Block 30 minutes/day** to actually run the product end-to-end (`make up && make seed && make demo`, then click through real flows).
2. **Log immediately** when something annoys you — don't batch at end of day, the friction details fade.
3. **One row per papercut.** No bundling. If you find three things on the same screen, log three rows.
4. **Severity scale**: P0 = blocks me from finishing the flow · P1 = adds visible friction · P2 = aesthetic / nit.
5. **Effort estimate**: S = ≤30min · M = half a day · L = multi-day.
6. At end of week, triage: anything P0 goes into the next sprint, P1s get batched, P2s get a quarterly polish pass.

## Schema

| Date | Surface | Flow | What I expected | What happened | Severity | Effort | Status | Fix PR |
|------|---------|------|-----------------|---------------|----------|--------|--------|--------|

## Log

| Date | Surface | Flow | What I expected | What happened | Severity | Effort | Status | Fix PR |
|------|---------|------|-----------------|---------------|----------|--------|--------|--------|
| _e.g. 2026-05-22_ | _Cockpit · Supplier detail_ | _Open a supplier and re-trigger submission_ | _One-click "Re-submit" button_ | _Had to navigate to submissions tab, find latest, then 3-dot menu → Re-run_ | _P1_ | _S_ | _open_ | _—_ |

## Daily session header template

Copy this block at the start of each session so the log doubles as a journal.

```
### YYYY-MM-DD — Day N

- Started: HH:MM
- Persona: (carrier-ops / mga-owner / broker)
- Goal: (e.g. "onboard 3 suppliers and submit COIs to AmTrust")
- Build: `git rev-parse --short HEAD` (or local commit-less marker)
- Outcome: (✅ goal hit · ⚠️ partial · ❌ blocked)
- Notes:
```

## Weekly triage (every Friday)

- Count of new P0s this week:
- Count of new P1s this week:
- Carry-over from last week:
- Top three regressions:
- Next week's focus:

## Rules of engagement

- **No logging hypothetical issues.** "It would be cool if…" goes in `ROADMAP_TO_BILLION.md`, not here.
- **Repro steps must be in the row.** If you can't repro it, it's not a bug, it's a vibe.
- **Don't fix while you log.** Triage runs separately, otherwise you'll lose flow context.
- **The log is the source of truth.** Anything not in here didn't happen.
