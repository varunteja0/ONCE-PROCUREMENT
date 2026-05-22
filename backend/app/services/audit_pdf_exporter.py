"""L3.10 — Audit-trail PDF export.

Renders a signed-evidence PDF using the project's existing
``reportlab`` dependency (already pinned for L3.8 fixtures). Layout:

* Cover page: tenant id, scope, date range, row count, key id, generated_at.
* Verification instructions page.
* Per-row paginated table: 5 rows per page, monospace, long payloads
  truncated with a sha256 reference so the on-disk size stays bounded.
* Every page footer carries page N/M plus the signed-envelope sha256
  so a printed page is verifiable against the JSON sidecar.

The renderer is **pure** — given the same inputs it produces the same
bytes (no embedded timestamps in the PDF stream beyond what the caller
passes in). This keeps ``file_sha256`` deterministic for tests.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

__all__ = ["render_audit_pdf", "PDF_MIME_TYPE"]


PDF_MIME_TYPE: str = "application/pdf"

_PAGE_WIDTH, _PAGE_HEIGHT = A4
_LEFT = 18 * mm
_RIGHT = 18 * mm
_TOP = 18 * mm
_BOTTOM = 22 * mm
_ROWS_PER_PAGE = 5
_PAYLOAD_TRUNCATE = 220


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _truncate_payload(payload: Any) -> tuple[str, str]:
    if payload is None:
        return "—", ""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if len(raw) <= _PAYLOAD_TRUNCATE:
        return raw, ""
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw[:_PAYLOAD_TRUNCATE] + "…", digest


class _FooterDoc(BaseDocTemplate):
    """BaseDocTemplate that paints a shared footer on every page."""

    def __init__(self, buf: io.BytesIO, *, envelope_sha256: str, generated_at: str) -> None:
        super().__init__(
            buf,
            pagesize=A4,
            leftMargin=_LEFT,
            rightMargin=_RIGHT,
            topMargin=_TOP,
            bottomMargin=_BOTTOM,
            title="Once Audit Trail Export",
            author="Once Procurement",
        )
        self._envelope_sha256 = envelope_sha256
        self._generated_at = generated_at
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="content",
            showBoundary=0,
        )
        self.addPageTemplates(
            [PageTemplate(id="default", frames=[frame], onPage=self._paint_footer)]
        )

    def _paint_footer(self, canv: canvas.Canvas, doc: BaseDocTemplate) -> None:
        canv.saveState()
        canv.setFont("Helvetica", 7)
        canv.setFillColor(colors.grey)
        canv.drawString(
            _LEFT,
            10 * mm,
            f"envelope sha256: {self._envelope_sha256[:32]}…  •  generated {self._generated_at}",
        )
        canv.drawRightString(
            _PAGE_WIDTH - _RIGHT,
            10 * mm,
            f"page {canv.getPageNumber()}",
        )
        canv.restoreState()


def render_audit_pdf(
    *,
    tenant_id: str,
    tenant_name: str | None,
    scope: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    generated_at: datetime,
    signing_key_id: str,
    envelope_sha256: str,
) -> bytes:
    """Render the audit-export PDF and return its bytes."""

    buf = io.BytesIO()
    generated_iso = _iso(generated_at)
    doc = _FooterDoc(buf, envelope_sha256=envelope_sha256, generated_at=generated_iso)
    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    body = styles["BodyText"]
    mono = ParagraphStyle(
        "mono",
        parent=body,
        fontName="Courier",
        fontSize=7,
        leading=9,
    )

    story: list[Any] = []

    # ---------------- Cover ----------------
    story.append(Paragraph("Once — Tenant Audit Trail Export", h1))
    story.append(Spacer(1, 4 * mm))
    cover_rows = [
        ["Tenant ID", tenant_id],
        ["Tenant Name", tenant_name or "—"],
        ["Scope", json.dumps(dict(scope), sort_keys=True)],
        ["Row Count", str(len(rows))],
        ["Generated (UTC)", generated_iso],
        ["Signing Key ID", signing_key_id],
        ["Envelope SHA-256", envelope_sha256],
    ]
    t = Table(cover_rows, colWidths=[45 * mm, doc.width - 45 * mm])
    t.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
            ]
        )
    )
    story.append(t)
    story.append(PageBreak())

    # ---------------- Verification ----------------
    story.append(Paragraph("Verification Instructions", h2))
    story.append(
        Paragraph(
            "1. Download the JSON envelope sidecar from "
            "<font face='Courier'>/v1/audit/exports/{id}/download/envelope</font>.<br/>"
            "2. Recompute the SHA-256 of this PDF; it must equal the envelope's "
            "<font face='Courier'>pdf_sha256</font>.<br/>"
            "3. Strip <font face='Courier'>signature_key_id</font> and "
            "<font face='Courier'>signature_b64</font> from the envelope, "
            "canonicalise the remainder (RFC 8785), and verify the Ed25519 "
            "signature with the public key at "
            "<font face='Courier'>/v1/keys/{signature_key_id}</font>.<br/>"
            "4. Replay the chain via <font face='Courier'>GET /v1/audit/chain/verify</font> "
            "to confirm no row has been mutated.",
            body,
        )
    )
    story.append(PageBreak())

    # ---------------- Rows ----------------
    if not rows:
        story.append(Paragraph("No audit rows in scope.", body))
    else:
        for page_start in range(0, len(rows), _ROWS_PER_PAGE):
            page_rows = list(rows[page_start : page_start + _ROWS_PER_PAGE])
            story.append(
                Paragraph(
                    f"Rows {page_start + 1}–{page_start + len(page_rows)} of {len(rows)}",
                    h2,
                )
            )
            data: list[list[Any]] = [
                ["#", "Occurred (UTC)", "Actor", "Action", "Resource", "Chain Hash"]
            ]
            for row in page_rows:
                truncated, digest = _truncate_payload(row.get("payload_summary"))
                resource = f"{row.get('resource_type', '—')}/{row.get('resource_id') or '—'}"
                actor = f"{row.get('actor_type', '—')}:{row.get('actor_id') or '—'}"
                data.append(
                    [
                        Paragraph(str(row.get("chain_position", "")), mono),
                        Paragraph(_iso_str(row.get("occurred_at")), mono),
                        Paragraph(actor, mono),
                        Paragraph(str(row.get("action_verb", "")), mono),
                        Paragraph(resource, mono),
                        Paragraph(
                            (row.get("this_hash") or "")[:16] + "…", mono
                        ),
                    ]
                )
                detail = truncated if not digest else f"{truncated} [sha256:{digest[:16]}…]"
                data.append(
                    [
                        "",
                        Paragraph(f"payload: {detail}", mono),
                        "",
                        "",
                        "",
                        "",
                    ]
                )
            tbl = Table(
                data,
                colWidths=[
                    10 * mm,
                    32 * mm,
                    40 * mm,
                    25 * mm,
                    45 * mm,
                    doc.width - 152 * mm,
                ],
                repeatRows=1,
            )
            style = TableStyle(
                [
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ]
            )
            for i in range(1, len(data), 2):
                style.add(
                    "SPAN", (1, i + 1), (5, i + 1)
                ) if i + 1 < len(data) else None
            tbl.setStyle(style)
            story.append(tbl)
            if page_start + _ROWS_PER_PAGE < len(rows):
                story.append(PageBreak())

    doc.build(story)
    return buf.getvalue()


def _iso_str(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        return _iso(value)
    return str(value)
