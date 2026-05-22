# Founder Cockpit

The **Founder Cockpit** is the internal operator surface that lets a single
trusted humans (founder, on-call engineer, support agent) sign in once and
act on behalf of any pilot tenant while preserving a tamper-evident audit
trail.

It is intentionally separate from the tenant-user surface:

- Separate **table** (`operators`), separate **JWT signing secret**
  (`COCKPIT_JWT_SECRET_KEY`), separate **cookie names**
  (`once_cockpit_*`), and separate **storage keys** in the SPA
  (`once.cockpit.access` / `once.cockpit.refresh`).
- Mounted at `/cockpit/*` on the API and `/cockpit/*` in the SPA.
- Does **not** share interceptors, refresh state, or storage with the
  tenant-user surface (`/v1/*`).

## Roles

| Role          | Capability                                               |
| ------------- | -------------------------------------------------------- |
| `founder`     | Sees and can act-as **every** tenant. Grants are bypassed. |
| `engineering` | Only tenants explicitly listed in `operator_tenant_grants`. |
| `support`     | Same grant model as engineering; read-leaning by default.  |

`OperatorStatus` is `active` or `suspended`. Suspended operators cannot
authenticate.

## Act-as flow

1. Operator signs in at `POST /cockpit/auth/login` → receives an access
   token + refresh token. Access cookie is set httponly at `/`, refresh
   cookie httponly at `/cockpit/auth`. A non-httponly CSRF cookie
   (`once_cockpit_csrf`) is also set so the SPA can echo it.
2. SPA stores the operator in `useCockpitStore` and sets
   `actingAsTenantId` to `null`.
3. To act as a tenant, SPA calls `POST /cockpit/tenants/act-as` with
   `{ tenant_id }`. Backend validates the operator has access (founder
   bypass or row in `operator_tenant_grants`) and that the tenant is
   active.
4. SPA stores the tenant id in `localStorage` under
   `once.cockpit.actingAs`. The `cockpitApi` axios request interceptor
   then sends `X-Operator-Acting-Tenant: <tenant_id>` on every cockpit
   request.
5. The backend `OperatorActAsMiddleware` rewrites
   `request.state.tenant_id` so tenant-scoped queries automatically
   resolve to the act-as tenant — the operator never sees raw tenant
   table joins.
6. Every cockpit request (success or failure) is recorded to
   `cockpit_audit` via a fire-and-forget async writer.

To exit the act-as context, the SPA clears the localStorage key and stops
sending the header.

## CLI

Bootstrap operators with:

```pwsh
python -m scripts.create_operator `
  --email founder@once.io `
  --role founder `
  --grant-all
```

Other flags:

- `--role {founder,engineering,support}`
- `--mfa-required` to require a TOTP code at login (TOTP is currently a
  stub — see roadmap)
- `--password '<pw>'` to skip the interactive `getpass` prompt
- `--grant-all` to write a wildcard grant (only meaningful for non-founder
  roles; founders bypass grants anyway)

Passwords must satisfy the B8 strength policy (length ≥ 12, mix of upper
+ lower + digit + symbol). Weak passwords are rejected at the service
layer.

## Environment variables

| Variable                          | Default                       | Meaning                                                              |
| --------------------------------- | ----------------------------- | -------------------------------------------------------------------- |
| `COCKPIT_JWT_SECRET_KEY`          | _required in prod_            | HMAC signing secret for cockpit access + refresh tokens.            |
| `COCKPIT_ACCESS_TTL_MINUTES`      | `15`                          | Access token lifetime.                                              |
| `COCKPIT_REFRESH_TTL_MINUTES`     | `60`                          | Refresh token lifetime.                                             |
| `COCKPIT_LOCKOUT_MAX_FAILURES`    | `5`                           | Lock account after N consecutive failed logins.                     |
| `COCKPIT_LOCKOUT_WINDOW_MINUTES`  | `15`                          | Rolling window for failure counting.                                |
| `ENABLE_COCKPIT_ACT_AS_MIDDLEWARE`| `true`                        | Set to `false` to disable the middleware (e.g. for migration tests). |
| `VITE_COCKPIT_API_BASE`           | `/cockpit`                    | SPA base URL for cockpit calls.                                     |

## Audit semantics

Table: `cockpit_audit` (append-only).

Columns:

- `id` (uuid), `occurred_at` (utc)
- `operator_id` (nullable for pre-auth failures)
- `tenant_id_acted_as` (nullable when no act-as header)
- `action` (e.g. `cockpit.login`, `cockpit.act_as`, `cockpit.request`)
- `resource_type`, `resource_id`
- `request_id`, `method`, `path`, `status_code`
- `ip`, `user_agent`
- `payload_redacted` (JSON; recursive over dict/list/tuple)

Indexes:

- `(operator_id, occurred_at desc)`
- `(tenant_id_acted_as, occurred_at desc)`
- `(action, occurred_at desc)`

The redactor blanks any key whose lowercased name is in:
`authorization`, `cookie`, `set-cookie`, `x-csrf-token`, `password`,
`totp_code`, `refresh_token`, `access_token`, `secret`, `api_key`.

There is **no UPDATE / DELETE endpoint** on this table. Migrations should
not add one.

## RFC 9457 problem types

All cockpit error responses are `application/problem+json`. Codes:

| `type` suffix                  | Status | Meaning                                            |
| ------------------------------ | ------ | -------------------------------------------------- |
| `cockpit/invalid-credentials`  | 401    | Email/password did not match.                      |
| `cockpit/account-locked`       | 423    | Too many failed logins.                            |
| `cockpit/mfa-required`         | 401    | `totp_code` missing or invalid.                    |
| `cockpit/operator-suspended`   | 403    | Operator status is `suspended`.                    |
| `cockpit/tenant-not-found`     | 404    | Requested act-as tenant doesn't exist.             |
| `cockpit/tenant-forbidden`     | 403    | No grant for this tenant (and not a founder).      |
| `cockpit/tenant-inactive`      | 409    | Tenant exists but is deactivated.                  |
| `cockpit/weak-password`        | 422    | Password fails the strength policy.                |

## Tests

Backend: `pytest backend/tests/test_operator_auth.py backend/tests/test_cockpit_act_as.py backend/tests/test_cockpit_audit.py -q` (30 tests).

Frontend: `npx vitest run src/pages/__tests__/CockpitLogin.test.tsx src/pages/__tests__/CockpitDashboard.test.tsx src/pages/__tests__/ActingAsBanner.test.tsx`.
