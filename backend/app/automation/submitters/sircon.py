"""Vertafore Sircon producer-licensing submitter (Playwright).

Production-grade automation against the Sircon producer-licensing portal.
Sircon is Vertafore's licensing system used to file producer entity / NPN
license-state requests. The local fixture in ``fixtures/portals/sircon/`` is
markup-compatible.
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING, Any

from app.automation.base import PlaywrightSubmitter
from app.automation.submitters import SUBMITTER_REGISTRY
from app.models.portal import PortalPlatform
from app.utils.logging import get_logger

from ._playwright_helpers import (
    SelectorDriftTracker,
    detect_auth_wall,
    detect_captcha,
    fill_by_label,
    set_react_input,
    wait_for_network_idle,
)
from .errors import (
    PortalAuthError,
    PortalSelectorDriftError,
    PortalValidationError,
)

if TYPE_CHECKING:  # pragma: no cover
    from playwright.sync_api import Page

logger = get_logger(__name__)
_CONFIRMATION_REF_RE = re.compile(r"^[A-Z]+-\d{4}-[A-Z0-9]+$")


class SirconSubmitter(PlaywrightSubmitter):
    """Sircon producer-licensing portal automation.

    URL :env:`PORTAL_SIRCON_URL`, creds :env:`SIRCON_USERNAME` /
    :env:`SIRCON_PASSWORD` (fixtures accept ``demo``/``demo``).
    """

    platform = PortalPlatform.VERTAFORE_SIRCON
    PLATFORM = PortalPlatform.VERTAFORE_SIRCON
    URL_ENV_VAR = "PORTAL_SIRCON_URL"
    USERNAME_ENV_VAR = "SIRCON_USERNAME"
    PASSWORD_ENV_VAR = "SIRCON_PASSWORD"  # noqa: S105
    PORTAL_REFERENCE_PREFIX = "SRC"
    SMOKE_PROBE_NEEDLE = "Sircon"

    REQUIRED_FIELDS = (
        "legal_name",
        "ein",
        "npn",
        "license_states",
    )

    FIELD_MAP = {
        "legal_name": "Producer Legal Name",
        "ein": "Tax ID (EIN)",
        "npn": "NPN",
        "license_states": "Requested License States",
        "agency_name": "Agency Name",
    }

    def _login(self, page: Page, *, url: str, username: str, password: str) -> None:
        page.goto(url, wait_until="domcontentloaded")
        detect_captcha(page)
        try:
            set_react_input(page, "input[name='username']", username)
            set_react_input(page, "input[name='password']", password)
        except PortalSelectorDriftError as exc:
            raise PortalAuthError(
                "login_form_unavailable",
                user_message="Sircon login form did not render.",
                cause=str(exc),
            ) from exc
        page.locator("button[type='submit']").first.click()
        wait_for_network_idle(page)
        detect_auth_wall(page, expected_path_fragment="dashboard")

    def _navigate_to_new_submission(self, page: Page, *, base_url: str) -> None:
        link = page.locator("a[data-action='new-submission']").first
        if link.count() == 0:
            raise PortalSelectorDriftError(
                "new_submission_link_missing",
                selector="a[data-action='new-submission']",
            )
        link.click()
        wait_for_network_idle(page)
        detect_captcha(page)

    def _fill_form(self, page: Page, payload: dict[str, Any]) -> None:
        tracker = SelectorDriftTracker(threshold=1)
        license_states = payload.get("license_states") or []
        states_text = ",".join(license_states) if isinstance(license_states, list | tuple) else str(license_states)
        fills: list[tuple[str, str]] = [
            ("legal_name", str(payload.get("legal_name", ""))),
            ("ein", str(payload.get("ein", ""))),
            ("npn", str(payload.get("npn", ""))),
            ("license_states", states_text),
        ]
        if payload.get("agency_name"):
            fills.append(("agency_name", str(payload["agency_name"])))

        for canonical, value in fills:
            if not value:
                continue
            label = type(self).FIELD_MAP[canonical]
            fill_by_label(page, label, value, tracker=tracker)

    def _submit_and_capture(self, page: Page) -> tuple[str, dict[str, Any]]:
        page.locator("button[data-action='submit-application']").first.click()
        wait_for_network_idle(page)
        detect_captcha(page)
        ref_el = page.locator("[data-testid='confirmation-reference']").first
        if ref_el.count() == 0:
            raise PortalSelectorDriftError(
                "confirmation_reference_missing",
                selector="[data-testid='confirmation-reference']",
            )
        reference = (ref_el.inner_text() or "").strip()
        if not _CONFIRMATION_REF_RE.match(reference):
            raise PortalValidationError(
                "confirmation_reference_malformed",
                reference=reference,
                pattern=_CONFIRMATION_REF_RE.pattern,
            )
        return reference, {"url": page.url, "idempotency_token": uuid.uuid4().hex}


SUBMITTER_REGISTRY[PortalPlatform.VERTAFORE_SIRCON] = SirconSubmitter
