"""OpenAPI tag metadata.

Surfaced by :mod:`app.api.v1.openapi_customization` so the generated spec
(and the rendered Swagger / Redoc docs) carry rich tag descriptions and
ordering — not just bare identifiers.
"""

from __future__ import annotations

from typing import Any

__all__ = ["OPENAPI_TAGS"]


def _tag(name: str, description: str, doc_slug: str | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": name, "description": description}
    if doc_slug:
        entry["externalDocs"] = {
            "description": "Guide",
            "url": f"https://docs.getonce.com/{doc_slug}",
        }
    return entry


OPENAPI_TAGS: list[dict[str, Any]] = [
    _tag("meta", "Liveness, readiness, and version metadata.", "ops/health"),
    _tag(
        "auth",
        "Registration, login, refresh, password reset. JWT bearer tokens (15 min access / 30 day refresh).",
        "auth",
    ),
    _tag(
        "tenants",
        "MGA / agency tenants. One tenant per organization; users belong to exactly one tenant.",
        "tenants",
    ),
    _tag(
        "suppliers",
        "Producers / sub-producers whose data Once submits to carrier portals.",
        "suppliers",
    ),
    _tag(
        "portals",
        "Catalogue of supported carrier / AMS portals (AmTrust, Markel, Applied Epic, …).",
        "portals",
    ),
    _tag(
        "submissions",
        "Submission lifecycle: queue → run → complete / fail / retry / block.",
        "submissions",
    ),
    _tag(
        "receipts",
        "Ed25519-signed submission receipts. Publicly verifiable at /verify/{receipt_id}.",
        "receipts",
    ),
    _tag(
        "loss-runs",
        "Carrier loss-run uploads attached to a supplier.",
        "loss-runs",
    ),
    _tag(
        "producer-licenses",
        "State producer-license records with expiry tracking.",
        "producer-licenses",
    ),
    _tag(
        "eo-certificates",
        "Errors & Omissions insurance certificates with expiry tracking.",
        "eo-certificates",
    ),
    _tag(
        "acord-forms",
        "Canonical ACORD form data captured once and replayed across portals.",
        "acord-forms",
    ),
    _tag(
        "risk-schedules",
        "Schedules of vehicles / properties / equipment attached to submissions.",
        "risk-schedules",
    ),
    _tag(
        "security",
        "Tenant-scoped security events: lockouts, secret rotation, audit log access.",
        "security",
    ),
    _tag(
        "public",
        "Unauthenticated endpoints (receipt verification, health). Rate-limited by IP.",
        "public",
    ),
]
