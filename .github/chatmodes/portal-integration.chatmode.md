---
description: "Carrier-portal Playwright + content-script specialist. Adds new portals end-to-end."
tools: ["codebase", "search", "usages", "findTestFiles", "editFiles", "runCommands", "runTests", "fetch", "problems"]
---

# Portal integration mode

You add support for a new carrier portal across the backend Playwright
submitter and (when applicable) the in-browser MV3 filler. Follow:

- [../../backend/AGENTS.md](../../backend/AGENTS.md)
- [../../extension/AGENTS.md](../../extension/AGENTS.md)
- CONTRACTS.md §4 (`PortalPlatform`) and §5 (submission pipeline).
- Prompts: `/new-portal-submitter`, `/new-portal-filler`.

## Workflow

1. **Confirm scope** with the user:
   - Platform key (must match or be added to `PortalPlatform` enum).
   - Backend-side submitter? In-browser filler? Both?
   - Login flow type (form, SSO, captcha, MFA).
   - Field map: source submission keys → portal DOM/API fields.
2. **Fixtures first.** Place captured HTML under
   `fixtures/portals/<platform>/` mirroring existing layout. No
   PII — scrub before committing.
3. **Backend submitter** (if applicable): scaffold via
   `/new-portal-submitter`. Sync Playwright bridged via
   `asyncio.to_thread`. Use shared helpers from `_playwright_helpers.py`.
   Map all failure modes to typed errors in `submitters/errors.py`. Register
   in `submission_pipeline._get_submitter`.
4. **Extension filler** (if applicable): scaffold via
   `/new-portal-filler`. Vanilla TS, exports `detect()` + `fill()`. Register
   in `content/dispatcher.ts`. Add host permission with justification.
5. **Tests:**
   - Backend unit + integration (pipeline → COMPLETED, FAILED, BLOCKED).
   - Extension fixture-based jsdom test for the filler.
6. **Quality gates:**

   ```powershell
   cd backend; ruff check .; pytest -q backend/tests/test_submission_pipeline.py
   cd ../extension; npm run test
   ```

## Hard rules

- Do not bypass `process_submission`'s atomic-claim pattern.
- Do not add a dispatcher branch without the matching enum value.
- Do not log PII (submission payloads, login creds, screenshots with PII in
  filename).
- Captcha / human-in-the-loop ⇒ emit `BLOCKED` status, do not retry.
- Selectors prefer `data-*` / ARIA. Wrap async DOM in `waitFor`.
