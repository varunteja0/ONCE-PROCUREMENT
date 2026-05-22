"""Locust load profile for the Once demo happy-path.

Two user classes:

* :class:`AuthenticatedUser` — logs in once as the demo ops persona and
  drives the supplier desk read surfaces plus an occasional supplier
  create. Targets the backend on ``--host`` (default ``http://localhost:8000``).
* :class:`AnonymousVerifierUser` — hits the public verifier on
  ``http://localhost:8080``. The host is hard-coded because the public
  verifier and the backend are two different processes on two different
  ports in local dev.

The seed manifest at ``tools/perf/seed_manifest.json`` provides the ids
and emails. If the manifest is missing we fall back to sentinel ids so
``locust -f tools/perf/locustfile.py`` still imports cleanly even with
no stack running.

Run examples::

    # quick smoke
    python -m locust -f tools/perf/locustfile.py --headless -u 5 -r 1 \\
        -t 60s --host http://localhost:8000 --only-summary

    # full baseline (50 users, 5 min)
    python -m locust -f tools/perf/locustfile.py --headless -u 50 -r 2 \\
        -t 5m --host http://localhost:8000 --only-summary
"""

from __future__ import annotations

import json
import random
import uuid
from pathlib import Path
from typing import Any

from locust import HttpUser, between, events, task

_HERE = Path(__file__).resolve().parent
_MANIFEST_PATH = _HERE / "seed_manifest.json"
_VERIFIER_HOST = "http://localhost:8080"

_FALLBACK_MANIFEST: dict[str, Any] = {
    "login_email": "brittany@demo.mga",
    "login_password": "dogfood-2026",
    "supplier_ids": ["00000000-0000-0000-0000-000000000000"],
    "submission_ids": ["00000000-0000-0000-0000-000000000000"],
    "receipt_ids": ["00000000-0000-0000-0000-000000000000"],
    "user_emails": ["brittany@demo.mga"],
    "source": "fallback",
}


def _load_manifest() -> dict[str, Any]:
    if not _MANIFEST_PATH.exists():
        return dict(_FALLBACK_MANIFEST)
    try:
        data = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(_FALLBACK_MANIFEST)
    merged = dict(_FALLBACK_MANIFEST)
    merged.update({k: v for k, v in data.items() if v})
    # Guard against empty lists in a partially-populated manifest.
    for k in ("supplier_ids", "submission_ids", "receipt_ids", "user_emails"):
        if not merged.get(k):
            merged[k] = list(_FALLBACK_MANIFEST[k])
    return merged


MANIFEST = _load_manifest()


@events.init.add_listener
def _announce_manifest(environment, **_: Any) -> None:  # pragma: no cover
    src = MANIFEST.get("source", "fallback")
    print(
        f"[perf] using seed_manifest.json (source={src}, "
        f"suppliers={len(MANIFEST['supplier_ids'])}, "
        f"submissions={len(MANIFEST['submission_ids'])}, "
        f"receipts={len(MANIFEST['receipt_ids'])})"
    )


class AuthenticatedUser(HttpUser):
    """Drives /v1/suppliers, /v1/submissions, /v1/receipts as a logged-in user."""

    wait_time = between(1, 3)
    weight = 3

    def on_start(self) -> None:
        self.token: str | None = None
        self.supplier_ids: list[str] = list(MANIFEST["supplier_ids"])
        self.submission_ids: list[str] = list(MANIFEST["submission_ids"])
        self.receipt_ids: list[str] = list(MANIFEST["receipt_ids"])
        self._login()

    def _login(self) -> None:
        payload = {
            "email": MANIFEST["login_email"],
            "password": MANIFEST["login_password"],
        }
        with self.client.post(
            "/v1/auth/login",
            json=payload,
            name="POST /v1/auth/login",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"login failed: {resp.status_code} {resp.text[:120]}")
                return
            try:
                body = resp.json()
                token = body.get("access_token")
            except (ValueError, AttributeError):
                resp.failure("login returned non-JSON body")
                return
            if not token:
                resp.failure("login response missing access_token")
                return
            self.token = token
            self.client.headers.update({"Authorization": f"Bearer {token}"})

    @task(5)
    def list_suppliers(self) -> None:
        self.client.get("/v1/suppliers", name="GET /v1/suppliers")

    @task(3)
    def get_supplier(self) -> None:
        sid = random.choice(self.supplier_ids)
        self.client.get(f"/v1/suppliers/{sid}", name="GET /v1/suppliers/{id}")

    @task(3)
    def list_submissions(self) -> None:
        self.client.get("/v1/submissions", name="GET /v1/submissions")

    @task(2)
    def get_receipt(self) -> None:
        rid = random.choice(self.receipt_ids)
        self.client.get(f"/v1/receipts/{rid}", name="GET /v1/receipts/{id}")

    @task(1)
    def create_supplier(self) -> None:
        ein_suffix = uuid.uuid4().hex[:9]
        payload = {
            "legal_name": f"Perf Harness Co {uuid.uuid4().hex[:8]}",
            "dba_name": "Perf DBA",
            "ein": f"99-{ein_suffix[:7]}",
            "naics_code": "541512",
            "primary_email": f"perf+{uuid.uuid4().hex[:10]}@example.com",
            "primary_phone": "+15555550100",
        }
        self.client.post(
            "/v1/suppliers", json=payload, name="POST /v1/suppliers"
        )


class AnonymousVerifierUser(HttpUser):
    """Drives the public verifier on :8080 with no auth."""

    wait_time = between(1, 3)
    weight = 1
    host = _VERIFIER_HOST

    def on_start(self) -> None:
        self.receipt_ids: list[str] = list(MANIFEST["receipt_ids"])

    @task(4)
    def verify_json(self) -> None:
        rid = random.choice(self.receipt_ids)
        self.client.get(
            f"/verify/{rid}",
            headers={"Accept": "application/json"},
            name="GET /verify/{id} (json)",
        )

    @task(2)
    def verify_html(self) -> None:
        rid = random.choice(self.receipt_ids)
        self.client.get(
            f"/verify/{rid}.html", name="GET /verify/{id}.html"
        )

    @task(1)
    def verify_badge(self) -> None:
        rid = random.choice(self.receipt_ids)
        self.client.get(
            f"/verify/{rid}/badge.svg", name="GET /verify/{id}/badge.svg"
        )

    @task(1)
    def verify_og(self) -> None:
        rid = random.choice(self.receipt_ids)
        self.client.get(
            f"/verify/{rid}/og.svg", name="GET /verify/{id}/og.svg"
        )
