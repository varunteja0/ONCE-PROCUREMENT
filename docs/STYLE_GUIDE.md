# Style Guide

The point of this document is to remove arguments. If the rule is here,
the reviewer doesn't have to litigate it. If you disagree, open a PR
against this file before the one that breaks the rule.

---

## 1. Python

### Toolchain

- **Formatter**: `ruff format` (Black-compatible). `black --check` runs as
  a secondary safety net in pre-commit.
- **Linter**: `ruff check` with rules enabled in `backend/pyproject.toml`
  (E, F, I, B, UP, S).
- **Type checker**: `mypy` in lenient mode in pre-commit; aim for strict
  in critical modules (auth, signing, pipeline).
- **Line length**: 120.

### Conventions

- Every module starts with `from __future__ import annotations`.
- Type hints on **every** public function (`def`/`async def` at module
  scope, plus class methods). Internal helpers may skip hints if the
  inference is obvious.
- Naming:
  - `snake_case` for functions, variables, modules.
  - `PascalCase` for classes and Pydantic models.
  - `UPPER_SNAKE` for module-level constants.
  - `_leading_underscore` for module-internal helpers (no `__dunder__`
    unless you're implementing a protocol).
- Docstrings: **Google style**.

  ```python
  def claim_submission(submission_id: str, *, worker_id: str) -> ClaimResult:
      """Atomically claim a submission for processing.

      Args:
          submission_id: Public ID of the submission to claim.
          worker_id: Stable identifier of the calling worker, recorded
              in the audit log.

      Returns:
          A ClaimResult describing whether the claim succeeded and the
          row version observed.

      Raises:
          SubmissionGone: If the submission was deleted between selection
              and update.
      """
  ```

- Imports in three blocks: stdlib, third-party, first-party. `ruff` sorts
  this for you.
- Never `print` in production code; use `from app.utils.logging import
  get_logger; logger = get_logger(__name__)`.
- Never `time.sleep` in async code. Use `asyncio.sleep`.
- SQL via SQLAlchemy 2.x style (`select(...).where(...)`), not legacy
  `Query`.

### Errors

- Raise specific exceptions; catch specific exceptions. `except
  Exception:` is a code smell unless followed by `raise` or strict
  logging + re-raise.
- Custom exceptions live in `backend/app/errors.py`. They inherit from a
  small set of base classes so middleware can map them to HTTP codes.

---

## 2. TypeScript

### Toolchain

- **Formatter**: Prettier (default settings + 100-col print width).
- **Linter**: ESLint with `@typescript-eslint`, the React plugin, and
  `eslint-plugin-tailwindcss`.
- **Type checker**: `tsc --noEmit` in `strict` mode.

### Conventions

- **No `any`.** Ever. Use `unknown` + a narrowing check, or define the
  shape. The eslint rule `@typescript-eslint/no-explicit-any` is `error`.
- **No `// @ts-ignore`.** Use `// @ts-expect-error` with a one-line
  reason — the compiler will tell you when it's no longer needed.
- Naming:
  - `PascalCase` for components, types, interfaces, enums.
  - `camelCase` for functions, variables, hooks (must start with `use`).
  - `UPPER_SNAKE` for module-level constants.
  - Files: `kebab-case.ts` for utilities, `PascalCase.tsx` for
    components.
- Prefer `type` over `interface` unless you genuinely need declaration
  merging.
- Use named exports; default exports only for top-level pages /
  Vite-required entry points.
- Hooks always live next to the component that owns them unless reused —
  then `frontend/src/hooks/`.
- Tailwind utility classes go in a single attribute; if it exceeds ~6
  classes, extract a `cva()` variant or a wrapper component.

### React specifics

- Components are function components. No class components.
- Side effects go in `useEffect` with explicit deps; if eslint complains,
  fix the deps — don't suppress.
- Server state via the project's data hooks (TanStack Query under the
  hood); local state via `useState` / `useReducer`. Don't mix.

---

## 3. SQL / migrations

- Keywords lowercase: `select`, `from`, `join`, `where`.
- Explicit `inner join` / `left join` — never implicit `,` joins.
- Never `select *` in application code (migrations and ad-hoc queries
  excepted).
- Migrations must be **SQLite-portable** and **reversible**:
  - `String(36)` for UUIDs, not `UUID`.
  - Generic `JSON`, not `JSONB`.
  - No partial indexes (`WHERE …`) — use full indexes or a different
    schema.
  - Provide a working `downgrade()`.

---

## 4. Git workflow

### Branches

`<area>/<short-kebab-summary>` — e.g. `backend/atomic-claim-retry`,
`docs/troubleshooting-bcrypt`. Areas: `backend`, `frontend`, `extension`,
`verifier`, `oncetax`, `docs`, `ci`, `chore`.

### Conventional commits

```
<type>(<scope>): <imperative summary, no period>

<body — what + why, wrapped at 72 cols>

<footer — Refs / Closes / BREAKING CHANGE>
```

Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`,
`build`, `ci`, `revert`. Scopes: same as branch areas, plus `auth`,
`receipts`, `pipeline`, `db`.

Examples:

```
feat(receipts): add Ed25519 key rotation endpoint
fix(pipeline): include status=retrying in atomic claim predicate
docs(troubleshooting): document bcrypt 4.0.1 pin
```

### PRs

- Under ~400 lines diff when possible. Stack larger work as multiple PRs.
- Squash-merge into `main`. PR title becomes the squash subject.
- The PR template enforces the review checklist (see CONTRIBUTING §5).

---

## 5. Code review

Reviewers must check, in this order:

1. **Security** — new auth paths, new SQL string interpolation, new HTML
   that renders user input, new file uploads, secrets in fixtures.
2. **Tenant isolation** — every new query must filter by `tenant_id`
   unless it's explicitly cross-tenant (verifier, public receipts).
3. **Correctness** — tests cover the happy path and at least one failure
   mode. Race conditions in the pipeline get an extra look.
4. **Performance** — N+1 queries, missing indexes on new FKs, oversized
   payloads.
5. **Public contracts** — anything in `app/api/v1/` or
   `extension/src/messaging/` that's part of the API surface needs a
   thought about versioning and backward compat.
6. **Tests + docs** — green CI is necessary but not sufficient. New env
   vars in `.env.example`. New routes in API_EXAMPLES.md. New runbook
   step if it changes ops.

Style nits are auto-fixed by pre-commit; reviewers should not be filing
them by hand.

---

## 6. Comments

The repo convention (mirrored in our Copilot instructions): comment only
when a reader needs a hint they couldn't infer from the code. Don't
restate types or paraphrase the function name. Do explain *why* — the
non-obvious constraint, the historical reason, the alternative that was
tried and rejected.

Bad:

```python
# Increment counter
counter += 1
```

Good:

```python
# Counter overflows at 2^31 because the legacy Vertafore client truncates;
# we wrap around explicitly to keep parity.
counter = (counter + 1) % (2 ** 31)
```
