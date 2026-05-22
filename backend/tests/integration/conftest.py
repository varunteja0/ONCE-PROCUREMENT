"""Pytest fixtures for the portal-fixture integration suite.

The suite is gated behind ``RUN_INTEGRATION_TESTS=1`` so it never runs in the
default ``pytest -q`` invocation (which is sqlite-in-memory + no browsers).

When enabled it expects the four nginx fixtures to be already reachable on
``localhost:8101..8104`` — start them with::

    docker compose up -d portal-fixtures

Or run nginx directly from ``fixtures/portals/_nginx/``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import urlopen

import pytest

# ---------------------------------------------------------------------------
# Global skip guard
# ---------------------------------------------------------------------------

_INTEGRATION_ENABLED = os.environ.get("RUN_INTEGRATION_TESTS", "") == "1"


def pytest_collection_modifyitems(config, items):  # noqa: D401, ARG001
    if _INTEGRATION_ENABLED:
        return
    skip = pytest.mark.skip(reason="set RUN_INTEGRATION_TESTS=1 to run integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


# ---------------------------------------------------------------------------
# Per-portal URL fixtures (env-driven; safe defaults to localhost)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PortalEndpoint:
    slug: str
    base_url: str
    username: str
    password: str


def _resolve(slug: str, default_port: int, env_prefix: str) -> PortalEndpoint:
    url = os.environ.get(f"PORTAL_{env_prefix}_URL", f"http://localhost:{default_port}/")
    user = os.environ.get(f"{env_prefix}_USERNAME", "demo")
    pwd = os.environ.get(f"{env_prefix}_PASSWORD", "demo")
    return PortalEndpoint(slug=slug, base_url=url.rstrip("/") + "/", username=user, password=pwd)


_PORTAL_SPECS: dict[str, tuple[int, str]] = {
    "amtrust": (8101, "AMTRUST"),
    "markel": (8102, "MARKEL"),
    "applied_epic": (8103, "APPLIED_EPIC"),
    "vertafore_ams360": (8104, "VERTAFORE_AMS360"),
    "sircon": (8105, "SIRCON"),
}


def _wait_for_url(url: str, *, timeout_sec: float = 5.0) -> bool:
    import time

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as resp:
                if 200 <= resp.status < 500:
                    return True
        except (TimeoutError, URLError, ConnectionError):
            time.sleep(0.25)
    return False


@pytest.fixture(scope="session")
def amtrust_portal() -> PortalEndpoint:
    ep = _resolve("amtrust", 8101, "AMTRUST")
    if not _wait_for_url(ep.base_url):
        pytest.skip(f"AmTrust fixture not reachable at {ep.base_url}")
    return ep


@pytest.fixture(scope="session")
def markel_portal() -> PortalEndpoint:
    ep = _resolve("markel", 8102, "MARKEL")
    if not _wait_for_url(ep.base_url):
        pytest.skip(f"Markel fixture not reachable at {ep.base_url}")
    return ep


@pytest.fixture(scope="session")
def applied_epic_portal() -> PortalEndpoint:
    ep = _resolve("applied_epic", 8103, "APPLIED_EPIC")
    if not _wait_for_url(ep.base_url):
        pytest.skip(f"Applied Epic fixture not reachable at {ep.base_url}")
    return ep


@pytest.fixture(scope="session")
def vertafore_portal() -> PortalEndpoint:
    ep = _resolve("vertafore_ams360", 8104, "VERTAFORE_AMS360")
    if not _wait_for_url(ep.base_url):
        pytest.skip(f"Vertafore AMS360 fixture not reachable at {ep.base_url}")
    return ep


@pytest.fixture(scope="session")
def sircon_portal() -> PortalEndpoint:
    ep = _resolve("sircon", 8105, "SIRCON")
    if not _wait_for_url(ep.base_url):
        pytest.skip(f"Sircon fixture not reachable at {ep.base_url}")
    return ep


# ---------------------------------------------------------------------------
# Shared payload + fake ORM objects
# ---------------------------------------------------------------------------


@dataclass
class _FakeSupplier:
    id: str = "sup-int-001"
    tenant_id: str = "tenant-int-001"
    legal_name: str = "Acme Underwriting LLC"


@dataclass
class _FakePortal:
    id: str = "portal-int-001"
    base_url: str | None = None


@pytest.fixture()
def fake_supplier() -> _FakeSupplier:
    return _FakeSupplier()


@pytest.fixture()
def fake_portal() -> _FakePortal:
    return _FakePortal()


@pytest.fixture()
def base_payload() -> dict:
    return {
        "submission_id": "subm-int-001",
        "named_insured": "Acme Underwriting LLC",
        "account_number": "ACME-0001",
        "fein": "12-3456789",
        "ams360_agency_code": "AG-0001",
        "agency_code": "AG-0001",
        "producer_code": "PC-0001",
        "producer": "Jane Producer",
        "effective_date": "2026-01-01",
        "premium_cents": 1234500,
        "line_of_business": "General Liability",
        "target_states": ["NY", "NJ"],
        "state": "NY",
        # Sircon (producer licensing) payload keys
        "legal_name": "Acme Underwriting LLC",
        "ein": "12-3456789",
        "npn": "1234567",
        "license_states": ["NY", "NJ", "CT"],
    }
