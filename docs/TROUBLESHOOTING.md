# Troubleshooting

The errors here have all bitten a real contributor. If you hit something
that isn't listed, please add it — that's how this file stays useful.

---

## docker compose

### `Bind for 0.0.0.0:5432 failed: port is already allocated`

Another Postgres on the host owns 5432.

```bash
# macOS Homebrew
brew services stop postgresql
# Linux
sudo systemctl stop postgresql
# Windows
Stop-Service postgresql-x64-16
```

Or change the host-side port in `.env`:

```env
POSTGRES_PORT=55432
```

Same pattern for 6379 (Redis), 5173 (Vite), 8000 (backend), 8080 (verifier).

### `error during connect … docker daemon is not running`

Start Docker Desktop (Windows / macOS) or `sudo systemctl start docker` (Linux).

### `permission denied while trying to connect to the Docker daemon socket`

Linux only:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Containers exit immediately on `make up`

```bash
docker compose logs backend | tail -50
```

Most common: `SECRET_KEY too short` or `RECEIPT_SIGNING_PRIVATE_KEY_PEM
not set`. Generate one:

```bash
python scripts/gen_signing_key.py --key-id primary >> .env
```

---

## Python / pytest

### `AttributeError: module 'bcrypt' has no attribute '__about__'`

`passlib` 1.7.x is incompatible with `bcrypt` 5.x. Pin:

```bash
pip install 'bcrypt==4.0.1'
```

Already pinned in `backend/requirements.txt`; if you see this, you've
upgraded by accident.

### `ModuleNotFoundError: No module named 'app'`

Run pytest from the `backend/` directory (it adds `.` to `sys.path`), not
from the repo root.

### `pytest hangs forever`

Almost always a leaked async fixture. Run with `-x -p no:randomly` to
pinpoint, then check that every `async with` closes.

### Alembic: `Target database is not up to date`

```bash
cd backend && alembic upgrade head
```

If that says `Can't locate revision identified by '…'`, your local DB has
a row from a deleted migration:

```sql
DELETE FROM alembic_version;
```

Then `alembic upgrade head` again.

### Alembic: `Multiple head revisions are present`

Two branches added migrations in parallel.

```bash
cd backend && alembic merge -m "merge heads" heads
alembic upgrade head
```

---

## Frontend

### `Network Error` / CORS errors in browser console

Two things to check:

1. `VITE_API_BASE_URL` in `frontend/.env.local` matches where the backend
   is actually listening (default `http://localhost:8000`).
2. `BACKEND_CORS_ORIGINS` in `.env` includes `http://localhost:5173`
   (it's the default; only an issue if you've edited it).

Restart Vite (`Ctrl-C` + `npm run dev`) after editing env files — they're
only read at boot.

### `Could not resolve "react"` after pulling

```bash
rm -rf frontend/node_modules frontend/package-lock.json
npm --prefix frontend install
```

### Tailwind classes not applied

`tailwind.config.js`'s `content` glob must include your file. Then
`Ctrl-S` to force Vite to re-scan.

---

## Extension

### "Manifest file is missing or unreadable"

You loaded `extension/` instead of `extension/dist/`. Always load the
built output. If `dist/` doesn't exist: `cd extension && npm run build`.

### Extension installs but does nothing

Open `chrome://extensions/`, click the **Service Worker** link under the
Once extension card, watch its DevTools console. Most issues are:

- Backend not reachable from the service worker (check `VITE_EXT_API_BASE_URL`).
- CSP blocking inline event handlers (we use MV3, no inline allowed).

### "Extension ID changed"

If you rebuild with a different signing key, the ID changes. Pin the key
in `extension/manifest.json`'s `key` field (base64 public key of the
private signing key you keep out of git).

---

## Playwright / submitters

### `Executable doesn't exist at .../chrome-linux/chrome`

```bash
playwright install chromium --with-deps
```

On Linux you may also need:

```bash
playwright install-deps
```

### Submitter test hangs

Headless Chromium sometimes can't reach the fixture nginx if Docker
networking is funky. Verify:

```bash
curl http://localhost:8101/amtrust/   # should return HTML
```

If 0 bytes, restart the `portal-fixtures` service:

```bash
docker compose restart portal-fixtures
```

### "Tests are flaky"

We use `pytest-randomly` — flakes are usually order-dependent state.
Reproduce with the printed seed:

```bash
pytest -p randomly --randomly-seed=12345
```

Then fix by tightening fixture cleanup or by adding an explicit DB reset.

---

## Pre-commit / hooks

### `Executable .../python3.12 not found`

`.pre-commit-config.yaml` pins Python 3.12. Install it (see DEVELOPMENT.md
§1) and `pre-commit clean && pre-commit install`.

### Hooks pass locally but fail in CI

Different versions. Run `pre-commit autoupdate` and commit the bumped
versions; CI uses whatever is in `.pre-commit-config.yaml`.

---

## Misc

### Disk filling up

```bash
docker system prune -af --volumes     # nukes ALL unused docker data
make clean                            # repo-local caches and node_modules
```

### "Where are the logs?"

- App logs: `docker compose logs <service>` or `make logs`.
- Playwright screenshots: `./.once/screenshots/` (configurable via
  `SCREENSHOT_DIR`).
- Pytest output: stdout; add `--log-file=pytest.log` to persist.

### Reset everything to a known-good state

```bash
make reset           # data only — keeps source, .env, node_modules, venv
make clean && make setup && make reset   # also re-bootstraps tooling
```
