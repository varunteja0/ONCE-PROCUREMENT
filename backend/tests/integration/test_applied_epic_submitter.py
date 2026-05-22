"""Integration tests for AppliedEpicSubmitter against the portal fixture."""
from __future__ import annotations

import asyncio
import os
import re

import pytest

from app.automation.submitters.applied_epic import AppliedEpicSubmitter
from app.automation.submitters.errors import (
    PortalAuthError,
    PortalCaptchaError,
    PortalSelectorDriftError,
    PortalValidationError,
)

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


def test_happy_path(applied_epic_portal, fake_supplier, fake_portal, base_payload):
    _set_env(applied_epic_portal, "APPLIED_EPIC")
    outcome = _run(AppliedEpicSubmitter, supplier=fake_supplier, portal=fake_portal, payload=base_payload)
    assert outcome.success is True
    assert _REF_RE.match(outcome.portal_reference or ""), outcome.portal_reference
    assert outcome.result_payload["submission_reference"] == outcome.portal_reference


def test_invalid_credentials(applied_epic_portal, fake_supplier, fake_portal, base_payload):
    bad = type(applied_epic_portal)(slug=applied_epic_portal.slug, base_url=applied_epic_portal.base_url, username="wrong", password="wrong")
    _set_env(bad, "APPLIED_EPIC")
    with pytest.raises(PortalAuthError):
        _run(AppliedEpicSubmitter, supplier=fake_supplier, portal=fake_portal, payload=base_payload)


def test_missing_required_field(applied_epic_portal, fake_supplier, fake_portal, base_payload):
    _set_env(applied_epic_portal, "APPLIED_EPIC")
    incomplete = dict(base_payload)
    incomplete["named_insured"] = ""  # blank required field
    with pytest.raises(PortalValidationError):
        _run(AppliedEpicSubmitter, supplier=fake_supplier, portal=fake_portal, payload=incomplete)


def test_selector_drift(applied_epic_portal, fake_supplier, fake_portal, base_payload):
    drift_url = applied_epic_portal.base_url + "?drift=1"
    _set_env(applied_epic_portal, "APPLIED_EPIC", url_override=drift_url)
    with pytest.raises(PortalSelectorDriftError):
        _run(AppliedEpicSubmitter, supplier=fake_supplier, portal=fake_portal, payload=base_payload)


def test_captcha(applied_epic_portal, fake_supplier, fake_portal, base_payload):
    captcha_url = applied_epic_portal.base_url + "?captcha=1"
    _set_env(applied_epic_portal, "APPLIED_EPIC", url_override=captcha_url)
    with pytest.raises(PortalCaptchaError):
        _run(AppliedEpicSubmitter, supplier=fake_supplier, portal=fake_portal, payload=base_payload)
