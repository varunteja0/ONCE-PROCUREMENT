"""Deterministic data generators for the realistic seed.

A single :class:`random.Random` instance is threaded through every helper so
the entire seed is reproducible from one ``SEED_SECRET`` integer. We avoid
the ``faker`` library on purpose — adding it would balloon dependencies for
a one-shot script when 50 names can trivially be composed from the static
word lists in :mod:`._seed_data.companies`.

The helpers are all *pure* (no DB, no clock, no env): they take inputs and
return dicts of values the orchestrator turns into ORM objects. That makes
them trivial to unit-test and keeps the seed deterministic across CPython
versions because we never touch ``hash()`` or set iteration order.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from random import Random
from typing import Any

from app.utils.canonical_json import canonical_json_bytes, payload_sha256

from . import SEED_MARKER
from .coi_templates import (
    ACORD_FORM_TYPES,
    CARRIER_NAMES,
    COVERAGE_TYPES,
    LICENSE_STATES,
    LIMIT_BUCKETS,
    LINES_OF_AUTHORITY,
    LINES_OF_BUSINESS,
)
from .companies import (
    CITY_STATE_ZIP,
    CONTACT_FIRST_NAMES,
    CONTACT_LAST_NAMES,
    CORP_SUFFIXES,
    NAICS_CODES,
    NAME_CORES,
    NAME_PREFIXES,
)

__all__ = [
    "DeterministicIds",
    "SEED_MARKER",
    "business_day_datetimes",
    "fein",
    "make_supplier",
    "make_consent_signed_text",
    "make_coi",
    "make_license",
    "make_eo",
    "make_acord",
    "make_risk_schedule",
    "make_loss_run",
    "submission_payload",
    "deterministic_signing_seed",
    "phone",
    "email_for",
    "us_holidays",
]


# ---------------------------------------------------------------------------
# Identifier helpers
# ---------------------------------------------------------------------------


_NAMESPACE = uuid.UUID("4f6f1fa6-7c2d-5b8a-9c8e-7e9c9b6e6a01")


@dataclass(frozen=True, slots=True)
class DeterministicIds:
    """Factory for stable UUIDs derived from ``(marker, kind, ordinal)``.

    Using uuid5 makes the same SEED_SECRET + same kind/ordinal always
    produce the same UUID, which is what enables INSERT-OR-IGNORE
    idempotency without an external ID-tracking table.
    """

    marker: str = SEED_MARKER

    def of(self, kind: str, ordinal: int | str) -> str:
        return str(
            uuid.uuid5(
                _NAMESPACE,
                f"{self.marker}|{kind}|{ordinal}",
            )
        )


# ---------------------------------------------------------------------------
# Deterministic Ed25519 seed
# ---------------------------------------------------------------------------


def deterministic_signing_seed(seed_secret: int) -> bytes:
    """Return a stable 32-byte Ed25519 seed derived from ``seed_secret``.

    We hash a marker-prefixed string so callers can rotate ``SEED_MARKER``
    without colliding with previously-generated keys.
    """

    raw = f"{SEED_MARKER}|signing|{seed_secret}".encode()
    return hashlib.sha256(raw).digest()


# ---------------------------------------------------------------------------
# Tiny domain helpers
# ---------------------------------------------------------------------------


def fein(rng: Random) -> str:
    """Return a ``99-XXXXXXX`` FEIN string.

    The ``99-`` prefix is reserved by the IRS for assignment but currently
    unused for production FEINs, which makes it the safest "obviously
    demo" range we can use without ever colliding with a real one.
    """

    return f"99-{rng.randint(1000000, 9999999)}"


def phone(rng: Random) -> str:
    """Return a ``+1 (555) ABC-DEFG`` phone, always in the 555 exchange."""

    return f"+1 (555) {rng.randint(200, 999)}-{rng.randint(1000, 9999)}"


def email_for(local_part: str) -> str:
    """All seeded emails live on ``@example.com`` per RFC 2606."""

    sanitized = local_part.lower().replace(" ", ".").replace(",", "").replace("&", "and")
    return f"{sanitized}@example.com"


# ---------------------------------------------------------------------------
# US business-day skewed timestamp generator
# ---------------------------------------------------------------------------


def us_holidays(years: Iterable[int]) -> set[date]:
    """Return a static set of federal-holiday dates for the given years.

    We hard-code the rules rather than depend on the ``holidays`` library —
    a 100-line table is cheaper than a dependency. We only need the holidays
    that fall on weekdays, since weekends are already excluded.
    """

    result: set[date] = set()
    for year in years:
        # Fixed-date holidays
        for month, day in ((1, 1), (7, 4), (11, 11), (12, 25)):
            result.add(date(year, month, day))
        # MLK Day — third Monday of January
        result.add(_nth_weekday(year, 1, 0, 3))
        # Presidents' Day — third Monday of February
        result.add(_nth_weekday(year, 2, 0, 3))
        # Memorial Day — last Monday of May
        result.add(_last_weekday(year, 5, 0))
        # Labor Day — first Monday of September
        result.add(_nth_weekday(year, 9, 0, 1))
        # Columbus Day — second Monday of October
        result.add(_nth_weekday(year, 10, 0, 2))
        # Thanksgiving — fourth Thursday of November
        result.add(_nth_weekday(year, 11, 3, 4))
        # Juneteenth (since 2021)
        if year >= 2021:
            result.add(date(year, 6, 19))
    return result


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        d = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        d = date(year, month + 1, 1) - timedelta(days=1)
    offset = (d.weekday() - weekday) % 7
    return d - timedelta(days=offset)


def business_day_datetimes(
    rng: Random, *, count: int, days: int, now: datetime
) -> list[datetime]:
    """Generate ``count`` UTC timestamps skewed toward recent business days.

    * Weekends and US federal holidays are excluded.
    * Times of day are uniformly distributed across 8:00–18:00 US Eastern
      (treated as UTC-5 — DST handling would be overkill for demo data).
    * Recent days are 3× more likely than days at the back of the window
      so the dashboard "ramps up" toward today like a live customer's
      activity would.
    """

    if count <= 0 or days <= 0:
        return []

    eligible: list[date] = []
    today = now.date()
    holidays = us_holidays(range(today.year - 1, today.year + 1))
    for offset in range(days):
        d = today - timedelta(days=offset)
        if d.weekday() >= 5 or d in holidays:
            continue
        eligible.append(d)

    if not eligible:
        return []

    # Recency weighting: index 0 is most recent → highest weight.
    weights = [max(1, days - i * 2 // 3) for i in range(len(eligible))]

    out: list[datetime] = []
    for _ in range(count):
        chosen_day = rng.choices(eligible, weights=weights, k=1)[0]
        hour = rng.randint(8, 17)
        minute = rng.randint(0, 59)
        second = rng.randint(0, 59)
        # Treat 8-18 ET as UTC-5 → add 5 hours to get UTC.
        eastern_naive = datetime.combine(chosen_day, time(hour, minute, second))
        out.append((eastern_naive + timedelta(hours=5)).replace(tzinfo=UTC))

    out.sort()
    return out


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------


def _legal_name(rng: Random, ordinal: int) -> str:
    prefix = NAME_PREFIXES[ordinal % len(NAME_PREFIXES)]
    core = NAME_CORES[(ordinal * 7 + 3) % len(NAME_CORES)]
    suffix = CORP_SUFFIXES[(ordinal * 11 + 5) % len(CORP_SUFFIXES)]
    return f"{prefix} {core} {suffix}"


def make_supplier(rng: Random, *, ordinal: int, size_bucket: str) -> dict[str, Any]:
    """Return kwargs for one ``Supplier`` row."""

    name = _legal_name(rng, ordinal)
    city, state, zip_code = CITY_STATE_ZIP[ordinal % len(CITY_STATE_ZIP)]
    contact_first = CONTACT_FIRST_NAMES[(ordinal * 3) % len(CONTACT_FIRST_NAMES)]
    contact_last = CONTACT_LAST_NAMES[(ordinal * 5) % len(CONTACT_LAST_NAMES)]
    contact = f"{contact_first} {contact_last}"

    return {
        "legal_name": name,
        "dba_name": None if ordinal % 4 else name.split(",")[0],
        "ein": fein(rng),
        "naics_code": NAICS_CODES[ordinal % len(NAICS_CODES)],
        "primary_email": email_for(f"{contact_first}.{contact_last}.{ordinal}"),
        "primary_phone": phone(rng),
        "website": f"https://{name.split()[0].lower()}-{ordinal}.example.com",
        "address_json": {
            "_seed_marker": SEED_MARKER,
            "size_bucket": size_bucket,
            "primary_contact": contact,
            "street": f"{rng.randint(100, 9999)} Demo Way",
            "suite": f"Suite {rng.randint(100, 999)}" if ordinal % 3 == 0 else None,
            "city": city,
            "state": state,
            "postal_code": zip_code,
            "country": "US",
        },
    }


# ---------------------------------------------------------------------------
# Compliance documents
# ---------------------------------------------------------------------------


def make_consent_signed_text(
    *, supplier_name: str, granted_at: datetime, portal_names: list[str]
) -> str:
    """Render the canonical signed-text body for a ConsentRecord row."""

    portals = ", ".join(portal_names) if portal_names else "all carrier portals"
    return (
        f"[seed:{SEED_MARKER}] {supplier_name} authorizes Once Procurement "
        f"to submit insurance and licensing applications on its behalf via "
        f"{portals}, effective {granted_at.isoformat()}. Consent may be "
        f"revoked in writing at any time."
    )


def make_coi(
    rng: Random,
    *,
    supplier_id: str,
    today: date,
    bucket: str,
) -> dict[str, Any]:
    """Return kwargs for one Certificate-of-Insurance row.

    ``bucket`` selects the expiry distribution:

    * ``"expiring_soon"`` — within the next 30 days (drives renewal demo).
    * ``"expired"`` — already lapsed (drives the "alert" demo).
    * ``"active"`` — comfortably in-force (the boring majority).
    """

    each_occ, aggregate = rng.choice(LIMIT_BUCKETS)
    coverage = rng.choice(COVERAGE_TYPES)
    carrier = rng.choice(CARRIER_NAMES)

    if bucket == "expiring_soon":
        days_to_expiry = rng.randint(2, 29)
    elif bucket == "expired":
        days_to_expiry = -rng.randint(5, 90)
    else:
        days_to_expiry = rng.randint(60, 330)

    expiry = today + timedelta(days=days_to_expiry)
    effective = expiry - timedelta(days=365)

    return {
        "supplier_id": supplier_id,
        "carrier_name": carrier,
        "policy_number": f"POL-{rng.randint(100_000, 999_999)}-{coverage[:3].upper()}",
        "coverage_type": coverage,
        "limit_each_occurrence": Decimal(str(each_occ)),
        "limit_aggregate": Decimal(str(aggregate)),
        "effective_date": effective,
        "expiry_date": expiry,
        "file_url": f"https://files.example.com/coi/{SEED_MARKER}/{rng.randrange(1 << 31):08x}.pdf",
    }


def make_license(
    rng: Random,
    *,
    supplier_id: str,
    supplier_name: str,
    state: str,
    today: date,
) -> dict[str, Any]:
    effective = today - timedelta(days=rng.randint(60, 720))
    expiration = effective + timedelta(days=rng.choice([365, 730]))
    lines = rng.sample(LINES_OF_AUTHORITY, k=rng.randint(2, 4))

    return {
        "supplier_id": supplier_id,
        "state": state,
        "license_number": f"{state}-{rng.randint(100_000, 999_999)}",
        "license_type": rng.choice([
            "resident_producer", "non_resident_producer",
            "surplus_lines", "mga", "wholesaler",
        ]),
        "licensee_name": supplier_name,
        "npn": str(rng.randint(10_000_000, 99_999_999)),
        "effective_date": effective,
        "expiration_date": expiration,
        "lines_authorized": lines,
        "status": "active" if expiration > today else "expired",
        "metadata_json": {"_seed_marker": SEED_MARKER},
    }


def make_eo(rng: Random, *, supplier_id: str, supplier_name: str, today: date) -> dict[str, Any]:
    effective = today - timedelta(days=rng.randint(60, 330))
    expiration = effective + timedelta(days=365)
    coverage_dollars = rng.choice([1_000_000, 2_000_000, 5_000_000])

    return {
        "supplier_id": supplier_id,
        "carrier_name": rng.choice(CARRIER_NAMES),
        "policy_number": f"EO-{rng.randint(100_000, 999_999)}",
        "coverage_amount_cents": coverage_dollars * 100,
        "aggregate_amount_cents": coverage_dollars * 200,
        "deductible_cents": rng.choice([10_000, 25_000, 50_000]) * 100,
        "effective_date": effective,
        "expiration_date": expiration,
        "named_insured": supplier_name,
        "additional_insureds": None,
        "status": "active",
        "metadata_json": {"_seed_marker": SEED_MARKER},
    }


def make_acord(
    rng: Random, *, supplier_id: str, supplier_name: str, today: date
) -> dict[str, Any]:
    form_type = rng.choice(ACORD_FORM_TYPES)
    payload = {
        "applicant_name": supplier_name,
        "form_type": form_type,
        "fein": fein(rng),
        "effective_date": (today - timedelta(days=rng.randint(1, 90))).isoformat(),
        "premium_estimate": rng.randint(5_000, 250_000),
        "_seed_marker": SEED_MARKER,
    }
    digest = payload_sha256(payload)

    return {
        "supplier_id": supplier_id,
        "form_type": form_type,
        "form_version": "2016/03",
        "payload": payload,
        "payload_hash": digest,
        "effective_date": today - timedelta(days=rng.randint(1, 90)),
        "expiration_date": today + timedelta(days=rng.randint(180, 540)),
        "status": rng.choice(["draft", "finalized", "submitted"]),
        "metadata_json": {"_seed_marker": SEED_MARKER},
    }


def make_risk_schedule(
    rng: Random, *, supplier_id: str, today: date
) -> dict[str, Any]:
    lob = rng.choice(LINES_OF_BUSINESS)
    if lob == "commercial_auto":
        schedule_type = "vehicle_schedule"
        items = [
            {
                "vin": f"1FUJ{rng.randint(10**11, 10**12 - 1)}",
                "year": rng.randint(2018, 2024),
                "make": rng.choice(["Freightliner", "Peterbilt", "Kenworth", "Volvo"]),
                "model": rng.choice(["Cascadia", "579", "T680", "VNL"]),
                "garaging_zip": rng.choice([z for _, _, z in CITY_STATE_ZIP]),
                "value_cents": rng.randint(80_000, 180_000) * 100,
            }
            for _ in range(rng.randint(3, 12))
        ]
    elif lob == "workers_comp":
        schedule_type = "employee_schedule"
        items = [
            {
                "class_code": rng.choice(["7219", "8742", "8810", "5403"]),
                "state": rng.choice(LICENSE_STATES),
                "headcount": rng.randint(1, 25),
                "payroll_cents": rng.randint(40_000, 120_000) * 100,
            }
            for _ in range(rng.randint(1, 5))
        ]
    else:
        schedule_type = "location_schedule"
        city, state, zip_code = rng.choice(CITY_STATE_ZIP)
        items = [
            {
                "street": f"{rng.randint(100, 9999)} Demo Way",
                "city": city,
                "state": state,
                "postal_code": zip_code,
                "building_value_cents": rng.randint(500_000, 3_000_000) * 100,
                "construction_class": rng.choice(["Frame", "Joisted Masonry", "Non-Combustible"]),
            }
            for _ in range(rng.randint(1, 4))
        ]

    total = sum(it.get("value_cents") or it.get("building_value_cents") or it.get("payroll_cents", 0) for it in items)
    items_hash = hashlib.sha256(canonical_json_bytes(items)).hexdigest()

    return {
        "supplier_id": supplier_id,
        "line_of_business": lob,
        "schedule_type": schedule_type,
        "effective_date": today - timedelta(days=rng.randint(1, 60)),
        "expiration_date": today + timedelta(days=rng.randint(180, 365)),
        "total_value_cents": total or None,
        "item_count": len(items),
        "items": items,
        "items_hash": items_hash,
        "metadata_json": {"_seed_marker": SEED_MARKER},
    }


def make_loss_run(rng: Random, *, supplier_id: str, today: date) -> dict[str, Any]:
    period_end = today - timedelta(days=rng.randint(1, 365 * 3))
    period_start = period_end - timedelta(days=365)
    lob = rng.choice(LINES_OF_BUSINESS)
    premium = rng.randint(20_000, 350_000) * 100
    paid = int(premium * rng.uniform(0.05, 0.6))
    incurred = paid + rng.randint(0, paid)

    return {
        "supplier_id": supplier_id,
        "period_start": period_start,
        "period_end": period_end,
        "carrier_name": rng.choice(CARRIER_NAMES),
        "line_of_business": lob,
        "total_premium_cents": premium,
        "total_incurred_cents": incurred,
        "total_paid_cents": paid,
        "claim_count": rng.randint(0, 12),
        "status": "parsed",
        "parsed_at": datetime.combine(period_end, time(9, 0), tzinfo=UTC),
        "metadata_json": {"_seed_marker": SEED_MARKER},
    }


# ---------------------------------------------------------------------------
# Submission payloads (sized to look real, hashable to feed receipts)
# ---------------------------------------------------------------------------


def submission_payload(
    rng: Random,
    *,
    supplier_name: str,
    portal: str,
    submitted_at: datetime,
) -> dict[str, Any]:
    return {
        "_seed_marker": SEED_MARKER,
        "supplier_name": supplier_name,
        "portal": portal,
        "submitted_at": submitted_at.isoformat(),
        "fields": {
            "fein": fein(rng),
            "policy_effective_date": submitted_at.date().isoformat(),
            "coverage_limit_dollars": rng.choice([500_000, 1_000_000, 2_000_000, 5_000_000]),
            "premium_estimate_dollars": rng.randint(5_000, 250_000),
            "primary_contact_email": email_for(supplier_name.split()[0] + "." + str(rng.randint(100, 999))),
        },
    }
