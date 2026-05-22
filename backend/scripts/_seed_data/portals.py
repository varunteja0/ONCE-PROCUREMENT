"""Static catalogue of carrier-portal seed rows.

The first five entries mirror the portals that ``tests/conftest.py``
defines so the realistic seed is interchangeable with the test fixture.
The remaining five fill out the long-tail platforms the product claims
support for in marketing copy — they are seeded as ``is_supported=False``
so dashboards make the "coming soon" gap visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.models import PortalPlatform


@dataclass(frozen=True, slots=True)
class PortalSeed:
    platform: PortalPlatform
    display_name: str
    base_url: str
    is_supported: bool
    risky: bool
    notes: str


PORTAL_SEEDS: Final[tuple[PortalSeed, ...]] = (
    PortalSeed(
        PortalPlatform.APPLIED_EPIC, "Applied Epic",
        "https://epic.example/", True, False,
        "Agency management system — primary integration for retail brokers.",
    ),
    PortalSeed(
        PortalPlatform.AMTRUST, "AmTrust Financial",
        "https://amtrust.example/", True, False,
        "Workers' comp + small-commercial submission portal.",
    ),
    PortalSeed(
        PortalPlatform.MARKEL, "Markel Specialty",
        "https://markel.example/", True, False,
        "Specialty / E&S carrier portal — frequent CAPTCHA challenges.",
    ),
    PortalSeed(
        PortalPlatform.VERTAFORE_AMS360, "Vertafore AMS360",
        "https://ams360.example/", True, False,
        "Agency management system — second-most-common AMS in the book.",
    ),
    PortalSeed(
        PortalPlatform.VERTAFORE_SIRCON, "Vertafore Sircon",
        "https://sircon.example/", True, False,
        "Producer licensing & appointments hub.",
    ),
    PortalSeed(
        PortalPlatform.NATIONWIDE_ES, "Nationwide E&S",
        "https://nationwide-es.example/", False, True,
        "Excess & surplus lines — TOS restricts automation, gated by flag.",
    ),
    PortalSeed(
        PortalPlatform.CNA, "CNA",
        "https://cna.example/", False, False,
        "Top-10 US commercial carrier portal — integration in progress.",
    ),
    PortalSeed(
        PortalPlatform.GUIDEWIRE, "Guidewire PolicyCenter",
        "https://guidewire.example/", False, False,
        "Carrier core-system integration — multi-tenant deployments.",
    ),
    PortalSeed(
        PortalPlatform.HAWKSOFT, "HawkSoft",
        "https://hawksoft.example/", False, False,
        "Mid-market agency management system.",
    ),
    PortalSeed(
        PortalPlatform.EZLYNX, "EZLynx",
        "https://ezlynx.example/", False, False,
        "Comparative rater + AMS used by personal-lines-heavy agencies.",
    ),
)


__all__ = ["PortalSeed", "PORTAL_SEEDS"]
