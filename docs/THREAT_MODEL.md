# Once — Threat Model (STRIDE)

Last updated: Phase 1.

This document enumerates the threats per component using
[STRIDE](https://en.wikipedia.org/wiki/STRIDE_model)
(Spoofing, Tampering, Repudiation, Information Disclosure, Denial of
Service, Elevation of Privilege).  Each cell lists the **threat**, the
**current mitigation**, **residual risk**, and **monitoring**.

Components in scope:

1. API Gateway (FastAPI app, edge of `api.once.io`)
2. Auth Service (`/v1/auth/*`, JWT issuance, password hashing)
3. Tenant-Scope Middleware (multi-tenant row isolation)
4. Submission Pipeline (worker that drives portal submissions)
5. Submitter (Playwright headless browser)
6. Receipt Signer (Ed25519 signing of tamper-evident receipts)
7. Verifier (public read-only verification microservice)
8. Extension Vault (browser extension credential storage)

---

## 1. API Gateway

| STRIDE | Threat | Mitigation | Residual | Monitoring |
| --- | --- | --- | --- | --- |
| S | Forged source IP via spoofed `X-Forwarded-For` | Trusted-proxy header chain configured on Fly.io; rate limit keyed on first untrusted hop | Moderate — depends on edge config | Access log + Sentry on rate-limit 429 |
| T | Header injection / smuggling | Uvicorn + httptools strict parsing; CSP `frame-ancestors 'none'`; `X-Content-Type-Options: nosniff` | Low | Sentry breadcrumbs, anomaly alerts on 4xx surge |
| R | Lost audit trail | Request-id middleware → propagates correlation id; access-log middleware writes one structured line per request | Low | Loki retention 90 d |
| I | Cross-origin info leak | Strict CORS allowlist; `Cross-Origin-Resource-Policy: same-site`; CSP `default-src 'self'` on HTML | Low | CSP `report-uri` (when configured) |
| D | Volumetric DoS | SlowAPI 120 req/min default; Fly autoscale; body-size middleware (1 MiB JSON, 25 MiB upload) | Moderate — no edge WAF yet | Prometheus `http_requests_total`, alerting on p95 latency |
| E | Privilege escalation via header trust | `Authorization` is the only auth-relevant header; CSRF middleware enforces double-submit cookie for cookie-bearing clients | Low | Audit log on every privileged action |

## 2. Auth Service

| STRIDE | Threat | Mitigation | Residual | Monitoring |
| --- | --- | --- | --- | --- |
| S | Credential stuffing | Sliding-window account lockout per (email, IP); password policy rejects top-100 + identity-related passwords | Low–Moderate — no MFA in Phase 1 | `account_locked` structured log, alert on spike |
| T | Token tampering | JWT signed with HS256 + 32+ char rotation-capable secret; entropy check refuses to boot in prod with weak secret | Low | Startup `secret_strength_fail` |
| R | Anonymous account actions | `AuditLog` row written on `register`, `login`, `token.refresh` | Low | DB query on `audit_log` table |
| I | Password leakage via logs | `secrets_redaction` log processor scrubs `password`/`token`/`secret` keys and JWT-shaped values | Low | Manual audit of sample logs |
| D | Brute-force lockout DoS | Lockout key is `(email, ip)` — a single hostile IP cannot lock everyone | Moderate (one user behind shared NAT) | Lockout admin unlock endpoint |
| E | Bypass tenant scope via crafted JWT | `tenant_id` claim validated against `TenantUser` row each request | Low | Tenant-scope middleware logs every reject |

## 3. Tenant-Scope Middleware

| STRIDE | Threat | Mitigation | Residual | Monitoring |
| --- | --- | --- | --- | --- |
| S | Cross-tenant query via direct ORM | Models inherit `TenantScopedMixin`; middleware sets `current_tenant_id` contextvar; query interceptor adds `WHERE tenant_id =` | Low | Test suite `test_tenant_isolation.py` |
| T | Forging `tenant_id` claim | Claim is in signed JWT; verified before middleware reads it | Low | Auth integration tests |
| R | Hard to attribute cross-tenant attempts | Every reject emits `tenant_scope.deny` log | Low | Alert on `tenant_scope.deny` spike |
| I | Row leak in raw SQL paths | Raw SQL discouraged; reviewed in PR; tenant_id filter present in audit queries | Moderate | Code review |
| D | Pathological queries cause lock | Statement timeout 5 s (Fly Postgres) | Low | pg slow-query log |
| E | Admin escalation via tenant join | `TenantUser.role` checked in dedicated dependency | Low | Audit `role.change` action |

## 4. Submission Pipeline

| STRIDE | Threat | Mitigation | Residual | Monitoring |
| --- | --- | --- | --- | --- |
| S | Fake portal callback | Webhooks validated with HMAC signatures; replay window 5 min | Low | `webhook.invalid_signature` log |
| T | Receipt body tampering | Canonical JSON + Ed25519 detached signature | Very low | Verifier reverifies on demand |
| R | Lost submission trail | Every state transition writes `SupplierSubmission.status` + audit row | Low | DB view |
| I | Credential leakage in worker logs | Redaction processor + Playwright credential masking | Low | Manual log review |
| D | Stuck job clogs queue | Celery soft / hard time limits; retry budget | Moderate | Flower / Celery exporter |
| E | Worker reads other tenant's data | Worker uses `with_tenant(tenant_id)` context manager | Low | Test fixture |

## 5. Submitter (Playwright)

| STRIDE | Threat | Mitigation | Residual | Monitoring |
| --- | --- | --- | --- | --- |
| S | Phishing portal mimicking real one | Strict allowlist of `Portal.base_url`; TLS pinning where supported | Moderate — visual mimicry undetectable | Submission diff against last successful run |
| T | Portal returns modified document | Hash document on download; record in `SubmissionReceipt.payload` | Low | Verifier mismatch alert |
| R | "We didn't submit that" customer dispute | Receipt with signed timestamp + signed canonical request body | Low | Public verifier link |
| I | Browser stores credentials on disk | Headless context uses ephemeral profile; storage cleared per run | Low | Worker startup log |
| D | Portal hangs the worker | Per-step timeouts (configurable, default 60 s) | Moderate | Celery hard-timeout |
| E | Compromised Chromium escapes sandbox | Containerized worker, dropped capabilities, read-only FS | Moderate | Image scan |

## 6. Receipt Signer

| STRIDE | Threat | Mitigation | Residual | Monitoring |
| --- | --- | --- | --- | --- |
| S | Signed receipt forgery | Ed25519 private key never leaves backend; verifier uses public key from registry | Very low | n/a |
| T | Receipt JSON post-hoc edit | Canonical-JSON normalization before sign; verifier rejects on hash mismatch | Very low | Verifier test suite |
| R | Lost private key history | `SigningKey` table preserves all key versions with `created_at` | Low | DB query |
| I | Private key in logs | Redaction processor flags `private_key`/`signing_key` substrings | Low | Manual audit |
| D | Signing call latency spike | Ed25519 is O(µs); negligible | Very low | Prometheus signer histogram |
| E | Stolen key signs arbitrary receipts | Rotate via documented runbook (`docs/SECRET_ROTATION.md`) | Moderate until first rotation | Alert on `signing_key.rotated` |

## 7. Verifier

| STRIDE | Threat | Mitigation | Residual | Monitoring |
| --- | --- | --- | --- | --- |
| S | Fake "verifier" site claims valid | Verifier is open source; canonical URL `verify.once.io` | Moderate | Documentation |
| T | Tampered public key in registry | Public-key registry served from primary backend over TLS; key id pinned in receipt | Low | Hash mismatch test |
| R | Cannot prove receipt validity in dispute | Receipt URL is permanent; signature deterministic | Very low | n/a |
| I | Public endpoint leaks tenant metadata | Response includes only signature-relevant fields | Low | Manual schema review |
| D | Public endpoint DDoS | Verifier on separate fly app; rate-limited; cacheable | Moderate | Fly metrics |
| E | Verifier becomes write surface | Verifier is read-only; HTTP `POST` returns 405 | Very low | Integration test |

## 8. Extension Vault

| STRIDE | Threat | Mitigation | Residual | Monitoring |
| --- | --- | --- | --- | --- |
| S | Malicious site reads vault | Extension uses MV3 service worker; messages signed/origin-checked | Moderate — depends on user not installing rogue ext | Manual review |
| T | Stored credential corruption | AES-GCM-256 with key derived via PBKDF2-310k from passphrase | Low | n/a |
| R | User claims "I didn't authorize this" | Every fill action logged to backend with timestamp + user-id | Low | Audit log |
| I | Credential exfiltration via dev tools | Vault encrypted at rest in `chrome.storage.local`; never plaintext in memory longer than needed | Moderate | Extension code review |
| D | Vault DB grows unbounded | Cap on entries; LRU eviction | Low | Self-check in popup |
| E | Extension permission creep | Minimal `host_permissions` list; reviewed per release | Low | Web Store review |

---

## Threat-model cell count

8 components × 6 STRIDE categories = **48 cells**, all populated above.

## Review cadence

- Per feature touching auth, signing, or tenant isolation → update affected
  rows in the same PR.
- Full review at every quarterly security checkpoint.
