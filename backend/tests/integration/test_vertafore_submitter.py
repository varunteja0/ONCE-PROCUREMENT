"""Integration tests for VertaforeAMS360Submitter against the portal fixture."""
from __future__ import annotations

import asyncio
import os
import re

import pytest

from app.automation.submitters.errors import (
    PortalAuthError,
    PortalCaptchaError,
    PortalSelectorDriftError,
    PortalValidationError,
)
from app.automation.submitters.vertafore_ams360 import VertaforeAMS360Submitter

pytestmark = pytest.mark.integration

_REF_RE = re.compile(r"^[A-Z]+-\d{4}-[A-Z0-9]+$")


def _run(submitter_cls, *, supplier, portal, payload, consent=None):
    return asyncio.run(
        submitter_cls.submit(supplier=supplier, portal=portal, payload=payload, consent=consent)
    )


def _set_env(ep, env_prefix: str, url_override: str | None = None) -> None:
    os.environ[f"PORTAL_{env_prefix}_URL"] = url_override or ep.base_url
    os.environ[f"{env_prefix}_USERNAME"] = ep.username
    os.environ[f"{env_prefix}_PASSWORD"] = ep.password
    os.environ.setdefault("PLAYWRIGHT_HEADLESS", "true")


def test_happy_path(vertafore_portal, fake_supplier, fake_portal, base_payload):
    _set_env(vertafore_portal, "VERTAFORE_AMS360")
    outcome = _run(VertaforeAMS360Submitter, supplier=fake_supplier, portal=fake_portal, payload=base_payload)
    assert outcome.success is True
    assert _REF_RE.match(outcome.portal_reference or ""), outcome.portal_reference
    assert outcome.result_payload["submission_reference"] == outcome.portal_reference


def test_invalid_credentials(vertafore_portal, fake_supplier, fake_portal, base_payload):
    bad = type(vertafore_portal)(slug=vertafore_portal.slug, base_url=vertafore_portal.base_url, username="wrong", password="wrong")
    _set_env(bad, "VERTAFORE_AMS360")
    with pytest.raises(PortalAuthError):
        _run(VertaforeAMS360Submitter, supplier=fake_supplier, portal=fake_portal, payload=base_payload)


def test_missing_required_field(vertafore_portal, fake_supplier, fake_portal, base_payload):
    _set_env(vertafore_portal, "VERTAFORE_AMS360")
    incomplete = dict(base_payload)
    incomplete["named_insured"] = ""  # blank required field
    with pytest.raises(PortalValidationError):
        _run(VertaforeAMS360Submitter, supplier=fake_supplier, portal=fake_portal, payload=incomplete)


def test_selector_drift(vertafore_portal, fake_supplier, fake_portal, base_payload):
    drift_url = vertafore_portal.base_url + "?drift=1"
    _set_env(vertafore_portal, "VERTAFORE_AMS360", url_override=drift_url)
    with pytest.raises(PortalSelectorDriftError):
        _run(VertaforeAMS360Submitter, supplier=fake_supplier, portal=fake_portal, payload=base_payload)


def test_captcha(vertafore_portal, fake_supplier, fake_portal, base_payload):
    captcha_url = vertafore_portal.base_url + "?captcha=1"
    _set_env(vertafore_portal, "VERTAFORE_AMS360", url_override=captcha_url)
    with pytest.raises(PortalCaptchaError):
        _run(VertaforeAMS360Submitter, supplier=fake_supplier, portal=fake_portal, payload=base_payload)
