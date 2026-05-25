# Once Customer Trust Plan

Last updated: 2026-05-25

Once should never ask customers to "blindly trust" us. The sales motion should
teach buyers how to verify our controls, inspect our evidence, and understand
the limits of the current pilot product before live supplier or portal data is
used.

## Trust Promise

We earn trust with four things:

1. **Clear scope:** selected pilot portals, documented customer authorization,
   and no unsupported universal-coverage claims.
2. **Data protection:** tenant-scoped access, production secret checks,
   least-privilege operations, local encrypted extension vault, and secure
   infrastructure defaults.
3. **Verifiable evidence:** Ed25519-signed receipts, public verifier, public key
   endpoint, audit logs, and customer exports.
4. **Honest documentation:** security overview, privacy policy, DPA summary,
   subprocessors, retention, incident response, and current SOC 2 status.

## Customer Questions We Must Answer Fast

| Buyer question                     | Current answer                                                                                                                            |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| What data do you store?            | Producer/supplier profile fields, documents, portal activity, consent records, receipts, audit events, billing/support/security metadata. |
| Is data isolated by customer?      | Yes: tenant-scoped models and API dependencies are core contracts. Continue adding tenant-filtered queries and tests for every endpoint.  |
| Who can access customer data?      | Customer tenant users by role, and limited Once operators for support/security. Cockpit/operator access must remain audited.              |
| How do we know what was submitted? | Signed receipt over canonical JSON plus audit trail and public verifier.                                                                  |
| Are you SOC 2 certified?           | Not yet. Say "SOC 2 readiness underway" until an auditor engagement and report exist.                                                     |
| Do you sell or train on our data?  | No customer data sale. No public AI model training on tenant data.                                                                        |
| What happens if a portal breaks?   | Portal drift becomes a support event. Risky portals/captcha/MFA require human review or blocking.                                         |
| How do we delete/export data?      | Provide export/deletion on request, subject to legal/audit receipt retention. Formalize this in the DPA.                                  |

## Public Artifacts

The landing site now exposes lightweight trust pages:

- `landing/security.html` — security overview and buyer-review posture.
- `landing/privacy.html` — pilot privacy policy.
- `landing/terms.html` — pilot terms summary.
- `landing/dpa.html` — DPA summary and subprocessor list.

These are intentionally conservative. They are not a substitute for signed legal
terms, but they stop the public website from having dead Privacy/Terms/Security
links and give prospects a first review packet.

## Near-Term Trust Work

### P0 Before Paid Live Data

- Align all domains, legal entity names, and contact emails across docs, app,
  extension, landing, verifier, and GTM materials.
- Finish customer-facing consent creation/revocation/approval flows.
- Ensure the public verifier resolves signing keys by `signing_key_id` and works
  with historical rotated keys.
- Enforce customer password policy and lockout on the public auth flow.
- Make production startup fail closed for signing-key readiness and required
  security middleware.
- Remove or clearly mark all generated scratch files and old log artifacts.

### P1 During First Design-Partner Pilot

- Convert `landing/dpa.html` into a lawyer-reviewed DPA and security addendum.
- Add a public subprocessor change-notice process.
- Add status page and incident-notification playbook for customers.
- Add a customer-facing retention/deletion request workflow.
- Prepare a short security questionnaire response pack under NDA.
- Add a sample receipt/verifier demo link and screenshots of consent ledger,
  receipt detail, and audit export.

### P2 Before Self-Serve SaaS

- Move browser app auth away from localStorage-backed bearer tokens or document
  and mitigate the XSS/token-theft risk with a stronger session design.
- Add database-enforced receipt immutability for signed receipts.
- Add secret-scanning and dependency-policy gates to CI.
- Complete SOC 2 Type I readiness, then begin Type II observation.

## Sales Guidance

Say this:

> Once is in controlled pilot readiness. We protect tenant data, require explicit
> authorization for portal activity, and emit signed receipts that your team can
> verify independently. We will walk your security team through the controls
> before live data is used.

Do not say this yet:

> We are SOC 2 certified, support every carrier portal, guarantee legal
> admissibility of receipts, or can run fully self-serve without onboarding.

## Customer Trust Flow

1. Discovery call: confirm portal scope, data classes, and compliance needs.
2. Security review: send trust pages, DPA summary, subprocessors, and security
   overview.
3. Pilot contract: include portal list, approval workflow, DPA, support window,
   and retention/deletion terms.
4. Sandbox demo: show consent ledger, portal fill, signed receipt, public
   verifier, and audit export.
5. Live pilot: start with 1 tenant, 1-3 portals, and explicit approval on every
   submission.

## Owner Checklist

- Security contact: `security@getonce.com`
- Privacy contact: `privacy@getonce.com`
- Sales contact: `varun@onceidentity.com`
- Legal entity in public docs: Once Procurement, Inc.
- Default public domain: `getonce.com`
- App domain: `app.getonce.com`
- Verifier domain: `verify.getonce.com`
