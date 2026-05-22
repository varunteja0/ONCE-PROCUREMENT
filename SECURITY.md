# Security Policy

> **Last reviewed:** Phase 1.  See [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md)
> for the full STRIDE matrix and [`docs/SECRET_ROTATION.md`](docs/SECRET_ROTATION.md)
> for runbooks.

## Threat-model summary

Once is a multi-tenant SaaS that submits insurance forms on behalf of MGAs
and issues cryptographically signed receipts third parties can verify.  We
maintain a STRIDE matrix covering eight components:

1. API Gateway
2. Auth Service
3. Tenant-Scope Middleware
4. Submission Pipeline
5. Submitter (Playwright)
6. Receipt Signer
7. Verifier
8. Extension Vault

The top three risks we actively monitor:

- **Cross-tenant data leak** — mitigated by `TenantScopeMixin` + middleware
  + integration tests (`backend/tests/test_tenant_isolation.py`).
- **Receipt forgery** — mitigated by Ed25519 signatures with a public-key
  registry; rotation procedure documented.
- **Credential stuffing on `/v1/auth/login`** — mitigated by sliding-window
  account lockout per `(email, ip)` tuple and a strict password policy.

## Cryptography choices

| Use | Algorithm | Notes |
| --- | --- | --- |
| Receipt signatures | **Ed25519** | Detached signatures over canonical JSON; deterministic; rotatable via registry. |
| Vault credential encryption (extension) | **AES-GCM-256** | Random 96-bit nonce per record; tag length 128 bits. |
| Vault passphrase derivation | **PBKDF2-HMAC-SHA256, 310 000 iterations** | OWASP 2024 minimum. |
| Password hashing (server) | **bcrypt** (`passlib[bcrypt]`, cost 12) | Migration path to argon2id deferred; tracked in roadmap. |
| JWT signing | **HS256** with ≥32-char high-entropy secret | Validated at startup (hard-fail in production). |
| TLS | **TLS 1.2+** terminated at Fly edge | HSTS preload-eligible (2 years, `includeSubDomains`). |

## Hardening posture

The backend ships the following defense-in-depth controls on every
response:

- `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
  (production only; configurable via `SECURITY_HSTS_ENABLED`)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()…`
- `Cross-Origin-Opener-Policy: same-origin`
- `Cross-Origin-Resource-Policy: same-site`
- `Content-Security-Policy: default-src 'self'; frame-ancestors 'none' …`
  (on HTML responses only)

And the following request-time controls:

- **Body-size limit** — 1 MiB JSON, 25 MiB upload (configurable per route)
- **CSRF** — double-submit cookie on cookie-bearing clients
- **Tenant scope** — every authenticated query carries an enforced
  `tenant_id` filter
- **Rate limit** — 120 req/min/IP default (slowapi)
- **Account lockout** — 5 failures / 15 min → 30 min lock per (email, ip)
- **Secret strength** — `SECRET_KEY` and `JWT_SECRET_KEY` validated at
  boot; hard-fail in production
- **Log redaction** — structlog processor scrubs passwords, tokens,
  signing keys, JWTs, AWS keys, etc.

### Known deferred items

- Existing user passwords were stored before the password policy landed.
  We do **not** retroactively rotate them; the policy enforces on
  `register` and `change-password` only.  We may add a force-rotate flag
  in Phase 2.
- JWT plural-secret rotation (`JWT_SECRET_KEYS`) is on the roadmap; until
  shipped, a JWT rotation forces users to re-login.
- MFA / WebAuthn is planned for Phase 2.

## Compliance posture

| Framework | Status | Phase |
| --- | --- | --- |
| SOC 2 Type I | Planned | Phase 5 |
| SOC 2 Type II | Aspirational (≥ 12 months post Type I) | Phase 6 |
| CCPA / GDPR data-subject requests | Manual via support | Phase 1 |
| HIPAA | Not in scope (no PHI) | n/a |
| PCI | Not in scope (Stripe-only payments) | n/a |

Sub-processor list lives in [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md).

## Bug-bounty program

We do **not** run a paid bounty in Phase 1.  We do issue **public credit**
and Once swag for valid medium-or-above reports.  A paid program will
launch alongside SOC 2 Type II or once the company reaches $25 K MRR,
whichever comes first.

## Reporting a vulnerability

If you believe you have found a security vulnerability in Once,
**please do not open a public GitHub issue.** Email us instead:

> **security@getonce.com**

> ⚠️ The shared inbox is configured but unmonitored outside business
> hours in Phase 1.  For Sev-1 issues with active exploitation, mention
> "ACTIVE EXPLOIT" in the subject for an out-of-band page.

PGP key fingerprint and `.asc` will be published at
`https://getonce.com/.well-known/security.txt` once the apex domain is
live; in the meantime, plain email is fine.  If you require an encrypted
channel before then, mention "PGP requested" in your email subject and we
will exchange keys out of band within one business day.

Please include:

- A clear description of the issue and its impact.
- Steps to reproduce (a minimal proof of concept is gold).
- Any logs, request IDs, or screenshots that help us triage.
- Your name/handle and whether you want public credit.

## Our commitments

- We acknowledge every report within **2 business days**.
- We aim to provide an initial assessment (severity, intended fix
  window) within **5 business days**.
- We follow a **90-day coordinated disclosure window** from the day a
  fix is available.  We will work with you on a public disclosure date
  before the window expires; if no fix exists at day 90, we will still
  work with you on a coordinated disclosure note describing the issue
  and any available mitigations.
- We do **not** pursue legal action against good-faith researchers
  acting within the scope below.
- We are happy to publicly credit reporters in our release notes
  (`@your-handle` or your full name — your choice).

## Scope

In scope:

- The production deployments of Once
  (`api.getonce.com`, `verify.getonce.com`, `app.getonce.com`) and the
  official browser extension as published in the Chrome Web Store,
  Firefox Add-ons, and Edge Add-ons stores.
- OnceTax production deployment.
- Any subdomain of `getonce.com` operated by Once Inc.
- Any code in this repository.

Out of scope:

- Customer-operated forks or self-hosted deployments — please report
  to that operator.
- Findings that require physical access to a user's device.
- Social-engineering attacks against Once employees.
- Volumetric DDoS without an accompanying vulnerability.
- Reports limited to missing best-practice headers on non-sensitive
  endpoints (we'll fix them, but they aren't bounty-eligible).

## What we ask of you

- Do not access, modify, or delete data that does not belong to you.
  If you incidentally access another tenant's data, stop, do not save
  copies, and tell us.
- Do not run automated scans that generate sustained load against
  production.  Local testing against `docker compose up` is preferred.
- Do not disclose the issue publicly until we have agreed on a
  disclosure date.
- Honor the 90-day window.

## Vendor disclosures and supply chain

If a vulnerability you find originates in one of our sub-processors
(listed in [`docs/COMPLIANCE.md`](./docs/COMPLIANCE.md) §7), tell us
and we will coordinate disclosure with that vendor while still
honoring the timelines above.

Thank you for keeping Once and its customers safe.

