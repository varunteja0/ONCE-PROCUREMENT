# Once — Copilot repo-wide instructions

> Read [CONTRACTS.md](../CONTRACTS.md) **first**. It is the source of truth for
> stack, model names, enums, env vars, file ownership, and quality bar.
> This file lists Copilot-specific working rules that apply on top.

## Subproject context

Each subproject has its own `AGENTS.md` with stack-specific rules. **Read the
nearest `AGENTS.md` before editing files in that tree.**

- [backend/AGENTS.md](../backend/AGENTS.md) — FastAPI + SQLAlchemy 2.0 async + Celery + Playwright
- [frontend/AGENTS.md](../frontend/AGENTS.md) — React 18 + Vite + TanStack Query + Zustand
- [extension/AGENTS.md](../extension/AGENTS.md) — MV3 Chrome extension, Vite + @crxjs
- [oncetax/AGENTS.md](../oncetax/AGENTS.md) — Remix on Cloudflare Workers (D1 + R2 + KV)
- [verifier/AGENTS.md](../verifier/AGENTS.md) — public Ed25519 receipt verifier

Glob-scoped rules live in [.github/instructions/](./instructions/) and are
auto-applied by Copilot via `applyTo` frontmatter. Current coverage:
`backend/app/models/**`, `backend/app/api/**`, `backend/app/services/**`,
`backend/app/workers/**`, `backend/tests/**`,
`backend/alembic/versions/**`, `frontend/src/**`, `extension/src/**`,
`oncetax/**`, `verifier/**`.

Reusable workflows live in [.github/prompts/](./prompts/). Invoke with
`/<prompt-name>` in Copilot Chat. Current set: `/new-api-endpoint`,
`/new-portal-submitter`, `/new-portal-filler`, `/new-acord-form`,
`/new-celery-task`, `/new-frontend-page`, `/fix-failing-tests`,
`/add-alembic-migration`.

Specialist chat modes live in [.github/chatmodes/](./chatmodes/). Switch via
the chat mode dropdown when the task fits: `reviewer` (read-only review),
`tdd` (test-first), `migration-doctor` (Alembic), `portal-integration`
(new carrier), `security-review` (auth / crypto / receipts / vault).

## Non-negotiables (apply everywhere)

1. **Do not rename** any canonical model, enum value, env var, or service from
   CONTRACTS.md §3, §4, §8. Downstream code, migrations, fixtures, and external
   contracts depend on these exact names.
2. **Tenant isolation:** every query against a tenant-scoped table MUST filter by
   `tenant_id` from `request.state.tenant_id` (backend) or the JWT (workers).
   No exceptions. Cross-tenant access = security incident.
3. **SQLite portability:** schema must run on both Postgres and in-memory
   SQLite. No `UUID`, `JSONB`, partial indexes, or PG-only functions. PKs are
   `String(36)` with `lambda: str(uuid.uuid4())`.
4. **Schema change ⇒ Alembic migration.** Adding/renaming/dropping a column or
   table without a matching `backend/alembic/versions/*.py` is a broken change.
5. **No `print`, no `console.log` in committed code.** Use `structlog`
   (`from app.utils.logging import get_logger`) or the extension's logger.
6. **No `any` in TypeScript.** Strict mode is on. `eslint --max-warnings 0`.
7. **Python:** `from __future__ import annotations` at the top of every module.
   Python 3.12 only. `ruff check .` must pass.
8. **Receipts are immutable.** Never mutate a `SubmissionReceipt` after signing.
   Re-sign = new receipt with new `receipt_id`.
9. **Secrets:** never hardcode keys, JWT secrets, or signing PEMs. Read from
   `app.config.settings` (backend) or `env` (Workers). `.env*` and `.dev.vars*`
   are gitignored — keep them that way.
10. **File ownership (CONTRACTS.md §12):** when in doubt about which file to put
    something in, match the existing ownership map rather than inventing a new
    location.

## How Copilot should work in this repo

- **Plan, then edit.** For changes touching > 2 files, restate the affected
  files and the contract sections you are honoring before editing.
- **Read before writing.** Open the existing module and the nearest test file;
  match the style (logger usage, error class, dependency injection pattern).
- **Tests matter.** Backend: add or update a `backend/tests/test_*.py`.
  Extension: add a `extension/tests/*.test.ts`. Frontend: add a Vitest under
  the colocated `__tests__` folder.
- **Run the quality gates** after non-trivial changes:
  - Backend → `cd backend && ruff check . && pytest -q`
  - Frontend → `cd frontend && npm run lint && npm run typecheck`
  - Extension → `cd extension && npm run test`
  - OnceTax → `cd oncetax && npm run typecheck && npm test`
- **Migrations:** `cd backend && alembic revision --autogenerate -m "<verb_object>"`
  then review the generated file. Never edit an already-applied migration —
  add a new one.
- **No drive-by refactors.** Touch only what the task requires. If you spot
  something unrelated, leave a comment in chat, not in the code.

## Tool-use guidance

- Prefer `grep_search` / `file_search` / `read_file` over terminal `rg` / `cat`.
- Run one terminal command at a time; wait for output before chaining.
- Long-running dev servers (`docker compose up`, `npm run dev`, `wrangler dev`)
  should be launched in async mode and reused, not spawned per turn.
- Destructive ops (`rm -rf`, `alembic downgrade`, `git push --force`, dropping
  tables) require explicit user confirmation every time.

## When CONTRACTS.md and any other doc disagree

CONTRACTS.md wins. Flag the inconsistency to the user; do not silently pick.
