"""Human-readable narratives for failed/blocked submissions and audit log lines.

These give the demo dashboards the texture of a real production system —
the alternative is uniform "error" strings that immediately read as test
data. Every string is short enough to fit in a single table cell.
"""

from __future__ import annotations

from typing import Final

FAILURE_NARRATIVES: Final[dict[str, tuple[str, ...]]] = {
    "captcha": (
        "Portal presented hCaptcha challenge after step 4/7; queued for human approval.",
        "reCAPTCHA v2 image grid triggered on submit — operator needed.",
        "AmTrust shows 'Are you human?' interstitial; bot paused.",
        "Captcha rate-limit window hit after 3 attempts in 10 minutes.",
        "Cloudflare turnstile required — escalated to ops.",
    ),
    "auth_failed": (
        "Stored credentials rejected — likely vault re-key required.",
        "Portal forced password rotation; user must update vault.",
        "MFA SMS challenge issued to producer phone, no operator on call.",
        "Session cookie expired mid-flow and refresh path returned 401.",
        "SAML federation handshake failed: certificate mismatch.",
    ),
    "selector_drift": (
        "Selector `#policyEffectiveDate` disappeared — portal UI updated overnight.",
        "Submit button moved from `.btn-primary` to `[data-action='submit']`.",
        "New 'Confirm carrier' dialog inserted between steps 5 and 6.",
        "Form field `coverage_amount` renamed to `coverage_limit` server-side.",
        "Step 3 of wizard now requires an additional file upload widget.",
    ),
    "timeout": (
        "Page-load timeout (45s) on portal status check.",
        "Submit POST exceeded 60-second window; transaction state unknown.",
        "Backend rate-limited us at 30 req/min — backing off.",
        "Document-upload spinner never resolved after 90s.",
        "Carrier sandbox returned 504 on three consecutive retries.",
    ),
    "network": (
        "DNS resolution failure for portal hostname.",
        "TLS handshake aborted — corporate proxy interfering.",
        "Connection reset by peer mid-upload.",
        "HTTP 502 from carrier edge after Cloudflare maintenance window.",
    ),
}

RUNNING_NARRATIVES: Final[tuple[str, ...]] = (
    "Navigating to portal login page…",
    "Filling supplier contact section (step 2/7)…",
    "Uploading ACORD 125 PDF (2.3 MB)…",
    "Awaiting carrier policy-number response…",
    "Re-attempt #2 after transient 503; backoff 30s.",
)

AUDIT_EVENT_TEMPLATES: Final[tuple[tuple[str, str], ...]] = (
    ("user.login", "{actor} signed in from 198.51.100.42"),
    ("supplier.created", "{actor} added supplier {resource}"),
    ("supplier.updated", "{actor} updated supplier {resource} contact info"),
    ("consent.granted", "{actor} captured submit-on-behalf consent for {resource}"),
    ("submission.queued", "{actor} queued submission {resource}"),
    ("submission.completed", "Pipeline marked submission {resource} completed"),
    ("submission.failed", "Pipeline marked submission {resource} failed"),
    ("receipt.signed", "Receipt {resource} signed with Ed25519 key default-1"),
    ("coi.uploaded", "{actor} uploaded COI {resource}"),
    ("coi.expired", "Monitor flagged COI {resource} as expired"),
    ("license.renewed", "{actor} renewed producer license {resource}"),
    ("vault.unlocked", "{actor} unlocked browser-extension vault"),
)


__all__ = ["FAILURE_NARRATIVES", "RUNNING_NARRATIVES", "AUDIT_EVENT_TEMPLATES"]
