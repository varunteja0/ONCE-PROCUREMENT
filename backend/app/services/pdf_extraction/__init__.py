"""PDF metadata extractors for Once.

This package houses the regex+heuristic extractors used by the upload
UI to pre-fill COI / E&O / producer-license forms. Vision-LLM-backed
extractors will replace these in Phase 4 - see ``docs/PDF_EXTRACTION.md``
for the roadmap.

Public surface:

* :class:`~app.services.pdf_extraction.base.BasePdfExtractor`
* :class:`~app.services.pdf_extraction.base.ExtractionOutput`
* :func:`get_extractor` - registry lookup by source-document type.
* :func:`extract_pages`, :func:`extract_text` - text-layer extraction.
"""

from __future__ import annotations

from typing import Final

from app.models.extraction_result import ExtractionSourceType
from app.services.pdf_extraction.base import (
    BasePdfExtractor,
    ExtractionOutput,
    Page,
    PdfEncryptedError,
    PdfParseError,
    PdfTooLargeError,
)
from app.services.pdf_extraction.coi_extractor import CoiExtractor
from app.services.pdf_extraction.eo_extractor import EoExtractor
from app.services.pdf_extraction.license_extractor import LicenseExtractor
from app.services.pdf_extraction.text_extractor import (
    extract_pages,
    extract_text,
    validate_pdf_header,
)

__all__ = [
    "BasePdfExtractor",
    "ExtractionOutput",
    "Page",
    "PdfEncryptedError",
    "PdfParseError",
    "PdfTooLargeError",
    "CoiExtractor",
    "EoExtractor",
    "LicenseExtractor",
    "extract_pages",
    "extract_text",
    "validate_pdf_header",
    "get_extractor",
    "EXTRACTORS",
]


EXTRACTORS: Final[dict[str, BasePdfExtractor]] = {
    ExtractionSourceType.COI.value: CoiExtractor(),
    ExtractionSourceType.EO_CERTIFICATE.value: EoExtractor(),
    ExtractionSourceType.PRODUCER_LICENSE.value: LicenseExtractor(),
}


def get_extractor(source_type: str | ExtractionSourceType) -> BasePdfExtractor:
    key = (
        source_type.value
        if isinstance(source_type, ExtractionSourceType)
        else str(source_type)
    )
    try:
        return EXTRACTORS[key]
    except KeyError as exc:
        raise ValueError(f"unknown extractor for source_type={key!r}") from exc
