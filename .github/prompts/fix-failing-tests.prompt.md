---
mode: agent
description: "Diagnose and fix failing tests in a specific subproject without expanding scope."
---

# Fix failing tests

Diagnose and fix failing tests in the target subproject. Do **not** refactor
unrelated code, do **not** add new features, and do **not** "improve" code
you did not need to touch.

## Workflow

1. Ask which subproject (`backend` / `frontend` / `extension` / `oncetax` /
   `verifier`) if not specified.
2. Run the subproject's test command and capture the failures:
   - backend → `cd backend && pytest -q`
   - frontend → `cd frontend && npm test`
   - extension → `cd extension && npm run test`
   - oncetax → `cd oncetax && npm test`
   - verifier → `cd verifier && pytest -q`
3. For each failing test, in order:
   a. Read the test and the code under test.
   b. State in chat: "Failure: ... Root cause: ... Minimal fix: ...".
   c. Apply the **smallest possible** change to the production code (or, if
      the test is genuinely wrong, the test) to make it pass.
   d. Re-run only the affected test file, then the full suite at the end.
4. If a fix needs a schema change → generate an Alembic migration
   (backend only) and hand-review it before re-running.
5. Stop and ask the user before:
   - Making changes outside the failing subproject.
   - Deleting tests.
   - Changing public API shapes.
   - Modifying an already-applied Alembic migration.

## Final report

End with a one-line summary per fix: file, root cause, change made.
Confirm the suite is fully green.
