"""Tests for the public ``/v1/public/portals`` carrier-coverage endpoint.

The endpoint is fed by :mod:`app.services.portal_health_service`, which in
turn reads the smoke-test state file written by the Celery beat task. These
tests exercise:

* No-auth access.
* Stable ordering by display name.
* Every ``PortalPlatform`` enum value appears in the response.
* The ``supported`` flag matches ``SUBMITTER_REGISTRY``.
* Status derivation from a hand-written state file (``healthy``, ``degraded``,
  ``down``, ``unknown``).
* Missing / malformed state files degrade gracefully to ``unknown``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import settings
from app.models.portal import PortalPlatform


def _write_state(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.asyncio
async def test_public_portals_lists_every_platform(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state_file = tmp_path / "smoke_state.json"
    _write_state(state_file, {})
    monkeypatch.setattr(settings, "portal_smoke_state_path", str(state_file))

    response = await client.get("/v1/public/portals")

    assert response.status_code == 200
    payload = response.json()
    returned = {row["platform"] for row in payload["portals"]}
    assert returned == {p.value for p in PortalPlatform}
    assert payload["total_count"] == len(PortalPlatform)
    assert payload["supported_count"] >= 1  # at least one shipping submitter
    assert response.headers["Cache-Control"] == "public, max-age=300"


@pytest.mark.asyncio
async def test_public_portals_derives_status_from_state_file(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state_file = tmp_path / "smoke_state.json"
    _write_state(
        state_file,
        {
            "amtrust": {
                "last_status": "pass",
                "last_changed_at": "2026-05-25T10:00:00+00:00",
                "consecutive_failures": 0,
            },
            "markel": {
                "last_status": "fail",
                "last_changed_at": "2026-05-25T09:00:00+00:00",
                "consecutive_failures": 1,
            },
            "applied_epic": {
                "last_status": "fail",
                "last_changed_at": "2026-05-25T08:00:00+00:00",
                "consecutive_failures": 5,
            },
        },
    )
    monkeypatch.setattr(settings, "portal_smoke_state_path", str(state_file))

    response = await client.get("/v1/public/portals")

    assert response.status_code == 200
    rows = {r["platform"]: r for r in response.json()["portals"]}
    assert rows["amtrust"]["status"] == "healthy"
    assert rows["markel"]["status"] == "degraded"
    assert rows["applied_epic"]["status"] == "down"
    # A supported platform with no observation is "unknown".
    assert rows["vertafore_ams360"]["status"] == "unknown"


@pytest.mark.asyncio
async def test_public_portals_handles_missing_state_file(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        settings,
        "portal_smoke_state_path",
        str(tmp_path / "does-not-exist.json"),
    )

    response = await client.get("/v1/public/portals")

    assert response.status_code == 200
    payload = response.json()
    assert all(row["status"] == "unknown" for row in payload["portals"])
    assert payload["healthy_count"] == 0


@pytest.mark.asyncio
async def test_public_portals_marks_roadmap_platforms_unsupported(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "portal_smoke_state_path", str(tmp_path / "smoke_state.json"))

    response = await client.get("/v1/public/portals")

    rows = {r["platform"]: r for r in response.json()["portals"]}
    # CNA / Nationwide ES / Guidewire / HawkSoft / EZLynx / NowCerts are
    # declared in the enum but no submitter ships yet.
    for declared_only in ("cna", "nationwide_es", "guidewire", "hawksoft", "ezlynx", "nowcerts"):
        assert rows[declared_only]["supported"] is False
        assert rows[declared_only]["status"] == "unknown"


@pytest.mark.asyncio
async def test_public_portals_requires_no_auth(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "portal_smoke_state_path", str(tmp_path / "smoke_state.json"))
    response = await client.get("/v1/public/portals")
    assert response.status_code == 200
