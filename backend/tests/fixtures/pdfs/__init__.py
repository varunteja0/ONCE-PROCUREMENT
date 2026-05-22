"""Synthetic-PDF helpers shared by the L3.8 extractor test modules.

We never commit binary PDFs to the repo. The :func:`make_pdf` helper
uses reportlab to build a tiny single- or multi-page PDF from a list of
lines at module-import time. Tests that need a PDF call this directly.
"""

from __future__ import annotations

import io
from collections.abc import Sequence

import pytest

__all__ = ["make_pdf", "reportlab"]


reportlab_mod = pytest.importorskip("reportlab")
reportlab = reportlab_mod


def make_pdf(lines: Sequence[str], *, page_break_every: int | None = None) -> bytes:
    """Render ``lines`` into a small PDF and return its bytes."""

    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    width, height = LETTER
    y = height - 50
    line_no = 0
    for line in lines:
        c.drawString(50, y, line)
        y -= 14
        line_no += 1
        if y < 50 or (page_break_every and line_no % page_break_every == 0):
            c.showPage()
            y = height - 50
    c.save()
    return buf.getvalue()
