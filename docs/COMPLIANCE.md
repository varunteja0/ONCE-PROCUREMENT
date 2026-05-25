# Once — Compliance Posture

This document describes how Once intends to satisfy the compliance
regimes our customers care about. It is **not** a legal opinion and it
is **not** an attestation of any kind. Where we make forward-looking
statements (e.g., "Type II by Q4"), they are plans, not promises.

Vulnerability disclosure: see [`../SECURITY.md`](../SECURITY.md).
Engineering threat model: see [`./SECURITY.md`](./SECURITY.md).

---

## 1. SOC 2 — control map sketch

We are targeting **SOC 2 Type I in Q3** and **Type II in Q1 of the
following year**, scoped to the Security and Confidentiality TSCs.
Availability and Processing Integrity are intentionally deferred.

| TSC area | Control we ship today | Evidence artifact |
|---|---|---|
| **CC1 — Control Environment** | Documented engineering standards in `CONTRACTS.md`; signed contributor agreements. | This repo + signed CLAs. |
| **CC2 — Communication** | This file + `RUNBOOK.md` + `SECURITY.md`. Customer-facing status page. | Public docs. |
| **CC3 — Risk Assessment** | Annual written risk assessment; per-PR threat-model note for any change touching auth, crypto, tenant isolation. | `docs/risk/` (private). |
| **CC4 — Monitoring** | Sentry on every service. Nightly Celery beat job `audit.verify_nightly_hash` (02:00 UTC) computes a chained SHA-256 over yesterday's `audit_logs` per tenant and alerts on any mismatch (status=`alert`). Uptime checks against `/v1/health`. | Sentry org, Statuspage, `app/workers/tasks/audit_tasks.py`, `audit_hash_digests` table, `GET /cockpit/compliance/audit-hash-digests`. |
| **CC5 — Control Activities** | Branch protection requires PR review + green CI. No direct push to `main`. | GitHub branch protection. |
| **CC6 — Logical Access** | JWT (15 min) + refresh (30 days) + bcrypt cost-12 passwords (`passlib[bcrypt]`; Argon2id migration tracked in the roadmap) + slowapi rate limiting. Vault is AES-GCM-256 PBKDF2-310k. Quarterly access review listing every user + role + last-login per tenant. Secret-rotation ledger captures every key change (receipt signing, JWT, cockpit JWT, DB password, Redis password, Fly token, Sentry DSN, operator passwords) with operator + timestamp. Three Celery beat jobs enforce rotation cadence: `keys.rotate_signing_key` (annually, 1st Jan 03:00 UTC) auto-rotates the receipt-signing key and writes a `KeyRotationLog`; `keys.warn_jwt_secret_age` (weekly, Mon 04:00 UTC) alerts via Sentry when the most recent `jwt_secret_key` rotation is >90 days old; `keys.warn_db_password_age` (weekly, Mon 04:15 UTC) alerts when the most recent `db_password` rotation is >180 days old. Verifier API keys (tenant-scoped, used by external buyers to hit `verify.once.io`) issued / revoked via owner-only cockpit endpoints under `/v1/admin/verifier-keys`; plaintext is shown exactly once at creation and only the SHA-256 hash is stored. Every issuance and revocation writes a `verifier_api_key.created` or `verifier_api_key.revoked` row to `AuditLog` capturing operator, tenant, key prefix, and monthly cap. Per-key monthly usage is tracked in `verifier_api_key_usage` (CC7). | `app/utils/security.py`, extension `lib/vault.ts`, `GET /cockpit/compliance/access-review`, `GET /cockpit/compliance/key-rotations`, `POST /cockpit/compliance/key-rotations`, `app/workers/tasks/key_rotation_tasks.py`, `app/api/v1/verifier_keys.py`, `app/services/verifier_key_service.py`. |
| **CC7 — System Operations** | Atomic-claim submission pipeline; idempotent receipt issuance; structlog-structured logs; Alembic migrations only. Chain-of-custody hashes (CC4) make `audit_logs` tamper-evident. | `app/services/submission_pipeline.py`, `alembic/`, `GET /cockpit/compliance/audit-export` (jsonl/csv). |
| **CC8 — Change Management** | Conventional commits; required PR review; CI matrix on every PR (`backend`, `frontend`, `extension`). | `.github/workflows/ci.yml`. |
| **CC9 — Risk Mitigation** | Daily Postgres base backup + WAL archive; quarterly restore drill; documented incident response in `RUNBOOK.md`. Tenant data lifecycle: GDPR-style hard erasure via founder-only `DELETE /cockpit/tenants/{id}` (requires slug confirmation + reason), leaves a single system-level `AuditLog` row with per-table row counts. | Fly Postgres + R2 archive, `app/services/tenant_deletion_service.py`, `RUNBOOK.md` §4 + §7. |
| **C1 — Confidentiality** | Tenant isolation enforced in middleware + service layer + schema FK. Receipts signed with Ed25519. Audit log append-only and chain-hashed (CC4). | `app/middleware/tenant_scope.py`, `app/services/receipt_signer.py`, `app/services/audit_hash_service.py`. |

**Quarterly evidence drill.** Every quarter, a founder operator runs
`python -m scripts.soc2_evidence_export` once per active tenant. The
script bundles the four read endpoints above into a single `.zip` with
a `manifest.json` carrying a SHA-256 + byte length per artifact, so an
auditor can byte-match the archive on download. Full procedure:
[`RUNBOOK.md` §7](./RUNBOOK.md).

The first audit period begins on the day SOC 2 Type I kicks off. Until
then, every customer contract uses our standard **MSA + DPA + Security
Addendum** ([`gtm/04-msa-template.md`](../gtm/04-msa-template.md)) as
the contractual security commitment.

## 2. GDPR (EU 2016/679)

Once is a US company; the operative GDPR question is whether we
process the personal data of EU data subjects on behalf of a customer
(MGA). For customers with EU producers, the answer is yes, and we act
as a **processor**.

Posture:

- **Lawful basis:** the controller (the MGA) is responsible for the
  lawful basis; Once is the processor and follows documented
  instructions per Article 28.
- **Article 28 DPA:** every customer signs our standard DPA
  alongside the MSA. The DPA names sub-processors (Fly.io, Cloudflare,
  Sentry) and grants the controller audit rights.
- **Article 30 records of processing:** maintained internally; a
  redacted copy is provided to controllers on request.
- **Article 32 security of processing:** see this repo's
  [`SECURITY.md`](./SECURITY.md). Pseudonymisation of supplier PII in
  the audit log; AES-256 at rest (Fly Postgres default); TLS 1.2+ in
  transit.
- **Article 33 breach notification:** 24-hour notification SLA to the
  controller for confirmed personal-data breaches (stricter than the
  72-hour regulatory window).
- **Articles 15–22 data-subject rights:** controller routes the
  request through our `/v1/admin/dsr` API; Once responds within 14
  days.
- **International transfers:** Standard Contractual Clauses
  (2021/914) attached to the DPA. We do not currently store EU data
  outside `iad`, but the SCCs cover us if we add a non-US region.
- **DPIA:** a template DPIA covering Once is available to controllers
  on request.

## 3. CCPA / CPRA (California Civil Code §1798.100 et seq.)

For California producers, Once is a **service provider** under
§1798.140(ag). Posture:

- We do not sell or share personal information. The MSA contains the
  required service-provider language.
- A "Do Not Sell or Share My Personal Information" mechanism is not
  required because we do neither; it remains absent from the operator
  console by design.
- DSR plumbing: same `/v1/admin/dsr` endpoint as GDPR. We respond
  within the CCPA-required 45 days (we target 14).

## 4. EU AI Act (Regulation (EU) 2024/1689)

The interesting article is **Article 6** (classification of high-risk
AI systems). Insurance underwriting AI is on the Annex III list. Even
though Once itself is not an underwriting system, our customers are
operating in that adjacent space and they ask us to support their
Article 6 obligations.

We support them in two ways:

1. **Verifiable submission receipts.** Article 6 systems are required
   to maintain logs that "ensure traceability of the AI system's
   functioning throughout its lifecycle" (Art. 12). Our Ed25519-signed
   receipts give the operator a forensic-grade record of every
   submission made to a carrier portal, including the canonical hash
   of the data submitted, the consent record, and the version of the
   carrier's TOS in force at the time.
2. **Append-only audit log with daily hash chain.** The
   `audit_logs` table is append-only at the application layer; a
   nightly Celery task computes a Merkle-style rolling hash over the
   day's rows and writes that root to immutable cold storage (R2
   bucket with object-lock). This satisfies the "automatically
   recorded events" and "tamper-evident" implication of Articles
   12(2) and 12(3).

We do **not** claim Once is a high-risk AI system under Article 6, and
we do not claim a conformity assessment under Article 43. We are an
audit-trail provider for our customers' Article-6-adjacent systems.

## 5. Insurance-specific regimes

- **NY DFS Part 500 (23 NYCRR 500), 2023 amendment** — we map to the
  written information security program (§500.02), risk assessment
  (§500.09), and access controls (§500.07) requirements. The MSA's
  Security Addendum tracks the §500 control list.
- **NAIC Model Law 668** — Once does not itself process insurance
  consumer information; our customers do. We provide the technical
  controls they need to satisfy §4 (information security program).
- **HIPAA** — out of scope. Once does not handle PHI and contracts
  explicitly exclude it. If a customer attempts to send PHI through
  Once, the MSA reserves our right to terminate.
- **PCI DSS** — out of scope. We do not process, store, or transmit
  cardholder data. OnceTax (Wedge B) uses Shopify Subscription
  Billing, which keeps PCI scope on Shopify's side.

## 6. Record retention

| Record class | Retention | Where | Why |
|---|---|---|---|
| Submission receipts | Indefinite | Postgres + R2 cold backup | Product purpose; carrier-audit support. |
| Audit log rows | 7 years | Postgres + R2 cold backup | Insurance and tax regimes. |
| Operator user account data | Life of account + 30 days | Postgres | Standard contract clause. |
| Backups (Postgres base + WAL) | 35 days | Fly Postgres | Operational recovery. |
| Sentry events | 90 days | Sentry SaaS | Bug investigation. |
| Application logs (structlog → Fly) | 30 days | Fly log shipping | On-call investigation. |
| Soft-deleted records | None — we hard-delete | n/a | GDPR Art. 17 + simplicity. |

## 7. Sub-processor list (current)

| Sub-processor | Purpose | Data categories | Region |
|---|---|---|---|
| Fly.io | Backend hosting + Postgres + Redis | All tenant data | iad (USA) |
| Cloudflare | OnceTax hosting (Workers, D1, R2, KV); CDN; verifier edge | OnceTax store data; OnceTax receipts | Global edge |
| Sentry | Error reporting | Scrubbed stack traces | USA |
| Shopify | OnceTax billing + storefront integration | Merchant identity + billing | USA |
| Resend | Transactional email (OnceTax) | Merchant email addresses | USA |

The current sub-processor list is published with each release. Customers
get 30 days' notice before a new sub-processor handles their data, per
the DPA.

## 8. How to ask for more

If your security/compliance team needs more than what's here — a SIG
Lite, a CAIQ, a custom DPA — email `compliance@once.io` and we will
respond within five business days.
