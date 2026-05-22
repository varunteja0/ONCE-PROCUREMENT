# Quickstart — Once in 5 minutes

A friendly walkthrough for first-time setup. If you just want the
commands, the [`README.md`](../README.md#quickstart-5-min) Quickstart
block is shorter. If you want a guided product tour after setup, see
[`docs/DEMO.md`](./DEMO.md).

> **Time budget:** ~10 minutes on a fresh laptop with a fast connection.
> ~90 seconds on a re-run when Docker images and node_modules are warm.

---

## 0. Prerequisites

You need:

- **Python 3.12+**
- **Node 20+** (npm comes with it)
- **Docker Desktop** (or Docker Engine + Compose v2 on Linux)
- ~5 GB of free disk (Docker images + Playwright Chromium)
- Free local ports: `5173`, `8000`, `8080`, `5432`, `6379`, `8081–8085`

If you're not sure — skip to step 1, the doctor will tell you.

---

## 1. Diagnose your environment

```bash
make doctor
```

(Windows without GNU Make: `.\tasks.ps1 doctor`.)

The doctor runs ~16 checks across toolchain, container runtime, free
ports, repo layout, and disk space. Each check has an ID
(e.g. `DOC.DOCKER.DAEMON`), a result (`✓` / `⚠` / `✗`), and a fix hint
with the exact command to run.

![Doctor output](assets/quickstart/doctor.png)

The exit code is **0** if all required checks pass (warnings don't
block), **1** otherwise. Fix any `✗` before continuing — the most common
ones are:

- **Docker daemon not responding** → start Docker Desktop, wait for the
  whale icon to stop animating.
- **Port in use** → the doctor prints the offending PID + a `kill` or
  `taskkill` hint.
- **OneDrive / iCloud / Dropbox path** → not fatal, but file syncs make
  npm/pip writes 5–10× slower. Move the repo to `~/dev/once-procurement`
  if you can.

---

## 2. Install everything

```bash
make setup
```

This is idempotent — safe to re-run any time. On a cold cache it takes
2–3 minutes. It will:

1. Run the doctor as a pre-flight (bails on hard failures).
2. Copy `.env.example` → `.env` in each subproject that has a template
   (and warn about leftover `# CHANGE_ME` placeholders).
3. Create `backend/.venv` and install `backend/requirements.txt`
   (+ verifier requirements into the same venv).
4. Run `npm ci` in `frontend/`, `extension/`, `oncetax/` if a lockfile
   exists (falls back to `npm install` otherwise).
5. Install Playwright Chromium with system deps (~250 MB; we skip
   webkit/firefox to save ~1 GB).
6. Run `alembic upgrade head` against a local sqlite for unit tests.
7. Install pre-commit hooks.

![Setup output](assets/quickstart/setup.png)

Each phase prints its elapsed time. The summary at the end lists which
phases passed and the total time spent.

Want to preview without changing anything? Use `--dry-run`:

```bash
python scripts/dev_setup.py --dry-run
```

---

## 3. Boot + seed + open the browser

```bash
make demo
```

This runs `make up` (docker compose up -d --build) and then
`make seed` (idempotent demo tenant seed), then opens
<http://localhost:5173> in your default browser.

![Demo dashboard](assets/quickstart/dashboard.png)

You should see:

- **Frontend** at <http://localhost:5173> — login as `demo@once.local`
  / `demo-password-change-me`.
- **API docs** at <http://localhost:8000/docs> (Swagger UI).
- **Verifier** at <http://localhost:8080/healthz> → `{"ok": true}`.

For the full guided tour ("click here, expect this, screenshot that"),
follow [`docs/DEMO.md`](./DEMO.md). For the screencast shot list
([`docs/SCREENCAST_SHOTLIST.md`](./SCREENCAST_SHOTLIST.md)) tells you
where the `assets/quickstart/*.png` images above come from.

---

## 4. When something goes wrong

| Symptom                                | First thing to try                                    |
| -------------------------------------- | ----------------------------------------------------- |
| `make doctor` fails on Docker daemon   | Start Docker Desktop and wait ~30 sec, then re-run.   |
| `make setup` hangs on npm              | `cd frontend && rm -rf node_modules && npm ci`        |
| Playwright "executable doesn't exist"  | `cd backend && .venv/bin/python -m playwright install chromium` |
| Port already in use                    | `make down`; if not us, the doctor prints the PID.    |
| Frontend can't reach backend           | Confirm `VITE_API_BASE_URL=http://localhost:8000` in `frontend/.env.local`. |
| Alembic "multiple heads"               | `cd backend && alembic merge -m "merge" heads`        |

More in [`docs/TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) and the
"Five common errors" section of [`CHEATSHEET.md`](../CHEATSHEET.md).

---

## What next?

- 📖 [`docs/DEMO.md`](./DEMO.md) — the 90-second product tour (canonical).
- 📖 [`LOCAL-BUILD.md`](../LOCAL-BUILD.md) — deeper local-only build guide.
- 📖 [`CONTRACTS.md`](../CONTRACTS.md) — the non-negotiables (read before contributing).
- 📖 [`CHEATSHEET.md`](../CHEATSHEET.md) — every `make` target on one page.
- 📖 [`AGENTS.md`](../AGENTS.md) — entry point if you're pairing with an AI assistant.
