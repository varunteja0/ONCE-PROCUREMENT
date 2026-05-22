---
mode: agent
description: "Scaffold a new in-browser MV3 content-script filler for a carrier portal."
---

# New portal filler (extension content script)

You will add a vanilla-TS content-script filler under
`extension/src/content/fillers/`. Follow
[../../extension/AGENTS.md](../../extension/AGENTS.md) and CONTRACTS.md §10.

## Inputs to gather

- **Platform key** (matches a `PortalPlatform` value).
- The portal's domain (for the `host_permissions` / `matches` entry, with
  justification).
- A captured fixture HTML (will live under `fixtures/portals/<platform>/`).
- Field-mapping table: which DOM field receives which profile / submission
  field. Selectors should prefer `data-*` / ARIA / labels.

## Plan

1. **Fixture**: drop the captured HTML into `fixtures/portals/<platform>/`.
2. **Filler**: create `extension/src/content/fillers/<platform>.ts` exporting:
   - `detect(): boolean` — fast `window.location` / DOM check.
   - `fill(profile, fields): Promise<FillResult>` — fills fields, returns
     `{ status: "ok" | "partial" | "blocked", filled: string[], missing: string[] }`.
   - Use `waitFor(selector, timeoutMs)` from `_shared.ts`. No `setTimeout`
     loops in feature code.
3. **Dispatcher**: register in `extension/src/content/dispatcher.ts`. Order
   matters — most-specific `detect()` first.
4. **Manifest**: if a new host permission is needed, edit
   `extension/manifest.config.ts` and add a comment on the new line
   justifying it.
5. **Types**: add new profile/portal fields to `extension/src/types/`.
6. **Tests**: add `extension/tests/fillers_<platform>.test.ts` that loads
   the fixture into jsdom and asserts the right inputs were set. Cover the
   happy path and at least one "field missing" path.

## Quality gates

```powershell
cd extension
npm run test -- fillers_<platform>
npm run build
```

Do not import React or any UI library into the filler. Do not import another
filler. Do not log sensitive profile values.
