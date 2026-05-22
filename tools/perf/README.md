# `tools/perf/` — local performance harness

A locust-based load harness for baselining the demo happy-path under
synthetic load. Net-new files only, no edits to `backend/app/**`,
`frontend/src/**`, `extension/src/**`, `verifier/app/**`, or `oncetax/**`.

## What it covers

Two user classes drive the canonical demo flow described in
[`docs/DEMO.md`](../../docs/DEMO.md):

1. **`AuthenticatedUser`** — logs in once as `brittany@demo.mga`
   against `POST /v1/auth/login`, then exercises the read-heavy supplier
   desk surfaces plus an occasional supplier create:
   - `GET  /v1/suppliers` (weight 5)
   - `GET  /v1/suppliers/{id}` (weight 3)
   - `GET  /v1/submissions` (weight 3)
   - `GET  /v1/receipts/{id}` (weight 2)
   - `POST /v1/suppliers` (weight 1) — fresh UUIDs, no collision
2. **`AnonymousVerifierUser`** — hits the public verifier on `:8080`:
   - `GET /verify/{receipt_id}` (Accept: application/json) (weight 4)
   - `GET /verify/{receipt_id}.html`                       (weight 2)
   - `GET /verify/{receipt_id}/badge.svg`                  (weight 1)
   - `GET /verify/{receipt_id}/og.svg`                     (weight 1)

Both classes use `wait_time = between(1, 3)` so we model a realistic
think-time, not synthetic max-throughput.

## Prereqs

```bash
make up                 # stack on :8000 (backend) and :8080 (verifier)
make seed-realistic     # 50 suppliers, ~150 submissions, ~80 receipts
python tools/perf/generate_seed_manifest.py    # writes seed_manifest.json
```

`generate_seed_manifest.py` reads `DATABASE_URL`
(default `postgresql://once:once@localhost:5432/once`) and pulls 50
supplier ids, 50 submission ids, 50 receipt ids, and the 4 demo user
emails for the `Demo Specialty MGA` tenant. It is **idempotent** — re-run
it whenever you re-seed. If the DB is unreachable it writes a safe-default
manifest so the locustfile still imports cleanly.

## Targets

| Target               | What it does                                              |
| -------------------- | --------------------------------------------------------- |
| `make perf-smoke`    | 5 users × 60s ramp 1/s — quick "is anything on fire" run  |
| `make perf-baseline` | 50 users × 5min ramp 2/s — the full baseline run          |
| `make perf-report`   | Diff the last baseline vs `baseline.csv` (committed)      |

Outputs land in `tools/perf/.last_smoke*` and `tools/perf/.last_baseline*`
(CSV + HTML), which are gitignored.

## Interpreting results

The committed `baseline.csv` is the reference. Per endpoint we track
`p50 / p95 / p99 / rps / failure %`.

### What "good" looks like

| Endpoint class          | p50      | p95      | p99      |
| ----------------------- | -------- | -------- | -------- |
| `GET /v1/*`             | < 50 ms  | < 200 ms | < 500 ms |
| `GET /verify/*`         | < 50 ms  | < 200 ms | < 500 ms |
| `POST /v1/*` (writes)   | < 100 ms | < 400 ms | < 1.0 s  |

Write endpoints get a 2× budget because they hit the DB transactionally
and emit audit-trail + (sometimes) signing work.

### What counts as a regression

`compare.py` flags an endpoint **RED** when either:

* `p95` > `baseline p95 + 20 %`, or
* `failure %` > `baseline failure % + 0.5 pp`

Any RED row makes `make perf-report` exit `1` so this can gate CI later.

## Baseline regeneration workflow

Real numbers only — never hand-edit `baseline.csv`.

```bash
make up && make seed-realistic
python tools/perf/generate_seed_manifest.py
make perf-baseline
# review tools/perf/.last_baseline.html — confirm no failures, sane RPS
cp tools/perf/.last_baseline_stats.csv tools/perf/baseline.csv
```

Commit the new `baseline.csv` only when the regression is intentional
(e.g. a feature that legitimately moves p95) and call it out explicitly
in the PR description.

## Why not k6?

k6 is a separate Go binary that the team would need to install out-of-band.
Locust is a single `pip install` away and reuses the backend venv we
already have. Throughput per generator node is lower than k6, but for a
local baseline harness — 5–50 concurrent users — locust is more than
enough and keeps the dependency surface flat.
