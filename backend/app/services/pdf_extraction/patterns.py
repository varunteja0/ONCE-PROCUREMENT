"""Shared regex + lookup library for the PDF extractors.

All patterns are intentionally permissive — extractors decide which
matches to keep and assign per-field confidence via
:mod:`app.services.pdf_extraction.confidence`. Keeping the regexes
small, named, and documented (positive + negative examples in
``tests/test_patterns.py``) is the core maintainability story for
Phase 3 before we replace heuristics with a Vision LLM in Phase 4.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Final

__all__ = [
    "DATE_RE",
    "MONEY_RE",
    "POLICY_NUMBER_RE",
    "NPN_RE",
    "STATE_CODE_RE",
    "FEIN_RE",
    "NAIC_RE",
    "US_STATES",
    "INSURER_LOOKUP",
    "LINES_OF_AUTHORITY",
    "parse_date",
    "parse_money_cents",
    "normalize_whitespace",
    "find_label_value",
    "find_label_value_below",
    "guess_state_code",
    "match_insurer",
    "match_lines_of_authority",
]


# ---------------------------------------------------------------------------
# Whitespace helper
# ---------------------------------------------------------------------------

_WS_RE: Final = re.compile(r"[ \t]+")
_MULTI_NL_RE: Final = re.compile(r"\n{3,}")


def normalize_whitespace(text: str) -> str:
    """Collapse runs of spaces/tabs and >2 blank lines.

    Preserves single newlines (extractors lean on line-by-line layout).
    """
    text = _WS_RE.sub(" ", text)
    text = _MULTI_NL_RE.sub("\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
#
# Supported formats:
#   - 12/31/2026, 12-31-2026, 12.31.2026
#   - 2026-12-31 (ISO)
#   - December 31, 2026 / Dec 31 2026
#   - 31 December 2026 (European-style — rare on ACORD but seen on E&O)
#
# 2-digit years are accepted in MM/DD/YY form and rolled forward into the
# 2000-2099 window (standard insurance-document convention).

DATE_RE: Final = re.compile(
    r"""(?ix)
    \b(
        # ISO  2026-12-31
        \d{4}-\d{2}-\d{2}
      |
        # MDY  12/31/2026   12/31/26
        \d{1,2}[\/\.\-]\d{1,2}[\/\.\-]\d{2,4}
      |
        # Named month  December 31, 2026   Dec 31 2026
        (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)
        [a-z]{0,7}\.?\s+\d{1,2},?\s+\d{2,4}
      |
        # Day-first  31 December 2026
        \d{1,2}\s+
        (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)
        [a-z]{0,7}\.?\s+\d{2,4}
    )\b
    """
)


_MONTHS: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _expand_two_digit_year(year: int) -> int:
    """ACORD/E&O convention: two-digit years map to 2000-2099."""
    if year < 100:
        return 2000 + year
    return year


def parse_date(raw: str) -> date | None:
    """Parse a date in any of the supported formats. Returns ``None`` if not
    parseable. Never raises."""
    if raw is None:
        return None
    s = raw.strip().rstrip(".,;")
    if not s:
        return None

    # ISO  YYYY-MM-DD
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    # MDY with /, -, .
    m = re.fullmatch(r"(\d{1,2})[\/\.\-](\d{1,2})[\/\.\-](\d{2,4})", s)
    if m:
        mm, dd, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        yy = _expand_two_digit_year(yy)
        try:
            return date(yy, mm, dd)
        except ValueError:
            return None

    # Named month: "December 31, 2026" or "Dec 31 2026"
    m = re.fullmatch(
        r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{2,4})", s
    )
    if m:
        key = m.group(1).lower()
        mon = _MONTHS.get(key[:4]) or _MONTHS.get(key[:3])
        if mon:
            try:
                return date(
                    _expand_two_digit_year(int(m.group(3))),
                    mon,
                    int(m.group(2)),
                )
            except ValueError:
                return None

    # Day-first: "31 December 2026"
    m = re.fullmatch(
        r"(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{2,4})", s
    )
    if m:
        key = m.group(2).lower()
        mon = _MONTHS.get(key[:4]) or _MONTHS.get(key[:3])
        if mon:
            try:
                return date(
                    _expand_two_digit_year(int(m.group(3))),
                    mon,
                    int(m.group(1)),
                )
            except ValueError:
                return None

    return None


# ---------------------------------------------------------------------------
# Money - "$1,000,000", "1000000.00", "1,000,000 USD", "1M", "500K"
# ---------------------------------------------------------------------------

MONEY_RE: Final = re.compile(
    r"""(?ix)
    (?:USD\s*|\$\s*)?
    (
        \d{1,3}(?:,\d{3})+(?:\.\d{1,2})?     #  1,000,000  1,000,000.00
        | \d+(?:\.\d{1,2})?                  #  1000000    1000000.00
    )
    \s*
    (M|MM|K|million|thousand)?
    (?:\s*USD)?
    """
)


_MONEY_SUFFIX_MULTIPLIER: dict[str, int] = {
    "k": 1_000,
    "thousand": 1_000,
    "m": 1_000_000,
    "mm": 1_000_000,
    "million": 1_000_000,
}


def parse_money_cents(raw: str) -> int | None:
    """Parse a money string into integer cents. Returns ``None`` if not
    parseable. Handles ``$1,000,000``, ``1M``, ``500K``, ``USD 250.00``.
    """
    if raw is None:
        return None
    m = MONEY_RE.search(raw)
    if not m:
        return None
    number = m.group(1).replace(",", "")
    suffix = (m.group(2) or "").lower()
    try:
        dec = Decimal(number)
    except Exception:
        return None
    if suffix:
        mult = _MONEY_SUFFIX_MULTIPLIER.get(suffix)
        if mult is not None:
            dec = dec * mult
    cents = int((dec * 100).quantize(Decimal("1")))
    if cents < 0:
        return None
    return cents


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------

# Policy numbers vary wildly across carriers but share a shape:
# 4-32 chars, uppercase letters + digits + ``-`` ``/`` ``.``.
POLICY_NUMBER_RE: Final = re.compile(
    r"\b([A-Z0-9][A-Z0-9\-\/\.]{3,31}[A-Z0-9])\b"
)

# NPN - National Producer Number. Always purely numeric, 5-10 digits in
# practice (NIPR allocates incrementally).
NPN_RE: Final = re.compile(r"\b(\d{5,10})\b")

# FEIN - Federal EIN, ``XX-XXXXXXX``.
FEIN_RE: Final = re.compile(r"\b(\d{2}-\d{7})\b")

# NAIC carrier code - 5-digit numeric assigned by NAIC.
NAIC_RE: Final = re.compile(r"\b(\d{5})\b")


# ---------------------------------------------------------------------------
# US states
# ---------------------------------------------------------------------------

US_STATES: Final[frozenset[str]] = frozenset({
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA",
    "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY",
    "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX",
    "UT", "VT", "VA", "WA", "WV", "WI", "WY", "PR",
})

STATE_CODE_RE: Final = re.compile(
    r"\b(" + "|".join(sorted(US_STATES, key=len, reverse=True)) + r")\b"
)


def guess_state_code(text: str) -> str | None:
    """Return the first plausible US state code in ``text`` or ``None``."""
    for m in STATE_CODE_RE.finditer(text or ""):
        code = m.group(1).upper()
        if code in US_STATES:
            return code
    return None


# ---------------------------------------------------------------------------
# Insurer lookup table
# ---------------------------------------------------------------------------
#
# Tiny seed table - sufficient to cover the most common ACORD 25 carriers
# the design partners ship. Extra carriers can be added without touching
# extractor code. The match is case-insensitive substring.

INSURER_LOOKUP: Final[dict[str, str]] = {
    "hartford": "The Hartford",
    "travelers": "Travelers",
    "chubb": "Chubb",
    "liberty mutual": "Liberty Mutual",
    "zurich": "Zurich",
    "aig": "AIG",
    "cna": "CNA",
    "nationwide": "Nationwide",
    "berkshire": "Berkshire Hathaway",
    "amtrust": "AmTrust",
    "markel": "Markel",
    "philadelphia": "Philadelphia Insurance",
    "great american": "Great American",
    "state auto": "State Auto",
    "allianz": "Allianz",
    "axa": "AXA",
    "munich re": "Munich Re",
    "swiss re": "Swiss Re",
    "lloyd": "Lloyd's of London",
    "lloyds": "Lloyd's of London",
    "starr": "Starr Insurance",
    "everest": "Everest National",
    "tokio marine": "Tokio Marine",
    "the doctors company": "The Doctors Company",
}


def match_insurer(text: str) -> str | None:
    """Return the canonical insurer name if the text mentions one we know."""
    if not text:
        return None
    lowered = text.lower()
    for needle, canonical in INSURER_LOOKUP.items():
        if needle in lowered:
            return canonical
    return None


# ---------------------------------------------------------------------------
# Producer-license lines of authority
# ---------------------------------------------------------------------------

LINES_OF_AUTHORITY: Final[frozenset[str]] = frozenset({
    "Property",
    "Casualty",
    "Life",
    "Health",
    "Accident",
    "Variable Life",
    "Variable Annuity",
    "Surplus Lines",
    "Personal Lines",
    "Commercial Lines",
    "Crop",
    "Bail Bonds",
    "Title",
    "Workers Compensation",
})


def match_lines_of_authority(text: str) -> list[str]:
    """Return the canonical LOAs found in ``text``."""
    if not text:
        return []
    out: list[str] = []
    lowered = text.lower()
    for loa in LINES_OF_AUTHORITY:
        if loa.lower() in lowered:
            out.append(loa)
    return sorted(set(out))


# ---------------------------------------------------------------------------
# Label/value helpers (two simple modes: same-line, next-line)
# ---------------------------------------------------------------------------


def _strip_label(value: str) -> str:
    return value.strip().rstrip(":").strip()


def find_label_value(
    text: str,
    labels: Iterable[str],
    *,
    max_value_chars: int = 120,
) -> str | None:
    """Find first ``Label: value`` on the same line."""
    for label in labels:
        pat = re.compile(
            rf"(?im)^\s*{re.escape(label)}\s*[:\-]\s*(.+?)\s*$"
        )
        for m in pat.finditer(text):
            val = m.group(1).strip()
            if val and len(val) <= max_value_chars:
                return val
    return None


def find_label_value_below(
    text: str,
    labels: Iterable[str],
    *,
    max_value_chars: int = 120,
) -> str | None:
    """Find a value that sits on the line BELOW one of the labels."""
    lines = text.splitlines()
    label_norms = {_strip_label(label).lower() for label in labels}
    for i, line in enumerate(lines):
        norm = _strip_label(line).lower()
        if norm in label_norms:
            for j in range(i + 1, min(i + 4, len(lines))):
                candidate = lines[j].strip()
                if candidate:
                    if len(candidate) > max_value_chars:
                        return candidate[:max_value_chars].strip()
                    return candidate
    return None
