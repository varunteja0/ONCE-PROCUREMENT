"""Applied Epic agency-management submitter (Playwright)."""

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


class AppliedEpicSubmitter(PlaywrightSubmitter):
    """Applied Epic submitter.

    URL :env:`PORTAL_APPLIED_EPIC_URL`, creds :env:`APPLIED_EPIC_USERNAME` /
    :env:`APPLIED_EPIC_PASSWORD`.
    """

    platform = PortalPlatform.APPLIED_EPIC
    PLATFORM = PortalPlatform.APPLIED_EPIC
    URL_ENV_VAR = "PORTAL_APPLIED_EPIC_URL"
    USERNAME_ENV_VAR = "APPLIED_EPIC_USERNAME"
    PASSWORD_ENV_VAR = "APPLIED_EPIC_PASSWORD"  # noqa: S105
    PORTAL_REFERENCE_PREFIX = "EPIC"
    SMOKE_PROBE_NEEDLE = "Applied Epic"

    REQUIRED_FIELDS = (
        "named_insured",
        "account_number",
        "fein",
        "effective_date",
        "premium_cents",
        "line_of_business",
    )

    FIELD_MAP = {
        "named_insured": "Account Name",
        "account_number": "Account Number",
        "fein": "FEIN",
        "effective_date": "Effective Date",
        "line_of_business": "Line of Business",
        "premium": "Premium",
        "producer": "Producer",
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
                user_message="Applied Epic login form did not render.",
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
        fills: list[tuple[str, str]] = [
            ("named_insured", str(payload.get("named_insured", ""))),
            ("account_number", str(payload.get("account_number", ""))),
            ("fein", str(payload.get("fein", ""))),
            ("effective_date", str(payload.get("effective_date", ""))),
            ("line_of_business", str(payload.get("line_of_business", ""))),
            ("premium", premium_dollars),
        ]
        if payload.get("producer"):
            fills.append(("producer", str(payload["producer"])))
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


SUBMITTER_REGISTRY[PortalPlatform.APPLIED_EPIC] = AppliedEpicSubmitter
