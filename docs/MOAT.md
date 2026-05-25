# MOAT.md — Why Once is hard to copy

> Single source of truth for Once's defensible advantages. Referenced from
> README.md, sales decks, partner conversations, and investor updates.
> If two docs disagree, **this file wins**.

## TL;DR

Anyone can build a form-filler. Almost no one will build the five things below
_in combination_, because each one alone is expensive and the combination
compounds. The wedges are ordered by **how-hard-to-copy** (descending), not by
how-shiny-to-market.

| #   | Moat                                                        | Why it's hard to copy                                                                     | Where it lives                                                          |
| --- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| 1   | **Cryptographic receipts + standalone verifier**            | Requires committing to immutable signed evidence forever; competitors won't add liability | `backend/app/services/receipt_signer.py`, `verifier/`                   |
| 2   | **Submitter framework with per-carrier reverse-eng**        | 100+ engineering-hours per portal; the registry compounds                                 | `backend/app/services/submitter_registry.py`, `backend/app/submitters/` |
| 3   | **Dual-runtime parity (server Playwright + MV3 extension)** | Same DOM mappings exercised from two runtimes; doubles testing cost                       | `extension/src/content/`, `backend/app/submitters/`                     |
| 4   | **Data-model depth (COIs, loss runs, EO certs, ACORD)**     | Insurance-document parsing + ACORD coverage takes years                                   | `backend/app/models/`, `docs/DATA_MODEL.md`                             |
| 5   | **Fake-portal fixtures**                                    | Hermetic regression suite that replays real DOMs without legal exposure                   | `fixtures/portals/`                                                     |

---

## 1. Cryptographic receipts + standalone verifier

**The wedge:** Once is the only carrier-submission product that emits an
Ed25519-signed, RFC-8785-canonical-JSON receipt for every submission AND
publishes the verifier as a separate, Apache-2.0-licensed microservice.

**Why competitors will not copy this:**

- Signing every submission means **publicly committing to immutable evidence**.
  If a competitor's submitter fills the wrong field, the customer now has a
  cryptographic artifact to wave in court. Most vendors will refuse to take on
  that liability.
- Publishing the verifier under Apache 2.0 forecloses the option of later
  charging for verification — once the keys are public and the verifier is
  open, you cannot put that genie back.
- DNS-TXT key publication (`_once-keys.getonce.com`) raises the bar one more
  notch: a key swap requires DNS compromise + backend compromise + verifier
  compromise simultaneously.

**What we ship to prove it:**

- `POST` and `GET` `/v1/verify/{receipt_id}` — JSON + HTML + badge SVG.
- `GET /v1/public/keys` (JSON) and `/v1/public/keys.txt` (DNS-TXT-ready PEM).
- `GET /trust`, `/verify`, `/coverage` — public web surface.
- Standalone `verifier/` service, separately deployable, separately licensed.

**Sales line:** _"Our receipts hold up in court. Theirs are screenshots."_

---

## 2. Submitter framework with per-carrier reverse-engineering

**The wedge:** Each supported carrier portal has a typed `BaseSubmitter`
implementation that has been hand-reverse-engineered from the live DOM,
exercised against a recorded fixture (`fixtures/portals/`), and proven in CI.
This registry compounds: every carrier added makes the next one cheaper
(shared utilities), but the catalog itself is the moat.

**Why it's hard to copy:**

- Each portal is ~80–120 engineering-hours to add, including fixture capture,
  selector hardening, error-recovery branches, and idempotency wiring.
- Selectors drift; without a regression suite, day-2 maintenance crushes
  vendors who didn't invest in the fake-portal harness (see Moat 5).
- The 14-day "new-carrier SLA" (`docs/PORTAL_SLA.md`) is a _commitment_
  competitors can't make until they have the framework. We have it now.

**Sales line:** _"Name a carrier. We'll have it in 14 days. Theirs takes a quarter."_

---

## 3. Dual-runtime parity (server Playwright + MV3 extension)

**The wedge:** The same DOM-mapping intent is implemented in two runtimes —
the server-side Playwright submitters and the MV3 content scripts under
`extension/src/content/`. This lets us:

- Submit headlessly from the cloud for fully-automated workflows.
- Submit from the user's browser session for portals that ban server IPs or
  require live SSO (CNA, several Big-3 AMSes).
- A/B the two runtimes against the same fixture and catch divergence.

**Why it's hard to copy:** RPA-only vendors (Bold Penguin/Relay/RPA shops) ship
only the extension half. SaaS-only vendors (Semsee, Indio, Broker Buddha) ship
only the server half. Doing both doubles QA cost — and _not_ doing both means
you lose every portal that flips the rule next quarter.

---

## 4. Data-model depth

**The wedge:** Once doesn't just submit forms. It owns the full insurance data
model: suppliers, certificates of insurance, loss runs, producer licenses,
E&O certificates, ACORD 25/27/28/125 etc., risk schedules, consent ledger,
audit log, inbound email routing, imports. See `docs/DATA_MODEL.md`.

**Why it's hard to copy:** Each entity above was 2–6 weeks of schema +
service + UI + tests + migrations. The whole catalog is a year-plus of
focused work, plus a parsing pipeline (`docs/PDF_EXTRACTION.md`) that
ingests carrier PDFs deterministically.

---

## 5. Fake-portal fixtures

**The wedge:** `fixtures/portals/` contains recorded DOMs of each supported
portal, sanitized for legal safety. They power a hermetic regression suite
that runs in CI without ever touching the real portal.

**Why it's hard to copy:** Capturing fixtures responsibly (without leaking
PII, respecting carrier ToS) is a discipline. Replaying them deterministically
requires a Playwright harness that most vendors haven't built. The fixtures
are also the only way to refactor a submitter safely.

---

## What we deliberately do NOT claim as a moat

These look like moats but aren't, and we should never lead with them:

- **The form-fill UX.** Anyone with a quarter and a designer can ship this.
- **Generic LLM "AI quoting"** — undifferentiated and trending to zero cost.
- **"We integrate with all the AMSes."** Ivans does, too. Integration alone is
  table stakes once you've shipped the data model.
- **Multi-tenancy.** Every B2B SaaS has it.
- **SOC 2.** Necessary, not differentiating.

---

## Validation rituals

- Every release that touches a submitter must update at least one fixture and
  one CI test in `backend/tests/test_submitter_*.py`.
- Every release that touches receipt signing must update `backend/tests/test_receipt_signer.py`
  AND `verifier/test_verify.py` and confirm byte-identity.
- Every customer call closes with the phrase "and you can verify that
  receipt yourself at getonce.com/verify — or run our open-source verifier."
- Every E&O insurer call walks through `docs/PARTNER_EO.md`.

## Roadmap of moat-deepening work

| Quarter | Investment                                                                  | Moat # |
| ------- | --------------------------------------------------------------------------- | ------ |
| Now     | Public `/coverage`, `/trust`, `/verify` pages; Apache-2.0 verifier split    | 1, 2   |
| +30d    | CNA + Nationwide ES submitters (first 14-day SLA shipments)                 | 2      |
| +60d    | DNS-TXT key publication; first E&O insurer partnership signed               | 1      |
| +90d    | Independent pen-test of extension vault published (`docs/PENTEST_BRIEF.md`) | 3      |
| +120d   | FIDO2/passkey as second-factor unlock (`docs/VAULT_PASSKEY_DESIGN.md`)      | 3      |
