# Once — Cheat Sheet

> One-page printable reference. Long-form docs live in
> [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) and
> [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

## Commands (macOS / Linux / Git Bash)

| Task                | Command                  | Notes                            |
| ------------------- | ------------------------ | -------------------------------- |
| First-time setup    | `make setup`             | venv + npm + playwright + hooks  |
| Diagnose env        | `make doctor`            | versions, ports, env vars        |
| Start everything    | `make up`                | docker compose up -d --build     |
| Stop                | `make down`              | preserves volumes                |
| Tail logs           | `make logs`              | all services                     |
| Reset local data    | `make reset`             | DESTRUCTIVE — drops volumes      |
| Seed demo tenant    | `make seed`              | idempotent                       |
| End-to-end demo     | `make demo`              | up + seed + open browser         |
| Realistic seed      | `make seed-realistic`    | 50 suppliers, 90-day transcript  |
| Reset realistic seed| `make seed-reset-realistic` | removes only realistic-seed rows |
| Run all tests       | `make test`              | backend + frontend + ext + ver   |
| Integration tests   | `make test-integration`  | nginx fixtures + Playwright      |
| Lint                | `make lint`              | ruff + eslint + tsc + prettier   |
| Format              | `make fmt`               | autofix everything safe          |
| Type-check          | `make typecheck`         | mypy + tsc                       |
| Migrate up          | `make migrate`           | alembic upgrade head             |
| New migration       | `make migrate-new MSG=…` | alembic revision --autogenerate  |
| Migrate down 1      | `make migrate-down`      | alembic downgrade -1             |
| Coverage report     | `make coverage`          | combined % across components     |
| Security audit      | `make security`          | bandit + pip-audit + npm audit   |
| Docs lint           | `make docs`              | prettier --check on *.md         |
| Open psql shell     | `make shell-db`          | inside `db` container            |
| Backend shell       | `make shell-backend`     | bash inside backend container    |
| Build everything    | `make build-all`         | docker + vite + extension        |
| Observability up    | `make obs-up`            | Prometheus + Grafana + Loki      |
| Observability down  | `make obs-down`          | stop the observability stack     |
| Perf smoke          | `make perf-smoke`        | 5 users × 60s (stack must be up) |
| Perf baseline       | `make perf-baseline`     | 50 users × 5min (full baseline)  |
| Perf report         | `make perf-report`       | last run vs committed baseline   |
| Clean caches        | `make clean`             | venvs, node_modules, build dirs  |

## Commands (Windows PowerShell)

Same surface, prefixed with `.\tasks.ps1`:

```powershell
.\tasks.ps1 doctor
.\tasks.ps1 setup
.\tasks.ps1 demo
.\tasks.ps1 up
.\tasks.ps1 test
.\tasks.ps1 migrate-new "add foo column"
.\tasks.ps1 perf-smoke
```

## URL map

| Service              | URL                                  |
| -------------------- | ------------------------------------ |
| Frontend (Vite)      | http://localhost:5173                |
| Backend API          | http://localhost:8000                |
| Backend Swagger      | http://localhost:8000/docs           |
| Verifier             | http://localhost:8080                |
| Postgres             | localhost:5432  (user/db: `once`)    |
| Redis                | localhost:6379                       |
| Portal: AmTrust      | http://localhost:8101/amtrust/       |
| Portal: Markel       | http://localhost:8102/markel/        |
| Portal: Applied Epic | http://localhost:8103/applied-epic/  |
| Portal: Vertafore    | http://localhost:8104/vertafore-ams360/ |
| Grafana (obs-up)     | http://localhost:3000                |

## Default credentials (dev only)

| Where             | User      | Password           |
| ----------------- | --------- | ------------------ |
| Postgres          | `once`    | `once_dev_password`|
| Demo tenant admin | `demo@once.local` | `demo-password-change-me` |
| Portal fixtures   | `demo`    | `demo`             |

## Logs

| Service     | Tail command                              |
| ----------- | ----------------------------------------- |
| All         | `make logs`                               |
| Backend     | `docker compose logs -f backend`          |
| Worker      | `docker compose logs -f worker`           |
| Verifier    | `docker compose logs -f verifier`         |
| Postgres    | `docker compose logs -f db`               |

## Database shell

```bash
make shell-db
# inside psql:
\dt                          # list tables
\d submissions               # describe table
SELECT id, status, created_at FROM submissions ORDER BY created_at DESC LIMIT 10;
```

## Reset everything

```bash
make reset            # drops volumes, re-migrates, re-seeds (asks first)
make reset --yes      # same, no prompt
```

## Five common errors → fixes

1. **`Bind for 0.0.0.0:5432 failed: port is already allocated`**
   Another Postgres is running locally. Stop it (`brew services stop postgresql`
   or kill the service) or change `POSTGRES_PORT` in `.env`.

2. **`pytest` fails with `bcrypt has no attribute __about__`**
   Pin `bcrypt==4.0.1`. See `docs/TROUBLESHOOTING.md`.

3. **`playwright._impl._errors.Error: Executable doesn't exist`**
   Run `playwright install chromium --with-deps` (or `make setup`).

4. **Frontend can't reach backend (`Network Error` in browser console)**
   CORS or wrong env var. Confirm
   `VITE_API_BASE_URL=http://localhost:8000` in `frontend/.env.local` and
   `BACKEND_CORS_ORIGINS` includes `http://localhost:5173`.

5. **Alembic: `Multiple head revisions are present`**
   Two migrations branched. `cd backend && alembic merge -m "merge" heads`.

## Where to find more

- Full dev guide: [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)
- Troubleshooting: [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)
- Style guide: [`docs/STYLE_GUIDE.md`](docs/STYLE_GUIDE.md)
- Architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Contracts: [`CONTRACTS.md`](CONTRACTS.md)
- Submitter authoring: [`docs/SUBMITTERS.md`](docs/SUBMITTERS.md)
