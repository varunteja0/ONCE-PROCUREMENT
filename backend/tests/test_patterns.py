"""Tests for app.services.pdf_extraction.patterns."""

from __future__ import annotations

from datetime import date

import pytest

from app.services.pdf_extraction.patterns import (
    DATE_RE,
    FEIN_RE,
    LINES_OF_AUTHORITY,
    MONEY_RE,
    NAIC_RE,
    NPN_RE,
    STATE_CODE_RE,
    US_STATES,
    find_label_value,
    find_label_value_below,
    guess_state_code,
    match_insurer,
    match_lines_of_authority,
    normalize_whitespace,
    parse_date,
    parse_money_cents,
)

# --- dates ----------------------------------------------------------------


def test_parse_date_iso() -> None:
    assert parse_date("2026-12-31") == date(2026, 12, 31)


def test_parse_date_mdy_slash() -> None:
    assert parse_date("12/31/2026") == date(2026, 12, 31)


def test_parse_date_mdy_dash() -> None:
    assert parse_date("12-31-2026") == date(2026, 12, 31)


def test_parse_date_mdy_dot() -> None:
    assert parse_date("12.31.2026") == date(2026, 12, 31)


def test_parse_date_two_digit_year_rolls_to_2000s() -> None:
    assert parse_date("01/15/26") == date(2026, 1, 15)


def test_parse_date_named_month_long() -> None:
    assert parse_date("December 31, 2026") == date(2026, 12, 31)


def test_parse_date_named_month_short() -> None:
    assert parse_date("Dec 31 2026") == date(2026, 12, 31)


def test_parse_date_named_month_with_period() -> None:
    assert parse_date("Sept. 5 2026") == date(2026, 9, 5)


def test_parse_date_day_first() -> None:
    assert parse_date("31 December 2026") == date(2026, 12, 31)


def test_parse_date_garbage_returns_none() -> None:
    assert parse_date("not a date") is None


def test_parse_date_empty_returns_none() -> None:
    assert parse_date("") is None
    assert parse_date("   ") is None


def test_parse_date_invalid_components_returns_none() -> None:
    assert parse_date("13/45/2026") is None


def test_date_re_finds_multiple() -> None:
    text = "Eff 01/15/2026 Exp 01/15/2027 Date: 2026-06-01"
    matches = [m.group(1) for m in DATE_RE.finditer(text)]
    assert matches == ["01/15/2026", "01/15/2027", "2026-06-01"]


# --- money ----------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("$1,000,000", 100_000_000),
        ("1000000.00", 100_000_000),
        ("USD 250.00", 25_000),
        ("$2,500.50", 250_050),
        ("1M", 100_000_000),
        ("500K", 50_000_000),
        ("1.5 million", 150_000_000),
    ],
)
def test_parse_money_cents_happy(raw: str, expected: int) -> None:
    assert parse_money_cents(raw) == expected


def test_parse_money_cents_garbage_returns_none() -> None:
    assert parse_money_cents("not a number") is None
    assert parse_money_cents("") is None


def test_money_re_extracts_from_sentence() -> None:
    m = MONEY_RE.search("Limit of $1,000,000 each occurrence")
    assert m is not None and m.group(1) == "1,000,000"


# --- identifiers ----------------------------------------------------------


def test_npn_matches_valid_range() -> None:
    assert NPN_RE.search("NPN 12345").group(1) == "12345"
    assert NPN_RE.search("NPN 1234567890").group(1) == "1234567890"


def test_npn_skips_too_short() -> None:
    assert NPN_RE.search("ID 123") is None


def test_fein_matches_canonical_format() -> None:
    assert FEIN_RE.search("FEIN: 12-3456789").group(1) == "12-3456789"


def test_fein_rejects_unhyphenated() -> None:
    assert FEIN_RE.search("FEIN: 123456789") is None


def test_naic_matches_5_digits() -> None:
    assert NAIC_RE.search("NAIC # 19682").group(1) == "19682"


# --- states ---------------------------------------------------------------


def test_guess_state_code_finds_first() -> None:
    assert guess_state_code("Issued in TX on 2025") == "TX"


def test_guess_state_code_none() -> None:
    assert guess_state_code("no state here") is None


def test_state_code_re_is_word_bounded() -> None:
    # "MARK" should not match "MA" as a substring.
    assert STATE_CODE_RE.search("MARKER") is None
    assert STATE_CODE_RE.search("from MA today").group(1) == "MA"


def test_us_states_coverage() -> None:
    assert "DC" in US_STATES and "PR" in US_STATES and len(US_STATES) >= 52


# --- insurer lookup -------------------------------------------------------


def test_match_insurer_hartford_variants() -> None:
    assert match_insurer("Hartford Fire Insurance") == "The Hartford"
    assert match_insurer("hartford") == "The Hartford"


def test_match_insurer_unknown() -> None:
    assert match_insurer("Generic Insurance Co.") is None


def test_match_insurer_empty_text() -> None:
    assert match_insurer("") is None


# --- lines of authority ---------------------------------------------------


def test_match_lines_of_authority_extracts_multiple() -> None:
    result = match_lines_of_authority("Authorized: Property, Casualty, Life")
    assert result == ["Casualty", "Life", "Property"]


def test_match_lines_of_authority_none() -> None:
    assert match_lines_of_authority("nothing here") == []


def test_lines_of_authority_contains_common() -> None:
    for required in ("Property", "Casualty", "Life", "Surplus Lines"):
        assert required in LINES_OF_AUTHORITY


# --- label helpers --------------------------------------------------------


def test_find_label_value_same_line() -> None:
    text = "Policy Number: GL-123-456\nOther: foo"
    assert find_label_value(text, ["Policy Number"]) == "GL-123-456"


def test_find_label_value_below() -> None:
    text = "CERTIFICATE HOLDER\nBig Co LLC\n1 Plaza"
    assert find_label_value_below(text, ["CERTIFICATE HOLDER"]) == "Big Co LLC"


def test_find_label_value_missing() -> None:
    assert find_label_value("nothing", ["Policy Number"]) is None


def test_find_label_value_below_missing() -> None:
    assert find_label_value_below("nothing", ["HEADER"]) is None


# --- whitespace -----------------------------------------------------------


def test_normalize_whitespace_collapses_runs() -> None:
    assert normalize_whitespace("a   b\t\tc") == "a b c"


def test_normalize_whitespace_preserves_newlines() -> None:
    assert normalize_whitespace("a\nb\n\n\n\nc") == "a\nb\n\nc"
