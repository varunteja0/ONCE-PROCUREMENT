# Once — Local Development Guide

This document is the long-form companion to [`CHEATSHEET.md`](../CHEATSHEET.md).
If you only want commands, use the cheat sheet. If you want to understand
the *why*, read on.

---

## 1. Prerequisites

| Tool              | Version | Install                                            |
| ----------------- | ------- | -------------------------------------------------- |
| Python            | 3.12.x  | https://www.python.org/downloads/                  |
| Node.js           | 20 LTS  | https://nodejs.org or `nvm install 20`             |
| npm               | 10+     | bundled with Node 20                               |
| Docker Desktop    | 4.30+   | https://www.docker.com/products/docker-desktop/    |
| Docker Compose v2 | bundled | check with `docker compose version`                |
| Git               | any     |                                                    |
| GNU Make (opt.)   | 4.x     | macOS: bundled; Linux: distro pkg; Windows: see ↓  |

### Windows notes

- Use **PowerShell 5.1+** (default) or **PowerShell 7**. Run
  `.\tasks.ps1 <task>` instead of `make <task>`. If you do want `make`,
  install Git Bash + `choco install make` or use WSL2.
- Long path support: enable in Group Policy (`Computer Configuration →
  Administrative Templates → System → Filesystem → Enable Win32 long paths`).
  Required for some Playwright browser archives.
- Line endings: `.gitattributes` normalizes to LF for source; `.ps1` stays CRLF.

### macOS notes

- `brew install python@3.12 node@20 docker postgresql` (postgresql client
  only — Postgres itself runs in Docker).
- Apple Silicon: Chromium needs Rosetta? No — Playwright ships arm64 builds.

### Linux notes

- Add yourself to the `docker` group: `sudo usermod -aG docker $USER` and
  log out / back in.

---

## 2. First-time setup (≈ 10 minutes)

```bash
git clone <repo> once && cd once
make setup          # OR: .\tasks.ps1 setup on Windows
```

`make setup` will:

1. Copy `.env.example` → `.env` if missing.
2. Create `backend/.venv` and `pip install -r backend/requirements.txt`.
3. Install ruff, black, mypy, pytest, pytest-cov, pre-commit into that venv.
4. `npm install` in `frontend/`, `extension/`, `oncetax/`.
5. `playwright install chromium`.
6. `pre-commit install` (hooks into `.git/hooks/`).

Then verify:

```bash
make doctor
```

You should see all green ✓s. If anything is red, see
[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).

---

## 3. Daily development loop

```bash
make up           # start db, redis, backend, worker, beat, frontend, fixtures
make logs         # in another tab — tail what's happening
# … edit code (uvicorn --reload + vite HMR pick up changes automatically) …
make test         # before committing
make fmt          # auto-format
```

The compose stack mounts source via bind mounts for `frontend/`, so HMR is
instant. The backend is built into an image; for fast Python iteration,
either:

- Run uvicorn locally against compose's Postgres + Redis (`make
  shell-backend` shows the env), **or**
- Use VS Code's "Backend: FastAPI (uvicorn --reload)" launch config which
  uses the venv directly.

---

## 4. Debugging tips

### Backend

- VS Code launch configs (`.vscode/launch.json`): pick "Backend: FastAPI"
  for the API, "Backend: Celery worker" for tasks, "Pytest: current file"
  to step through a test.
- Drop `import pdb; pdb.set_trace()` (or `breakpoint()`) anywhere; uvicorn
  reload preserves the breakpoint across edits in the same module.
- Tail SQL: set `LOG_LEVEL=debug` and watch `docker compose logs -f
  backend` — SQLAlchemy echoes every statement.

### Frontend

- React DevTools + the browser's network tab.
- `VITE_API_BASE_URL` controls where API calls go — change it in
  `frontend/.env.local` to point at a deployed backend.

### Extension

- `chrome://extensions` → toggle Developer mode → "Load unpacked" →
  `extension/dist/`. Use the **Service Worker** link to open DevTools for
  the background script.
- The "Extension: Chrome (load unpacked)" launch config in `.vscode/`
  spawns a clean Chrome instance with the extension preloaded.

### Verifier

- Standalone FastAPI on port 8080. Test directly with `curl
  http://localhost:8080/v1/verify/<receipt_id>`.

---

## 5. Architecture pointers

- High-level: [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
- Cross-module contracts (don't break these): [`../CONTRACTS.md`](../CONTRACTS.md)
- Data model: [`./DATA_MODEL.md`](./DATA_MODEL.md)
- Receipt signing + verification: [`./VERIFIER.md`](./VERIFIER.md)
- Threat model: [`./THREAT_MODEL.md`](./THREAT_MODEL.md)

---

## 6. Adding things

### Add a new API route

1. Pick the right router module under `backend/app/api/v1/` (or create one).
2. Define the Pydantic schemas in `backend/app/schemas/`.
3. Write the service function in `backend/app/services/` — keep route
   handlers thin (HTTP → service → response).
4. Register the router in `backend/app/api/v1/router.py`.
5. Add tests in `backend/tests/`. Tenant-scoped routes need an
   isolation test.

### Add a new ORM model

1. Subclass `Base` in `backend/app/models/`.
2. Add `tenant_id: Mapped[str]` if it's per-tenant; include the FK + index.
3. Generate a migration: `make migrate-new MSG="add table foo"`.
4. Hand-edit the migration to be SQLite-portable (`String(36)` for UUIDs,
   generic `JSON` type, no partial indexes).
5. `make migrate` to apply locally.

### Add a new frontend page

1. Create the component under `frontend/src/pages/` and a route entry
   in `frontend/src/router.tsx`.
2. Reuse hooks in `frontend/src/hooks/` for API calls (they already
   handle auth + CSRF).
3. Tests with vitest + Testing Library go in `frontend/src/__tests__/`.

### Add a new portal submitter

See [`./SUBMITTERS.md`](./SUBMITTERS.md). Short version: subclass
`BaseSubmitter`, implement `_run_sync`, register in the submitter
registry, drop a fixture portal under `fixtures/portals/<name>/`.

---

## 7. Running a single test

```bash
# Backend
cd backend && pytest tests/test_auth.py::test_login_success -vv

# Frontend
cd frontend && npx vitest run src/__tests__/Login.test.tsx

# Extension
cd extension && npx vitest run tests/vault.test.ts

# Verifier
cd verifier && pytest tests/test_verify.py -k "expired" -vv
```

Or in VS Code: open the test file, F5, pick "Pytest: current file".

---

## 8. Observability stack (local)

```bash
make obs-up        # Prometheus + Grafana + Loki + Promtail
# Grafana: http://localhost:3000  (admin/admin first login)
# Pre-provisioned dashboards under "Once / *"
make obs-down
```

Enable Prom scraping on the backend by setting `METRICS_ENABLED=true` and
`METRICS_TOKEN=<some-bearer>` in `.env`.

---

## 9. Performance profiling

- Backend hot path: use `py-spy record -o profile.svg --pid <uvicorn-pid>`
  while hitting the endpoint.
- SQL slowness: enable `LOG_LEVEL=debug` and grep for the slow query, then
  `EXPLAIN ANALYZE` in `make shell-db`.
- Frontend bundle: `cd frontend && npx vite build --mode analyze`
  (rollup-plugin-visualizer is wired).

---

## 10. Generating test data

```bash
make seed                           # demo MGA tenant + 50-ish submissions
python scripts/seed_demo_tenant.py --suppliers 500   # bigger dataset
```

The seed script is idempotent — running it twice is safe.

---

## 11. Going further

- Submit a PR: see [`../CONTRIBUTING.md`](../CONTRIBUTING.md).
- Deploy: see [`./DEPLOY.md`](./DEPLOY.md) and [`./RUNBOOK.md`](./RUNBOOK.md).
- Rotate signing keys: see [`./SECRET_ROTATION.md`](./SECRET_ROTATION.md).
