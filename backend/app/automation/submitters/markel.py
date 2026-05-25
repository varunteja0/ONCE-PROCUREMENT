"""Markel specialty-portal submitter (Playwright)."""

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


class MarkelSubmitter(PlaywrightSubmitter):
    """Markel specialty-portal automation.

    URL :env:`PORTAL_MARKEL_URL`, creds :env:`MARKEL_USERNAME` / :env:`MARKEL_PASSWORD`.
    """

    platform = PortalPlatform.MARKEL
    PLATFORM = PortalPlatform.MARKEL
    URL_ENV_VAR = "PORTAL_MARKEL_URL"
    USERNAME_ENV_VAR = "MARKEL_USERNAME"
    PASSWORD_ENV_VAR = "MARKEL_PASSWORD"  # noqa: S105
    PORTAL_REFERENCE_PREFIX = "MKL"
    SMOKE_PROBE_NEEDLE = "Markel"

    REQUIRED_FIELDS = (
        "named_insured",
        "fein",
        "effective_date",
        "premium_cents",
        "line_of_business",
        "target_states",
    )

    FIELD_MAP = {
        "named_insured": "Insured Legal Name",
        "fein": "Tax ID (FEIN)",
        "agency_code": "Agency Code",
        "effective_date": "Policy Effective Date",
        "line_of_business": "Product Line",
        "premium": "Estimated Premium",
        "target_states": "States",
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
                user_message="Markel login form did not render.",
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
        premium_cents = payload.get("premium_cents")
        premium_dollars = f"{int(premium_cents) / 100:.2f}" if premium_cents is not None else ""
        target_states = payload.get("target_states") or []
        states_text = ",".join(target_states) if isinstance(target_states, list | tuple) else str(target_states)
        fills: list[tuple[str, str]] = [
            ("named_insured", str(payload.get("named_insured", ""))),
            ("fein", str(payload.get("fein", ""))),
            ("effective_date", str(payload.get("effective_date", ""))),
            ("line_of_business", str(payload.get("line_of_business", ""))),
            ("premium", premium_dollars),
            ("target_states", states_text),
        ]
        if payload.get("agency_code"):
            fills.append(("agency_code", str(payload["agency_code"])))
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
            )
        return reference, {"url": page.url, "idempotency_token": uuid.uuid4().hex}


SUBMITTER_REGISTRY[PortalPlatform.MARKEL] = MarkelSubmitter
