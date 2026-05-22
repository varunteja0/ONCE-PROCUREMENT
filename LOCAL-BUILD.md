# LOCAL-BUILD.md — Phase L2 (local-only product completion)

> **Mode**: local-only. No git push, no cloud, no deploy. Goal = full
> end-to-end happy-path demo running on `docker compose up` on your
> laptop, with green tests and a recorded walkthrough.
>
> This supersedes `ROADMAP.md` for now (which was the company-formation
> plan). Read after `PLAN.md` (strategy) and `CONTRACTS.md` (code
> rules).

---

## Where we are right now (status snapshot, 2026-05-20)

### ✅ Done

- 25-agent v1 build: 115 files, full repo skeleton (backend, frontend, extension, verifier, oncetax, gtm).
- 10-agent Phase-1 hardening: test scaffolding, observability, CSRF wiring, signing-key registry, ops scripts, landing page.
- Locked decisions: brand = **Once**, domain = **getonce.com**, license = BSL 1.1, first ICP = US trucking MGAs.
- Test scaffolding: ~20 backend, 9 verifier, vault + fillers covered in extension.
- Infra blueprints: Dockerfile, fly.toml, vercel.json, GitHub Actions, all written to disk but **not fired**.

### ⚠ Verified-on-paper but not yet executed

- `pytest`, `npm test`, `tsc`, `vitest`, `npm run build` — never actually run (sandbox has no shell). 85–95% confidence from line-by-line code reading. **First L2 task: actually run them and fix any reds.**
- `docker compose up` has never been started.
- `bootstrap-phase1.py` (creates `scripts/`, `landing/`) needs you to run it once.

### ❌ Gaps that block "real product"

The product cannot be demoed end-to-end today because:

1. **Submitters are deterministic mocks** — they don't navigate anywhere.
   Every `SupplierSubmission` resolves `completed` in 0.1s with a fake
   receipt. No browser opens. No portal is filled. No proof anything
   actually works.
2. **No demo portals to point at** — real AmTrust/Markel portals
   require live credentials + IP whitelist + are ToS-risky to test
   against. We need **local HTML fixtures** that look like those portals
   so the extension + submitter can run against them.
3. **Public receipt UI is raw JSON** — the share URL works but
   auditors see `{"verified":true,...}`. Needs an HTML page.
4. **Extension popup → backend submission round-trip is unverified.**
   The fillers work in-page; we haven't confirmed the popup can dispatch
   a server-side submission and surface the receipt.
5. **Celery worker chain (`enqueue → claim → run submitter → sign →
persist`) has never actually been exercised**, only unit-tested with
   monkey-patched components.
6. **Frontend has the pages but several are stubs** — Submission detail
   polling, Receipt detail with verify widget, COI upload form.
7. **Seed data is too thin to demo** — 1 supplier, 3 portals, no real
   submission history.
8. **No end-to-end test** that exercises:
   `extension → backend → worker → submitter → receipt → verifier`.

---

## Phase L2 — the next milestone

### Definition of done

You can run, on your laptop, in <10 minutes from a fresh `git clone`:

```bash
docker compose up -d            # backend + worker + beat + verifier + db + redis + 4 mock portals + frontend
python scripts/seed_demo_tenant.py
./scripts/smoke_test.sh         # green
open http://localhost:5173      # login, see dashboard, click "New submission"
                                # extension auto-fills a fake AmTrust portal in a real Chrome tab
                                # backend signs the receipt
                                # share URL renders a verifier page showing ✓
```

…and:

```bash
make test                       # ALL backend + frontend + extension + verifier + e2e green (~120 tests)
```

When that demo runs cleanly twice in a row → L2 done.

---

## L2 workstreams (10 parallel tracks)

Each track is independent and ownable by one subagent (mirrors the 10-agent
parallelism we used in Phase 1). Tracks tagged ★ are blockers for the
demo.

### ★ L2.1 — Run the existing test suite + fix all reds _(YOU first, then me)_

The 95%-confidence reading is meaningless until pytest actually runs.

1. `python bootstrap-phase1.py`
2. `cd backend && pip install -r requirements.txt && pytest -q`
3. `cd frontend && npm install && npx tsc --noEmit && npm run lint && npm run build`
4. `cd extension && npm install && npm test && npm run build`
5. `cd verifier && pip install -r requirements.txt && pytest -q`
6. Paste any red output → I send patches.

**Output**: 4 green test suites.

### ★ L2.2 — Local portal fixtures + real Playwright submitters

**The product's spine.** Today's submitters return `{"status":"ok"}` with
no navigation. Replace 4 of 5 with real Playwright runs against local HTML
fixtures we control.

- `fixtures/portals/amtrust/` — static HTML mimicking AmTrust producer
  portal login + new-submission form (fields: producer code, named
  insured, FEIN, effective date, premium, line of business, COI upload).
- `fixtures/portals/markel/` — same pattern, different field labels.
- `fixtures/portals/applied_epic/` — Epic submission form fixture.
- `fixtures/portals/vertafore_ams360/` — AMS360-style.
- `docker-compose.yml`: add 4 nginx services serving these on ports
  8101–8104.
- Real Playwright submitters under `backend/app/automation/submitters/`:
  `amtrust.py`, `markel.py`, `applied_epic.py`, `vertafore_ams360.py`.
  Each subclasses `BaseSubmitter._run_sync`, opens the fixture URL,
  fills the form, captures `submission_reference` (the fixture echoes a
  fake confirmation number), and screenshots for the receipt envelope.
- Submitter timeouts, retry semantics, selector-drift detection logged.
- Integration test per submitter: spins up the fixture container,
  asserts a successful run → receipt → DB row.

**Output**: 4 real submitters, 4 portal fixtures, 4 integration tests.

### ★ L2.3 — Frontend wiring completeness

Make every page actually work, with real loading/error/empty states.

- Login → JWT in `useAuthStore` → redirect to dashboard.
- Dashboard: live count of submissions by status, fed by
  `useSubmissions()` TanStack hook.
- Suppliers list + create + detail (already scaffolded).
- New Submission wizard: pick supplier → pick portals (multi-select) →
  review canonical data → submit → redirect to submission detail.
- Submission detail page: polls `/v1/submissions/{id}` every 2s while
  `status in (queued, running, retrying)`, switches to receipt view when
  `completed`.
- Receipt detail: shows envelope, signature, "Copy public verify URL"
  button.
- Consent ledger page wired to `/v1/consents`.
- All forms use React Hook Form + zod schemas mirrored from backend
  Pydantic.
- Toast notifications on every mutation.

**Output**: every nav-bar link reaches a working page; demo flow clickable.

### ★ L2.4 — Verifier HTML view

Today `verify.getonce.com/verify/<id>` returns JSON. Add an HTML view at
the same URL when `Accept: text/html`:

- Big green check or red X.
- Issued at, supplier, portal, signer key id.
- "Download signed receipt JSON" button.
- "Verify with our public key" code snippet (Python + Node).
- No-JS friendly; HTMX-style server-rendered.

**Output**: `verifier/app/templates/verify.html` + Jinja2 dependency +
test that asserts both content-types work.

### L2.5 — Extension end-to-end

Confirm the extension popup can:

1. Unlock vault with passphrase.
2. List configured suppliers (synced from backend).
3. "Fill this page" button — runs the right filler based on URL match.
4. "Submit to backend" — sends captured data + screenshot to
   `/v1/submissions`.
5. Show last 5 submissions with status.

Tests use jsdom + a vault round-trip + a fake fetch.

**Output**: popup flow tested + manual checklist in `DEMO.md`.

### L2.6 — Data-model completeness

The pitch promises: "risk schedule, loss runs, ACORD forms, COIs,
producer licenses, E&O certs." Models exist for COI only. Add the rest
as **minimal first-class entities** (no parsing AI yet — just upload +
metadata):

- `LossRun` — supplier_id, period_start, period_end, file_url,
  uploaded_at.
- `ProducerLicense` — supplier_id, state, number, expires_at, file_url.
- `EOCertificate` — supplier_id, carrier, limit, expires_at, file_url.
- `AcordForm` — supplier_id, form_type (125/126/127), payload (JSON),
  pdf_url.
- `RiskSchedule` — supplier_id, line_of_business, payload (JSON).

All under `backend/app/models/`. Alembic migration. Pydantic schemas.
CRUD routes under `/v1/{loss-runs,licenses,eo-certs,acord,risk-schedules}`.
Frontend list pages.

**Output**: 5 new models, 1 migration, 5 route modules, 5 frontend
pages. Submission wizard pulls from these.

### L2.7 — Test coverage to ~70 % LOC

Current ~20 backend tests is thin for confidence. Add:

- A test per API route (happy + 401/403/404/422).
- Auth edge cases (expired token, refresh-token replay, locked account).
- Tenant isolation across every new model in L2.6.
- Submission pipeline failure modes (timeout, captcha-blocked, selector
  drift, atomic-claim contention).
- Frontend component tests for SubmissionTable, ConsentLedgerTable,
  EmptyState, ProtectedRoute.
- One Playwright e2e test that runs the whole happy path against docker
  compose.

**Output**: pytest coverage report ≥70 %; vitest coverage ≥60 %; 1 e2e
test green.

### L2.8 — Local observability

- `docker compose up` includes optional `grafana + loki + promtail`
  profile (`--profile observability`) so logs are searchable in browser.
- structlog JSON output everywhere — no raw `print`.
- Request-id middleware: every log line tagged with the X-Request-ID.
- `/v1/metrics` Prometheus endpoint (gated on env flag).
- `make tail` shows colorized backend + worker + verifier logs.

**Output**: Grafana dashboard JSON checked in; logs queryable.

### L2.9 — Demo polish

- `DEMO.md`: 5-minute walkthrough script (every click, every URL).
- `scripts/seed_demo_tenant.py` extended to seed:
  - 1 tenant "Once Demo MGA"
  - 5 suppliers with varied profiles
  - 30 historical submissions (mix of completed / failed / running)
  - 12 receipts (10 signed valid, 2 with tampered payloads for the
    failure demo)
  - 8 COIs (3 expiring within 30 days)
  - 6 producer licenses across 4 states
- `scripts/reset_demo.py` — drops + recreates demo data idempotently.
- `docs/screenshots/` — 8 PNGs captured from the running app for
  README + future investor deck.
- A 60-second OBS/screen-recording shot list documented (so when a
  cofounder candidate or partner asks, you can record it in one take).

**Output**: anyone with the repo can run the demo unaided.

### L2.10 — Dev-experience polish

- `Makefile` (and `tasks.ps1` for Windows): `make test`, `make up`,
  `make seed`, `make demo`, `make reset`, `make tail`, `make fmt`,
  `make lint`.
- `.pre-commit-config.yaml`: ruff, black-check, eslint, prettier-check,
  trufflehog (secret scan).
- `.vscode/launch.json`: debug configs for backend (uvicorn), worker
  (celery), extension popup, e2e test.
- `CHEATSHEET.md`: one-page reference for every command.
- `.env.example` updated as L2 adds new env vars.

**Output**: `git clone && make up && make demo` works first try.

---

## Sequencing (within L2)

```
L2.1 (run tests, fix reds)
   ↓
L2.6 (data models)  ←──┐
L2.2 (submitters)      │  parallel
L2.3 (frontend)        │
L2.4 (verifier UI)     │
L2.5 (extension)   ────┘
   ↓
L2.7 (test coverage)
L2.8 (observability)
L2.9 (demo polish)
L2.10 (dev experience)
```

Order matters: data models first (L2.6) because submitters (L2.2) and
frontend wizard (L2.3) both reference them.

---

## What you do vs. what I do

| Track | You                                        | Me (subagent fleet)                    |
| ----- | ------------------------------------------ | -------------------------------------- |
| L2.1  | Run 4 test suites, paste failures          | Patch any reds                         |
| L2.2  | Tell me if 4 fixtures = right or want more | 4 fixtures + 4 real submitters + tests |
| L2.3  | Click through, list UX bugs                | Implement                              |
| L2.4  | Approve HTML design                        | Build + test                           |
| L2.5  | Load extension in Chrome, click through    | Popup wiring + manual test plan        |
| L2.6  | Confirm 5 models cover the pitch           | Build all 5 end-to-end                 |
| L2.7  | Watch coverage report grow                 | Write tests                            |
| L2.8  | Optional — say if you want Grafana         | Build it gated behind a profile        |
| L2.9  | Record the 60-sec demo once it works       | Write the script + seed                |
| L2.10 | Use `make` commands                        | Author them                            |

**Estimated work**: roughly equivalent to Phase 1 (10-agent batch) +
half. ~150 file changes. Doable in one session if L2.1 turns up no
showstoppers.

---

## Out of scope for L2 (deferred)

- Real portal credentials / live AmTrust calls (sales-stage work).
- Vanta / SOC 2 / cyber insurance (compliance is Phase 3).
- Sales motion, cofounder hunt, fundraise (Phase 2+ of company plan).
- AI-powered field extraction from PDFs (Phase 4).
- Multi-region deploys (we're local only).
- OnceTax (Wedge B) — parallel-run, separate scope.

---

## Risks + mitigations

| Risk                                                    | Mitigation                                                                                                                       |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| L2.1 turns up cascading failures                        | I patch in batches; we don't move on until 4 suites green.                                                                       |
| Local portal fixtures don't represent real portals well | Mark them clearly as **demo fixtures**, NOT certified replicas; real submitters get rewritten when sales-stage credentials land. |
| Playwright in Docker is heavyweight (~1GB image)        | Already accepted — image stays <1.2GB per A8 estimate.                                                                           |
| Coverage push at L2.7 surfaces design bugs              | Good — better now than at Phase 3 (sales).                                                                                       |
| You don't have time to actually click through           | Demo seed + automated e2e test means even hands-off, `make test` proves the flow works.                                          |

---

## After L2 → L3 preview (still local-only)

When L2 is done, the natural next local milestone is **L3: dogfood for
30 days as if you were a real MGA**. You run the product daily, file
real internal submissions to local fixtures, generate real (test)
receipts, find every UX paper-cut. Then we polish based on observed
friction. **No deploy still.**

After L3 ships clean → that's when company-formation Phase 0 (Stripe
Atlas, sales stack) becomes worth your money.

---

_Document version: 1.0 · 2026-05-20 · Local-only build mode._
