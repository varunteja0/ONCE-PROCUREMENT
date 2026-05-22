# LOCAL-BUILD.md — current local-build status (May 2026)

> **Mode**: local-only. No production cloud is in scope here. Goal = full
> end-to-end happy-path running on `docker compose up` on your laptop,
> with green test suites and a recorded walkthrough.
>
> This supersedes the company-formation `ROADMAP.md` for day-to-day work.
> Read after `PLAN.md` (strategy) and `CONTRACTS.md` (code rules).
>
> History: this document was written for the very first L2 push when most
> things were stubs. The original L2 plan is preserved further down for
> historical reference; the **status snapshot below is the current truth**.

---

## Status snapshot — 2026-05-22

### ✅ Done and verified by tests

**Suites currently green on `main`:**

| Suite     | Count | How to run                                                              |
| --------- | ----- | ----------------------------------------------------------------------- |
| backend   | 1144  | `cd backend && .\.venv\Scripts\python.exe -m pytest -q`                 |
| extension | 84    | `cd extension && npx vitest run`                                        |
| frontend  | 165   | `cd frontend && npx vitest run`                                         |
| verifier  | ~10   | `cd verifier && pytest -q`                                              |

**Real Playwright submitters** (replace the old deterministic mocks; live
under [`backend/app/automation/submitters/`](backend/app/automation/submitters/)
with integration tests under [`backend/tests/integration/`](backend/tests/integration/)):

- Vertafore AMS360 — `test_vertafore_submitter.py`
- Sircon — `test_sircon_submitter.py`
- AmTrust — `test_amtrust_submitter.py`
- Applied Epic — `test_applied_epic_submitter.py`
- Markel — `test_markel_submitter.py`
- Plus a long-running soak suite — `test_submitter_soak.py`
  (gate behind `RUN_INTEGRATION_TESTS=1` / `RUN_SOAK_TESTS=1` and the
  nginx portal fixtures in [`fixtures/portals/`](fixtures/portals/)).

**Backend feature surface that's wired and tested:**

- Cockpit (multi-tenant operator console: act-as, compliance, MFA routes,
  tenant deletion) — `app/api/cockpit/`, `test_cockpit_*.py`.
- Billing (Stripe webhooks + plan management) — `app/api/billing.py`,
  `test_billing_api.py`, `test_billing_webhooks.py`.
- Operator MFA / TOTP — `test_operator_auth_mfa.py`, `test_cockpit_mfa_routes.py`.
- Audit hash-chain + Celery rebuild job + export task —
  `test_audit_chain.py`, `test_audit_hash_job.py`, `test_audit_export_task.py`.
- Verifier API keys (rotation + scope checks) — `test_verifier_api_keys.py`.
- Imports pipeline with AV scanning + per-tenant isolation —
  `test_import_av_integration.py`, `test_imports_tenant_isolation.py`.
- Inbound email routing (IMAP + Postmark webhook + attachment storage +
  per-tenant isolation) — `test_imap_client.py`, `test_postmark_webhook.py`,
  `test_inbound_email_service.py`, `test_inbound_attachments.py`,
  `test_inbound_tenant_isolation.py`.
- Data-model surface from the original L2.6: COI, LossRun, ProducerLicense,
  EOCertificate, AcordForm, RiskSchedule — all with CRUD routes + tests.
- Sanctions / OFAC screening — `test_sanctions.py`.
- Receipts signing + key registry + rotation tasks — `test_receipts_signing.py`,
  `test_signing_key_registry.py`, `test_key_rotation_tasks.py`.

**Extension popup ↔ backend round-trip:**

- Capture flow uses canonical `payload` + `consent_record_id` (replaces the
  earlier `fields_submitted` shape) — see `extension/src/lib/api.ts` and
  the matching backend `app/api/submissions.py`.
- New **Receipts screen** in the popup (`extension/src/popup/screens/Receipts.tsx`)
  surfaces last N submissions with status + verify-URL copy.
- Typed `profile.active` message between content script and background;
  receipts are cached under `once.cache.receipts` after each drain.
- Background portal-detect now uses `sender.tab.id` (was inferred), and
  cached portals live under `once.cache.portals` so the popup can resolve
  `portal_id` without a network round-trip.
- Tests under `extension/tests/background/`, `extension/tests/popup/`,
  `extension/tests/lib/` cover the capture, API call, Receipts screen,
  and the typed messaging contract.

**Frontend:**

- Cockpit, billing, audit, consents, submissions, suppliers, imports,
  inbound, COIs, loss runs, producer licenses, E&O, ACORD, risk schedules
  pages all wired against the backend with TanStack Query.
- 165 Vitest tests across components, hooks, and route shells.

**Verifier:**

- HTML + JSON views at `verifier/app/templates/verify.html`.
- API-key auth (issued by backend) with scope check + per-tenant rate
  limit. Tested against the canonical-JSON byte-match contract.

### ⚠ Still work-in-progress / not in scope yet

- End-to-end Playwright run that exercises
  `extension → backend → worker → submitter → receipt → verifier`
  inside `docker compose` is wired piece-by-piece but no single CI lane
  runs the whole chain yet.
- Optional observability profile (`docker compose --profile observability`)
  ships structlog + a Loki/Promtail/Grafana stack — checked in but only
  smoke-tested manually.
- Demo seed (`scripts/seed_demo_tenant.py`) is current; the 60-second
  screencast in [`docs/SCREENCAST_SHOTLIST.md`](docs/SCREENCAST_SHOTLIST.md)
  has not been re-recorded since the L2.5 ext↔backend changes.

### ❌ Out of scope for this build mode

- Real portal credentials / live AmTrust / Markel calls (sales-stage).
- Vanta / SOC 2 / cyber insurance (Phase 3).
- Sales motion, cofounder hunt, fundraise (Phase 2+).
- AI-powered PDF field extraction (Phase 4 — placeholder service exists
  but is deterministic).
- Multi-region deploys (this doc covers local only).
- OnceTax (Wedge B) — parallel-run, separate scope, lives under
  [`oncetax/`](oncetax/).

---

## Definition of done (still the bar)

You can run, on your laptop, in <10 minutes from a fresh `git clone`:

```powershell
docker compose up -d            # backend + worker + beat + verifier + db + redis + nginx fixtures + frontend
python scripts/seed_demo_tenant.py
./scripts/smoke_test.sh         # green
start http://localhost:5173     # login, see dashboard, click "New submission"
                                # extension auto-fills a fake portal in a real Chrome tab
                                # backend signs the receipt
                                # share URL renders a verifier page showing ✓
```

…and:

```powershell
make test                       # all 4 suites green
```

When that demo runs cleanly twice in a row → L2 is "done enough" to move
to L3 (dogfood for 30 days).

---

## Historical L2 plan (for reference)

> Everything below this line is the **original** L2 work-breakdown that
> was the source-of-truth in early-May 2026. It is preserved so you can
> trace why a given module exists, but it no longer drives day-to-day
> work — the status snapshot above does.

### L2 workstreams (10 parallel tracks, original plan)

Each track was independent and ownable by one subagent (mirrors the
10-agent parallelism we used in Phase 1). Tracks tagged ★ were demo
blockers.

#### ★ L2.1 — Run the existing test suite + fix all reds

Initial bring-up: install deps, run pytest / vitest, fix any reds.
**Status: done.** All four suites are green (see the table above).

#### ★ L2.2 — Local portal fixtures + real Playwright submitters

Replace deterministic stubs with real Playwright runs against local HTML
fixtures we control.

- `fixtures/portals/amtrust/`, `markel/`, `applied_epic/`,
  `vertafore_ams360/`, `sircon/` — static HTML mimicking each carrier's
  producer-portal login + new-submission form.
- `docker-compose.yml`: nginx services serving these fixtures.
- Real Playwright submitters under `backend/app/automation/submitters/`:
  `amtrust.py`, `markel.py`, `applied_epic.py`, `vertafore_ams360.py`,
  `sircon.py`. Each subclasses `BaseSubmitter._run_sync`, opens the
  fixture URL, fills the form, captures `submission_reference` (the
  fixture echoes a fake confirmation number), and screenshots for the
  receipt envelope.
- Integration test per submitter under `backend/tests/integration/`.

**Status: done.** 5 submitters + 5 fixtures + 5 integration tests + soak.

#### ★ L2.3 — Frontend wiring completeness

Make every page actually work, with real loading/error/empty states.

- Login → JWT in `useAuthStore` → redirect to dashboard.
- Dashboard: live count of submissions by status, fed by
  `useSubmissions()` TanStack hook.
- Suppliers list + create + detail.
- New Submission wizard.
- Submission detail polls every 2 s while pending.
- Receipt detail with "Copy public verify URL" button.
- Consent ledger page wired to `/v1/consents`.
- All forms use React Hook Form + zod schemas mirrored from backend
  Pydantic.

**Status: done.** 165 Vitest tests across the surface.

#### ★ L2.4 — Verifier HTML view

Today `verify.getonce.com/verify/<id>` returns JSON. Add an HTML view at
the same URL when `Accept: text/html`.

**Status: done.** `verifier/app/templates/verify.html` + Jinja2 + tests
asserting both content-types.

#### L2.5 — Extension end-to-end

Confirm the extension popup can:

1. Unlock vault with passphrase.
2. List configured suppliers (synced from backend).
3. "Fill this page" — runs the right filler based on URL match.
4. "Submit to backend" — sends captured `payload` + `consent_record_id`
   to `/v1/submissions`.
5. Show last 5 submissions + receipts.

**Status: done.** Popup screens for Setup, Home (capture), Submissions,
Receipts; background handlers for `submission.capture`, `api.call`,
`portal.detect`, `profile.active`; all under test in
`extension/tests/`.

#### L2.6 — Data-model completeness

5 new first-class entities: `LossRun`, `ProducerLicense`, `EOCertificate`,
`AcordForm`, `RiskSchedule` — models, migrations, schemas, CRUD routes,
frontend pages.

**Status: done.** All 5 live with route modules and tests.

#### L2.7 — Test coverage push

A test per API route (happy + 401/403/404/422); auth edge cases; tenant
isolation across every new model; submission pipeline failure modes;
component tests on the frontend; one end-to-end Playwright happy path.

**Status: substantially done.** 1144 backend + 165 frontend + 84
extension tests. Full e2e docker-compose Playwright lane is the next gap.

#### L2.8 — Local observability

`docker compose --profile observability` adds loki + promtail + grafana.
structlog JSON everywhere; request-id middleware; `/v1/metrics`
Prometheus endpoint gated on env flag.

**Status: done.** Grafana dashboard JSON under `ops/observability/`.

#### L2.9 — Demo polish

`DEMO.md` walkthrough; `scripts/seed_demo_tenant.py` seeds a tenant
"Once Demo MGA" with 5 suppliers, 30 historical submissions, 12 receipts
(2 tampered for the failure demo), 8 COIs, 6 producer licenses;
`scripts/reset_demo.py` is idempotent; screenshots in
`docs/screenshots/`; shot list in `docs/SCREENCAST_SHOTLIST.md`.

**Status: done (seed + script + shot list); re-record pending.**

#### L2.10 — Dev-experience polish

`Makefile` + `tasks.ps1` for Windows: `make test`, `make up`, `make seed`,
`make demo`, `make reset`, `make tail`, `make fmt`, `make lint`,
`make doctor`. `.pre-commit-config.yaml` and `.vscode/launch.json`
configured. `CHEATSHEET.md` one-pager.

**Status: done.**

---

## After L2 → L3 preview (still local-only)

L3 = **dogfood for 30 days as if you were a real MGA**. Run the product
daily, file real internal submissions to local fixtures, generate real
(test) receipts, find every UX paper-cut. Polish based on observed
friction. **No deploy still.**

After L3 ships clean → company-formation Phase 0 (Stripe Atlas, sales
stack) becomes worth your money.

---

_Document version: 1.1 · 2026-05-22 · Local-only build mode._
