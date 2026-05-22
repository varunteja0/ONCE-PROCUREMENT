# extension/ — Agent rules

> Authoritative rules: [CONTRACTS.md](../CONTRACTS.md) §10, §12 (rows 15–19).
> This file = MV3-extension-only working rules.

## Stack snapshot

- **Manifest V3** Chrome extension
- Vite + `@crxjs/vite-plugin`
- React + TypeScript for the popup
- **Vanilla TypeScript** for content scripts (no React in content)
- Vault: encrypted IndexedDB via WebCrypto SubtleCrypto
  - AES-GCM-256, key derived via PBKDF2 SHA-256, **310k iterations**
- Vitest + jsdom for unit tests

## Layout

```
src/
  background/    # MV3 service worker (single entry)
  content/
    dispatcher.ts          # detects portal, delegates to filler
    fillers/
      _shared.ts           # common helpers — keep tiny, no UI
      <platform>.ts        # one per supported portal
  lib/
    api.ts                 # backend API client (uses fetch + JWT)
    crypto.ts              # WebCrypto helpers — DO NOT reinvent
    storage.ts             # chrome.storage wrappers
    vault.ts               # encrypted profile store
  popup/                   # React UI (App, Approve, Profile, Receipts)
  types/                   # profile.ts, portal.ts — shared types
tests/                     # mirrors src/ — vault, fillers, dispatcher
```

## Hard rules (extension)

1. **No React in content scripts.** Content runs in the page's world; keep it
   small, dependency-free, and CSP-friendly.
2. **All cryptography goes through `lib/crypto.ts`.** Never call
   `crypto.subtle` directly from elsewhere; never roll your own KDF.
3. **PBKDF2 params are locked:** SHA-256, **310,000** iterations, 16-byte
   salt, 12-byte IV. Changing these breaks every existing vault.
4. **Vault items are encrypted at rest** before hitting IndexedDB. Plaintext
   profile data must never be stored or logged.
5. **Permissions:** keep `manifest.config.ts` minimum-necessary. Adding a new
   host permission or API requires a comment justifying it.
6. **Filler contract:** each `fillers/<platform>.ts` exports
   `detect(): boolean` and `fill(profile, fields): Promise<FillResult>`.
   The dispatcher picks one filler; no filler may import another.
7. **DOM access:** prefer `data-*` selectors and ARIA roles over brittle
   class/CSS chains. Wrap in `waitFor(selector, timeoutMs)`.
8. **No `console.log`** in committed code — use the logger in `lib/`. Test
   logs only.
9. **No `any`.** TS strict. ESLint `--max-warnings 0`.
10. **Tests required** for every new filler (`tests/fillers_<platform>.test.ts`)
    and for any change to `vault.ts` / `crypto.ts` / `dispatcher.ts`.

## Adding a new portal filler

1. Add fixture HTML under `fixtures/portals/<platform>/` at repo root.
2. Create `src/content/fillers/<platform>.ts` exporting `detect` and `fill`.
3. Register in `src/content/dispatcher.ts`.
4. Add `tests/fillers_<platform>.test.ts` loading the fixture into jsdom.
5. Add the matching backend submitter only if server-side automation is also
   needed (different concern — see [backend/AGENTS.md](../backend/AGENTS.md)).

## Running locally

```powershell
cd extension
npm install
npm run dev          # vite dev with crxjs HMR
npm run build        # production bundle into dist/
npm run test         # vitest run
```

Load `extension/dist/` in `chrome://extensions` with Developer Mode on.

## Never do

- Ship a content script that imports React / any UI library.
- Store unencrypted profile data anywhere.
- Add a host permission without justification in the PR.
- Use synchronous `chrome.storage` callbacks — wrap in promises in
  `lib/storage.ts`.
- Hardcode the backend URL — read from `lib/api.ts` config.
