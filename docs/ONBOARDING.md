# Once — Self-Serve Onboarding (L3.6)

> Get a brand-new MGA from "I have a credit card" to "I have shipped my first submission" in **under 10 minutes**, with no human in the loop.

---

## Flow

```
┌─ /onboarding/signup         POST /v1/onboarding/start           → tenant pending, code emailed
│
├─ /onboarding/verify-email   POST /v1/onboarding/verify-email    → tenant active, JWT pair issued
│
├─ /onboarding/profile        POST /v1/onboarding/company-profile → legal name, EIN, state
│
├─ /onboarding/plan           POST /v1/onboarding/skip-step       → free, or redirect to /pricing
│  (skippable)
│
├─ /onboarding/portal         POST /v1/onboarding/connect-portal  → Fernet-encrypted creds in step_data
│  (skippable)
│
├─ /onboarding/supplier       POST /v1/onboarding/add-supplier    → first Supplier row
│  (skippable)
│
├─ /onboarding/submission     POST /v1/onboarding/run-first-submission → auto-consent + Submission
│  (skippable, but recommended)
│
└─ /onboarding/done           POST /v1/onboarding/complete        → state=DONE, navigate /dashboard
```

State is persisted server-side in `onboarding_states.current_step` and is fully
idempotent: re-issuing the same step is a no-op, the only allowed back-step is
`profile → start` for an edge-case email correction.

## State machine

| Step             | Skippable | Endpoint                               |
|------------------|-----------|----------------------------------------|
| `start`          | no        | `POST /v1/onboarding/start`            |
| `email_verify`   | no        | `POST /v1/onboarding/verify-email`     |
| `profile`        | no        | `POST /v1/onboarding/company-profile`  |
| `plan`           | yes       | `POST /v1/onboarding/skip-step` or external `/pricing` |
| `portal`         | yes       | `POST /v1/onboarding/connect-portal`   |
| `supplier`       | yes       | `POST /v1/onboarding/add-supplier`     |
| `submission`     | yes       | `POST /v1/onboarding/run-first-submission` |
| `done`           | —         | `POST /v1/onboarding/complete`         |

## Security model

* `POST /start` issues an **onboarding-scoped JWT** (`scope=onboarding`, 30 min TTL).
  It can only call `/onboarding/verify-email`.
* After successful email verification, the server issues the normal access /
  refresh pair via `issue_token_pair`, and the onboarding token is discarded
  client-side.
* Verification codes:
  * 6 digits, generated via `secrets.choice`.
  * Stored as `sha256(code + pepper)` only (pepper = `settings.secret_key`).
  * Constant-time comparison via `hmac.compare_digest`.
  * Per-email rate limit: **3 codes / hour** (configurable).
  * **5 attempts / code** before invalidation.
  * **30 minute** expiry, single-use (`consumed_at`).
* Honeypot field `website_url` in `OnboardingStartRequest` — when populated by
  a bot, the API returns a plausible-looking dummy payload (no tenant created)
  to avoid leaking detection.
* Portal credentials are encrypted with **Fernet** (key derived from
  `secret_key`) and stored in `onboarding_states.step_data_json["connected_portal"]`.
  The plaintext password is never logged.
* Audit log on every endpoint with `ip`, `user_agent`, `request_id`,
  `tenant_id`.

## Environment variables

| Var                                       | Default              | Purpose                                                                 |
|-------------------------------------------|----------------------|-------------------------------------------------------------------------|
| `EMAIL_DISPATCHER`                        | `outbox`             | `outbox` (file `.eml`) or `resend` (HTTP API).                          |
| `RESEND_API_KEY`                          | —                    | Required when `EMAIL_DISPATCHER=resend`.                                |
| `EMAIL_FROM_ADDRESS`                      | `no-reply@once.dev`  | RFC822 `From:` header.                                                  |
| `EMAIL_OUTBOX_DIR`                        | `.once/outbox`       | Where the outbox dispatcher writes `.eml` files.                        |
| `EMAIL_VERIFICATION_CODE_TTL_MINUTES`     | `30`                 | Code lifetime.                                                          |
| `EMAIL_VERIFICATION_MAX_ATTEMPTS`         | `5`                  | Wrong-attempts per code before it is burned.                            |
| `EMAIL_VERIFICATION_MAX_CODES_PER_HOUR`   | `3`                  | Per-email rate limit on `issue_code`.                                   |
| `ONBOARDING_SESSION_TTL_MINUTES`          | `30`                 | Lifetime of the onboarding-scoped JWT.                                  |
| `ONBOARDING_SKIP_EMAIL_VERIFY`            | `false`              | **Dev only.** Auto-accepts the next verification regardless of input.   |
| `APP_ENV`                                 | `development`        | When `development`, `/start` echoes the code in `dev_verification_code`.|

## Local dev: reading the outbox

```bash
# Tail the latest verification email in dev:
ls -t .once/outbox/*.eml | head -1 | xargs cat | grep -E '^Subject:|[0-9]{6}'
```

`StepSignup` also stores the code in Zustand so `StepVerifyEmail` pre-fills it
on dev (rendered in an amber notice so you can't ship that build by accident).

## Frontend wiring

| Route                          | Page component                |
|--------------------------------|-------------------------------|
| `/onboarding`                  | `Wizard` (auto-redirects to current step) |
| `/onboarding/signup`           | `StepSignup`                  |
| `/onboarding/verify-email`     | `StepVerifyEmail`             |
| `/onboarding/profile`          | `StepCompanyProfile`          |
| `/onboarding/plan`             | `StepChoosePlan`              |
| `/onboarding/portal`           | `StepConnectPortal`           |
| `/onboarding/supplier`         | `StepAddSupplier`             |
| `/onboarding/submission`       | `StepFirstSubmission`         |
| `/onboarding/done`             | `StepDone`                    |

State is hydrated by `useOnboardingState()` (calls `GET /v1/onboarding/state`)
once the user is past `verify-email` and stored in `useOnboardingStore`.

The onboarding-scoped JWT is held in `localStorage` under
`once.onboarding_token` and is swapped for the regular `once.access` /
`once.refresh` pair by `StepVerifyEmail` upon a successful verify.

## Integration points with sibling agents

* **C2 (cockpit)** — reads `onboarding_states` to render an "Onboarding stalled"
  filter on the tenant list.
* **C3 (billing)** — `StepChoosePlan` deep-links to `/pricing?from=onboarding`
  so the user can pick a paid plan and return to the wizard.
* **C5 (lifecycle)** — every onboarding endpoint emits structured audit logs
  consumable by the lifecycle/observability pipeline.

## Tests

* Backend: 44 tests (`tests/test_onboarding_{service,api}.py`,
  `tests/test_email_{verification,dispatcher}.py`).
* Frontend: 6 tests (`Wizard.test.tsx`, `StepVerifyEmail.test.tsx`,
  `ProgressRail.test.tsx`).
