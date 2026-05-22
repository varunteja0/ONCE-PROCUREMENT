from __future__ import annotations

from typing import Any

__all__ = [
    "OnceError",
    "SubmissionNotClaimable",
    "SubmitterNotFound",
    "PortalUnsupported",
    "ConsentMissing",
    "PortalAuthRequired",
    "PortalCaptcha",
    "PortalRateLimited",
    "PortalTransientError",
    "PortalPermanentError",
]


class OnceError(Exception):
    """Base class for all Once domain errors.

    Carries a human-readable ``message`` plus an arbitrary structured
    ``context`` dict suitable for inclusion in structured log records and
    audit trails. Subclasses do not add new fields; they only categorize.
    """

    def __init__(self, message: str, /, **context: Any) -> None:
        super().__init__(message)
        self.message: str = message
        self.context: dict[str, Any] = dict(context)

    def __str__(self) -> str:  # pragma: no cover - trivial
        if not self.context:
            return self.message
        ctx = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
        return f"{self.message} [{ctx}]"

    def to_dict(self) -> dict[str, Any]:
        """Serializable representation for logs / API error payloads."""

        return {
            "error": type(self).__name__,
            "message": self.message,
            "context": dict(self.context),
        }


class SubmissionNotClaimable(OnceError):
    """The submission row could not be atomically claimed for processing.

    Raised when the ``UPDATE ... WHERE status IN ('queued', 'retrying')``
    affected zero rows — meaning another worker already claimed it, it has
    already completed, or it was canceled.
    """


class SubmitterNotFound(OnceError):
    """No automation submitter is registered for the target portal platform."""


class PortalUnsupported(OnceError):
    """The portal is recognized but explicitly not supported for submission."""


class ConsentMissing(OnceError):
    """No valid consent record covers this (supplier, portal, scope) tuple."""


class PortalAuthRequired(OnceError):
    """The portal session is unauthenticated or credentials are missing/expired."""


class PortalCaptcha(OnceError):
    """The portal challenged the bot with a captcha — human intervention required."""


class PortalRateLimited(OnceError):
    """The portal rate-limited us; retry with backoff."""


class PortalTransientError(OnceError):
    """Transient portal/network failure; retry with backoff."""


class PortalPermanentError(OnceError):
    """Permanent portal failure (validation rejected, account closed, etc.)."""
