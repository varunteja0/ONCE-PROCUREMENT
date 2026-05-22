# Once — Shared Contracts (every module must honor)

> All subagents writing files into this repo must conform. Read before writing.

## 1. Identity
- Product: **Once** — supplier-portal autopilot for US specialty insurance MGAs.
- Pitch: "Submit once. Prove it forever." Captures producer/MGA submission data once, submits to many carrier portals, emits Ed25519-signed audit receipts.
- Repo: `once-procurement` (new). Sister repo: `oncetax-shopify` (Wedge B, separate stack).

## 2. Backend stack (locked)
- Python **3.12** only. `from __future__ import annotations` at top of every module.
- FastAPI + SQLAlchemy 2.0 async (`Mapped[...] = mapped_column(...)`) + Alembic + Celery + Playwright sync (bridged via `asyncio.to_thread`).
- Pydantic v2 + pydantic-settings. structlog (no `print`). slowapi for rate limits.
- DB: Postgres in prod, SQLite in-memory (`sqlite+aiosqlite:///:memory:`, StaticPool) in tests. **Schema must stay SQLite-portable** — NO `UUID`, `JSONB`, partial indexes. Use `String(36)` for UUIDs, `JSON` (sqlalchemy generic) for JSON.
- All PKs: `String(36)` defaulting to `lambda: str(uuid.uuid4())`.
- Status enums: `class XStatus(str, enum.Enum)`.
- Routes inject `AsyncSession = Depends(get_db)`; `get_db` autocommits on success.
- Logging: `from app.utils.logging import get_logger`.
- Config: `from app.config import settings`.
- Tenant scoping: every row in tenant-scoped tables has `tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)`. Middleware sets `request.state.tenant_id` from JWT.

## 3. Canonical model names (DO NOT rename)
| Model | Purpose |
|---|---|
| `Tenant` | top-level org (MGA) |
| `TenantUser` | user belongs to tenant |
| `User` | global identity (email, hashed_pw) |
| `Supplier` | the producer/MGA whose data is being submitted (one tenant has many) |
| `Portal` | a target carrier portal (e.g., AmTrust, Markel, Applied Epic, Vertafore AMS360) |
| `SupplierSubmission` | one submission attempt to one portal for one supplier. Has lifecycle status. |
| `SubmissionReceipt` | Ed25519-signed receipt for a successful submission. Verifiable publicly. |
| `ConsentRecord` | per-supplier signed consent: "Once may submit on my behalf to portal X". |
| `CertificateOfInsurance` | tracked COI with expiry → renewal monitor reads this. |
| `AuditLog` | append-only event log |

## 4. Canonical enums
```python
class SubmissionStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    BLOCKED = "blocked"          # captcha / human-needed
    PLATFORM_UNSUPPORTED = "platform_unsupported"

class PortalPlatform(str, enum.Enum):
    APPLIED_EPIC = "applied_epic"
    VERTAFORE_AMS360 = "vertafore_ams360"
    VERTAFORE_SIRCON = "vertafore_sircon"
    AMTRUST = "amtrust"
    MARKEL = "markel"
    NATIONWIDE_ES = "nationwide_es"
    CNA = "cna"
    GUIDEWIRE = "guidewire"
    HAWKSOFT = "hawksoft"
    EZLYNX = "ezlynx"
    NOWCERTS = "nowcerts"

class ConsentScope(str, enum.Enum):
    READ_ONLY = "read_only"
    SUBMIT_ON_BEHALF = "submit_on_behalf"
    SUBMIT_AND_SIGN = "submit_and_sign"
```

## 5. Submission pipeline atomic-claim contract
Port the autoapplyai pattern. Single canonical dispatcher.
```python
# app/services/submission_pipeline.py
async def process_submission(submission_id: str, session: AsyncSession) -> SubmissionResult: ...
# Atomically claims: UPDATE supplier_submissions SET status='running' WHERE id=:id AND status IN ('queued','retrying') RETURNING ... ; rowcount must == 1
# Then dispatches via _get_submitter(portal_platform) → BaseSubmitter subclass.
```
`BaseSubmitter` is async; sync Playwright bots are bridged via `asyncio.to_thread`.

## 6. Receipt schema (Ed25519, verifiable)
```python
# app/services/receipt_signer.py
ReceiptPayload = {
  "receipt_id": "uuid",                      # PK
  "tenant_id": "uuid",
  "supplier_id": "uuid",
  "portal": "amtrust",                       # PortalPlatform.value
  "submission_id": "uuid",
  "submitted_at": "ISO8601 UTC",
  "payload_hash": "sha256(canonical_json(fields_submitted))",
  "tos_version_hash": "sha256(portal_tos_text_at_time)",
  "consent_record_id": "uuid",
}
# Signed payload bytes = canonical_json(ReceiptPayload).encode()
# sig = Ed25519 over signed_bytes; public key fetchable from /v1/keys/{key_id}
# Verifier endpoint: GET /verify/{receipt_id} → {payload, sig, public_key, verified: bool}
```

## 7. Auth
- JWT access token (15 min) + refresh token (30 days). HS256, secret from `settings.jwt_secret_key`.
- `app.api.deps.get_current_user(token: str = Depends(oauth2_scheme)) -> User`.
- `app.api.deps.get_current_tenant_id(user = Depends(get_current_user)) -> str`.
- CSRF: double-submit cookie on state-changing routes for browser clients.

## 8. Env vars (settings.* names)
```
APP_ENV=development|staging|production
DATABASE_URL=postgresql+asyncpg://... | sqlite+aiosqlite:///:memory:
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=...
JWT_SECRET_KEY=...
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30
BACKEND_CORS_ORIGINS=["http://localhost:5173"]
RECEIPT_SIGNING_KEY_ID=default
RECEIPT_SIGNING_PRIVATE_KEY_PEM=... # PEM, base64 fine
PORTAL_SMOKE_TEST_TIMEOUT_SEC=60
ENABLE_IN_PROCESS_PROCESSOR=False
ENABLE_TOS_RISKY_PLATFORMS=False     # gate for risky portals
SENTRY_DSN=
```
Pydantic `Settings` must refuse to boot outside `APP_ENV=development` if `SECRET_KEY`/`JWT_SECRET_KEY`/`DATABASE_URL` look like placeholders.

## 9. Frontend stack (locked)
- React 18 + TypeScript + Vite + Tailwind + TanStack Query v5 + Zustand + axios + Lucide icons + react-hot-toast.
- Axios client with JWT refresh interceptor; tokens in `localStorage`.
- TypeScript strict; no `any` in committed code; ESLint `--max-warnings 0`.

## 10. Extension stack
- MV3, Vite + @crxjs/vite-plugin, React + TS for popup, vanilla TS for content scripts.
- Vault: encrypted IndexedDB via WebCrypto SubtleCrypto AES-GCM-256, key derived from passphrase via PBKDF2 (310k iterations, SHA-256).
- Vitest for unit tests with jsdom.

## 11. OnceTax (Wedge B) stack
- Remix on Cloudflare Workers, D1 SQLite, R2 PDF storage, KV sessions, Shopify Subscription Billing API. NO Stripe Connect.
- pdf-lib in Worker for filing-prep PDFs. **No auto-file in v0.** Resend transactional email. Plausible analytics. Sentry.
- Wrangler 3, TypeScript strict, Tailwind.

## 12. File ownership (per-subagent, NO overlap)
| Agent | Owned files (absolute paths under repo root) |
|---|---|
| 01 backend-core | `backend/app/main.py`, `backend/app/config.py`, `backend/app/db.py`, `backend/app/utils/logging.py`, `backend/app/utils/__init__.py`, `backend/app/__init__.py`, `backend/.env.example` |
| 02 models | `backend/app/models/__init__.py`, `backend/app/models/{base,tenant,user,supplier,portal,submission,receipt,consent,coi,audit}.py` |
| 03 alembic | `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/alembic/versions/0001_initial_schema.py` |
| 04 auth-api | `backend/app/api/__init__.py`, `backend/app/api/deps.py`, `backend/app/api/v1/__init__.py`, `backend/app/api/v1/auth.py`, `backend/app/services/auth_service.py`, `backend/app/schemas/auth.py`, `backend/app/utils/security.py` |
| 05 tenants-suppliers-api | `backend/app/api/v1/tenants.py`, `backend/app/api/v1/suppliers.py`, `backend/app/middleware/__init__.py`, `backend/app/middleware/tenant_scope.py`, `backend/app/services/tenant_service.py`, `backend/app/services/supplier_service.py`, `backend/app/schemas/{tenant,supplier}.py` |
| 06 submissions-api | `backend/app/api/v1/portals.py`, `backend/app/api/v1/submissions.py`, `backend/app/api/v1/receipts.py`, `backend/app/services/portal_service.py`, `backend/app/services/submission_service.py`, `backend/app/schemas/{portal,submission,receipt}.py` |
| 07 pipeline | `backend/app/services/submission_pipeline.py`, `backend/app/services/exceptions.py` |
| 08 automation-core | `backend/app/automation/__init__.py`, `backend/app/automation/base.py`, `backend/app/automation/detector.py`, `backend/app/automation/submitters/__init__.py`, `backend/app/automation/submitters/applied_epic.py` |
| 09 automation-platforms | `backend/app/automation/submitters/{amtrust,markel,vertafore_ams360,sircon}.py` |
| 10 receipts-crypto | `backend/app/services/receipt_signer.py`, `backend/app/utils/crypto.py`, `backend/app/utils/canonical_json.py` |
| 11 workers | `backend/app/workers/__init__.py`, `backend/app/workers/celery_app.py`, `backend/app/workers/tasks/__init__.py`, `backend/app/workers/tasks/{submission_tasks,renewal_tasks,sanctions_tasks,smoke_test_tasks}.py`, `backend/app/services/{sanctions_service,coi_monitor_service}.py` |
| 12 router-csrf | `backend/app/middleware/csrf.py`, `backend/app/api/v1/router.py` (registers ALL v1 routes), `backend/app/api/v1/health.py` |
| 13 backend-tests | `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_{auth,tenant_isolation,submission_pipeline,receipts_signing,sanctions}.py` |
| 14 backend-meta | `backend/requirements.txt`, `backend/Dockerfile`, `backend/pyproject.toml`, `backend/pytest.ini`, `backend/entrypoint.sh` |
| 15 ext-meta | `extension/package.json`, `extension/vite.config.ts`, `extension/manifest.config.ts`, `extension/tsconfig.json`, `extension/tsconfig.node.json`, `extension/postcss.config.js`, `extension/tailwind.config.js`, `extension/vitest.config.ts`, `extension/vitest.setup.ts`, `extension/src/background/index.ts` |
| 16 ext-vault | `extension/src/lib/{vault,crypto,api,storage}.ts`, `extension/src/types/{profile,portal}.ts` |
| 17 ext-fillers | `extension/src/content/dispatcher.ts`, `extension/src/content/fillers/{_shared,applied_epic,amtrust,markel}.ts` |
| 18 ext-popup | `extension/src/popup/{App,index,Approve,Profile,Receipts}.tsx`, `extension/src/popup/popup.html`, `extension/src/popup/popup.css` |
| 19 ext-tests | `extension/tests/{vault,fillers_amtrust,fillers_applied_epic,dispatcher}.test.ts` |
| 20 fe-meta | `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/tailwind.config.js`, `frontend/postcss.config.js`, `frontend/index.html`, `frontend/.eslintrc.cjs`, `frontend/src/main.tsx`, `frontend/src/index.css`, `frontend/src/App.tsx` |
| 21 fe-services | `frontend/src/services/{api,auth}.ts`, `frontend/src/store/auth.ts`, `frontend/src/hooks/{useAuth,useSubmissions,useReceipts,usePortals,useSuppliers}.ts`, `frontend/src/types/api.ts` |
| 22 fe-pages | `frontend/src/pages/{Login,Register,Dashboard,Submissions,Portals,Suppliers,Receipts,ConsentLedger,Settings}.tsx` |
| 23 fe-components | `frontend/src/components/{ProtectedRoute,Layout,Sidebar,SubmissionTable,PortalCard,ReceiptVerifierWidget,ConsentLedgerTable,StatusPill,EmptyState}.tsx` |
| 24 verifier-and-oncetax | `verifier/app/main.py`, `verifier/requirements.txt`, `verifier/Dockerfile`, `verifier/fly.toml`, `oncetax/package.json`, `oncetax/wrangler.toml`, `oncetax/tsconfig.json`, `oncetax/tailwind.config.js`, `oncetax/app/{root,entry.server,entry.client}.tsx`, `oncetax/app/routes/{_index,oauth.callback,billing,dashboard,api.calc}.tsx`, `oncetax/app/lib/{shopify,tax_calc,pdf,d1,sessions}.ts`, `oncetax/app/schema.sql`, `oncetax/.dev.vars.example` |
| 25 meta-and-docs | `README.md`, `ARCHITECTURE.md`, `LICENSE`, `.gitignore`, `.env.example`, `docker-compose.yml`, `fly.toml`, `.github/workflows/ci.yml`, `.github/workflows/extension.yml`, `docs/{PITCH,SECURITY,COMPLIANCE,RUNBOOK,API}.md`, `CONTRIBUTING.md`, `SECURITY.md` |

## 13. Quality bar
- Backend: `ruff check .` must pass; `pytest -q` must pass against in-memory SQLite.
- Frontend: `tsc --noEmit` clean; `eslint --max-warnings 0` clean.
- Extension: `vitest run` clean.
- All code production-grade — full types, structured errors, structured logging, no TODOs in critical paths.

## 14. Repo root
**`C:\Users\ChVarunTeja\OneDrive - Ramp Group Technologies\Desktop\once-procurement\`** — use this as the prefix for every absolute file path.
