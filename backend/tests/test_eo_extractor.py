"""Tests for the E&O certificate extractor."""

from __future__ import annotations

from app.services.pdf_extraction import EoExtractor, extract_pages
from tests.fixtures.pdfs import make_pdf


def _baseline_lines() -> list[str]:
    return [
        "ERRORS & OMISSIONS CERTIFICATE OF INSURANCE",
        "Carrier: The Hartford Insurance Group",
        "Policy Number: EO-2026-00777",
        "Named Insured: Acme Insurance Brokers LLC",
        "Effective Date: 02/01/2026",
        "Expiration Date: 02/01/2027",
        "Retroactive Date: 02/01/2020",
        "Limit of Liability: $2,000,000",
        "Aggregate Limit: $4,000,000",
        "Deductible: $25,000",
    ]


def _build(lines: list[str]):
    return extract_pages(make_pdf(lines))


def test_eo_extracts_carrier_with_lookup() -> None:
    out = EoExtractor().extract(_build(_baseline_lines()))
    assert out.fields["carrier_name"] == "The Hartford"


def test_eo_extracts_policy_number() -> None:
    out = EoExtractor().extract(_build(_baseline_lines()))
    assert out.fields["policy_number"] == "EO-2026-00777"


def test_eo_extracts_named_insured() -> None:
    out = EoExtractor().extract(_build(_baseline_lines()))
    assert "Acme" in out.fields["named_insured"]


def test_eo_extracts_dates() -> None:
    out = EoExtractor().extract(_build(_baseline_lines()))
    assert out.fields["effective_date"] == "2026-02-01"
    assert out.fields["expiration_date"] == "2027-02-01"
    assert out.fields["retroactive_date"] == "2020-02-01"


def test_eo_extracts_money_fields() -> None:
    out = EoExtractor().extract(_build(_baseline_lines()))
    assert out.fields["coverage_amount_cents"] == 200_000_000
    assert out.fields["aggregate_amount_cents"] == 400_000_000
    assert out.fields["deductible_cents"] == 2_500_000


def test_eo_handles_missing_fields_gracefully() -> None:
    out = EoExtractor().extract(_build([
        "ERRORS & OMISSIONS CERTIFICATE",
        "Carrier: Travelers",
        "Policy Number: EO-XYZ-001",
    ]))
    assert out.fields["carrier_name"] == "Travelers"
    assert out.fields["policy_number"] == "EO-XYZ-001"
    assert "effective_date" not in out.fields


def test_eo_handles_empty_pages() -> None:
    out = EoExtractor().extract([])
    assert "no pages" in out.warnings


def test_eo_warns_on_inverted_dates() -> None:
    lines = _baseline_lines()
    for i, line in enumerate(lines):
        if line.startswith("Effective Date"):
            lines[i] = "Effective Date: 02/01/2027"
        if line.startswith("Expiration Date"):
            lines[i] = "Expiration Date: 02/01/2026"
    out = EoExtractor().extract(_build(lines))
    assert any("expiration_date" in w for w in out.warnings)
