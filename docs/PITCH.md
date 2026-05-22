# Once — Supplier-Side Procurement, with an MGA Insurance Wedge

> The customer-facing one-pager lives at
> [`../gtm/01-one-page-pitch.md`](../gtm/01-one-page-pitch.md).
> This document is the **longer founder narrative**: why this market,
> why now, why this team, and how the insurance MGA wedge gets us to
> default-alive revenue inside two quarters.

## TL;DR

US specialty insurance MGAs spend an obscene amount of human time
re-keying the same supplier and producer data into carrier portals that
were built in 2003 and never upgraded. AmTrust. Markel. Applied Epic.
Vertafore AMS360 and Sircon. CNA. Nationwide E&S. Hawksoft. NowCerts.
Every portal is a different shape; every MGA has a back office full of
people whose job is to retype the same fifty fields into them.

**Once** is the autopilot for that back office. Operators install a
browser extension, fill their supplier/producer profile into an
encrypted vault on first use, and from then on Once submits to any
carrier portal in one click — and emits an Ed25519-signed audit receipt
that proves *what was submitted, by whom, under what consent, against
what version of the carrier's terms* — forever.

The wedge is procurement-shaped (supplier data, COIs, consent,
auditability) but the buyer is an MGA, which means the contract value
is **5–10× a generic procurement seat** and the renewal cycle is tied
to carrier audits we already win.

## 1. The shape of the problem

A typical specialty MGA running ~$80M of premium has:

- **8–20 carrier portals** they submit into. Most accept no API.
- **30–200 producer relationships**, each with a slightly different
  legal entity, NAIC number, E&O policy, W-9, COI.
- **A back-office team of 4–25 people** whose primary job, measured in
  hours, is *retyping* and *reconciling*.
- **Annual carrier audits** that require the MGA to demonstrate
  consent, submission timestamps, and the precise data submitted, for
  every binder. Nobody can produce this; the audits are graded on a
  curve.
- **A growing E&O exposure** because a single typo in a carrier portal
  becomes a coverage gap that's discovered at claim time.

Existing tools fail in specific, repeatable ways:

| Tool category | Why it fails for MGAs |
|---|---|
| Generic AMS (Applied/Vertafore) | Owns the system of record but does not submit *into* third-party carrier portals. |
| Generic procurement (Coupa, Ariba) | Built for buyers procuring goods, not for an MGA placing risk into carriers. |
| RPA platforms (UiPath, Automation Anywhere) | $100k+ implementations; fragile against portal UI drift; no consent/receipt primitive. |
| Browser-based form fillers (1Password, LastPass) | No portal-awareness, no audit trail, no tenant model, no consent. |

## 2. Our wedge — "Submit once. Prove it forever."

Once is shaped like a procurement tool (a supplier portal, COIs,
consent ledger) but priced and sold like a compliance tool (per-MGA,
six-figure ACV, anchor renewal at carrier audit time). The signed
receipt is the wedge: it gives MGAs a single artifact they can hand to
a carrier auditor, regulator, or plaintiff's attorney and say "here is
what we submitted, here is the consent, here is the carrier's TOS
hash at the time, signed by a key whose public half is published."

Why now:

1. **EU AI Act Article 6** (high-risk AI in insurance underwriting)
   creates an immediate appetite for cryptographically-verifiable
   audit trails — even US MGAs with EU-domiciled reinsurers need
   them.
2. **NY DFS Part 500 (2023 amendment)** and similar state regs are
   pulling MGAs into the same data-handling bucket as carriers.
3. **Carrier portals are still un-API'd** in 2025 because there is no
   incentive on the carrier side to expose APIs that would commoditize
   their distribution. This will not change. Browser-side automation
   is the only viable path for the foreseeable future.
4. **WebCrypto + MV3 + Ed25519** finally make it possible to build a
   trustworthy operator-side extension that holds the credentials
   without the vendor (us) holding them.

## 3. The insurance MGA wedge — why this beats generic procurement

A generic procurement SaaS sells a $400/seat/month tool and lives or
dies on seat expansion. An MGA-focused tool sells a *per-binder
guarantee* — "every binder you place will produce a signed receipt and
a renewal calendar entry" — which the buyer scores against E&O premium
savings and audit-cycle headcount.

The unit economics:

- **ACV anchor:** $36k–$120k/year per MGA, depending on premium volume.
- **Renewal trigger:** carrier audit cycle. Once we're in the audit
  binder, we're not coming out.
- **Expansion vector:** add carrier portals; add a "second MGA"
  tenant inside the same parent organization; sell the **verifier
  endpoint** (white-labelled) to carriers as a "proof of submission"
  service.

## 4. The product, today

The repo you are reading contains:

- A **FastAPI + SQLAlchemy 2.0 async backend** that owns tenants,
  suppliers, portals, submissions, receipts, consent, COIs and an
  append-only audit log. Pipeline is Celery-fanout with atomic claim,
  so a worker crash never double-submits.
- A **React/Tanstack-Query operator console** for the MGA back-office
  team: queue, receipts, consent ledger, COI expiry monitor.
- A **MV3 browser extension** with an encrypted IndexedDB vault
  (AES-GCM-256, PBKDF2-310k key derivation) and portal-specific
  content scripts for the first five carrier portals.
- A **public verifier service** that anyone — a carrier, a regulator,
  the supplier themselves — can hit to verify a receipt without
  trusting Once.
- A **sister product, OnceTax** (Shopify sales-tax SaaS), as a
  Wedge-B revenue line on a completely separate stack (Cloudflare
  Workers + D1) so cash flow from the tax product funds the MGA
  enterprise sale cycle.

## 5. What we're not building (and why)

- **No carrier-side integrations.** We will never ship code that runs
  inside a carrier. The asymmetric position — operator-side,
  consent-bound, signed receipts — is the moat.
- **No auto-signing of binders without a human in the loop.** The
  `ConsentScope.SUBMIT_AND_SIGN` enum value exists but is gated behind
  a manual feature flag (`ENABLE_TOS_RISKY_PLATFORMS=False` by
  default).
- **No US sales-tax filing in OnceTax v0.** PDF prep only; an actual
  filing engine creates a regulatory surface we don't want yet.

## 6. The 12-month plan

| Quarter | Milestone |
|---|---|
| Q1 | 5 design partners, 3 carrier portals live, signed-receipt v1 in production, $180k of annualized ARR. |
| Q2 | 10 paying MGAs, 8 portals, OnceTax launched in Shopify App Store, first carrier-side verifier integration. |
| Q3 | $1M ARR run-rate across both wedges, SOC 2 Type I report, first reinsurance-broker tenant. |
| Q4 | Series A on the back of audit-cycle renewals; ship the carrier-side white-labelled verifier as a separate product line. |

## 7. Why us

Founders have shipped both browser-side automation at scale
(autoapplyai) and tax/compliance SaaS into regulated buyers. The
codebase you're looking at is not a prototype — it ships with a real
test suite, a real CI matrix, signed receipts, tenant isolation, and a
dual-licensed source tree (BSL → Apache 2.0).

## 8. What to read next

- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — the system diagram and
  the receipt data-flow.
- [`./SECURITY.md`](./SECURITY.md) — threat model.
- [`./COMPLIANCE.md`](./COMPLIANCE.md) — how we map to SOC 2, GDPR,
  CCPA, EU AI Act Article 6.
- [`../gtm/`](../gtm/) — the go-to-market collateral: one-pager,
  cold-email templates, ICP target list, MSA template, discovery-call
  script.
