"""Shared Playwright primitives used by every portal submitter.

Mirrors the React-tracked-input setter trick from
``extension/src/content/fillers/_shared.ts`` so headless Playwright drives
React-controlled inputs (most carrier portals) the same way the browser
extension does.

All helpers are synchronous — the submitters run inside Celery worker threads
and bridge to the async pipeline via :func:`asyncio.to_thread`.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from app.utils.logging import get_logger

from .errors import (
    PortalAuthError,
    PortalCaptchaError,
    PortalNetworkError,
    PortalSelectorDriftError,
    PortalTimeoutError,
)

if TYPE_CHECKING:  # pragma: no cover - import only for type-checkers
    from playwright.sync_api import Locator, Page

_logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_NETWORK_IDLE_MS: int = 1_500
DEFAULT_ACTION_TIMEOUT_MS: int = 10_000
DEFAULT_NAV_TIMEOUT_MS: int = 30_000

CAPTCHA_HOST_FRAGMENTS: tuple[str, ...] = (
    "recaptcha",
    "hcaptcha",
    "challenges.cloudflare.com",  # Turnstile
)
CAPTCHA_DOM_SELECTORS: tuple[str, ...] = (
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "iframe[src*='challenges.cloudflare.com']",
    "div.g-recaptcha",
    "div.h-captcha",
    "div.cf-turnstile",
    "div[data-sitekey]",
)
AUTH_WALL_PATH_FRAGMENTS: tuple[str, ...] = (
    "/login",
    "/signin",
    "/auth",
    "session-expired",
)

# JS expression that recovers the original native value setter on
# HTMLInputElement/HTMLTextAreaElement, calls it, then dispatches a bubbling
# `input` + `change` event so React's `onChange` re-runs.
_REACT_SET_VALUE_JS = """
([el, value]) => {
  const tag = el.tagName;
  const proto =
    tag === 'TEXTAREA'
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype;
  const desc = Object.getOwnPropertyDescriptor(proto, 'value');
  const setter = desc && desc.set;
  if (typeof setter === 'function') {
    setter.call(el, value);
  } else {
    el.value = value;
  }
  el.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
  el.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
  return true;
}
"""


# ---------------------------------------------------------------------------
# Selector-drift tracking
# ---------------------------------------------------------------------------


class SelectorDriftTracker:
    """Counts consecutive selector misses; trips after ``threshold`` misses."""

    def __init__(self, threshold: int = 1) -> None:
        self.threshold: int = threshold
        self.misses: dict[str, int] = {}

    def record_hit(self, selector: str) -> None:
        self.misses.pop(selector, None)

    def record_miss(self, selector: str) -> int:
        count = self.misses.get(selector, 0) + 1
        self.misses[selector] = count
        return count

    def should_trip(self, selector: str) -> bool:
        return self.misses.get(selector, 0) >= self.threshold


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def set_react_input(page: Page, selector: str, value: str) -> None:
    """Programmatically set an input's value such that React picks it up.

    Raises :class:`PortalSelectorDriftError` if the selector matches nothing.
    """

    locator = page.locator(selector).first
    if locator.count() == 0:
        raise PortalSelectorDriftError(
            "selector_returned_no_elements",
            selector=selector,
            field="react_input",
        )
    handle = locator.element_handle()
    if handle is None:
        raise PortalSelectorDriftError(
            "selector_returned_no_element_handle",
            selector=selector,
        )
    page.evaluate(_REACT_SET_VALUE_JS, [handle, value])


def fill_by_label(
    page: Page,
    label: str,
    value: str,
    *,
    tracker: SelectorDriftTracker | None = None,
) -> None:
    """Fill the first input/textarea/select associated with ``label``.

    Uses Playwright's accessibility-aware ``get_by_label`` first; falls back to
    a CSS selector matching the `for` attribute. Records hits/misses against the
    optional :class:`SelectorDriftTracker`.
    """

    candidate: Locator | None = None
    try:
        candidate = page.get_by_label(label, exact=False).first
        if candidate.count() == 0:
            candidate = None
    except Exception:  # pragma: no cover - playwright internals vary
        candidate = None

    if candidate is None:
        # Fallback: find <label> with matching text → resolve `for` → query by id.
        label_loc = page.locator(f"label:has-text({label!r})").first
        if label_loc.count() == 0:
            if tracker:
                tracker.record_miss(label)
            raise PortalSelectorDriftError(
                "label_not_found",
                label=label,
            )
        target_id = label_loc.get_attribute("for")
        if not target_id:
            if tracker:
                tracker.record_miss(label)
            raise PortalSelectorDriftError(
                "label_missing_for_attr",
                label=label,
            )
        candidate = page.locator(f"#{target_id}").first

    if tracker:
        tracker.record_hit(label)

    tag = (candidate.evaluate("el => el.tagName") or "").upper()
    if tag == "SELECT":
        candidate.select_option(value=value)
    else:
        # Use the React-aware setter so controlled inputs are committed.
        handle = candidate.element_handle()
        if handle is None:
            raise PortalSelectorDriftError("element_handle_missing", label=label)
        page.evaluate(_REACT_SET_VALUE_JS, [handle, value])


def wait_for_network_idle(
    page: Page, *, timeout_ms: int = DEFAULT_NETWORK_IDLE_MS
) -> None:
    """Wait for network to be idle; convert timeouts to :class:`PortalTimeoutError`."""

    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception as exc:
        raise PortalTimeoutError(
            "network_idle_timeout",
            timeout_ms=timeout_ms,
        ) from exc


def detect_captcha(page: Page) -> None:
    """Scan the live DOM + recent network for a captcha challenge.

    Raises :class:`PortalCaptchaError` (permanent → ``BLOCKED``) on hit.
    """

    for selector in CAPTCHA_DOM_SELECTORS:
        try:
            if page.locator(selector).count() > 0:
                raise PortalCaptchaError(
                    "captcha_detected",
                    selector=selector,
                    url=page.url,
                )
        except PortalCaptchaError:
            raise
        except Exception as exc:  # pragma: no cover - locator may throw on detached frame
            _logger.debug(
                "portal.captcha_selector_probe_failed",
                selector=selector,
                error=str(exc),
            )
            continue

    # Cheap script-src scan as a fallback (covers captchas mounted post-load).
    try:
        srcs: list[str] = page.eval_on_selector_all(
            "script[src]", "els => els.map(e => e.src)"
        )
    except Exception:  # pragma: no cover
        srcs = []
    for src in srcs:
        if any(frag in src for frag in CAPTCHA_HOST_FRAGMENTS):
            raise PortalCaptchaError(
                "captcha_script_loaded",
                script_src=src,
                url=page.url,
            )


def detect_auth_wall(page: Page, *, expected_path_fragment: str | None = None) -> None:
    """Raise :class:`PortalAuthError` if the URL drifted to a login page."""

    url = page.url
    for fragment in AUTH_WALL_PATH_FRAGMENTS:
        if fragment in url:
            raise PortalAuthError(
                "auth_wall_detected",
                url=url,
                fragment=fragment,
            )
    if expected_path_fragment and expected_path_fragment not in url:
        raise PortalAuthError(
            "post_login_url_mismatch",
            url=url,
            expected_fragment=expected_path_fragment,
        )


def expect_response_ok(page: Page, url_fragment: str, *, timeout_ms: int) -> None:
    """Listen for a response containing ``url_fragment`` and ensure 2xx/3xx."""

    try:
        with page.expect_response(
            lambda r: url_fragment in r.url, timeout=timeout_ms
        ) as info:
            pass
        status = info.value.status
    except Exception as exc:
        raise PortalNetworkError(
            "expected_response_not_received",
            url_fragment=url_fragment,
            timeout_ms=timeout_ms,
        ) from exc
    if status >= 400:
        raise PortalNetworkError(
            "non_success_status",
            url_fragment=url_fragment,
            status=status,
        )


def safe_locator_text(
    page: Page,
    selector: str,
    *,
    tracker: SelectorDriftTracker | None = None,
) -> str:
    """Return locator inner text, tripping drift detection on miss."""

    loc = page.locator(selector).first
    if loc.count() == 0:
        if tracker and tracker.should_trip(selector):
            raise PortalSelectorDriftError(
                "selector_drift_trip", selector=selector
            )
        if tracker:
            tracker.record_miss(selector)
        raise PortalSelectorDriftError("selector_returned_nothing", selector=selector)
    if tracker:
        tracker.record_hit(selector)
    return (loc.inner_text() or "").strip()


def require_fields(payload: dict[str, object], required: Iterable[str]) -> None:
    """Raise :class:`PortalValidationError` if any required key is missing/blank."""

    from .errors import PortalValidationError  # local import: avoid cycle

    missing: list[str] = []
    for key in required:
        value = payload.get(key) if isinstance(payload, dict) else None
        if value is None:
            missing.append(key)
            continue
        if isinstance(value, str) and not value.strip():
            missing.append(key)
            continue
        if isinstance(value, list | tuple) and len(value) == 0:
            missing.append(key)
    if missing:
        raise PortalValidationError(
            "missing_required_fields",
            user_message=f"Missing required fields: {', '.join(missing)}",
            missing=missing,
        )
