# Once — Security Model

Audience: engineers shipping changes to this repo, and security
reviewers from prospective customers.

This document is the **threat model**. Operational security procedures
(key rotation, restore drill, on-call response) live in
[`RUNBOOK.md`](./RUNBOOK.md). Vulnerability disclosure lives in
[`../SECURITY.md`](../SECURITY.md).

---

## 1. Assets we protect

| Asset | Where it lives | Why an attacker wants it |
|---|---|---|
| Tenant A's supplier data | Postgres, `tenant_id`-scoped | Pivot into Tenant A's carrier portals; identity fraud. |
| Operator portal credentials | Browser extension vault, AES-GCM-256 in IndexedDB | Direct access to carrier portals. |
| Receipt signing private key | Worker process env (`RECEIPT_SIGNING_PRIVATE_KEY_PEM`) | Forge audit receipts; undermine the whole product. |
| JWT signing secret | Backend env (`JWT_SECRET_KEY`) | Impersonate any user across any tenant. |
| Append-only audit log | Postgres, `audit_logs` | Cover tracks; tamper with forensic record. |
| OnceTax customer Shopify tokens | Cloudflare KV / D1 | Read/modify Shopify stores. |

## 2. Adversary model

We design against three classes of adversary:

1. **External attacker, no foothold** — internet attacker hitting our
   public surface (API, verifier, operator console, extension store
   listing).
2. **Authenticated tenant user** — a legitimate user of Tenant A who
   wants to read Tenant B's data, escalate to admin, or forge a
   receipt as another supplier.
3. **Compromised single component** — a worker container is popped, or
   a developer laptop is stolen, or a third-party dep ships malware.
   We want to bound the blast radius.

We do **not** design against a fully compromised cloud provider or a
nation-state with physical access to the database host. We do design
against an actor who has read-only DB access (e.g., a leaked backup)
not being able to forge receipts.

## 3. Tenant isolation

This is the single most important property of the system. Every
tenant-scoped table (suppliers, portals, submissions, receipts,
consent, COIs, audit logs) carries
`tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)`.

Three layers of enforcement:

1. **Schema layer** — FK with `ON DELETE CASCADE`. No orphan rows.
2. **Middleware** — `app.middleware.tenant_scope` reads `tenant_id`
   from the decoded JWT and writes it to `request.state.tenant_id`.
   Any route that touches tenant-scoped tables MUST call
   `get_current_tenant_id` to obtain that value.
3. **Service layer** — every service function takes `tenant_id` as an
   explicit argument and includes `WHERE tenant_id = :tenant_id` in
   every query. We do **not** rely on Postgres RLS — the SQLite test
   environment cannot enforce it, and we want one code path.

Test coverage: `backend/tests/test_tenant_isolation.py` enumerates
every router and asserts that Tenant A cannot read or mutate any
Tenant B row, by either explicit ID or by query.

## 4. Authentication and session

- **Algorithm:** HS256 (HMAC) for JWT. Asymmetric not needed because
  only the backend issues and verifies tokens.
- **Access token TTL:** 15 minutes. **Refresh token TTL:** 30 days.
- **Refresh rotation:** every refresh exchange issues a new refresh
  token and invalidates the previous one (server-side denylist in
  Redis).
- **Storage on the client:** access + refresh in `localStorage` for the
  operator console; axios interceptor handles refresh on 401.
- **CSRF:** double-submit cookie on every state-changing route for
  browser clients (the extension uses a bearer token only and sets a
  custom header that bypasses CSRF).
- **Password hashing:** bcrypt cost 12 via `passlib[bcrypt]` (see
  `backend/app/auth/security.py`). Migration to Argon2id is tracked on the
  roadmap; the existing bcrypt hashes will be rehashed on next successful
  login once the change ships.
- **Rate limiting:** slowapi on `/v1/auth/*` (5/min/IP for login,
  10/min/IP for register).

## 5. Browser extension vault

The extension holds the most sensitive client-side data in the
product: carrier portal credentials and supplier profile fields.

- Storage: encrypted IndexedDB.
- Cipher: **AES-GCM-256**, fresh 12-byte nonce per record.
- Key derivation: **PBKDF2-SHA256, 310,000 iterations** over the
  operator's vault passphrase. The passphrase is never sent to the
  backend and is never persisted on disk.
- Lock policy: vault auto-locks after 15 minutes of inactivity; the
  passphrase must be re-entered.
- Export: only as an encrypted blob; never as plaintext.

## 6. Receipt signing (Ed25519)

Receipts are the product. They must be tamper-evident and verifiable
without trusting Once.

- **Algorithm:** Ed25519. Fast, deterministic, small signatures (64
  bytes), no nonces to mess up.
- **Key id:** `RECEIPT_SIGNING_KEY_ID` is embedded in every receipt so
  signatures can be verified after a rotation.
- **Key handling:** `RECEIPT_SIGNING_PRIVATE_KEY_PEM` is set only on
  the worker process. The API process does not need it. The frontend
  never sees it. Stored in Fly secrets in production, never in git.
- **Canonical JSON:** signed bytes are
  `app.utils.canonical_json.dumps(payload).encode()` — RFC-8785-style
  sorted keys, no insignificant whitespace, `\uXXXX` escapes. This is
  what makes third-party verification possible.
- **Public key distribution:** `GET /v1/keys/{key_id}` returns the
  raw 32-byte Ed25519 public key (base64url). The verifier service
  fetches it.
- **Rotation:** see [`RUNBOOK.md`](./RUNBOOK.md). Old public keys are
  retained forever so old receipts remain verifiable.

## 7. Append-only audit log

`audit_logs` rows are written by the service layer at every meaningful
event (login, consent granted/revoked, submission created/claimed/
completed/failed, receipt issued, key rotation). The table:

- Has no `UPDATE` route in the API.
- Has a daily `pg_audit`-style verification job that recomputes a
  rolling hash and stores it in S3 / R2 (operator can compare).
- Is included in every backup.

The application-layer rule is **no service may mutate an audit row
once written**. Code review enforces this; a CI lint flags any
`update(AuditLog)` statement.

## 8. Secrets handling

- **No secrets in git.** `.env*` is gitignored except `.env.example`
  and `.env.*.example`. CI runs `gitleaks` on every PR.
- **Production secrets** live in Fly secrets (`fly secrets set ...`),
  Cloudflare Worker secrets (`wrangler secret put ...`), or the local
  developer's `.env`. Nowhere else.
- **Rotation cadence:**
  - JWT secret: every 90 days.
  - Receipt signing key: every 365 days, or immediately on suspected
    compromise. See [`RUNBOOK.md`](./RUNBOOK.md).
  - Database password: every 180 days.
  - Shopify app secret (OnceTax): on every Shopify-flagged event.

## 9. Dependency policy

- **Python:** pinned in `backend/requirements.txt` to exact versions.
  Dependabot opens weekly PRs; security advisories are merged within 7
  days.
- **JS:** pinned via lockfile. `npm audit --production` runs in CI;
  high+ severity advisories block merge.
- **Playwright browsers:** pinned to the version shipped with the
  Playwright package; CI installs them deterministically.
- **No `eval`-shaped dynamic loaders** in production code. The
  automation submitters are imported by name via a static dispatch
  table in `app/automation/__init__.py`.

## 10. Transport and CORS

- All public HTTPS. HSTS with `includeSubDomains; preload` once we own
  the apex domain.
- CORS allowlist driven by `BACKEND_CORS_ORIGINS` env var. Wildcards
  are rejected at startup if `APP_ENV=production`.
- The verifier service is read-only and CORS-open by design — it's the
  thing third parties are supposed to call.

## 11. Data retention and deletion

- Soft-delete is forbidden in the API. A "delete tenant" operation
  hard-deletes from Postgres via `ON DELETE CASCADE`. The audit log
  for that tenant is preserved (per the EU AI Act and most US
  carrier-audit contracts) but contains only references, not PII.
- Backups are retained for 35 days, then expired.
- Receipts are retained indefinitely by design; that's the product.

## 12. What's explicitly out of scope (today)

- Server-side WAF rules beyond Fly's defaults.
- HSM-backed receipt signing (planned for v2).
- DLP scanning of supplier free-text fields.
- BYOK encryption-at-rest for tenants on shared Postgres (planned for
  v2 as a paid add-on).

If any of these matters for a specific deal, raise it in the issue
tracker and link the PR.
