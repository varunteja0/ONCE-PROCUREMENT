<!--
  PR template — mirrors CONTRIBUTING.md §5 and AGENTS.md non-negotiables.
  Delete sections that genuinely do not apply; do not delete checkboxes by default.
-->

## Summary

<!-- 1–3 sentences: what changed and why. Link the issue if there is one. -->

## Area(s) touched

- [ ] backend
- [ ] frontend
- [ ] extension
- [ ] oncetax
- [ ] verifier
- [ ] docs / ci / chore

## Type

- [ ] feat
- [ ] fix
- [ ] refactor / perf
- [ ] docs / test / chore

---

## Contract & rule check (`AGENTS.md` non-negotiables)

- [ ] I read [`CONTRACTS.md`](../CONTRACTS.md) and the nearest `AGENTS.md`.
- [ ] No canonical model / enum / env var / service was renamed.
- [ ] No new code lives outside the file ownership map in CONTRACTS.md §12.
- [ ] All tenant-scoped queries filter on `tenant_id` (defense-in-depth in
      services too).
- [ ] Schema is SQLite-portable (no `UUID`, `JSONB`, partial indexes;
      `String(36)` PKs; generic `JSON`).
- [ ] If a model changed → a new Alembic migration is included **and**
      hand-reviewed (no PG-only ops).
- [ ] No new `print` / `console.log` in committed code.
- [ ] No new `any` in TypeScript; strict mode honored.
- [ ] Python files start with `from __future__ import annotations`.
- [ ] Secrets are read from `settings` / `env`, never hardcoded.

## Tests

- [ ] New code paths have happy-path tests.
- [ ] New endpoints have 401 / 422 / cross-tenant tests.
- [ ] Receipts / signing / canonical-JSON changes have byte-pinned tests in
      both `backend/` and `verifier/`.
- [ ] All subproject quality gates pass locally:

  ```powershell
  cd backend   ; ruff check . ; pytest -q
  cd frontend  ; npm run lint ; npm run typecheck ; npm test
  cd extension ; npm run test
  cd oncetax   ; npm run typecheck ; npm test
  cd verifier  ; pytest -q
  ```

## Security / compliance

- [ ] No change to PBKDF2 / Ed25519 / receipt canonicalization.
      (If yes → explain below and tag a reviewer.)
- [ ] No new outbound network call from the verifier.
- [ ] No new host permissions in `extension/manifest.config.ts` without a
      justification comment.
- [ ] No new env var without an `.env.example` / `.dev.vars.example` entry
      and a default/guard in `settings`.

## Notes for reviewers

<!-- Threat-model notes (if touching auth / receipts / audit), migration
backfill plan, follow-ups, screenshots, anything reviewers should know. -->
