"""Generate ``tools/perf/seed_manifest.json`` from the running demo DB.

Reads ``DATABASE_URL`` (default ``postgresql://once:once@localhost:5432/once``)
and snapshots the ``Demo Specialty MGA`` tenant into a small JSON file the
locustfile loads at startup:

* 50 supplier ids
* 50 submission ids
* 50 receipt ids
* 4 demo user emails

Idempotent — re-run after ``make seed-realistic``.

If the database is unreachable (no stack running, no creds), we still
write a manifest with safe-default sentinel ids so ``locust -f ... ``
imports cleanly. Those sentinels will 404 against a real backend, which
is exactly what you want when sanity-checking the harness without a
stack up.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_MANIFEST_PATH = _HERE / "seed_manifest.json"

_DEFAULT_DSN = "postgresql://once:once@localhost:5432/once"
_DEMO_TENANT_NAME = "Demo Specialty MGA"
_DEMO_EMAILS = [
    "brittany@demo.mga",
    "dan@demo.mga",
    "carmen@demo.mga",
    "audit@demo.mga",
]
_DEMO_PASSWORD = "dogfood-2026"

_SAFE_DEFAULT_MANIFEST: dict[str, Any] = {
    "tenant_name": _DEMO_TENANT_NAME,
    "tenant_id": None,
    "login_email": _DEMO_EMAILS[0],
    "login_password": _DEMO_PASSWORD,
    "user_emails": list(_DEMO_EMAILS),
    "supplier_ids": ["00000000-0000-0000-0000-000000000000"],
    "submission_ids": ["00000000-0000-0000-0000-000000000000"],
    "receipt_ids": ["00000000-0000-0000-0000-000000000000"],
    "source": "fallback",
}


def _connect(dsn: str):  # pragma: no cover - thin wrapper
    import psycopg2  # type: ignore[import-not-found]

    return psycopg2.connect(dsn, connect_timeout=3)


def _collect(dsn: str) -> dict[str, Any]:
    with _connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM tenants WHERE name = %s LIMIT 1",
                (_DEMO_TENANT_NAME,),
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError(
                    f"Tenant {_DEMO_TENANT_NAME!r} not found — "
                    "run `make seed-realistic` first."
                )
            tenant_id = str(row[0])

            cur.execute(
                "SELECT id FROM suppliers WHERE tenant_id = %s "
                "ORDER BY created_at ASC LIMIT 50",
                (tenant_id,),
            )
            supplier_ids = [str(r[0]) for r in cur.fetchall()]

            cur.execute(
                "SELECT id FROM supplier_submissions WHERE tenant_id = %s "
                "ORDER BY created_at ASC LIMIT 50",
                (tenant_id,),
            )
            submission_ids = [str(r[0]) for r in cur.fetchall()]

            cur.execute(
                "SELECT id FROM submission_receipts WHERE tenant_id = %s "
                "ORDER BY created_at ASC LIMIT 50",
                (tenant_id,),
            )
            receipt_ids = [str(r[0]) for r in cur.fetchall()]

            cur.execute(
                "SELECT u.email FROM users u "
                "JOIN tenant_users tu ON tu.user_id = u.id "
                "WHERE tu.tenant_id = %s "
                "ORDER BY u.created_at ASC LIMIT 4",
                (tenant_id,),
            )
            user_emails = [r[0] for r in cur.fetchall()] or list(_DEMO_EMAILS)

    if not supplier_ids:
        supplier_ids = list(_SAFE_DEFAULT_MANIFEST["supplier_ids"])
    if not submission_ids:
        submission_ids = list(_SAFE_DEFAULT_MANIFEST["submission_ids"])
    if not receipt_ids:
        receipt_ids = list(_SAFE_DEFAULT_MANIFEST["receipt_ids"])

    login_email = (
        _DEMO_EMAILS[0] if _DEMO_EMAILS[0] in user_emails else user_emails[0]
    )

    return {
        "tenant_name": _DEMO_TENANT_NAME,
        "tenant_id": tenant_id,
        "login_email": login_email,
        "login_password": _DEMO_PASSWORD,
        "user_emails": user_emails,
        "supplier_ids": supplier_ids,
        "submission_ids": submission_ids,
        "receipt_ids": receipt_ids,
        "source": "database",
    }


def _write(manifest: dict[str, Any]) -> None:
    _MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    dsn = os.environ.get("DATABASE_URL", _DEFAULT_DSN)
    try:
        manifest = _collect(dsn)
    except Exception as exc:  # noqa: BLE001 - graceful degradation by design
        sys.stderr.write(
            f"[perf] WARN: could not query {dsn}: {exc}\n"
            "[perf] Writing safe-default manifest so the locustfile still "
            "imports. Re-run after `make up && make seed-realistic`.\n"
        )
        _write(_SAFE_DEFAULT_MANIFEST)
        return 0

    _write(manifest)
    sys.stdout.write(
        "[perf] wrote {path} — {ns} suppliers, {nm} submissions, "
        "{nr} receipts, {nu} users (tenant {tid}).\n".format(
            path=_MANIFEST_PATH,
            ns=len(manifest["supplier_ids"]),
            nm=len(manifest["submission_ids"]),
            nr=len(manifest["receipt_ids"]),
            nu=len(manifest["user_emails"]),
            tid=manifest["tenant_id"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
