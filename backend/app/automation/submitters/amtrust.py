"""AmTrust producer-portal submitter (Playwright).

Production-grade automation against the AmTrust producer portal. The selector
strategy uses label-text matching where possible (resilient to ID changes) and
falls back to stable CSS hooks for elements without accessible labels.

The local fixture in ``fixtures/portals/amtrust/`` is markup-compatible.
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
    DEFAULT_NETWORK_IDLE_MS,
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


class AmTrustSubmitter(PlaywrightSubmitter):
    """AmTrust producer-portal automation.

    Fixture URL :env:`PORTAL_AMTRUST_URL` (e.g. ``http://localhost:8101/amtrust/``).
    Credentials :env:`AMTRUST_USERNAME` / :env:`AMTRUST_PASSWORD`
    (fixtures accept ``demo``/``demo``).
    """

    platform = PortalPlatform.AMTRUST
    PLATFORM = PortalPlatform.AMTRUST
    URL_ENV_VAR = "PORTAL_AMTRUST_URL"
    USERNAME_ENV_VAR = "AMTRUST_USERNAME"
    PASSWORD_ENV_VAR = "AMTRUST_PASSWORD"  # noqa: S105
    PORTAL_REFERENCE_PREFIX = "AMT"
    SMOKE_PROBE_NEEDLE = "AmTrust"

    REQUIRED_FIELDS = (
        "named_insured",
        "fein",
        "effective_date",
        "premium_cents",
        "line_of_business",
    )

    FIELD_MAP = {
        "named_insured": "Named Insured",
        "fein": "FEIN",
        "producer_code": "Producer Code",
        "effective_date": "Effective Date",
        "line_of_business": "Line of Business",
        "premium": "Annual Premium",
        "state": "Risk State",
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
                user_message="AmTrust login form did not render.",
                cause=str(exc),
            ) from exc
        page.locator("button[type='submit']").first.click()
        wait_for_network_idle(page, timeout_ms=DEFAULT_NETWORK_IDLE_MS)
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
            ("fein", str(payload.get("fein", ""))),
            ("effective_date", str(payload.get("effective_date", ""))),
            ("line_of_business", str(payload.get("line_of_business", ""))),
            ("premium", premium_dollars),
        ]
        if payload.get("producer_code"):
            fills.append(("producer_code", str(payload["producer_code"])))
        if payload.get("state"):
            fills.append(("state", str(payload["state"])))

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
        metadata = {
            "url": page.url,
            "idempotency_token": uuid.uuid4().hex,
        }
        return reference, metadata


SUBMITTER_REGISTRY[PortalPlatform.AMTRUST] = AmTrustSubmitter
