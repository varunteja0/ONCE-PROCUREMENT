# Submitter playbook

How to ship a new portal submitter for Once. Targeted at engineers, not
operators.

> Contract: [`CONTRACTS.md` §7](../CONTRACTS.md) — every submitter must conform
> to the `submitter.submit(*, supplier, portal, payload, consent)` shape; see
> `backend/app/services/submission_pipeline.py`.

---

## 1. Architecture

```
SubmissionPipeline
   │
   ▼
_get_submitter(platform) ─► SUBMITTER_REGISTRY[platform]  (class)
   │
   ▼
SubmitterClass.submit(supplier=…, portal=…, payload=…, consent=…)
   │   (PlaywrightSubmitter.submit is a @classmethod that bridges
   │    sync Playwright into asyncio via asyncio.to_thread)
   ▼
SubmitterOutcome(success, portal_reference, result_payload, screenshot_url)
```

Every Playwright submitter inherits `PlaywrightSubmitter`
(`backend/app/automation/base.py`), which provides:

* browser lifecycle (Chromium launch → context → page → teardown)
* per-portal timeouts (`NAV_TIMEOUT_MS`, `ACTION_TIMEOUT_MS`)
* auto-screenshot on every failure path (`screenshot_store.py`)
* React-tracked-input setter, network-idle wait, captcha & auth-wall detectors
  (`_playwright_helpers.py`)
* wrap-and-reraise of every uncaught error as a typed `PortalError`

---

## 2. Five steps to add a new portal

### Step 1 — Identify the canonical fields

Open the live carrier portal in incognito and screenshot every required input
on the new-submission form. Cross-reference with `payload` keys already used by
the existing four submitters (`named_insured`, `fein`, `effective_date`,
`premium_cents`, `line_of_business`, etc.) — reuse those names where the
semantics match. Add new canonical keys only when there is no existing
equivalent.

### Step 2 — Build the `FIELD_MAP`

```python
FIELD_MAP: dict[str, str] = {
    "named_insured": "Insured Name",     # carrier's label text
    "fein": "Tax ID",
    # ...
}
```

Prefer the **label text** as the value — `fill_by_label` resolves via
`page.get_by_label(...)`, which is resilient to ID and class churn. Fall back to
stable CSS hooks (`[data-action='…']`, `[data-testid='…']`) only for
unlabelled controls (buttons, links).

### Step 3 — Implement the five hooks

In `backend/app/automation/submitters/<carrier>.py`:

```python
class FooSubmitter(PlaywrightSubmitter):
    platform = PortalPlatform.FOO
    PLATFORM = PortalPlatform.FOO
    URL_ENV_VAR = "PORTAL_FOO_URL"
    USERNAME_ENV_VAR = "FOO_USERNAME"
    PASSWORD_ENV_VAR = "FOO_PASSWORD"
    REQUIRED_FIELDS = (...)
    FIELD_MAP = {...}

    def _login(self, page, *, url, username, password): ...
    def _navigate_to_new_submission(self, page, *, base_url): ...
    def _fill_form(self, page, payload): ...
    def _attach_files(self, page, payload): ...        # optional
    def _submit_and_capture(self, page): ...           # → (reference, metadata)
```

Register at module bottom:

```python
SUBMITTER_REGISTRY[PortalPlatform.FOO] = FooSubmitter
```

Then add the module to the side-effect import in
`backend/app/automation/submitters/__init__.py` (owned by agent 08 — coordinate
with that agent).

### Step 4 — Build the fixture

Copy `fixtures/portals/amtrust/` as a template, change the labels to match
`FIELD_MAP`, and add a new `server { listen <port> ... }` block in
`fixtures/portals/_nginx/nginx.conf`. Add the port mapping to
`docker-compose.yml`'s `portal-fixtures` service and the env vars on the
backend service.

**Fixture port allocations** (must match `docker-compose.yml`,
`fixtures/portals/_nginx/nginx.conf`, and
`backend/tests/integration/conftest.py::_PORTAL_SPECS`):

| Portal               | Port | Submitter module                                  |
| -------------------- | ---- | ------------------------------------------------- |
| AmTrust              | 8101 | `backend/app/automation/submitters/amtrust.py`            |
| Markel               | 8102 | `backend/app/automation/submitters/markel.py`             |
| Applied Epic         | 8103 | `backend/app/automation/submitters/applied_epic.py`       |
| Vertafore AMS360     | 8104 | `backend/app/automation/submitters/vertafore_ams360.py`   |
| Sircon               | 8105 | `backend/app/automation/submitters/sircon.py`             |

### Step 4b — Wire the smoke probe

Every `PlaywrightSubmitter` subclass MUST set `SMOKE_PROBE_NEEDLE` to a
case-insensitive substring that only the carrier's real login page would
render (typically the brand name in the `<h1>` or `<title>`). The
15-minute Celery beat task (`smoke_test.run_all`) calls
`PlaywrightSubmitter._smoke_test` which GETs the configured `URL_ENV_VAR`,
asserts a 2xx/3xx response, and looks for the needle. A missing needle or
non-2xx response collapses to a Slack drift alert on `#portal-drift` — do
NOT skip this step.

### Step 5 — Write the integration tests

Copy `backend/tests/integration/test_amtrust_submitter.py`. The five required
test cases are non-negotiable:

1. **happy path** — confirmation reference matches `^[A-Z]+-\d{4}-[A-Z0-9]+$`.
2. **invalid credentials** → `PortalAuthError`.
3. **missing required field** → `PortalValidationError`.
4. **`?drift=1` simulation** → `PortalSelectorDriftError`.
5. **`?captcha=1` simulation** → `PortalCaptchaError`.

Add the new portal fixture's port to `backend/tests/integration/conftest.py`'s
`_PORTAL_SPECS` map and ship a session-scoped portal endpoint fixture.

---

## 3. Selector-drift recovery

When `PortalSelectorDriftError` rate exceeds 5% over a 15-min window the
alerting (operated by agent B7) pages the on-call. Recovery flow:

1. Inspect the latest failure screenshot under
   `$SCREENSHOT_DIR/<tenant>/<submission>/`.
2. Diff the live portal markup against the last-known selectors.
3. Update `FIELD_MAP` (or the data-attribute selectors) on a branch.
4. Re-run the relevant integration test with `RUN_INTEGRATION_TESTS=1`
   against a staging fixture pinned to the new markup.
5. Ship; the pipeline's retry budget (`MAX_ATTEMPTS=5`) will quietly re-drain
   the failed submissions.

**Rollback**: revert the commit; do *not* hand-edit selectors in production.

---

## 4. Local headed debugging

```bash
export PLAYWRIGHT_HEADLESS=false
export PORTAL_AMTRUST_URL=http://localhost:8101/
export AMTRUST_USERNAME=demo AMTRUST_PASSWORD=demo
export RUN_INTEGRATION_TESTS=1
cd backend && pytest tests/integration/test_amtrust_submitter.py -k happy_path -s
```

The Chromium window will open; the test pauses at every `wait_for_network_idle`
so you can step through.

---

## 5. Screenshot retention policy

* Default root: `$SCREENSHOT_DIR` or `./.once/screenshots`.
* Layout: `{tenant_id}/{submission_id}/{utc_iso_ts}-{label}.png`.
* Production retention: 30 days (operated by the cleanup Celery beat task —
  owned by agent B6).
* Each failure screenshot path is included in the
  `SupplierSubmission.result_json` so operator dashboards can deep-link to it.

---

## 6. Error → status mapping (quick reference)

| Exception                     | Pipeline status             | Retryable? |
|-------------------------------|-----------------------------|------------|
| `PortalCaptchaError`          | `BLOCKED`                   | No (human) |
| `PortalAuthError`             | `FAILED`                    | No         |
| `PortalValidationError`       | `FAILED`                    | No         |
| `PortalTimeoutError`          | `RETRYING` → `FAILED` @ 5   | Yes        |
| `PortalNetworkError`          | `RETRYING` → `FAILED` @ 5   | Yes        |
| `PortalSelectorDriftError`    | `RETRYING` → `FAILED` @ 5   | Yes        |

See `app/services/submission_pipeline.py::_classify_failure`.
