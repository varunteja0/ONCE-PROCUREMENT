from __future__ import annotations

import re
from urllib.parse import urlparse

from app.models.portal import PortalPlatform

_HOST_PATTERNS: tuple[tuple[re.Pattern[str], PortalPlatform], ...] = (
    (re.compile(r"(^|\.)appliedepic\.com$", re.IGNORECASE), PortalPlatform.APPLIED_EPIC),
    (re.compile(r"(^|\.)ams360\.com$", re.IGNORECASE), PortalPlatform.VERTAFORE_AMS360),
    (re.compile(r"(^|\.)sircon\.com$", re.IGNORECASE), PortalPlatform.VERTAFORE_SIRCON),
    (re.compile(r"(^|\.)amtrustfinancial\.com$", re.IGNORECASE), PortalPlatform.AMTRUST),
    (re.compile(r"^producers\.amtrust", re.IGNORECASE), PortalPlatform.AMTRUST),
    (re.compile(r"(^|\.)markelcorp\.com$", re.IGNORECASE), PortalPlatform.MARKEL),
    (re.compile(r"^cnabrokerportal\.cna\.com$", re.IGNORECASE), PortalPlatform.CNA),
)

_URL_PATTERNS: tuple[tuple[re.Pattern[str], PortalPlatform], ...] = (
    (re.compile(r"markel\.com/producers", re.IGNORECASE), PortalPlatform.MARKEL),
    (re.compile(r"nationwide\.com/business", re.IGNORECASE), PortalPlatform.NATIONWIDE_ES),
)


def detect_portal(url: str) -> PortalPlatform | None:
    """Identify the carrier portal platform for ``url`` (host + path based)."""
    if not url:
        return None

    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or "").lower()
    full = f"{host}{parsed.path or ''}"

    if host:
        for pattern, platform in _HOST_PATTERNS:
            if pattern.search(host):
                return platform

    for pattern, platform in _URL_PATTERNS:
        if pattern.search(full):
            return platform

    return None


def is_risky(platform: PortalPlatform | None) -> bool:
    """Return True for portals whose ToS bars third-party automation.

    All currently supported portals are insurance carrier portals where Once
    operates with an authorized agent relationship, so none are flagged risky.
    The gate is preserved so that ``settings.enable_tos_risky_platforms`` can
    short-circuit any future additions without code changes elsewhere.
    """
    return False
