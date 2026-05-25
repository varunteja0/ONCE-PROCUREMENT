# PARTNER_EO.md — E&O insurer partnership program

> Internal pitch document for E&O insurer business-development calls.
> Target carriers: Beazley, Tokio Marine HCC, CFC, Hiscox. The ask:
> a documented premium discount for insureds who run on Once, justified by
> cryptographic receipt evidence.

## The trade

| What Once provides                                                          | What the insurer provides                                   |
| --------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Immutable, Ed25519-signed receipt for every carrier submission              | A documented credit (5–15%) on the insured's E&O premium    |
| Standalone Apache-2.0 verifier service (independent audit)                  | Listing of Once as a "qualified loss-prevention technology" |
| Optional API endpoint that lets the insurer's claims team verify in seconds | Co-marketing: case studies, conference appearances          |
| 14-day new-carrier SLA so insureds aren't carrier-blocked                   | Joint webinars to the insurer's broker base                 |

## Why this matters to the insurer

E&O claims in the wholesale/MGA channel cluster around two failure modes:

1. **"We submitted but the carrier never received it."** Today, the
   defense is screenshots and email archives — easily disputed.
2. **"We submitted the wrong information."** Today, the defense is
   institutional memory and PDF copies — also easily disputed.

Once eliminates both failure modes with a signed, timestamped, byte-exact
record of what was submitted, when, to which portal, and under which TOS
version. The insurer can:

- Reduce claim defense costs (clear evidence accelerates settlement or
  dismissal).
- Underwrite Once-using agencies more confidently (lower frequency _and_
  lower severity).
- Differentiate their E&O product to brokers who care about modern tooling.

## Why this matters to the broker/MGA

- A 5–15% E&O premium credit is meaningful and visible.
- Once-using agencies look better in their own audits and SOC 2 reviews.
- The receipts double as marketing collateral when wholesaling to retailers.

## Mechanics

### Verification integration

The insurer's claims team gets one of:

1. **API access** — `GET https://getonce.com/v1/verify/{receipt_id}` (public,
   no auth, JSON response). They can hit it from a SOAR playbook.
2. **Self-hosted verifier** — they deploy the `verifier/` microservice on
   their own infrastructure. Apache 2.0 licensed; runs against the public
   keys; no Once dependencies. Best for insurers with strict third-party
   policies.
3. **Bookmarklet** — a one-click verify for non-engineering claims
   adjusters (see `frontend/public/verifier-bookmarklet.js`).

### Discount eligibility

Default proposed structure:

- **5% credit** for any insured who provides receipt evidence for at least
  80% of submissions in the policy year.
- **10% credit** for 95%+, plus enabling Once's "audit export" feature
  (`/audit/exports`) for the insurer.
- **15% credit** for 95%+ AND deploying the insurer's own verifier
  instance (= full third-party validation).

Final tiers are per-insurer; this is the opening anchor.

### Co-marketing

- Joint press release on partnership announcement.
- Once is listed as a "qualified technology" on the insurer's broker portal.
- One joint webinar per quarter to the insurer's broker base.
- Logo permission both ways, subject to the usual brand-use review.

## FAQ for the insurer

**Q: How do we know Once isn't faking the receipts?**
A: You don't have to trust us. The `verifier/` microservice is open source
under Apache 2.0. The public keys are published in DNS as
`_once-keys.getonce.com` TXT records (out-of-band of the Once infra). You
can verify any receipt without touching Once at all.

**Q: What if Once gets breached?**
A: Receipts cryptographically bind a payload to a key at a moment in time.
A breach cannot retroactively alter a receipt — only forward-signing
behavior is at risk. Key rotation procedures are documented in
`docs/SECRET_ROTATION.md` and `docs/PUBLIC_TRUST_KEYS.md`.

**Q: What about chain of custody for the underlying payload?**
A: The payload's `payload_hash` is part of the signed receipt, so the
hash is bound to the signature. The full canonical payload is also
returned by `GET /v1/verify/{id}.json` for independent inspection.

**Q: How current is your coverage?**
A: The live carrier scorecard is at `https://getonce.com/coverage`.
We commit to 14-day delivery for any requested carrier under
`docs/PORTAL_SLA.md`.

**Q: What about non-Once submissions during the policy year?**
A: Mixed-mode is fine. The credit is graded on coverage, not exclusivity.
We have customers who route specialty lines through Once and standard
lines through their existing AMS.

**Q: Pricing — what does Once cost the agency?**
A: See `docs/PRICING_TIERS.md`. The credit you offer should be net
positive for the agency at every tier.

## Internal next actions

1. Identify the partnership owner at each of {Beazley, Tokio Marine HCC,
   CFC, Hiscox}.
2. Send the cold email template (`gtm/02-cold-email-templates.md` — add a
   variant for E&O insurers).
3. First call: walk through this document; show the `/verify` page live
   with a real receipt ID.
4. Second call: technical review with their claims engineering team.
5. Third call: pilot agreement covering 10 named insureds.

## See also

- [docs/MOAT.md](./MOAT.md) §1 — cryptographic receipts.
- [verifier/README.md](../verifier/README.md) — independent verifier.
- [docs/PUBLIC_TRUST_KEYS.md](./PUBLIC_TRUST_KEYS.md) — DNS key publication.
- [docs/PRICING_TIERS.md](./PRICING_TIERS.md) — what the agency pays.
