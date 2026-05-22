---
applyTo: "extension/src/**/*.{ts,tsx}"
description: "MV3 extension rules — no React in content, crypto via lib/crypto only, locked KDF params"
---

# Extension (MV3) — required behavior

1. **Content scripts (`src/content/**`)** are **vanilla TypeScript**. Do not
   import React, JSX runtimes, or any UI library here. Keep bundles small and
   CSP-friendly.
2. **Popup (`src/popup/**`)** is React. Components import shared types from
   `src/types/` and API calls from `src/lib/api.ts`.
3. **All crypto goes through `src/lib/crypto.ts`.** Never call
   `crypto.subtle` directly elsewhere; never write a new KDF or cipher path.
4. **PBKDF2 parameters are locked**: SHA-256, **310,000** iterations, 16-byte
   salt, 12-byte IV. Changing any of these invalidates every existing vault —
   do not change without explicit approval and a migration plan.
5. **Vault writes encrypt before persistence.** Plaintext profile data must
   never reach IndexedDB, `chrome.storage`, logs, or analytics.
6. **`chrome.storage` access** goes through `src/lib/storage.ts` (promisified
   wrappers). Do not call the callback APIs directly in feature code.
7. **API calls** go through `src/lib/api.ts`. The backend base URL is read
   from configuration, never hardcoded.
8. **Filler contract:** each `src/content/fillers/<platform>.ts` exports
   `detect(): boolean` and `fill(profile, fields): Promise<FillResult>`.
   Fillers may not import each other; only `_shared.ts` helpers.
9. **Selectors:** prefer `data-*` attributes and ARIA roles. Wrap DOM lookups
   in `waitFor(selector, timeoutMs)` to handle async portal renders.
10. **No `console.log`** in committed code (use the shared logger).
    **No `any`.** TypeScript strict, ESLint `--max-warnings 0`.

## Permissions

Modifying `extension/manifest.config.ts` to add a permission, host permission,
or `content_scripts` match requires:

- A comment on the change line justifying the addition.
- Mention in the PR description.

## Tests

- New filler → new `extension/tests/fillers_<platform>.test.ts` loading the
  fixture from `fixtures/portals/<platform>/`.
- Any change to `vault.ts`, `crypto.ts`, or `dispatcher.ts` requires a
  matching test update.

Run: `cd extension && npm run test`.
