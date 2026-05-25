# PRICING_TIERS.md — Packaging and pricing

> Internal reference. Numbers are anchors for sales conversations; final
> contracts are signed at the deal level. Customer-facing pricing is
> rendered from `/v1/billing/pricing` (server-driven) and shown on `/pricing`.

## Tier overview

| Tier               | Audience                                                | Per-seat / mo | Annual commit | Distinguishing capability                                          |
| ------------------ | ------------------------------------------------------- | ------------- | ------------- | ------------------------------------------------------------------ |
| **Free**           | Solo brokers / pilots                                   | $0            | n/a           | 25 submissions/mo; receipts; public verify page                    |
| **Pro**            | Small / mid agencies (≤10 seats)                        | $79           | $69           | Unlimited submissions; full data model; standard support           |
| **Extension-Only** | Agencies that _cannot_ let credentials leave the device | $149          | $129          | Credentials NEVER leave the user's browser; SaaS surface read-only |
| **Enterprise**     | Wholesalers, MGAs, top-100 agencies                     | Custom        | Custom        | SSO/SAML, audit export, E&O insurer integration, premium SLA       |

All paid tiers include the cryptographic receipt + public verifier
features. Trust is not a paid upgrade.

## Tier details

### Free

Goal: zero-friction trial. Convert to Pro within 30 days or churn cleanly.

- 25 submissions per calendar month, soft-capped (warnings, not hard blocks
  until 110%).
- Full receipt signing.
- Public `/verify`, `/trust`, `/coverage` access (these are public anyway).
- Single seat; community support only.
- 90-day data retention.
- No SLA, no SSO, no audit export.

### Pro — $79/seat/month ($69 annual)

The default tier. Most agencies land here.

- Unlimited submissions.
- Full data model (COIs, loss runs, EO certs, ACORD forms, risk schedules,
  consent ledger, inbound email).
- Standard email support, 1-business-day response.
- 7-year data retention (matches insurance recordkeeping norms).
- Includes the Chrome extension at no extra cost.
- 14-day new-carrier SLA (see `docs/PORTAL_SLA.md`).

### Extension-Only — $149/seat/month ($129 annual)

**Wedge C tier.** Built for agencies whose security posture forbids
credentials from ever leaving the user's device. Charges a premium because
the use case is genuinely security-driven, not budget-driven.

- All Pro features.
- All carrier submissions are driven through the MV3 extension only;
  the server-side Playwright path is disabled for this tenant.
- Vault keys are derived from the user's passphrase locally; backend never
  sees plaintext.
- Mandatory enrollment of FIDO2/passkey as second-factor unlock (when
  shipped per `docs/VAULT_PASSKEY_DESIGN.md`).
- Includes the most recent extension vault pen-test report
  (`docs/PENTEST_BRIEF.md` output) under NDA.
- Quarterly security review call with Once security lead.

### Enterprise — Custom

For wholesalers, MGAs, top-100 retail agencies, and any customer who needs
contractual customization.

- Everything in Pro + Extension-Only options as needed.
- SSO/SAML (Okta, Azure AD, Google Workspace).
- SCIM provisioning.
- Audit export endpoint (`/v1/audit/exports`) with custom schedules.
- Direct E&O insurer integration support (see `docs/PARTNER_EO.md`).
- 4-hour-response premium SLA.
- Named customer success engineer.
- Annual contract minimum; 100-seat floor preferred.

## What every tier includes (and we never charge for)

These are foundational and must remain free across all tiers, including
Free, because they're the moat:

- Cryptographic receipts.
- Public verifier microservice (anyone can self-host).
- Public `/coverage`, `/trust`, `/verify` pages.
- DNS-published signing keys.

If we ever paywall any of the above, we have lost the plot — re-read
`docs/MOAT.md`.

## Discount policy

- **Annual commit:** ~12.5% discount as shown in the table.
- **Multi-year:** additional 5% per year on top, capped at 3 years.
- **Brokerage / association:** custom; coordinate with deal owner.
- **Education / non-profit:** Pro at Free price; case-by-case.
- **E&O-discounted insureds:** no Once discount; the insurer absorbs it.

## Conversion levers

- Free → Pro: hit the 25-submission cap, see /pricing CTA.
- Pro → Extension-Only: security-questionnaire-driven; sales-led.
- Pro → Enterprise: 25+ seats, SSO question, or audit-export request.

## Anti-patterns we won't ship

- Per-submission metering on Pro+ tiers — sales friction killer.
- Charging for individual carrier integrations — undermines the 14-day SLA.
- Tying the verifier to a paid plan — destroys Moat #1.
- Free trials on Extension-Only — the security validation is real work.

## See also

- [docs/MOAT.md](./MOAT.md) — why the free features are free.
- [docs/PARTNER_EO.md](./PARTNER_EO.md) — insurer credit interplay.
- [docs/BILLING.md](./BILLING.md) — engineering reference for the billing API.
