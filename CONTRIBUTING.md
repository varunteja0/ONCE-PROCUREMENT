# Contributing to Once

Welcome. This document is the contract between you and the codebase.
Read it once; then never have to think about it again.

If you are reporting a **security issue**, do not open a public issue —
follow [`SECURITY.md`](./SECURITY.md).

---

## 1. Repository ground rules

- Every module-level Python file starts with `from __future__ import annotations`.
- The shared cross-module contracts in [`CONTRACTS.md`](./CONTRACTS.md)
  are normative. Read that file first; align before opening a PR.
- The schema must stay **SQLite-portable**: no `UUID`, no `JSONB`, no
  partial indexes. Use `String(36)` for UUIDs and the generic `JSON`
  type for JSON columns.
- No `print`; use the project logger (`from app.utils.logging import get_logger`).
- No `TODO` in critical paths; either do it, or open an issue and link it.

### 1a. AI-assistant configuration (read this if you pair with Copilot / Cursor / Codex)

All AI rules live in two layers:

1. **Cross-tool** — [`AGENTS.md`](./AGENTS.md) at the repo root plus a
   per-subproject `AGENTS.md` (`backend/`, `frontend/`, `extension/`,
   `oncetax/`, `verifier/`). Every major AI coding tool (Copilot, Cursor,
   Codex, Aider, Claude Code, opencode) reads these.
2. **Copilot-specific** — `.github/copilot-instructions.md` (always loaded),
   glob-scoped rules in `.github/instructions/`, slash-command workflows in
   `.github/prompts/`, specialist chat modes in `.github/chatmodes/`.

If your change adds or alters a repeating workflow, tighten the relevant
`.instructions.md` / `AGENTS.md` / `.prompt.md` in the same PR — that's how
the assistant gets smarter about this repo over time.

---

## 2. Branch model

We use a **trunk-based** model with short-lived feature branches.

- `main` is always deployable and protected. Direct pushes are
  disabled; merge via PR with at least one approving review.
- Branch name: `<area>/<short-kebab-summary>` — e.g.,
  `backend/atomic-claim-retry`, `extension/amtrust-filler-tweak`,
  `docs/runbook-restore-drill`.
- Areas: `backend`, `frontend`, `extension`, `verifier`, `oncetax`,
  `docs`, `ci`, `chore`.
- Keep PRs under ~400 lines diff where possible. Bigger changes get
  broken into stacked PRs.
- Squash-merge into `main`. Use the PR title as the squash commit
  subject.

---

## 3. Commit style

Conventional Commits, narrowed:

```
<type>(<scope>): <short imperative summary>

<body — what + why, not how>

<footer — refs, breaking-change notes>
```

Allowed `<type>` values: `feat`, `fix`, `refactor`, `perf`, `docs`,
`test`, `chore`, `build`, `ci`, `revert`.

Allowed `<scope>` examples: `backend`, `frontend`, `extension`,
`verifier`, `oncetax`, `pipeline`, `auth`, `receipts`, `automation`,
`db`, `docs`, `ci`.

Examples:

```
feat(receipts): add Ed25519 key rotation endpoint

Retired keys remain queryable via /v1/keys/{key_id} so historical
receipts continue to verify.

Refs #142
```

```
fix(pipeline): include status=retrying in atomic claim predicate

Without this, retried submissions never leave the queue.
```

Breaking changes get a `BREAKING CHANGE:` footer and bump the next
minor/major release notes.

---

## 4. Lint and test commands

The canonical interface is the [`Makefile`](./Makefile) (or
[`tasks.ps1`](./tasks.ps1) on Windows). Every command below has a
one-liner equivalent:

| Action               | Make                  | PowerShell                       |
| -------------------- | --------------------- | -------------------------------- |
| Bootstrap            | `make setup`          | `.\tasks.ps1 setup`              |
| Diagnose env         | `make doctor`         | `.\tasks.ps1 doctor`             |
| Run all tests        | `make test`           | `.\tasks.ps1 test`               |
| Lint everything      | `make lint`           | `.\tasks.ps1 lint`               |
| Auto-format          | `make fmt`            | `.\tasks.ps1 fmt`                |
| Combined coverage    | `make coverage`       | `.\tasks.ps1 coverage`           |

The per-component commands below still work — use them when you want to
target a single suite.

### Backend (Python 3.12)

```bash
cd backend
pip install -r requirements.txt
ruff check .                # lint — must be clean
ruff format --check .       # formatting — must be clean
pytest -q                   # tests — must be green
```

### Frontend (Node 20)

```bash
cd frontend
npm ci
npx tsc --noEmit            # type check — must be clean
npx eslint . --max-warnings 0
npm run build               # smoke
```

### Extension (Node 20)

```bash
cd extension
npm ci
npx vitest run              # tests — must be green
npm run build               # build — must succeed
```

### OnceTax (Node 20)

```bash
cd oncetax
pnpm install
pnpm typecheck
pnpm test
pnpm wrangler dev --local   # smoke
```

CI ([`.github/workflows/ci.yml`](./.github/workflows/ci.yml)) runs the
backend + frontend + extension matrices on every PR. CI must be green
before a PR is merged.

### Git hooks

Pre-commit framework hooks are configured in
[`.pre-commit-config.yaml`](./.pre-commit-config.yaml) and installed by
`make setup`. They run ruff, prettier, eslint, mypy (lenient),
trufflehog (secrets scan), and the usual whitespace / merge-conflict
checks. To enable conventional-commit validation on commit messages:

```bash
pre-commit install --hook-type commit-msg
```

For more, see [`docs/DEVELOPMENT.md`](./docs/DEVELOPMENT.md),
[`docs/TROUBLESHOOTING.md`](./docs/TROUBLESHOOTING.md), and
[`docs/STYLE_GUIDE.md`](./docs/STYLE_GUIDE.md).

---

## 5. Code review checklist

> Opening a PR via GitHub pre-fills [`.github/PULL_REQUEST_TEMPLATE.md`](./.github/PULL_REQUEST_TEMPLATE.md)
> with this checklist plus the AGENTS.md non-negotiables. Tick boxes there.

A reviewer should be able to answer "yes" to all of these before
approving:

- [ ] CI green.
- [ ] No new `any` in TypeScript.
- [ ] No new `print`/`console.log` outside test fixtures.
- [ ] Public functions have type hints (Python) or explicit return
      types (TypeScript).
- [ ] New tenant-scoped tables include `tenant_id` FK + index.
- [ ] New service-layer queries pass `tenant_id` explicitly.
- [ ] New routes are registered in
      `backend/app/api/v1/router.py`.
- [ ] New env vars are documented in `.env.example` *and*
      `backend/.env.example` *and* defaulted (or guarded) in
      `app.config.settings`.
- [ ] Migrations are SQLite-portable and reversible.
- [ ] If the change touches receipts, signing, or audit logs, an
      engineering threat-model note is in the PR description.
- [ ] If the change touches auth, the relevant tests in
      `backend/tests/test_auth.py` and
      `backend/tests/test_tenant_isolation.py` are updated.

---

## 6. Releasing

- Versioning: SemVer. `0.x.y` until we cut `1.0.0` at GA.
- Tag format: `vMAJOR.MINOR.PATCH` on `main`.
- Release notes are generated from squashed commit titles + manual
  hand-edit; pasted into the GitHub Release.
- Production deploy is **manual** via `fly deploy` (see
  [`docs/RUNBOOK.md`](./docs/RUNBOOK.md) §1).

---

## 7. Code of conduct

Be excellent to each other. Disagreements about engineering belong in
the PR thread; disagreements about people belong in DM with a
maintainer. We follow the [Contributor Covenant
2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
Report violations to `conduct@once.io`.

---

## 8. License of contributions

By opening a PR you agree that your contribution is licensed under the
project's [Business Source License 1.1](./LICENSE), which converts to
Apache 2.0 on the Change Date. If you cannot sign that agreement (for
example, your employer disallows it), do not open the PR.
