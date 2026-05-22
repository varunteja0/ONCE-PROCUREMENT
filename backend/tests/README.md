# Once backend test suite

This directory holds the hermetic, async test suite for the Once backend
(FastAPI + SQLAlchemy + Ed25519 receipts).

## Quick start

```bash
# from backend/
python -m pytest -q                              # full suite
python -m pytest -q --cov=app --cov-report=term-missing
python -m pytest tests/test_receipts_extended.py -q
```

Environment variables required:

```bash
JWT_SECRET_KEY=test-secret SECRET_KEY=test-secret python -m pytest
```

Anything else (database URL, signing key) is wired up by the fixtures in
`tests/conftest.py`.

## Test taxonomy

| Layer | Files | What it pins |
| --- | --- | --- |
| **Unit / pure** | `test_canonical_json.py` | RFC8785 encoding, key ordering, NaN/Inf rejection. |
| **Service** | `test_consents.py`, `test_cois.py`, `test_signing_key_registry.py`, `test_pipeline_failures.py` | Service-layer behavior with a real async session and SQLite. |
| **API** | `test_auth_extended.py`, `test_suppliers_extended.py`, `test_submissions_extended.py`, `test_receipts_extended.py`, `test_portals.py`, `test_health.py`, `test_pagination.py`, `test_errors.py` | End-to-end routes through `httpx.ASGITransport`. |
| **Middleware** | `test_middleware_csrf.py`, `test_middleware_tenant_scope.py`, `test_middleware_rate_limit.py` | Each middleware bound to a tiny dedicated FastAPI app. |
| **Observability** | `test_observability_handlers.py` | Structured 4xx/5xx/422 error envelopes from `register_exception_handlers`. |
| **Audit log** | `test_audit_log.py` | Mutating endpoints emit `AuditLog` rows with correct linkage. |
| **Failure / property** | `test_pipeline_failures.py`, `test_canonical_json.py::TestRoundTrip` | Exception-classification table + JSON round-trip equality. |

The root `tests/conftest.py` is the single source of truth for fixtures used
across every layer. Anything more specialized (two-tenant clients, app with
observability handlers wired up) lives in `tests/conftest_helpers.py` and
must be imported explicitly. Tests never modify the root conftest.

## Key fixtures

| Fixture | What you get | Notes |
| --- | --- | --- |
| `_test_engine` | Fresh in-memory SQLite engine bound to `app.db` for the test. | Seeds the 5 canonical `Portal` rows. |
| `async_session` | Standalone `AsyncSession` against the test engine. | Auto-rolls back at teardown. |
| `signing_key` | A freshly generated Ed25519 key patched into `settings` and the crypto cache. | Required by every receipt-related test. |
| `test_app` / `client` | Minimal FastAPI app + `httpx.AsyncClient`. | Includes `TenantScopeMiddleware`; no CSRF, no rate limit, no observability handlers. |
| `auth_client` | `(client, RegisteredUser)` tuple already authenticated as `owner@example.com`. | Use for any happy-path API test. |
| `two_tenants` *(from `conftest_helpers`)* | Two registered tenants with bearer headers ready. | For cross-tenant isolation tests. |
| `client_with_handlers` *(from `conftest_helpers`)* | Client mounted on an app that also has the structured exception handlers. | Use only when asserting on the observability envelope. |

## Factories

`tests/factories.py` exposes hand-rolled async factories. They live outside
the conftest so they can be imported from any module without triggering the
plugin auto-load order.

```python
from tests.factories import (
    make_tenant, make_user, make_tenant_user,
    make_supplier, make_portal, make_consent, make_submission,
    make_receipt, make_signing_key, make_coi,
    register_and_token, make_auth_headers,
)
```

Each factory accepts `**overrides` and commits/flushes as needed so the
returned ORM instance is immediately usable (its `.id` is populated).

## Adding a test

1. **Pick the layer.** If you're testing a pure function, write a unit
   test. If you're testing an API endpoint, prefer using `auth_client` over
   building scaffolding by hand.
2. **Mark async tests.** Pytest-asyncio is in *strict* mode, so add
   `pytestmark = pytest.mark.asyncio` at the top of any file with async
   tests.
3. **Don't touch the root conftest.** New fixtures go in
   `tests/conftest_helpers.py` and are imported explicitly.
4. **Use the factories.** They handle FK requirements, unique slugs, and
   timestamps consistently with the rest of the suite.

## Coverage

Coverage configuration lives in `backend/pyproject.toml` (`[tool.coverage.*]`)
with a redundant copy in `backend/.coveragerc` for tools that don't yet read
pyproject. Run with:

```bash
python -m pytest --cov=app --cov-report=term-missing --cov-report=html
```

The configured floor is **75% statement coverage with branch coverage
enabled**. The signer (`receipt_signer.py`), canonical JSON encoder
(`canonical_json.py`), CSRF middleware, and tenant-scope middleware are
covered at or near 100%.

## Known pre-existing issues

* `tests/test_receipts_signing.py::test_mutated_public_payload_fails_verification`
  is sensitive to SQLite's JSON-column mutation tracking and flakes
  intermittently. It is NOT covered or fixed by this suite — it pre-dates
  this work.
* `app.services.submission_pipeline._sign_receipt` calls
  `receipt_signer.sign_receipt` with kwargs (`supplier`, `portal`,
  `outcome`) that the signer doesn't accept. The success path in
  `tests/test_pipeline_failures.py::TestProcessSubmission::test_success_path_signs_receipt`
  is marked `xfail(strict=False)` until production is reconciled.
