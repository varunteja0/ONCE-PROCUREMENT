"""L3.9 — Inbound router registry."""

from __future__ import annotations

from app.models.inbound_routing_rule import InboundRuleAction

from .base import InboundRouter, RoutingResult
from .submission_creator import SubmissionCreatorRouter

__all__ = [
    "RoutingResult",
    "InboundRouter",
    "get_router",
    "register_router",
    "ROUTER_REGISTRY",
]


ROUTER_REGISTRY: dict[InboundRuleAction, InboundRouter] = {}


def register_router(action: InboundRuleAction, router: InboundRouter) -> None:
    ROUTER_REGISTRY[action] = router


def get_router(action: InboundRuleAction) -> InboundRouter | None:
    return ROUTER_REGISTRY.get(action)


register_router(InboundRuleAction.CREATE_SUBMISSION, SubmissionCreatorRouter())


class _NoopRouter(InboundRouter):
    name = "noop"

    async def route(self, session, *, email, attachments, rule):  # type: ignore[override]
        return RoutingResult(status="routed", notes={"action": rule.action.value})


class _QuarantineRouter(InboundRouter):
    name = "quarantine"

    async def route(self, session, *, email, attachments, rule):  # type: ignore[override]
        return RoutingResult(
            status="quarantined",
            notes={"reason": "matched_rule", "rule_id": rule.id},
        )


register_router(InboundRuleAction.QUARANTINE, _QuarantineRouter())
register_router(InboundRuleAction.DISCARD, _NoopRouter())
register_router(InboundRuleAction.TAG_ONLY, _NoopRouter())
