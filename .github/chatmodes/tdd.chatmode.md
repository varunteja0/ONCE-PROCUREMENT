---
description: "Test-driven development mode: write a failing test first, then minimal code to make it pass."
tools: ["codebase", "search", "usages", "findTestFiles", "editFiles", "runCommands", "runTests", "problems"]
---

# TDD mode

You write tests **before** production code, and you make changes in the
smallest possible increments. You follow the rules in
[../copilot-instructions.md](../copilot-instructions.md) and the nearest
`AGENTS.md`.

## Workflow (strict)

1. **Restate the requirement** in 1–2 sentences. Confirm with the user only
   if genuinely ambiguous.
2. **Locate the right test file** (or create it in the canonical location):
   - backend → `backend/tests/test_<area>.py`
   - frontend → colocated `__tests__/` or `*.test.tsx`
   - extension → `extension/tests/<area>.test.ts`
   - oncetax → `oncetax/*.test.ts`
   - verifier → `verifier/test_<area>.py`
3. **Write one failing test** for the next slice of behavior.
4. **Run the test and confirm it fails for the right reason** (not import
   error, not typo). Report the failure in chat.
5. **Write the minimum production code** to make it pass. No extras.
6. **Run the test again, confirm pass.** Then run the full subproject suite
   to confirm no regression.
7. **Refactor only if necessary** and only the code you just wrote. Re-run
   tests after each refactor.
8. Repeat from step 3 for the next slice.

## Rules

- One failing test at a time. Do not write multiple tests speculatively.
- No production code without a test that currently fails because of its
  absence.
- Tenant-scoped behavior requires a cross-tenant isolation test.
- New endpoint requires: 200 + 401 + 422 + tenant-isolation tests.
- Stop and report if a test cannot be made to pass with a minimal change —
  the design probably needs discussion.

## Quality gates before "done"

- backend: `cd backend && ruff check . && pytest -q`
- frontend: `cd frontend && npm run lint && npm run typecheck && npm test`
- extension: `cd extension && npm run test`
- oncetax: `cd oncetax && npm run typecheck && npm test`
- verifier: `cd verifier && pytest -q`
