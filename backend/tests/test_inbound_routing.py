"""L3.9 — Routing engine tests."""

from __future__ import annotations

from app.models.inbound_routing_rule import InboundRoutingRule, InboundRuleAction
from app.services.inbound_email_service import select_rule


def _rule(**kw) -> InboundRoutingRule:
    base = dict(
        id=kw.get("id", "r"),
        tenant_id="t1",
        name=kw.get("name", "rule"),
        priority=kw.get("priority", 100),
        match_from_domain=kw.get("from_domain"),
        match_subject_regex=kw.get("subject"),
        match_attachment_kind=kw.get("att_kind"),
        action=kw.get("action", InboundRuleAction.CREATE_SUBMISSION),
        action_params=None,
        active=True,
    )
    return InboundRoutingRule(**base)


def test_fallback_when_no_rules():
    out = select_rule(
        [], tenant_id="t1", from_address="a@x.com", subject=None, attachment_kinds=set()
    )
    assert out.id == "__fallback__"
    assert out.priority == 999


def test_priority_ordering_first_match_wins():
    rules = [
        _rule(id="r10", priority=10, from_domain="x.com", action=InboundRuleAction.QUARANTINE),
        _rule(id="r5", priority=5, from_domain="x.com", action=InboundRuleAction.CREATE_SUBMISSION),
    ]
    rules.sort(key=lambda r: r.priority)
    out = select_rule(
        rules, tenant_id="t1", from_address="a@x.com", subject=None, attachment_kinds=set()
    )
    assert out.id == "r5"


def test_from_domain_match():
    r = _rule(from_domain="amtrust.com")
    assert select_rule(
        [r], tenant_id="t1", from_address="quote@amtrust.com", subject=None, attachment_kinds=set()
    ).id == "r"


def test_from_domain_mismatch_falls_through():
    r = _rule(from_domain="amtrust.com")
    out = select_rule(
        [r], tenant_id="t1", from_address="quote@other.com", subject=None, attachment_kinds=set()
    )
    assert out.id == "__fallback__"


def test_subject_regex_match():
    r = _rule(subject=r"renewal\s+coi")
    assert select_rule(
        [r], tenant_id="t1", from_address="x@y.com", subject="Renewal COI 2026", attachment_kinds=set()
    ).id == "r"


def test_subject_regex_no_match():
    r = _rule(subject=r"^URGENT:")
    out = select_rule(
        [r], tenant_id="t1", from_address="x@y.com", subject="quote", attachment_kinds=set()
    )
    assert out.id == "__fallback__"


def test_attachment_kind_match():
    r = _rule(att_kind="pdf")
    out = select_rule(
        [r], tenant_id="t1", from_address="x@y.com", subject=None, attachment_kinds={"pdf"}
    )
    assert out.id == "r"


def test_attachment_kind_mismatch():
    r = _rule(att_kind="xlsx")
    out = select_rule(
        [r], tenant_id="t1", from_address="x@y.com", subject=None, attachment_kinds={"pdf"}
    )
    assert out.id == "__fallback__"


def test_compound_match_requires_all_criteria():
    r = _rule(from_domain="amtrust.com", subject="quote", att_kind="pdf")
    # Missing attachment_kind → fall through.
    out = select_rule(
        [r], tenant_id="t1", from_address="x@amtrust.com", subject="quote attached", attachment_kinds={"csv"}
    )
    assert out.id == "__fallback__"
    # All three match → win.
    out2 = select_rule(
        [r], tenant_id="t1", from_address="x@amtrust.com", subject="quote attached", attachment_kinds={"pdf"}
    )
    assert out2.id == "r"


def test_invalid_regex_does_not_crash():
    r = _rule(subject="(*)bad")
    out = select_rule(
        [r], tenant_id="t1", from_address="x@y.com", subject="anything", attachment_kinds=set()
    )
    assert out.id == "__fallback__"


def test_priority_zero_runs_before_default():
    rules = [
        _rule(id="r0", priority=0, action=InboundRuleAction.QUARANTINE),
        _rule(id="r100", priority=100, action=InboundRuleAction.CREATE_SUBMISSION),
    ]
    out = select_rule(
        rules, tenant_id="t1", from_address="x@y.com", subject=None, attachment_kinds=set()
    )
    assert out.id == "r0"
    assert out.action == InboundRuleAction.QUARANTINE
