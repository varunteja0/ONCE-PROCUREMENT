# Once — Chrome Extension (MV3)

The Once browser extension is the user-facing surface of the supplier-portal
autopilot. It detects supported carrier portals, fills them from an
**encrypted local vault**, and captures a tamper-evident receipt for every
submission.

## Permissions (and why)

| Permission   | Why it's required                                                                  |
|--------------|------------------------------------------------------------------------------------|
| `storage`    | Tokens, API base URL, auto-lock duration, default-supplier-per-portal preferences. |
| `activeTab`  | Send `content.fill` to the active tab on an explicit user gesture (toolbar click). |
| `scripting`  | Programmatic re-injection of the content script after options/popup actions.       |
| `alarms`     | Periodic sync (5 min), pending-submission retry (30 s), auto-lock check (1 min).   |
| `idle`       | Drives the auto-lock state machine when the user steps away from the browser.     |
| `tabs`       | `tabs.onUpdated` for URL-pattern portal detection and per-tab badge text/colour.   |

Host permissions are limited to the carrier domains in `manifest.config.ts`.
No `<all_urls>` access is granted.

## Architecture

```
┌──────────────────────┐  routeMessages()  ┌─────────────────────────┐
│  popup / options     │ ◄───────────────► │  background SW           │
│  (React + Zustand)   │                   │  alarms, fetch proxy,    │
│  vault session key   │                   │  portal detect, badge    │
└──────┬───────────────┘                   └──────────┬──────────────┘
       │ sendToTab(content.fill)                     │ chrome.idle
       ▼                                              ▼
┌──────────────────────┐                   ┌─────────────────────────┐
│ content/dispatcher   │                   │  chrome.storage.local    │
│ + per-portal fillers │                   │  (tokens, prefs, cache)  │
└──────────────────────┘                   └─────────────────────────┘
```

* **Vault session key** lives **only** in the popup process. The background
  service worker stores a `vaultUnlockedAt` timestamp so it can drive
  auto-lock, but it never sees the AES key. This keeps fillable profiles
  off-disk in service-worker memory.
* **Messaging** is a discriminated-union bus (`src/lib/messaging.ts`) with a
  matching `ResponseMap`. The background registers a `HandlerMap` via
  `routeMessages` which always returns `true` to keep the MV3 async channel
  open.
* **Sync** (`src/lib/sync.ts`) pulls suppliers and submissions from the
  backend, conflict-resolves last-write-wins on `updated_at`, and drains a
  pending-submission queue (max 5 attempts each).
* **Activity log** (`src/lib/activity.ts`) is an IndexedDB ring buffer
  capped at 200 entries — events only, never field values.
* **Auto-lock** is layered: the in-process vault has its own 15-minute
  timer; the background additionally checks every minute against
  `chrome.idle` state and broadcasts a `vault.lock` message when the
  user has been idle past the configured threshold.

## Project layout

```
extension/
├── manifest.config.ts          # MV3 manifest (typed via @crxjs)
├── src/
│   ├── background/
│   │   ├── index.ts            # service worker entry + handlers + alarms
│   │   ├── portalDetector.ts   # URL-pattern detection + badge map
│   │   └── autoLock.ts         # idle-driven lock scheduler
│   ├── content/
│   │   ├── dispatcher.ts       # runs on portal pages, dispatches to filler
│   │   └── fillers/*           # per-platform DOM adapters (frozen)
│   ├── lib/
│   │   ├── api.ts              # typed REST client via API_CALL proxy
│   │   ├── messaging.ts        # typed message bus + routeMessages
│   │   ├── store.ts            # Zustand popup state
│   │   ├── sync.ts             # pull + queue + drain
│   │   ├── activity.ts         # IndexedDB ring buffer
│   │   ├── storage.ts          # chrome.storage.local wrappers
│   │   ├── crypto.ts           # WebCrypto primitives (frozen)
│   │   └── vault.ts            # AES-GCM-256 vault (frozen)
│   ├── popup/                  # React UI (Setup / Locked / Home / Suppliers / Submissions / Activity)
│   └── options/                # Settings page (connection, security, defaults, vault import/export)
└── tests/                      # vitest + @testing-library/react
```

## Build / test / lint

```pwsh
cd extension
npm install
npm test           # vitest run
npm run lint
npm run build      # tsc --noEmit && vite build → dist/
```

Load `dist/` as an unpacked extension in Chrome (`chrome://extensions` →
*Developer mode* → *Load unpacked*).

## Manual test checklist

1. **First-run setup** — install, click toolbar icon, enter backend URL +
   access token, choose a vault passphrase ≥ 8 chars, confirm. Expect to
   land on Home.
2. **Lock + unlock** — click the lock icon; the popup re-opens to the
   Locked screen. Enter the passphrase to unlock again.
3. **Portal detection** — open `https://app.appliedepic.com`; the toolbar
   badge shows `EPIC` and the Home tab shows the detection card with a
   confidence > 90 %.
4. **Fill** — on a supported portal, click *Fill from supplier*. The active
   filler runs and a success banner shows the field counts.
5. **Capture** — click *Capture this submission*; an entry appears in the
   Submissions tab within ~5 minutes (after the next sync).
6. **Offline → online** — disable network, capture; the entry is queued
   in `once.pendingSubmissions`. Re-enable network; the queue drains on
   the next 30-second retry alarm or when *Sync* is pressed manually.
7. **Auto-lock** — set auto-lock to 5 min on the options page; idle the
   browser; the vault locks within a minute of the 5-minute threshold.
8. **Options → export / import vault** — round-trip the JSON file; the
   popup still unlocks with the original passphrase.
9. **Options → clear vault** — type `DELETE`, click *Clear vault*; the
   extension returns to first-run setup.

## Privacy

* The vault is encrypted with AES-GCM-256 using a key derived from the
  passphrase via PBKDF2-SHA-256 (310 000 iterations, per `lib/crypto.ts`).
* Plaintext profile fields never leave the popup process except as the
  `content.fill` payload sent to the matching tab.
* Telemetry is **always off** — there is no analytics endpoint of any kind.
  All HTTP traffic targets the user-configured backend URL.
