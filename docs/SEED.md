# Realistic Demo Seed

`backend/scripts/seed_realistic.py` populates the **Demo Specialty MGA**
tenant with a deterministic 3-month transcript so anyone running
`make seed-realistic` sees a product that looks like a real customer's
book of business — not a test fixture.

## What it creates

| Entity                       | Count | Notes |
|---|---:|---|
| Tenant                       |   1   | `demo-specialty-mga` |
| Users (owner / admin / 2 ops)|   4   | `owner@example.com`, etc. |
| Portals                      |  10   | 5 supported, 5 "coming soon" |
| Suppliers                    |  50   | 60% small / 30% mid / 10% large |
| Consent records              | ≥35   | one per supplier that ever submitted |
| Certificates of Insurance    | 120   | **18 expiring within 30 days**, 6 expired |
| Producer licenses            |  80   | every one of CA/TX/FL/NY/IL/GA/PA/OH/NC/MI/WA/AZ present |
| E&O certificates             |  35   | |
| ACORD forms                  |  60   | 125/126/127 weighted |
| Risk schedules               |  45   | vehicle / employee / location |
| Loss runs                    | 200   | spanning 3 years |
| Submissions                  | 800   | 72% completed / 8% failed / 4% running / 16% queued |
| Submission receipts          | 576   | one per completed submission — **12 tampered for the failure-demo flow** |
| Audit log entries            | 150   | gives the audit page real density |

Failed submissions follow the realistic mix: 35% captcha, 25% auth_failed,
20% selector_drift, 15% timeout, 5% network. Each one carries a human-
readable `last_error` so the dashboard reads like a production tool.

Submission timestamps follow US business-day skew: weekends and federal
holidays are skipped, times cluster between 08:00 and 18:00 US Eastern,
and recent days are 3× more likely than days at the back of the window.

## How to run

```bash
make seed-realistic                # default: SEED_SECRET=42, 50 suppliers, 90 days
make seed-reset-realistic          # remove only seed-marker rows

# Direct invocation (Windows or anywhere without Make):
python backend/scripts/seed_realistic.py
python backend/scripts/seed_realistic.py --seed 99 --suppliers 100 --days 180
python backend/scripts/seed_realistic.py --dry-run     # counts only
python backend/scripts/seed_realistic.py --reset       # reset then re-seed
python backend/scripts/seed_realistic_reset.py         # standalone reset
```

The PowerShell wrapper exposes the same operations:

```powershell
.\tasks.ps1 seed-realistic
.\tasks.ps1 seed-reset-realistic
```

> The original `make seed` target still runs the thin `seed_demo_tenant.py`.
> The realistic seed lives behind its own target so smoke tests stay fast.

## Determinism contract

* Every primary key is `uuid5(namespace, "{SEED_MARKER}|{kind}|{ordinal}")`,
  so the same `SEED_SECRET` always produces identical UUIDs.
* All randomness flows through a single `random.Random` seeded from
  `hashlib.sha256(SEED_MARKER || SEED_SECRET)`. No reliance on `hash()`,
  set iteration order, or wall-clock time *for content* (timestamps use
  `datetime.now()` for the window but are bucketed deterministically).
* The Ed25519 signing key for receipts is itself derived from
  `SEED_SECRET` (`sha256(SEED_MARKER || "signing" || SEED_SECRET)`),
  so receipt signatures verify identically across runs.
* The seed script logs `__random_state_hash__` — two runs with the same
  inputs must produce the same hash. Tests assert this.

## Idempotency

* `seed_realistic.py` checks for the deterministic tenant ID. If found,
  the run is a **no-op** (logged as `seed_realistic_skip_existing`).
* `seed_realistic_reset.py` deletes only the IDs the seed would emit
  under the current `SEED_MARKER`. **Rows created by humans in the real
  app are never touched.** The reset enumerates ~25 000 candidate IDs
  per entity (a safe upper bound) and uses `DELETE … WHERE id IN (…)` —
  unknown IDs are silently ignored.
* To regenerate from scratch:

  ```bash
  python backend/scripts/seed_realistic.py --reset
  ```

## Adding new entities safely

1. Add a generator helper to `backend/scripts/_seed_data/generators.py`.
2. Compute the row's PK with `ids.of("<kind>", ordinal)` in
   `seed_realistic.py` — choose a `<kind>` string that doesn't collide
   with the existing ones in `seed_realistic_reset._id_space`.
3. Add the model + key to the `_DELETE_ORDER` tuple in the reset script,
   in correct FK-dependency order (children before parents).
4. Bump `SEED_MARKER` from `L3-2-realistic-v1` to `L3-2-realistic-v2`
   **only when** existing seeded data is no longer compatible with the
   new entity layout — that way the old reset can still clean up the
   previous generation.
5. Add an assertion in `backend/tests/test_seed_realistic.py` so the new
   counts/shape are part of the determinism contract.

## The six demo moments the seed enables

1. **Suppliers → COIs:** the 18 yellow "expiring in <30 days" badges
   make the renewal-monitor product feel alive.
2. **Submissions table:** ~576 green completed rows next to 64 red
   failed rows with human-readable error reasons (captcha, drift, etc.).
3. **Receipt verifier:** pick any completed receipt → /verify returns
   `verified: true`. The 12 tampered receipts return `verified: false`,
   demoing the tamper-evident audit trail.
4. **Consent ledger:** 35+ signed `submit_on_behalf` consents prove the
   product respects producer permissions before automating anything.
5. **Producer licenses:** every state in the top-12 trucking corridor is
   represented — useful when prospects ask "do you handle multi-state?".
6. **Audit log:** 150 events spread across 90 days show the kind of
   compliance trail a SOC2 auditor would want to see day one.
