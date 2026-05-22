# Once — End-to-End Demo Walkthrough

90-second product tour you can run on a fresh laptop. This is the script we follow on every sales call. If a step fails on `main`, file a P0 in [`docs/UX_LOG.md`](./UX_LOG.md) before continuing — the demo path is the highest-priority happy path in the whole repo.

For the recording version of this script (frame-by-frame for screencast capture), see [`docs/SCREENCAST_SHOTLIST.md`](./SCREENCAST_SHOTLIST.md).

## 0. Pre-flight (≤2 min, one-time)

```bash
make doctor             # validates Docker, Node 20+, Python 3.12+, ports 5173/8000/8080
make setup              # bootstraps backend venv, FE node_modules, Playwright browsers
```

If `make doctor` complains, fix the underlying issue before continuing. The demo assumes a clean machine.

## 1. Boot the stack (≤45s on warm Docker cache)

```bash
make up                 # backend + worker + beat + frontend + db + redis + 5 nginx fixture portals
make ps                 # confirm all 11 services are "running" / "healthy"
```

Wait until `make ps` shows every row as `running` + `healthy`. Open:

- **Frontend**: <http://localhost:5173>
- **API docs**: <http://localhost:8000/docs>
- **Verifier**: <http://localhost:8080/healthz>

If any of these don't load, run `make logs` and search for `ERROR` / `Traceback`.

## 2. Seed the demo tenant (≤30s)

```bash
make seed-realistic     # 50 suppliers, 90-day transcript, signed receipts, hash-chained audit
```

This is the **L3.2 realistic seed** — not the toy seed. It produces:

- 1 tenant: `Demo Specialty MGA`
- 4 users: `brittany@demo.mga` (ops), `dan@demo.mga` (broker), `carmen@demo.mga` (carrier), `audit@demo.mga` (read-only auditor)
- 50 suppliers across trucking, contracting, hospitality
- ~150 submissions across 5 portals over 90 days
- ~80 receipts (signed Ed25519)
- ~120 COI/EO/license documents
- 12 inbound emails (4 routed, 6 needs-review, 2 spam)
- 1 Stripe customer with active `pro` subscription (mock mode)

**Idempotent** — re-running `make seed-realistic` produces the same UUIDs and never doubles up. To wipe only seed data without touching user-created rows, run `make seed-reset-realistic`.

## 3. Sign in (15s)

Open <http://localhost:5173/login> and use:

| Persona | Email | Password | Why |
|---------|-------|----------|-----|
| Ops lead | `brittany@demo.mga` | `dogfood-2026` | Primary demo persona — runs the supplier desk |
| Broker | `dan@demo.mga` | `dogfood-2026` | Shows the broker-side onboarding view |
| Carrier ops | `carmen@demo.mga` | `dogfood-2026` | Shows the receipt verifier from a relying-party angle |
| Auditor | `audit@demo.mga` | `dogfood-2026` | Read-only — shows the audit/compliance surfaces |
| **Cockpit operator** | `cockpit@once.local` | `cockpit-2026` | Internal ops mode — separate JWT, MFA-gated |

For the standard demo, always start as **brittany@demo.mga**.

## 4. Tour the supplier list (15s)

- Land on `/suppliers`. 50 rows, sorted by most-recently-submitted.
- Point out the **status chip** column: `Active` / `Expiring soon` / `Lapsed` derived from COI expiry.
- Hover the **last submitted** column → tooltip shows portal + receipt link.

Click into any `Active` supplier (e.g. `Acme Trucking LLC`).

## 5. Open a supplier (20s)

Three tabs visible: **Profile · Documents · Submissions**.

- **Profile**: name, EIN (masked), 6-digit risk score, owner email.
- **Documents**: 3 PDFs (COI, EO, license). Each has confidence-scored extracted fields and a "View" sheet that highlights the source region.
- **Submissions**: chronological list with portal name, status, receipt link.

Hover any **confidence badge** to show the source provenance tooltip — point out that low-confidence fields are always human-reviewable.

## 6. Demo the onboarding wizard (45s)

From `/suppliers`, click **Add supplier** to open the **9-step onboarding wizard**.

1. Identity (name, type, EIN). Pre-filled from upload if you drop a W-9.
2. Contacts (1 primary required, multiple allowed).
3. Addresses (mailing + service, autocompleted from USPS validation).
4. **Documents** — drag a COI PDF from `fixtures/coi/acord25_sample.pdf`. Show the extracted-fields toast within ~1.5s.
5. License (state, type, expiry).
6. Coverage (limits, carriers).
7. Risk schedule (rows from CSV import or manual).
8. Connections (which portals this supplier should be submitted to).
9. Review — all confidence badges visible. Click **Submit & onboard**.

Two key talking points:

- **PDF extraction is local** (no LLM in the demo) — predictable latency, no PII leaves the box.
- **Every field has provenance** — auditor can trace any value back to the source PDF region.

## 7. Trigger a multi-portal submission (30s)

From the supplier detail page, click **Submit to portals**. Multi-select:

- AmTrust
- Markel
- Applied Epic

Hit **Submit**. The submissions table updates in real time:

- `queued` → `submitting` → `submitted` with a green check.
- Each row gets a **Receipt** link.

Behind the scenes: Playwright drives the local nginx fixtures at `http://fixtures.local`. **In production this is replaced by real carrier portal selectors** — see [`docs/SUBMITTERS.md`](./SUBMITTERS.md) for the contract.

## 8. Verify a receipt (20s)

Click any **Receipt** link. New tab opens at `http://localhost:8080/verify/{receipt_id}`.

- Big green **Verified** hero. Subtitle shows supplier + portal + issued-at.
- Scroll down: receipt details (Ed25519 + RFC 8785 canonical JSON).
- Click **Download signed receipt JSON** to grab the raw envelope.
- Click **Social card (SVG)** to see the per-receipt OG card (this is what unfurls in Slack/iMessage).

Talking point: *"This is the same URL we'd embed in a vendor contract. Anyone — your auditor, your insurer, the supplier — can re-verify without an account."*

## 9. Open the audit trail (20s)

Switch back to <http://localhost:5173>. Sign out and log in as **audit@demo.mga**.

- Land on `/audit`. Hash-chained event log with tenant filter pre-set.
- Click the **chain integrity** indicator — green check confirms the SHA-256 hash links are intact.
- Click **Export signed PDF**. The PDF includes a QR code linking back to `getonce.com/verify/{event_id}`.

Talking point: *"This export is the artifact your SOC 2 / market conduct examiner wants. We don't ship audit logs to a SaaS — they stay on your tenant."*

## 10. Show the cockpit (operator mode) (20s)

In a fresh incognito window, open <http://localhost:5173/cockpit>. Sign in as `cockpit@once.local` / `cockpit-2026`.

- Separate JWT issuer, separate audit middleware, separate URL prefix.
- Tenants list shows `Demo Specialty MGA` with row counts.
- Click into the tenant → see the **Act as** menu: select `brittany@demo.mga` and a banner appears: **"Acting as Brittany Smith (operator session, audited)"**.
- Every action you take in this session is logged with `actor=cockpit@once.local act_as=brittany@demo.mga` for later forensic review.

Talking point: *"This is how we do safe customer support. The operator never sees raw credentials, and every override is logged with crypto integrity."*

## 11. Show the billing surface (10s)

Back as `brittany@demo.mga`, open `/billing`.

- Active subscription: **Pro · $799/mo**, monthly usage chart, last 12 invoices.
- Click **Open Stripe portal** — mock mode prints "would redirect to Stripe billing portal" to the console.

Talking point: *"Stripe is wired end-to-end including webhooks. Flip `STRIPE_MOCK_MODE=false` and a real key, and it ships."*

## 12. Wrap (10s)

That's the whole demo path. The whole flow — from `make up` to verifier — completes in ≤4 minutes on a warm cache, ≤7 on a cold one. Hand the laptop to the prospect and tell them to click around.

## Resetting between demos

```bash
make seed-reset-realistic   # idempotent, surgical — only removes seeded rows
make seed-realistic         # re-seed
```

For a full nuke (drops the database, re-migrates from zero, re-seeds), use `make reset`. Slower (~60s on a warm Docker daemon) but recovers from any schema drift.

## Pre-recording checklist (for screencasts)

- [ ] `make doctor` clean
- [ ] All caches warm (`make seed-realistic` ran in the last hour)
- [ ] Browser zoom at 100%, dark mode OFF (or both shots — pick one)
- [ ] Notification / focus mode ON
- [ ] Cursor size: large
- [ ] Window: 1920×1080
- [ ] No personal tabs visible in tab bar (use a fresh profile)

## Troubleshooting (most common failures)

| Symptom | Cause | Fix |
|---------|-------|-----|
| `make up` hangs on `fixtures` | nginx fixture port collision | `docker compose down`, `lsof -i :8081`, kill, retry |
| Receipt page shows `Verification error` | Verifier missing `PUBLIC_KEY_PEM` | check `.env`, run `make seed` again — it writes the demo key |
| Wizard step 4 PDF upload silently fails | Tesseract not installed | `brew install tesseract` (mac) or skip — extraction degrades gracefully |
| Submitter stuck at `submitting` | Playwright browser not installed | `make setup` re-runs `playwright install` |
| Stripe portal button does nothing | `STRIPE_MOCK_MODE=true` (default) | expected — for the demo this is fine |
| Cockpit login redirects to `/login` | Wrong issuer | the cockpit uses a different JWT issuer, must use `/cockpit/login` |

Every line above maps to a real failure we've hit. If you see a new one, add a row here and file a P0 in `docs/UX_LOG.md`.

## What you intentionally do NOT show on a sales call

- Cockpit MFA stub (it's a stub — turn into production-grade TOTP **after** first paid pilot).
- Stripe metered billing edge cases (only flip when prospect asks).
- The 30 conditionally-skipped tests (irrelevant to demo unless someone asks "how do you handle Postmark?").
- The L3.2 seed determinism contract (interesting to engineers, not buyers).
- Any submitter against a real carrier portal — until paid pilot with that carrier's permission.

Stay on the script. The script sells.
