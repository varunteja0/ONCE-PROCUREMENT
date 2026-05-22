"""Templates for synthetic Certificate-of-Insurance + adjacent compliance docs.

Each template is a tuple of static fields the seed mixes with deterministic
random choices to produce realistic-looking COIs, E&O certificates, ACORD
forms, producer licenses, risk schedules and loss runs.

Limits are expressed in **dollars** here for readability — the generators
convert to cents (``BigInteger``) before persisting where the schema
requires it.
"""

from __future__ import annotations

from typing import Final

CARRIER_NAMES: Final[tuple[str, ...]] = (
    "Travelers Indemnity Co.",
    "Hartford Casualty Insurance Co.",
    "Liberty Mutual Fire Insurance Co.",
    "Zurich American Insurance Co.",
    "Chubb Indemnity Insurance Co.",
    "CNA Insurance Co.",
    "Nationwide Mutual Insurance Co.",
    "Progressive Commercial Casualty Co.",
    "Great West Casualty Co.",
    "Berkshire Hathaway Specialty Insurance",
    "Markel American Insurance Co.",
    "AmTrust Financial Services",
    "Crum & Forster Indemnity Co.",
    "Sentry Insurance Co.",
    "Old Republic Insurance Co.",
)

COVERAGE_TYPES: Final[tuple[str, ...]] = (
    "commercial_auto", "commercial_auto", "commercial_auto",
    "general_liability", "general_liability",
    "workers_comp", "umbrella", "cargo",
    "physical_damage", "non_trucking_liability",
)

LIMIT_BUCKETS: Final[tuple[tuple[int, int], ...]] = (
    (1_000_000, 2_000_000),
    (1_000_000, 2_000_000),
    (1_000_000, 1_000_000),
    (2_000_000, 4_000_000),
    (5_000_000, 5_000_000),
    (500_000, 1_000_000),
)

LICENSE_STATES: Final[tuple[str, ...]] = (
    "CA", "TX", "FL", "NY", "IL", "GA",
    "PA", "OH", "NC", "MI", "WA", "AZ",
)

LINES_OF_AUTHORITY: Final[tuple[str, ...]] = (
    "Property", "Casualty", "Personal Lines",
    "Surplus Lines", "Life", "Health",
)

ACORD_FORM_TYPES: Final[tuple[str, ...]] = (
    "acord_125", "acord_125",
    "acord_126", "acord_126",
    "acord_127", "acord_127",
    "acord_130", "acord_140",
)

LINES_OF_BUSINESS: Final[tuple[str, ...]] = (
    "commercial_auto", "general_liability", "workers_comp",
    "commercial_property", "inland_marine", "umbrella",
)


__all__ = [
    "CARRIER_NAMES", "COVERAGE_TYPES", "LIMIT_BUCKETS",
    "LICENSE_STATES", "LINES_OF_AUTHORITY",
    "ACORD_FORM_TYPES", "LINES_OF_BUSINESS",
]
