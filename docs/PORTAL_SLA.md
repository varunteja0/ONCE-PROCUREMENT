# PORTAL_SLA.md — The 14-day new-carrier SLA

> A binding commitment, not a marketing line. If a customer requests a
> carrier portal we don't yet support, we ship a working submitter within
> **14 calendar days** of intake. This document defines the scope, the
> intake process, the milestones, and what's currently in flight.

## Why we make this commitment

Competing vendors (Semsee, Bold Penguin, Indio, Broker Buddha, Relay) treat
new carriers as quarterly roadmap items. That's because they don't have a
submitter framework or a fake-portal fixture harness — every portal is a
greenfield project. We have both (see `docs/MOAT.md` §2, §5), so 14 days is
genuinely how long it takes us. Publishing the SLA pulls forward the trust
that the framework deserves.

## In scope

A "shipped" submitter must:

1. Authenticate against the carrier portal using credentials the customer
   provides (server-side Playwright OR extension-driven, whichever the
   portal allows).
2. Submit a representative ACORD 125 application end-to-end.
3. Capture a confirmation number, the submitted payload, and a screenshot.
4. Emit a signed `SubmissionReceipt` byte-identical to every other Once
   receipt.
5. Have at least one hermetic test in `backend/tests/test_submitter_<platform>.py`
   driven by a recorded fixture in `fixtures/portals/<platform>/`.
6. Appear with `supported=true` on the public `/coverage` scorecard.

## Out of scope (we do not commit to these in 14 days)

- Custom field mappings beyond standard ACORD 125 lines (those are
  scoped per-customer separately).
- Bind-quote workflows past initial submission.
- Loss-control surveys with embedded carrier IDP flows.
- Carriers that require a notarized API agreement (intake clock pauses
  until the agreement is signed).

## Intake process

1. Customer emails `carriers@getonce.com` with: carrier name, portal URL,
   credential set we can use for a sandbox/test account, and the LOB(s)
   they need.
2. We acknowledge within one business day (T+0) and create an entry in
   `docs/PORTAL_SLA.md` under "In-flight."
3. T+1: a deal owner schedules a 30-min reverse-engineering session with
   the customer to walk the portal once.
4. T+2 → T+10: implementation against the live portal + fixture capture.
5. T+10 → T+12: hardening, idempotency, error-branch coverage.
6. T+12 → T+14: customer-side smoke test with their real credentials;
   declaration of "supported" and addition to the scorecard.

If we miss T+14, the customer gets the next 30 days free.

## Currently in flight (as of repo HEAD)

These platforms are declared in the `PortalPlatform` enum but do **not**
have a shipping submitter. They will be the first deliverables under the
SLA program once the first customer asks.

| Platform        | Type    | Priority  | Notes                                                              |
| --------------- | ------- | --------- | ------------------------------------------------------------------ |
| `cna`           | Carrier | P0 — high | Frequently requested in WSIA pipeline.                             |
| `nationwide_es` | Carrier | P0 — high | E&S desk; customer-pull from gtm/.                                 |
| `guidewire`     | AMS     | P1        | PolicyCenter integration via API where available; portal fallback. |
| `hawksoft`      | AMS     | P1        | High customer pull from smaller agencies.                          |
| `ezlynx`        | AMS     | P1        | Large installed base.                                              |
| `nowcerts`      | AMS     | P2        | Smaller footprint but recurring requests.                          |

## Shipped today

See `/coverage` (or `GET /v1/public/portals`) for the live list. As of HEAD
that includes (non-exhaustive): AmTrust, Markel, AMS360, Applied Epic, plus
the platforms with full submitter implementations in
`backend/app/services/submitter_registry.py`.

## Tracking commitments

Every SLA engagement is logged with: customer, carrier, T+0 date, T+14
target, ship date, and outcome (delivered/missed/credit). The log lives in
the deal owner's runbook; aggregated reliability numbers are published
quarterly in customer business reviews.

## When the SLA does NOT apply

- Customer is on the free tier (Pro and Enterprise only).
- The portal has been the subject of an active legal complaint from the
  carrier against any RPA vendor (we won't put the customer at risk).
- The portal has no test/sandbox environment and the customer cannot
  provide a non-production credential set (we will not test against
  production accounts we don't own).

## See also

- [docs/MOAT.md](./MOAT.md) §2 — the submitter framework as a moat.
- [docs/SUBMITTERS.md](./SUBMITTERS.md) — engineer-facing implementation guide.
- [backend/AGENTS.md](../backend/AGENTS.md) — engineering conventions.
