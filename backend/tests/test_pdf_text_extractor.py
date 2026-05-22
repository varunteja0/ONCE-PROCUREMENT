"""Tests for app.services.pdf_extraction.text_extractor."""

from __future__ import annotations

import pytest

from app.services.pdf_extraction import (
    PdfEncryptedError,
    PdfParseError,
    PdfTooLargeError,
    extract_pages,
    extract_text,
    validate_pdf_header,
)
from tests.fixtures.pdfs import make_pdf


def test_extract_text_returns_concatenated_pages() -> None:
    blob = make_pdf(["Hello", "World"])
    text = extract_text(blob)
    assert "Hello" in text and "World" in text


def test_extract_pages_returns_page_objects() -> None:
    blob = make_pdf(["Page one only"])
    pages = extract_pages(blob)
    assert len(pages) == 1
    assert pages[0].number == 1
    assert "Page one only" in pages[0].text
    assert pages[0].lines


def test_extract_pages_handles_multipage() -> None:
    blob = make_pdf([f"Line {i}" for i in range(120)])
    pages = extract_pages(blob)
    assert len(pages) >= 2


def test_validate_pdf_header_rejects_non_pdf() -> None:
    with pytest.raises(PdfParseError):
        validate_pdf_header(b"not a pdf at all")


def test_validate_pdf_header_rejects_empty() -> None:
    with pytest.raises(PdfParseError):
        validate_pdf_header(b"")


def test_validate_pdf_header_size_limit() -> None:
    fake = b"%PDF-1.4\n" + b"X" * (2 * 1024 * 1024)
    with pytest.raises(PdfTooLargeError):
        validate_pdf_header(fake, max_size_mb=1)


def test_validate_pdf_header_detects_encrypt_hint() -> None:
    blob = b"%PDF-1.4\n%...\n/Encrypt 1 0 R\n"
    with pytest.raises(PdfEncryptedError):
        validate_pdf_header(blob)


def test_extract_pages_respects_max_pages() -> None:
    blob = make_pdf([f"L{i}" for i in range(200)], page_break_every=5)
    with pytest.raises(PdfTooLargeError):
        extract_pages(blob, max_pages=2)


def test_extract_text_preserves_separator() -> None:
    blob = make_pdf(["alpha", "beta"], page_break_every=1)
    text = extract_text(blob, separator="|PAGE|")
    assert "|PAGE|" in text
