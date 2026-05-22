# Build & Verify — Once

> Runtime note: the agent session that authored this codebase ran inside a
> sandbox without a working shell, so no commands below were executed. Before
> trusting the code, run them on a real workstation.

## Backend (Python 3.12)

```bash
cd backend
python -m venv .venv
. .venv/bin/activate           # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
ruff check .
pytest -q
```

`pytest` runs against in-memory SQLite (`sqlite+aiosqlite:///:memory:` with
`StaticPool`); no Postgres or Redis needed for the test suite.

To run the API locally against Postgres:

```bash
docker compose up -d db redis
export DATABASE_URL=postgresql+asyncpg://once:once@localhost:5432/once
export REDIS_URL=redis://localhost:6379/0
export SECRET_KEY=dev-secret-change-me
export JWT_SECRET_KEY=dev-jwt-secret-change-me
export RECEIPT_SIGNING_PRIVATE_KEY_PEM=$(python -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; from cryptography.hazmat.primitives import serialization as s; k=Ed25519PrivateKey.generate(); print(k.private_bytes(encoding=s.Encoding.PEM, format=s.PrivateFormat.PKCS8, encryption_algorithm=s.NoEncryption()).decode())")
alembic upgrade head
uvicorn app.main:app --reload
```

OpenAPI: `http://localhost:8000/docs`.

## Frontend (Vite + React)

```bash
cd frontend
npm install
npm run lint
npx tsc --noEmit
npm run dev   # http://localhost:5173
```

## Extension (MV3)

```bash
cd extension
npm install
npm run test
npm run build         # outputs ./dist  → load unpacked in chrome://extensions
```

> `fake-indexeddb` is referenced by `tests/vault.test.ts`. If `npm install`
> doesn't pull it transitively, run `npm i -D fake-indexeddb`.

## OnceTax (Wedge B, Cloudflare Workers)

```bash
cd oncetax
npm install
cp .dev.vars.example .dev.vars   # fill in Shopify keys
npx wrangler d1 execute oncetax --local --file=app/schema.sql
npx wrangler dev
```

## Verifier service

```bash
cd verifier
pip install -r requirements.txt
export RECEIPT_PUBLIC_KEY_PEM=...   # public half of backend signing key
export BACKEND_BASE_URL=http://localhost:8000
uvicorn app.main:app --port 8080
```

## docker-compose (everything)

```bash
docker compose up --build
# backend  http://localhost:8000/docs
# frontend http://localhost:5173
```

## Known follow-ups before first paying pilot

1. **Real Playwright submitters** — current submitters are deterministic
   mocks. M2 work: implement actual portal automation for Applied Epic +
   AmTrust under `BaseSubmitter._run_sync`. See `docs/RUNBOOK.md`.
2. ~~**Backend public receipts endpoint** — `verifier/app/main.py` calls
   `GET /v1/public/receipts/{id}` on the main backend. Today the closest
   endpoint is `GET /verify/{receipt_id}` exposed by
   `app/api/v1/receipts.py:public_receipt_router`. Either alias the path or
   point the verifier env var to the existing one.~~ **Resolved** —
   `public_v1_receipt_router` now serves `GET /v1/public/receipts/{id}`
   (mounted in `app/main.py`) while `/verify/{id}` remains for share-links.
   Verifier `backend_receipt_path` defaults to `/v1/public/receipts/`.
3. ~~**Signing key registry** — `receipt_signer.get_public_key_pem(key_id)` is
   a single-key map today. Add a Postgres-backed registry before key rotation.~~
   **Resolved** — new `signing_keys` table (migration
   `20260519_02_signing_keys`) backs lookups via
   `receipt_signer.load_signing_key_into_cache`; `bootstrap_signing_key` runs
   on app startup to register the env-configured key.
4. **fake-indexeddb** — add to `extension/package.json` devDeps explicitly.
5. ~~**CSRF middleware** — implemented in `app/middleware/csrf.py` but not yet
   wired into `create_app()`. Add `app.add_middleware(CSRFMiddleware)` once
   the frontend exchanges the `once_csrf` cookie on POST/PUT/PATCH/DELETE.~~
   **Resolved** — `CSRFMiddleware` is wired in `create_app()`. Bypasses
   `/v1/auth/*`, `/v1/webhooks/*`, `/v1/public/*`, `/verify/*`, health probes,
   and any `Authorization: Bearer ...` request (the SPA + extension flows).
6. ~~**`PortalPlatform` import path** — `app/automation/submitters/__init__.py`
   and `app/automation/detector.py` imported `PortalPlatform` from
   `app.models.submission` (doesn't exist there). Now imported from
   `app.models.portal`.~~ ✅ done (Agent B11).
7. ~~**`submission_pipeline._sign_receipt` kwargs mismatch** —
   `_sign_receipt` passed `supplier`/`portal`/`outcome` to
   `receipt_signer.sign_receipt`, which only accepts
   `(session, *, submission, consent, tos_version_hash)`. Fixed; a
   placeholder ToS hash is derived per-portal until ToS capture lands.~~
   ✅ done (Agent B11).
8. ~~**`GET /v1/receipts` 500** — `ReceiptRead.model_validate(<ORM>)` ran
   before `verify_url` was injected, but `verify_url` is required. List/get
   now build the dict with `verify_url` first via `_receipt_to_read`.~~
   ✅ done (Agent B11).
9. ~~**passlib + bcrypt on Python 3.13/3.14** — bcrypt ≥4.1 dropped
   `__about__`, which passlib 1.7's bcrypt backend inspects on import. Pinned
   `bcrypt==4.0.1` in `backend/requirements.txt` until passlib ships a fix.~~
   ✅ done (Agent B11).
