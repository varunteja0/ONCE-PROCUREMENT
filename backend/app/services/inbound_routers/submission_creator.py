"""L3.9 — Submission-creator router."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Supplier
from app.models.inbound_attachment import InboundAttachment
from app.models.inbound_email import InboundEmail
from app.models.inbound_routing_rule import InboundRoutingRule
from app.models.portal import Portal
from app.models.submission import SubmissionStatus, SupplierSubmission
from app.utils.logging import get_logger

from .base import InboundRouter, RoutingResult

__all__ = ["SubmissionCreatorRouter", "resolve_supplier"]


_logger = get_logger(__name__)

_SUPPLIER_TAG_RE = re.compile(r"\[supplier:([^\]]+)\]", re.IGNORECASE)


def _extract_domain(address: str) -> str | None:
    if not address or "@" not in address:
        return None
    return address.rsplit("@", 1)[-1].strip().lower() or None


async def resolve_supplier(
    session: AsyncSession,
    *,
    tenant_id: str,
    from_address: str,
    subject: str | None,
) -> tuple[Supplier | None, str]:
    """Return ``(supplier_or_none, reason)``.

    Resolution precedence:
      1. ``[supplier:<id-or-email>]`` tag in the subject.
      2. Exact match on ``Supplier.primary_email``.
      3. Domain match against ``Supplier.primary_email`` domain.
    """

    if subject:
        m = _SUPPLIER_TAG_RE.search(subject)
        if m:
            token = m.group(1).strip()
            stmt = select(Supplier).where(
                Supplier.tenant_id == tenant_id,
                (Supplier.id == token) | (Supplier.primary_email == token),
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is not None:
                return row, "tag"

    if from_address:
        stmt = select(Supplier).where(
            Supplier.tenant_id == tenant_id,
            Supplier.primary_email == from_address,
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is not None:
            return row, "email_exact"

    domain = _extract_domain(from_address)
    if domain:
        stmt = select(Supplier).where(
            Supplier.tenant_id == tenant_id,
            Supplier.primary_email.is_not(None),
            Supplier.primary_email.ilike(f"%@{domain}"),
        )
        row = (await session.execute(stmt)).scalars().first()
        if row is not None:
            return row, "email_domain"

    return None, "unresolved"


class SubmissionCreatorRouter(InboundRouter):
    name = "submission_creator"

    async def route(
        self,
        session: AsyncSession,
        *,
        email: InboundEmail,
        attachments: list[InboundAttachment],
        rule: InboundRoutingRule,
    ) -> RoutingResult:
        supplier, reason = await resolve_supplier(
            session,
            tenant_id=email.tenant_id,
            from_address=email.from_address,
            subject=email.subject,
        )

        if supplier is None:
            return RoutingResult(
                status="routed",
                draft_supplier_id=None,
                notes={
                    "supplier_resolution": reason,
                    "attachments": [a.filename for a in attachments],
                },
            )

        portal = (await session.execute(select(Portal).limit(1))).scalars().first()
        if portal is None:
            return RoutingResult(
                status="routed",
                draft_supplier_id=supplier.id,
                notes={"supplier_resolution": reason, "error": "no_portal_seeded"},
            )

        submission = SupplierSubmission(
            tenant_id=email.tenant_id,
            supplier_id=supplier.id,
            portal_id=portal.id,
            status=SubmissionStatus.BLOCKED,
            payload_json={
                "source": "inbound_email",
                "inbound_email_id": email.id,
                "from_address": email.from_address,
                "subject": email.subject,
                "attachment_ids": [a.id for a in attachments],
                "supplier_resolution": reason,
            },
            last_error="inbound_email_pending_operator_review",
        )
        session.add(submission)
        await session.flush()

        _logger.info(
            "inbound.submission_drafted",
            email_id=email.id,
            supplier_id=supplier.id,
            submission_id=submission.id,
            resolution=reason,
        )

        return RoutingResult(
            status="routed",
            draft_submission_id=submission.id,
            draft_supplier_id=supplier.id,
            notes={"supplier_resolution": reason},
        )
