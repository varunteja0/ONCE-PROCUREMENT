---
mode: agent
description: "Scaffold a new backend Playwright submitter for a carrier portal (backend-side automation)."
---

# New portal submitter (backend Playwright)

You will add a backend Playwright submitter under
`backend/app/automation/submitters/`. Follow
[../../backend/AGENTS.md](../../backend/AGENTS.md) and CONTRACTS.md §4, §5.

## Inputs to gather

- **Platform key** (must match a `PortalPlatform` enum value — add it to the
  enum **only** if missing, and update consumers).
- Portal **login URL** and submission page URL.
- Fields the submitter writes and which submission payload keys map to them.
- Required selectors (prefer `data-*` / ARIA / accessible names).
- Whether captcha or human-in-the-loop steps exist → emit `BLOCKED` status.

## Plan

1. **Fixtures**: place captured portal HTML under
   `fixtures/portals/<platform>/` mirroring existing layout.
2. **Submitter file**: `backend/app/automation/submitters/<platform>.py`
   subclassing `BaseSubmitter`. Sync Playwright bridged with
   `asyncio.to_thread`. Reuse `_playwright_helpers.py`.
3. **Errors**: raise the appropriate class from `submitters/errors.py` (e.g.
   `PortalLoginFailed`, `PortalBlocked`, `PortalFieldMissing`). The pipeline
   maps these to `SubmissionStatus` values per CONTRACTS.md §4.
4. **Screenshots**: on failure, write via `screenshot_store.py`. Never embed
   PII in the filename.
5. **Dispatcher**: register the submitter in
   `backend/app/services/submission_pipeline.py` via `_get_submitter`.
6. **Tests**:
   - Unit test that the submitter is selected for the correct enum.
   - Integration test that loads the fixture HTML in a Playwright context and
     asserts the right fields were filled.
   - Pipeline test that a `SupplierSubmission` for this platform transitions
     `QUEUED → RUNNING → COMPLETED` (and `FAILED` on simulated error).

## Quality gates

```powershell
cd backend
ruff check .
pytest -q backend/tests/test_submission_pipeline.py
pytest -q backend/tests/integration -k <platform>
```

Do not bypass the atomic-claim pattern in `process_submission`. Do not add a
new branch in the dispatcher without a registered enum value.
