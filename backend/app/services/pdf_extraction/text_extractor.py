"""PDF → text + Page list, with PyMuPDF (preferred) and pdfminer.six fallback.

Order of attempts:

1. **PyMuPDF (``fitz``)** - if importable; fast (<50ms/page typically)
   and provides per-line bounding boxes which the COI extractor uses
   to lift label/value-proximity confidence scores.
2. **pdfminer.six** - pure-python fallback that ships in
   ``requirements.txt``. No layout boxes, but text quality is good
   enough for our regex-based extractors.

A *file-size* + *page-count* guard runs **before** either backend so
attackers can't OOM us by uploading a 2 GB PDF. Encrypted PDFs are
rejected up front because OCR-on-encrypted-PDFs is out of scope for
Phase 3.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterable

from app.config import settings
from app.services.pdf_extraction.base import (
    Page,
    PdfEncryptedError,
    PdfParseError,
    PdfTooLargeError,
)

__all__ = [
    "extract_pages",
    "extract_text",
    "validate_pdf_header",
]


# A PDF file MUST start with %PDF-<version>. We accept 1.x and 2.x.
_PDF_MAGIC = re.compile(rb"^%PDF-[12]\.\d")
# Crude scan for /Encrypt object - pdf_encrypted error path. Live PDFs that
# carry an /Encrypt dict are password-protected (per ISO 32000-1 §7.6).
_ENCRYPT_HINT = re.compile(rb"/Encrypt\b")


def validate_pdf_header(
    blob: bytes,
    *,
    max_size_mb: int | None = None,
) -> None:
    """Cheap pre-flight: magic bytes, size, encryption guard.

    Raises :class:`PdfParseError` for malformed input,
    :class:`PdfTooLargeError` for over-quota files,
    :class:`PdfEncryptedError` for encrypted files.
    """
    if blob is None or len(blob) == 0:
        raise PdfParseError("empty pdf")

    max_mb = max_size_mb if max_size_mb is not None else getattr(
        settings, "pdf_max_size_mb", 25
    )
    if len(blob) > max_mb * 1024 * 1024:
        raise PdfTooLargeError(
            f"pdf exceeds size limit ({len(blob)} > {max_mb * 1024 * 1024} bytes)"
        )

    head = blob[:8]
    if not _PDF_MAGIC.match(head):
        raise PdfParseError(f"not a pdf (magic={head!r})")

    if _ENCRYPT_HINT.search(blob[: 64 * 1024]):
        # Heuristic only - /Encrypt may appear inside content streams, but a
        # match in the first 64KB (the catalog area) is a very strong signal.
        raise PdfEncryptedError("pdf is encrypted")


# ---------------------------------------------------------------------------
# Backend wrappers
# ---------------------------------------------------------------------------


def _extract_with_fitz(blob: bytes, max_pages: int) -> list[Page] | None:
    try:
        import fitz  # type: ignore  # PyMuPDF
    except Exception:
        return None
    try:
        doc = fitz.open(stream=blob, filetype="pdf")
    except Exception as exc:  # pragma: no cover - depends on PyMuPDF internals
        raise PdfParseError(f"PyMuPDF failed: {exc}") from exc

    try:
        if getattr(doc, "is_encrypted", False):
            raise PdfEncryptedError("pdf is encrypted")
        if doc.page_count > max_pages:
            raise PdfTooLargeError(
                f"pdf page count {doc.page_count} > limit {max_pages}"
            )
        out: list[Page] = []
        for i in range(doc.page_count):
            page = doc.load_page(i)
            text = page.get_text("text") or ""
            lines = tuple(text.splitlines())
            boxes: list[tuple[float, float, float, float, str]] = []
            try:
                blocks = page.get_text("blocks") or []
                for b in blocks:
                    # fitz returns (x0, y0, x1, y1, text, block_no, block_type)
                    if len(b) >= 5:
                        x0, y0, x1, y1, txt = (
                            float(b[0]), float(b[1]), float(b[2]),
                            float(b[3]), str(b[4]),
                        )
                        boxes.append((x0, y0, x1 - x0, y1 - y0, txt))
            except Exception:
                boxes = []
            out.append(
                Page(number=i + 1, text=text, lines=lines, boxes=tuple(boxes))
            )
        return out
    finally:
        doc.close()


def _extract_with_pdfminer(blob: bytes, max_pages: int) -> list[Page]:
    try:
        from pdfminer.high_level import extract_text as _pm_extract_text
        from pdfminer.pdfdocument import PDFDocument, PDFPasswordIncorrect
        from pdfminer.pdfpage import PDFPage
        from pdfminer.pdfparser import PDFParser
    except Exception as exc:
        raise PdfParseError(
            "no PDF backend available - install PyMuPDF or pdfminer.six"
        ) from exc

    # Page-count guard (cheap; doesn't extract text).
    try:
        parser = PDFParser(io.BytesIO(blob))
        document = PDFDocument(parser)
    except PDFPasswordIncorrect as exc:
        raise PdfEncryptedError("pdf is encrypted") from exc
    except Exception as exc:
        raise PdfParseError(f"pdfminer parse failed: {exc}") from exc

    if not document.is_extractable:
        raise PdfParseError("pdf disallows text extraction")

    page_count = sum(1 for _ in PDFPage.create_pages(document))
    if page_count > max_pages:
        raise PdfTooLargeError(
            f"pdf page count {page_count} > limit {max_pages}"
        )

    out: list[Page] = []
    for i in range(page_count):
        try:
            text = _pm_extract_text(io.BytesIO(blob), page_numbers=[i]) or ""
        except Exception as exc:
            raise PdfParseError(f"pdfminer page {i} failed: {exc}") from exc
        lines = tuple(text.splitlines())
        out.append(Page(number=i + 1, text=text, lines=lines))
    return out


def extract_pages(
    blob: bytes,
    *,
    max_pages: int | None = None,
    max_size_mb: int | None = None,
) -> list[Page]:
    """Parse ``blob`` into a list of :class:`Page` objects.

    Performs pre-flight validation, then tries PyMuPDF, then pdfminer.
    """
    validate_pdf_header(blob, max_size_mb=max_size_mb)
    page_limit = max_pages if max_pages is not None else getattr(
        settings, "pdf_max_pages", 50
    )

    pages = _extract_with_fitz(blob, max_pages=page_limit)
    if pages is not None:
        return pages
    return _extract_with_pdfminer(blob, max_pages=page_limit)


def extract_text(
    blob: bytes,
    *,
    max_pages: int | None = None,
    max_size_mb: int | None = None,
    separator: str = "\n\n",
) -> str:
    """Convenience: extract + join pages into a single string."""
    pages = extract_pages(blob, max_pages=max_pages, max_size_mb=max_size_mb)
    return separator.join(p.text for p in pages)


def _join_pages_text(pages: Iterable[Page]) -> str:
    return "\n\n".join(p.text for p in pages)
