"""Health endpoint smoke tests."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize("path", ["/health", "/healthz"])
def test_health_endpoint_returns_ok(configured_app: Any, path: str) -> None:
    client = TestClient(configured_app)
    resp = client.get(path)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "service" in body
