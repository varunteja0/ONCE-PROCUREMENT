"""Tests for the producer-license extractor."""

from __future__ import annotations

from app.services.pdf_extraction import LicenseExtractor, extract_pages
from tests.fixtures.pdfs import make_pdf


def _baseline_lines() -> list[str]:
    return [
        "STATE OF TEXAS",
        "DEPARTMENT OF INSURANCE",
        "PRODUCER LICENSE",
        "Licensee: Jane Q Producer",
        "License Number: 1234567",
        "State: TX",
        "License Type: Resident Producer",
        "Effective Date: 03/01/2024",
        "Expiration Date: 03/01/2028",
        "NPN: 9988776",
        "Lines: Property, Casualty, Life, Health",
    ]


def _build(lines: list[str]):
    return extract_pages(make_pdf(lines))


def test_license_extracts_name() -> None:
    out = LicenseExtractor().extract(_build(_baseline_lines()))
    assert "Jane" in out.fields["licensee_name"]


def test_license_extracts_number() -> None:
    out = LicenseExtractor().extract(_build(_baseline_lines()))
    assert out.fields["license_number"] == "1234567"


def test_license_extracts_state() -> None:
    out = LicenseExtractor().extract(_build(_baseline_lines()))
    assert out.fields["state"] == "TX"


def test_license_extracts_type() -> None:
    out = LicenseExtractor().extract(_build(_baseline_lines()))
    assert out.fields["license_type"] == "resident_producer"


def test_license_extracts_dates() -> None:
    out = LicenseExtractor().extract(_build(_baseline_lines()))
    assert out.fields["effective_date"] == "2024-03-01"
    assert out.fields["expiration_date"] == "2028-03-01"


def test_license_extracts_npn() -> None:
    out = LicenseExtractor().extract(_build(_baseline_lines()))
    assert out.fields["npn"] == "9988776"


def test_license_extracts_loas() -> None:
    out = LicenseExtractor().extract(_build(_baseline_lines()))
    assert set(["Property", "Casualty", "Life", "Health"]).issubset(
        set(out.fields["lines_authorized"])
    )


def test_license_handles_non_resident() -> None:
    lines = _baseline_lines()
    for i, line in enumerate(lines):
        if line.startswith("License Type"):
            lines[i] = "License Type: Non-Resident Producer"
    out = LicenseExtractor().extract(_build(lines))
    assert out.fields["license_type"] == "non_resident_producer"


def test_license_handles_empty() -> None:
    out = LicenseExtractor().extract([])
    assert "no pages" in out.warnings
