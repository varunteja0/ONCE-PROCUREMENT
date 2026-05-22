# Screencast Shot List — Once Demo Reel

**Purpose**: A precise, frame-by-frame shot list for a ≤90 second product demo video. Goal: a stranger watching this should immediately understand *what Once does, who it's for, and why it's not a generic RPA toy*.

Recording target: **1920×1080 @ 30fps**, no audio (we'll voice over post). Use OBS or QuickTime. Keep the cursor visible and slow. Record in a fresh incognito window with the brand demo seed (`make seed && make demo`).

## Cold open (0:00 – 0:05)

| Time | Visual | Caption (top-left, 32pt) | Notes |
|------|--------|--------------------------|-------|
| 0:00 | Black frame fade in to Once wordmark + tagline "Stop typing the same form twice." | — | 0.4s fade in, 1s hold, 0.4s fade out. |
| 0:04 | Cut to a real AmTrust supplier portal screenshot, slightly blurred. | "Specialty insurance still runs on copy-paste." | Public screenshot only; redact account #s. |

## Problem framing (0:05 – 0:20)

| Time | Visual | Caption | Notes |
|------|--------|---------|-------|
| 0:05 | Time-lapse of a Brittany-style ops user filling the same supplier across 3 portals (AmTrust → Markel → Applied Epic). Speed to 4×. | "Same data. Three portals. Twelve fields each." | Use the local nginx fixture portals — do **not** record actual carrier portals. |
| 0:18 | Cut to clock graphic. | "12 min/supplier. 400 suppliers/month. = 80 hours." | Static motion graphic, 2s hold. |

## Solution reveal (0:20 – 0:45)

| Time | Visual | Caption | Notes |
|------|--------|---------|-------|
| 0:20 | Hard cut to Once cockpit home (`/cockpit`). | "Connect once. Submit everywhere." | Use the `acme-demo` seed tenant. |
| 0:24 | Click "Add supplier" → onboarding wizard step 1 (basic info). | — | Show step indicator clearly: 1/9. |
| 0:28 | Drag a sample COI PDF into the upload zone. Show extracted fields auto-populating. | "ACORD 25 extracted in 1.4s." | Capture the actual extraction toast. |
| 0:34 | Wizard auto-advances. Show review step (step 9) with confidence badges. | "Confidence-scored, every field." | Hover one badge to show provenance tooltip. |
| 0:38 | Click "Submit to AmTrust + Markel + Applied Epic" (multi-select chip). | — | Multi-portal submit is the wow moment. |
| 0:41 | Cut to live submissions table: 3 rows turning from "queued" → "submitting" → "submitted" with green check + receipt link. | "Three portals. One click." | Use the local Playwright submitter against fixtures. |

## Proof / receipts (0:45 – 1:05)

| Time | Visual | Caption | Notes |
|------|--------|---------|-------|
| 0:45 | Click a receipt link → opens `getonce.com/verify/{id}` in a new tab. | — | Real verifier page. |
| 0:48 | Show the green "Verified" hero, then scroll to receipt details. | "Every submission is signed and verifiable." | Hold on the Ed25519 + canonical JSON line. |
| 0:54 | Cut to the audit trail page in cockpit, showing hash chain. | "Hash-chained audit log. Tamper-evident." | Highlight the chain integrity indicator. |
| 1:00 | Click "Export signed PDF". Show the PDF preview with QR code. | "Auditor-ready in one click." | The PDF is downloadable from `/cockpit/audit/{tenant}/export.pdf`. |

## Closing (1:05 – 1:25)

| Time | Visual | Caption | Notes |
|------|--------|---------|-------|
| 1:05 | Cut to a 3-up grid: MGA logo, broker logo, carrier ops logo (placeholders). | "Built for MGAs, brokers, and carrier ops." | Use generic silhouette logos until real ones are paid. |
| 1:10 | Show pricing card: 3 tiers with key numbers visible. | "Pilots from $500/month. White-glove onboarding." | Read straight off `frontend/src/pages/pricing.tsx`. |
| 1:17 | End card: Once wordmark + URL `getonce.com` + email `pilots@getonce.com`. | "Talk to a human." | Hold 4s. |
| 1:25 | Fade to black. | — | — |

## B-roll to capture (no fixed slot)

These are extra shots to splice in if pacing needs filler. Capture them while you're already recording — cheaper than going back.

- Slow scroll through the supplier list (~6s).
- Cursor hovering the Stripe billing portal showing the metered usage chart.
- The inbound email triage view receiving a COI by email and auto-routing it.
- The Chrome extension popup showing "Last submission: 12s ago · ✓ AmTrust".

## Don't include

- ❌ Actual carrier portal screens (legal risk — use fixtures).
- ❌ Real customer names, account numbers, NAIC codes, supplier names. Use the seed data.
- ❌ Animations longer than 1.5s (kills retention).
- ❌ Voice-overs in the raw recording (we record audio separately).
- ❌ Stripe test card numbers visible on screen.

## Post-production checklist

- [ ] All carrier names redacted or fixture-only.
- [ ] All UUIDs / receipt IDs are from seed data (no real customer leakage).
- [ ] Captions in Inter font, 32pt, white with 60% black drop shadow.
- [ ] Total runtime ≤ 90s — if longer, cut B-roll first, then the closing pricing card.
- [ ] Export H.264 MP4 + WebM, plus a 6MB GIF preview for cold emails.
- [ ] Upload to `gtm/assets/screencasts/v{n}/` (gitignored, local only).
- [ ] Update `gtm/PITCH.md` with link to latest cut.

## Recording environment checklist

- [ ] Browser: Chrome incognito, 1920×1080 window, 100% zoom, no extensions.
- [ ] Cursor: enabled, large size for visibility.
- [ ] Notifications: macOS / Windows Focus mode ON.
- [ ] Seed: `make reset-db && make seed` immediately before recording (clean state).
- [ ] Demo tenant: `acme-demo` with `brittany@acme.test` user.
- [ ] All five fixture portals reachable: `make portals-up` (see `fixtures/portals/README.md`).
