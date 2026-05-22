"""Tests for the ACORD 25 COI extractor."""

from __future__ import annotations

from app.services.pdf_extraction import CoiExtractor, extract_pages
from app.services.pdf_extraction.base import Page
from tests.fixtures.pdfs import make_pdf


def _build_acord_pages(lines: list[str]) -> list[Page]:
    blob = make_pdf(lines)
    return extract_pages(blob)


def _baseline_lines() -> list[str]:
    return [
        "ACORD 25 CERTIFICATE OF LIABILITY INSURANCE",
        "DATE 01/15/2026",
        "PRODUCER",
        "Smith & Jones Insurance Brokers",
        "123 Main St, New York, NY 10001",
        "",
        "INSURED",
        "Acme Manufacturing Inc.",
        "FEIN: 12-3456789",
        "",
        "INSURER A: The Hartford Fire Insurance Co NAIC # 19682",
        "INSURER B: Travelers Indemnity Co NAIC # 25658",
        "",
        "COMMERCIAL GENERAL LIABILITY",
        "POLICY NUMBER: GL-2026-00123",
        "EFF 01/15/2026 EXP 01/15/2027",
        "$1,000,000 each occurrence",
        "$2,000,000 general aggregate",
        "",
        "CERTIFICATE HOLDER",
        "Big Co LLC",
        "1 Plaza, Boston, MA",
        "",
        "CERTIFICATE NUMBER: CERT-2026-9999",
        "X Additional Insured",
        "X Waiver of Subrogation",
    ]


def test_coi_extracts_carrier() -> None:
    out = CoiExtractor().extract(_build_acord_pages(_baseline_lines()))
    assert out.fields["carrier_name"] == "The Hartford"


def test_coi_extracts_carrier_naic() -> None:
    out = CoiExtractor().extract(_build_acord_pages(_baseline_lines()))
    assert out.fields["carrier_naic"] == "19682"


def test_coi_extracts_policy_number() -> None:
    out = CoiExtractor().extract(_build_acord_pages(_baseline_lines()))
    assert out.fields["policy_number"] == "GL-2026-00123"


def test_coi_extracts_dates() -> None:
    out = CoiExtractor().extract(_build_acord_pages(_baseline_lines()))
    assert out.fields["effective_date"] == "2026-01-15"
    assert out.fields["expiry_date"] == "2027-01-15"


def test_coi_extracts_limits_in_cents() -> None:
    out = CoiExtractor().extract(_build_acord_pages(_baseline_lines()))
    assert out.fields["limit_each_occurrence_cents"] == 100_000_000
    assert out.fields["limit_aggregate_cents"] == 200_000_000


def test_coi_extracts_certificate_holder_and_number() -> None:
    out = CoiExtractor().extract(_build_acord_pages(_baseline_lines()))
    assert out.fields["certificate_holder"].startswith("Big Co")
    assert out.fields["certificate_number"] == "CERT-2026-9999"


def test_coi_extracts_fein_from_insured_block() -> None:
    out = CoiExtractor().extract(_build_acord_pages(_baseline_lines()))
    assert out.fields["insured_fein"] == "12-3456789"


def test_coi_detects_additional_insured_and_waiver() -> None:
    out = CoiExtractor().extract(_build_acord_pages(_baseline_lines()))
    assert out.fields["additional_insured"] is True
    assert out.fields["waiver_of_subrogation"] is True


def test_coi_multiple_insurers_collected() -> None:
    out = CoiExtractor().extract(_build_acord_pages(_baseline_lines()))
    assert set(out.fields["insurers"].keys()) == {"A", "B"}


def test_coi_records_multiple_policies() -> None:
    lines = _baseline_lines() + [
        "",
        "AUTOMOBILE LIABILITY",
        "POLICY NUMBER: AL-2026-00456",
        "EFF 01/15/2026 EXP 01/15/2027",
        "$1,000,000 combined single limit",
    ]
    out = CoiExtractor().extract(_build_acord_pages(lines))
    types = [p["coverage_type"] for p in out.fields["policies"]]
    assert "commercial_general_liability" in types
    assert "automobile_liability" in types


def test_coi_confidence_for_known_carrier_is_high() -> None:
    out = CoiExtractor().extract(_build_acord_pages(_baseline_lines()))
    assert out.confidences["carrier_name"] >= 0.6


def test_coi_confidence_date_high_when_consistent() -> None:
    out = CoiExtractor().extract(_build_acord_pages(_baseline_lines()))
    assert out.confidences["effective_date"] >= 0.6
    assert out.confidences["expiry_date"] >= 0.6


def test_coi_warns_on_inverted_dates() -> None:
    lines = _baseline_lines()
    # Swap effective/expiry
    for i, line in enumerate(lines):
        if "EFF 01/15/2026 EXP 01/15/2027" in line:
            lines[i] = "EFF 01/15/2027 EXP 01/15/2026"
    out = CoiExtractor().extract(_build_acord_pages(lines))
    assert any("expiry_date" in w for w in out.workings()) if False else any(
        "expiry_date" in w for w in out.warnings
    )


def test_coi_handles_empty_pages_gracefully() -> None:
    out = CoiExtractor().extract([])
    assert "no pages" in out.warnings
    assert out.fields == {}


def test_coi_unknown_carrier_falls_through_with_lower_confidence() -> None:
    lines = _baseline_lines()
    for i, line in enumerate(lines):
        if "INSURER A:" in line:
            lines[i] = "INSURER A: Generic Underwriters Ltd NAIC # 99999"
        if "INSURER B:" in line:
            lines[i] = ""
    out = CoiExtractor().extract(_build_acord_pages(lines))
    assert out.fields["carrier_name"].startswith("Generic")
    # Unknown carriers: regex_strength=0.6 -> overall <= 0.78.
    assert out.confidences["carrier_name"] <= 0.85


def test_coi_handles_missing_policy_block_without_crashing() -> None:
    lines = [
        "ACORD 25 CERTIFICATE OF LIABILITY INSURANCE",
        "INSURER A: Travelers Indemnity Co",
    ]
    out = CoiExtractor().extract(_build_acord_pages(lines))
    assert out.fields.get("carrier_name") == "Travelers"
    assert "policies" not in out.fields
