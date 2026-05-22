"""L3.9 — Inbound router base class.

A *router* is a strategy invoked by ``inbound_email_service`` after a
matching :class:`InboundRoutingRule` selects it. Routers translate the
parsed email + attachments into a domain action (creating a draft
submission, quarantining, etc.).

Routers must be:

* Idempotent — re-running a router for the same email MUST NOT create
  duplicate domain rows. Use stable lookup keys (email id, message id).
* Side-effect-bounded — return a :class:`RoutingResult` describing what
  happened; let the orchestrator commit / persist on the email row.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:  # pragma: no cover
    from app.models.inbound_attachment import InboundAttachment
    from app.models.inbound_email import InboundEmail
    from app.models.inbound_routing_rule import InboundRoutingRule


__all__ = ["RoutingResult", "InboundRouter"]


@dataclass(slots=True)
class RoutingResult:
    """Outcome of a single router invocation."""

    status: str  # one of: routed, failed, quarantined
    draft_submission_id: str | None = None
    draft_supplier_id: str | None = None
    error: str | None = None
    notes: dict[str, Any] = field(default_factory=dict)


class InboundRouter:
    """Base class for routers."""

    name: str = "base"

    async def route(
        self,
        session: AsyncSession,
        *,
        email: InboundEmail,
        attachments: list[InboundAttachment],
        rule: InboundRoutingRule,
    ) -> RoutingResult:
        raise NotImplementedError
