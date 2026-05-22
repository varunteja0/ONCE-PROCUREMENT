# AGENTS.md — repo root entry point for AI coding assistants

> If you are an AI coding assistant (Copilot, Cursor, Codex, Aider, Claude
> Code, opencode, etc.), read this file first, then the linked files below.
> If you are a human, you can skim this — the same rules apply to your PRs.

## Read order (do this once per session)

1. [`CONTRACTS.md`](CONTRACTS.md) — **normative**. Locked stack, model and
   enum names, env vars, file ownership map, quality bar. Nothing here is
   negotiable without a CONTRACTS.md update.
2. [`.github/copilot-instructions.md`](.github/copilot-instructions.md) —
   repo-wide non-negotiables, working rules, tool-use guidance.
3. The **nearest** subproject `AGENTS.md` for the area you are editing:
   - [`backend/AGENTS.md`](backend/AGENTS.md) — FastAPI + SQLAlchemy 2.0 async + Celery + Playwright
   - [`frontend/AGENTS.md`](frontend/AGENTS.md) — React 18 + Vite + TanStack Query + Zustand
   - [`extension/AGENTS.md`](extension/AGENTS.md) — MV3 + Vite + @crxjs + WebCrypto vault
   - [`oncetax/AGENTS.md`](oncetax/AGENTS.md) — Remix on Cloudflare Workers (D1 + R2 + KV)
   - [`verifier/AGENTS.md`](verifier/AGENTS.md) — public Ed25519 receipt verifier

## How the rule files are organized

```
.github/
  copilot-instructions.md          # always loaded by Copilot Chat
  instructions/                    # glob-scoped via `applyTo` frontmatter
    backend-models.instructions.md       → backend/app/models/**
    backend-api.instructions.md          → backend/app/api/**
    backend-services.instructions.md     → backend/app/services/**
    backend-workers.instructions.md      → backend/app/workers/**
    backend-tests.instructions.md        → backend/tests/**
    backend-migrations.instructions.md   → backend/alembic/versions/**
    frontend.instructions.md             → frontend/src/**
    extension.instructions.md            → extension/src/**
    oncetax.instructions.md              → oncetax/**
    verifier.instructions.md             → verifier/**
  prompts/                         # slash-invokable workflows
    new-api-endpoint.prompt.md           /new-api-endpoint
    new-portal-submitter.prompt.md       /new-portal-submitter
    new-portal-filler.prompt.md          /new-portal-filler
    new-acord-form.prompt.md             /new-acord-form
    new-celery-task.prompt.md            /new-celery-task
    new-frontend-page.prompt.md          /new-frontend-page
    fix-failing-tests.prompt.md          /fix-failing-tests
    add-alembic-migration.prompt.md      /add-alembic-migration
  chatmodes/                       # specialized Copilot chat modes
    reviewer.chatmode.md                 read-only senior code review
    tdd.chatmode.md                      test-first, smallest-step workflow
    migration-doctor.chatmode.md         safe Alembic migrations only
    portal-integration.chatmode.md       end-to-end new carrier portal
    security-review.chatmode.md          auth / crypto / receipts / vault
  PULL_REQUEST_TEMPLATE.md         # PR checklist (mirrors CONTRIBUTING §5)
  workflows/                       # CI/CD (do not edit casually)
```

Other AI tools (Cursor / Codex / Aider / Claude Code / opencode) will not
read the `.github/` files — but they **will** read this `AGENTS.md` and the
subproject `AGENTS.md` files. The rules in those files are intentionally
self-contained.

## Non-negotiables (1-screen summary)

These apply everywhere. The full rationale is in `CONTRACTS.md`.

1. **Do not rename** canonical models / enums / env vars / services.
2. **Tenant isolation:** every tenant-scoped query filters on `tenant_id`.
3. **SQLite-portable schema** (no `UUID`, `JSONB`, partial indexes); PKs are
   `String(36)` with `default=lambda: str(uuid.uuid4())`.
4. **Schema change ⇒ new Alembic migration**, hand-reviewed. Never edit an
   applied migration.
5. **No `print` / `console.log`** in committed code. Use structlog
   (backend) or the extension logger.
6. **No `any` in TypeScript.** Strict mode is on.
7. **Python 3.12** with `from __future__ import annotations` at the top of
   every module. `ruff check .` must pass.
8. **Receipts are immutable.** Never mutate a `SubmissionReceipt` after
   signing — re-sign = new `receipt_id`.
9. **Secrets never hardcoded.** Use `app.config.settings` (backend) or
   `context.cloudflare.env` (Workers).
10. **File ownership** (CONTRACTS.md §12) — put new code where the ownership
    map says it goes; do not invent new top-level locations.

## Quality gates (run before declaring "done")

```powershell
cd backend   ; ruff check . ; pytest -q
cd frontend  ; npm run lint ; npm run typecheck ; npm test
cd extension ; npm run test
cd oncetax   ; npm run typecheck ; npm test
cd verifier  ; pytest -q
```

## Tool-specific notes

- **VS Code + Copilot Chat:** use the slash commands above; switch to
  `reviewer` / `tdd` / `migration-doctor` / `portal-integration` mode from
  the chat mode dropdown when a specialist persona is appropriate.
- **Cursor:** Cursor reads this file and the subproject `AGENTS.md`. The
  `.github/` directory is informational only for Cursor; mirror what you
  need into your Cursor Rules if you want it.
- **Codex CLI / Aider / Claude Code / opencode:** all read `AGENTS.md` by
  convention. Point them at the repo root.

## When CONTRACTS.md and any other doc disagree

CONTRACTS.md wins. Flag the inconsistency in your PR; do not silently pick.
