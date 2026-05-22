from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from app.models.consent import ConsentRecord
from app.models.portal import Portal, PortalPlatform
from app.models.supplier import Supplier
from app.utils.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from playwright.sync_api import Browser, BrowserContext, Page

T = TypeVar("T")

_logger = get_logger(__name__)


@dataclass
class SubmitterOutcome:
    """Result of a single portal submission attempt."""

    success: bool
    portal_reference: str | None
    result_payload: dict[str, Any] = field(default_factory=dict)
    screenshot_url: str | None = None


class BaseSubmitter(ABC):
    """Abstract base for portal submitters.

    Concrete subclasses set ``platform`` and implement :meth:`submit`.
    Sync Playwright code should be bridged via :meth:`_run_sync` which wraps
    ``asyncio.to_thread`` so that the async pipeline never blocks the loop.
    """

    platform: PortalPlatform

    def __init__(
        self,
        supplier: Supplier,
        portal: Portal,
        payload: dict[str, Any],
        consent: ConsentRecord | None = None,
    ) -> None:
        self.supplier = supplier
        self.portal = portal
        self.payload = payload
        self.consent = consent

    @abstractmethod
    async def submit(self) -> SubmitterOutcome:
        """Execute the submission and return an outcome."""

    async def _run_sync(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Bridge sync Playwright (or other blocking) calls into async land."""
        return await asyncio.to_thread(fn, *args, **kwargs)

    async def _smoke_test(self) -> bool:
        """Lightweight reachability check. Subclasses may override."""
        return True


# ---------------------------------------------------------------------------
# PlaywrightSubmitter — production-grade base for real portal automation
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _BrowserBundle:
    """Holds the live Playwright objects for one submission attempt."""

    playwright: Any
    browser: Browser
    context: BrowserContext
    page: Page


class PlaywrightSubmitter(BaseSubmitter):
    """Production base for portal submitters that drive Chromium via Playwright.

    The pipeline (see ``app/services/submission_pipeline.py``) invokes the
    submitter as a *class*::

        outcome = await SubmitterClass.submit(
            supplier=..., portal=..., payload=..., consent=...,
        )

    so :meth:`submit` is a ``@classmethod`` here. It is also instance-callable
    via :meth:`run` for backwards-compatibility with the original
    :class:`BaseSubmitter` shape.

    Concrete subclasses override:

    * :attr:`PLATFORM` (and the legacy :attr:`platform`)
    * :attr:`REQUIRED_FIELDS` — payload keys validated before any browser work.
    * :attr:`FIELD_MAP` — canonical-key → portal-label/selector.
    * :attr:`PORTAL_REFERENCE_PREFIX` — e.g. ``"AMT"``.
    * :meth:`_login`, :meth:`_navigate_to_new_submission`,
      :meth:`_fill_form`, :meth:`_attach_files`, :meth:`_submit_and_capture`.

    Behavioural knobs:

    * ``NAV_TIMEOUT_MS`` / ``ACTION_TIMEOUT_MS`` — per-portal overrides.
    * ``PLAYWRIGHT_HEADLESS`` env (default ``true``) — set ``false`` to debug.
    """

    PLATFORM: ClassVar[PortalPlatform]
    REQUIRED_FIELDS: ClassVar[tuple[str, ...]] = ()
    FIELD_MAP: ClassVar[dict[str, str]] = {}
    PORTAL_REFERENCE_PREFIX: ClassVar[str] = "PRT"
    NAV_TIMEOUT_MS: ClassVar[int] = 30_000
    ACTION_TIMEOUT_MS: ClassVar[int] = 10_000

    # The URL/credential env-var names. Subclasses MUST set these.
    URL_ENV_VAR: ClassVar[str]
    USERNAME_ENV_VAR: ClassVar[str]
    PASSWORD_ENV_VAR: ClassVar[str]

    # Phase 4 — 15-min smoke-test probe. The reachability check downloads the
    # login page and asserts ``SMOKE_PROBE_NEEDLE`` (case-insensitive) appears
    # in the body. Set to a string only the carrier's real page would render.
    SMOKE_PROBE_NEEDLE: ClassVar[str] = ""
    SMOKE_PROBE_TIMEOUT_SEC: ClassVar[float] = 5.0

    # ------------------------------------------------------------------ submit
    @classmethod
    async def submit(  # type: ignore[override]
        cls,
        *,
        supplier: Supplier,
        portal: Portal,
        payload: dict[str, Any],
        consent: ConsentRecord | None,
    ) -> SubmitterOutcome:
        """Pipeline-facing entry point. Bridges sync Playwright via a thread."""

        instance = cls(supplier=supplier, portal=portal, payload=payload, consent=consent)
        return await asyncio.to_thread(instance._run_sync_pipeline)

    # Convenience instance form for tests / scripts that prefer an instance.
    async def run(self) -> SubmitterOutcome:
        return await asyncio.to_thread(self._run_sync_pipeline)

    # ----------------------------------------------------------- orchestration
    def _run_sync_pipeline(self) -> SubmitterOutcome:
        from app.services.exceptions import OnceError

        from ._playwright_helpers import require_fields
        from .errors import (
            PortalTimeoutError,
        )
        from .screenshot_store import get_default_store

        cls = type(self)
        log = _logger.bind(
            portal=cls.PLATFORM.value,
            supplier_id=getattr(self.supplier, "id", None),
            portal_id=getattr(self.portal, "id", None),
        )
        log.info("submitter.start")

        # Cheap, browser-free validation first.
        require_fields(self.payload, cls.REQUIRED_FIELDS)

        url = self._resolve_url()
        username, password = self._resolve_credentials()

        store = get_default_store()
        tenant_id = getattr(self.supplier, "tenant_id", "unknown-tenant")
        submission_id = self.payload.get("submission_id") or "ad-hoc"

        bundle: _BrowserBundle | None = None
        screenshot_path: str | None = None
        try:
            bundle = self._launch_browser()
            self._configure_timeouts(bundle.page)
            self._login(bundle.page, url=url, username=username, password=password)
            log.info("submitter.login_success")
            self._navigate_to_new_submission(bundle.page, base_url=url)
            self._fill_form(bundle.page, self.payload)
            log.info("submitter.form_filled")
            self._attach_files(bundle.page, self.payload)
            reference, metadata = self._submit_and_capture(bundle.page)
            log.info("submitter.confirmation_captured", reference=reference)

            screenshot_path = self._capture_screenshot(
                store,
                bundle.page,
                tenant_id=tenant_id,
                submission_id=str(submission_id),
                label="confirmation",
            )

            return SubmitterOutcome(
                success=True,
                portal_reference=reference,
                screenshot_url=screenshot_path,
                result_payload={
                    "submission_reference": reference,
                    "screenshot_path": screenshot_path,
                    "completed_at": datetime.now(UTC).isoformat(),
                    "portal_metadata": metadata,
                    "portal": cls.PLATFORM.value,
                },
            )
        except OnceError as exc:
            # Already typed — capture screenshot, log, and re-raise.
            if bundle is not None:
                screenshot_path = self._safe_capture_screenshot(
                    store, bundle.page, tenant_id, str(submission_id), label="failure"
                )
            log.warning(
                "submitter.failure",
                error_type=type(exc).__name__,
                error=str(exc),
                screenshot=screenshot_path,
            )
            raise
        except Exception as exc:  # noqa: BLE001 - wrap-and-reraise as typed
            if bundle is not None:
                screenshot_path = self._safe_capture_screenshot(
                    store, bundle.page, tenant_id, str(submission_id), label="unhandled"
                )
            log.exception(
                "submitter.unhandled_failure",
                error_type=type(exc).__name__,
                screenshot=screenshot_path,
            )
            # Map Playwright timeouts to typed errors when possible.
            module = type(exc).__module__
            name = type(exc).__name__
            if "playwright" in module and "Timeout" in name:
                raise PortalTimeoutError(
                    "playwright_timeout",
                    cause=str(exc),
                ) from exc
            from .errors import PortalNetworkError

            raise PortalNetworkError(
                "unhandled_playwright_error",
                cause=str(exc),
                error_type=name,
            ) from exc
        finally:
            if bundle is not None:
                self._teardown_browser(bundle)

    # ------------------------------------------------------------- subclass API
    def _login(
        self, page: Page, *, url: str, username: str, password: str
    ) -> None:
        raise NotImplementedError

    def _navigate_to_new_submission(self, page: Page, *, base_url: str) -> None:
        raise NotImplementedError

    def _fill_form(self, page: Page, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    def _attach_files(self, page: Page, payload: dict[str, Any]) -> None:
        """Default: no attachments. Subclasses with upload widgets override."""

    def _submit_and_capture(self, page: Page) -> tuple[str, dict[str, Any]]:
        """Return (submission_reference, portal_metadata). Subclass must impl."""

        raise NotImplementedError

    # ------------------------------------------------------------- internals
    def _resolve_url(self) -> str:
        cls = type(self)
        portal_url = getattr(self.portal, "submission_url", None) or getattr(
            self.portal, "base_url", None
        )
        env_url = os.environ.get(cls.URL_ENV_VAR)
        url = env_url or portal_url
        if not url:
            from .errors import PortalValidationError

            raise PortalValidationError(
                "portal_url_not_configured",
                env_var=cls.URL_ENV_VAR,
            )
        return url

    def _resolve_credentials(self) -> tuple[str, str]:
        cls = type(self)
        username = os.environ.get(cls.USERNAME_ENV_VAR, "")
        password = os.environ.get(cls.PASSWORD_ENV_VAR, "")
        if not username or not password:
            from .errors import PortalAuthError

            raise PortalAuthError(
                "credentials_not_configured",
                user_message=(
                    f"Set {cls.USERNAME_ENV_VAR} and {cls.PASSWORD_ENV_VAR} "
                    "in the environment."
                ),
                username_env=cls.USERNAME_ENV_VAR,
                password_env=cls.PASSWORD_ENV_VAR,
            )
        return username, password

    def _launch_browser(self) -> _BrowserBundle:
        from playwright.sync_api import sync_playwright

        headless_env = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower()
        headless = headless_env not in ("0", "false", "no")
        pw = sync_playwright().start()
        try:
            browser = pw.chromium.launch(
                headless=headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                accept_downloads=False,
                ignore_https_errors=True,
            )
            page = context.new_page()
        except Exception:
            pw.stop()
            raise
        return _BrowserBundle(playwright=pw, browser=browser, context=context, page=page)

    def _configure_timeouts(self, page: Page) -> None:
        cls = type(self)
        page.set_default_navigation_timeout(cls.NAV_TIMEOUT_MS)
        page.set_default_timeout(cls.ACTION_TIMEOUT_MS)

    def _teardown_browser(self, bundle: _BrowserBundle) -> None:
        for closer in (bundle.context.close, bundle.browser.close, bundle.playwright.stop):
            try:
                closer()
            except Exception:  # pragma: no cover - best-effort teardown
                _logger.debug("submitter.teardown_swallowed", call=closer.__name__)

    def _capture_screenshot(
        self,
        store: Any,
        page: Page,
        *,
        tenant_id: str,
        submission_id: str,
        label: str,
    ) -> str:
        png = page.screenshot(full_page=True)
        return store.save(
            tenant_id=tenant_id,
            submission_id=submission_id,
            label=label,
            data=png,
        )

    def _safe_capture_screenshot(
        self,
        store: Any,
        page: Page,
        tenant_id: str,
        submission_id: str,
        *,
        label: str,
    ) -> str | None:
        try:
            return self._capture_screenshot(
                store,
                page,
                tenant_id=tenant_id,
                submission_id=submission_id,
                label=label,
            )
        except Exception:  # pragma: no cover - capture must never mask root cause
            _logger.debug("submitter.screenshot_capture_failed", label=label)
            return None

    # Maintain a sane default for `platform` (the abstract field on BaseSubmitter).
    @property
    def platform_value(self) -> str:
        return type(self).PLATFORM.value

    # ----------------------------------------------------- smoke-test (Phase 4)
    async def _smoke_test(self) -> bool:  # type: ignore[override]
        """15-minute reachability probe used by ``smoke_test.run_all``.

        HTTP-only: deliberately does NOT launch Playwright (keeps the beat
        task cheap and parallel-safe) and does NOT call
        :meth:`_resolve_credentials` (smoke must work in CI without secrets).
        All failure modes — URL not configured, DNS error, timeout, 5xx,
        needle-missing — collapse to ``False`` so the beat task can dispatch
        a Slack drift alert.
        """

        import httpx

        cls = type(self)
        try:
            url = self._resolve_url()
        except Exception as exc:  # noqa: BLE001 - never raise from smoke
            _logger.warning(
                "submitter.smoke_probe_url_unresolved",
                portal=cls.PLATFORM.value,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return False

        try:
            resp = await asyncio.to_thread(
                httpx.get,
                url,
                timeout=cls.SMOKE_PROBE_TIMEOUT_SEC,
                follow_redirects=True,
            )
        except Exception as exc:  # noqa: BLE001 - DNS / connect / timeout
            _logger.warning(
                "submitter.smoke_probe_request_failed",
                portal=cls.PLATFORM.value,
                url=url,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return False

        if not (200 <= resp.status_code < 400):
            _logger.warning(
                "submitter.smoke_probe_bad_status",
                portal=cls.PLATFORM.value,
                url=url,
                status_code=resp.status_code,
            )
            return False

        needle = cls.SMOKE_PROBE_NEEDLE
        if needle and needle.lower() not in (resp.text or "").lower():
            _logger.warning(
                "submitter.smoke_probe_needle_missing",
                portal=cls.PLATFORM.value,
                url=url,
                needle=needle,
            )
            return False

        return True
