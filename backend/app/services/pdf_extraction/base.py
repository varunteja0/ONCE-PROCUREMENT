"""Base types + Protocol for the PDF extractor family."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "Page",
    "ExtractionOutput",
    "BasePdfExtractor",
    "PdfParseError",
    "PdfEncryptedError",
    "PdfTooLargeError",
]


class PdfParseError(Exception):
    """PDF could not be parsed by either backend."""


class PdfEncryptedError(PdfParseError):
    """PDF is encrypted / password-protected - we refuse to brute force."""


class PdfTooLargeError(PdfParseError):
    """PDF exceeds the configured file-size or page-count limit."""


@dataclass(frozen=True, slots=True)
class Page:
    """One page of a PDF, post-text-extraction.

    ``text`` is the plain-text dump (preserves newlines). ``lines`` is a
    convenience split that downstream extractors lean on instead of
    re-splitting every time.

    ``boxes`` is reserved for layout-aware data
    (``[(x, y, w, h, text)]``) when PyMuPDF is available. The pdfminer
    fallback leaves it empty - extractors must work without it.
    """

    number: int
    text: str
    lines: tuple[str, ...] = ()
    boxes: tuple[tuple[float, float, float, float, str], ...] = ()


@dataclass(slots=True)
class ExtractionOutput:
    fields: dict[str, Any] = field(default_factory=dict)
    confidences: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class BasePdfExtractor(Protocol):
    document_type: str
    version: str
    required_fields: tuple[str, ...]

    def extract(self, pages: list[Page]) -> ExtractionOutput: ...
