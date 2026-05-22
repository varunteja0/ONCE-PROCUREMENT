"""Typed portal-error taxonomy used by every Playwright submitter.

The pipeline (``app/services/submission_pipeline.py``) routes failures via the
existing :class:`app.services.exceptions.PortalTransientError` /
:class:`app.services.exceptions.PortalPermanentError` ancestors — see
``_classify_failure``. To preserve that routing while giving operators (and the
frontend) actionable, structured codes, every submitter raises one of the
concrete subclasses below.

Every error carries:

* ``code``      — snake-case stable identifier safe for dashboards/alerts.
* ``user_message`` — operator-facing string (no PII).
* ``details``   — structured dict copied from kwargs at construction time.

The CONTRACTS.md §4 status mapping:

* :class:`PortalCaptchaError` → ``SubmissionStatus.BLOCKED``
* :class:`PortalAuthError`, :class:`PortalValidationError` →
  ``SubmissionStatus.FAILED`` (no retry; permanent).
* :class:`PortalTimeoutError`, :class:`PortalNetworkError`,
  :class:`PortalSelectorDriftError` → ``SubmissionStatus.RETRYING`` until the
  pipeline's ``MAX_ATTEMPTS`` budget is exhausted.
"""

from __future__ import annotations

from typing import Any

from app.services.exceptions import (
    PortalCaptcha,
    PortalPermanentError,
    PortalTransientError,
)

__all__ = [
    "PortalTimeoutError",
    "PortalNetworkError",
    "PortalSelectorDriftError",
    "PortalCaptchaError",
    "PortalAuthError",
    "PortalValidationError",
]


class _PortalErrorMixin:
    """Shared constructor surface for every typed portal error."""

    code: str = "portal_error"

    def __init__(
        self,
        message: str,
        /,
        *,
        code: str | None = None,
        user_message: str | None = None,
        **details: Any,
    ) -> None:
        # Cooperative super().__init__() — the concrete subclass MRO resolves
        # to one of the OnceError ancestors which sets ``message``/``context``.
        super().__init__(message, **details)  # type: ignore[misc]
        if code is not None:
            self.code = code
        self.user_message: str = user_message or message
        self.details: dict[str, Any] = dict(details)

    def to_dict(self) -> dict[str, Any]:  # type: ignore[override]
        base = super().to_dict()  # type: ignore[misc]
        base["code"] = self.code
        base["user_message"] = self.user_message
        base["details"] = dict(self.details)
        return base


# ---------------------------------------------------------------------------
# Transient (retry-eligible) errors
# ---------------------------------------------------------------------------


class PortalTimeoutError(_PortalErrorMixin, PortalTransientError):
    """A Playwright navigation or action exceeded its configured timeout."""

    code = "portal_timeout"


class PortalNetworkError(_PortalErrorMixin, PortalTransientError):
    """A non-2xx network response or DNS/TLS failure surfaced from the browser."""

    code = "portal_network"


class PortalSelectorDriftError(_PortalErrorMixin, PortalTransientError):
    """A selector that previously matched a critical element now returns None.

    Treated as transient because portals occasionally A/B test; the retry budget
    gives an operator time to push a selector update before the submission is
    finalized as ``FAILED``.
    """

    code = "selector_drift"


# ---------------------------------------------------------------------------
# Permanent (no-retry) errors
# ---------------------------------------------------------------------------


class PortalCaptchaError(_PortalErrorMixin, PortalCaptcha):
    """Portal challenged us with reCAPTCHA / hCaptcha / Turnstile."""

    code = "portal_captcha"


class PortalAuthError(_PortalErrorMixin, PortalPermanentError):
    """Credentials rejected or session expired and could not be re-established."""

    code = "portal_auth"


class PortalValidationError(_PortalErrorMixin, PortalPermanentError):
    """Portal rejected the payload (e.g. unknown NAICS, malformed FEIN)."""

    code = "portal_validation"
