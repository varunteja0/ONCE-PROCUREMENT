"""L3.9 — REST API for the inbound email pipeline.

Tenant-scoped:

* ``GET    /v1/inbound``                        — list emails
* ``GET    /v1/inbound/{id}``                   — detail + attachments
* ``POST   /v1/inbound/{id}/retry``             — re-run routing
* ``POST   /v1/inbound/{id}/quarantine``        — manual quarantine
* ``GET    /v1/inbound/rules``                  — list rules
* ``POST   /v1/inbound/rules``                  — create rule
* ``PATCH  /v1/inbound/rules/{id}``             — update rule
* ``DELETE /v1/inbound/rules/{id}``             — delete rule
* ``POST   /v1/inbound/rules/reorder``          — bulk re-prioritize
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId
from app.db import get_db
from app.models.inbound_attachment import InboundAttachment
from app.models.inbound_email import InboundEmail, InboundEmailStatus
from app.models.inbound_routing_rule import InboundRoutingRule, InboundRuleAction
from app.schemas.inbound import (
    InboundAttachmentRead,
    InboundEmailDetail,
    InboundEmailListItem,
    InboundRetryResponse,
    InboundRuleCreate,
    InboundRuleRead,
    InboundRuleReorder,
    InboundRuleUpdate,
)
from app.services import inbound_email_service

__all__ = ["router"]

router = APIRouter(prefix="/inbound", tags=["inbound"])


def _email_to_list(row: InboundEmail) -> InboundEmailListItem:
    return InboundEmailListItem(
        id=row.id,
        tenant_id=row.tenant_id,
        message_id=row.message_id,
        from_address=row.from_address,
        from_name=row.from_name,
        to_address=row.to_address,
        subject=row.subject,
        received_at=row.received_at,
        status=row.status.value,
        spam_score=row.spam_score,
        routing_error=row.routing_error,
        attachment_count=row.attachment_count,
        draft_submission_id=row.draft_submission_id,
        draft_supplier_id=row.draft_supplier_id,
    )


def _rule_to_read(rule: InboundRoutingRule) -> InboundRuleRead:
    return InboundRuleRead(
        id=rule.id,
        tenant_id=rule.tenant_id,
        name=rule.name,
        priority=rule.priority,
        match_from_domain=rule.match_from_domain,
        match_subject_regex=rule.match_subject_regex,
        match_attachment_kind=rule.match_attachment_kind,
        action=rule.action.value,
        action_params=rule.action_params,
        active=rule.active,
        created_at=rule.created_at,
    )


# ---------------------------------------------------------------------------
# Emails
# ---------------------------------------------------------------------------


@router.get("", response_model=list[InboundEmailListItem])
async def list_emails(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    response: Response,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[InboundEmailListItem]:
    stmt = select(InboundEmail).where(InboundEmail.tenant_id == tenant_id)
    if status_filter:
        try:
            parsed_status = InboundEmailStatus(status_filter)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid_status") from exc
        stmt = stmt.where(InboundEmail.status == parsed_status)
    stmt = stmt.order_by(InboundEmail.received_at.desc()).limit(limit).offset(offset)
    rows = list((await session.execute(stmt)).scalars().all())

    total_stmt = select(InboundEmail.id).where(InboundEmail.tenant_id == tenant_id)
    if status_filter:
        total_stmt = total_stmt.where(InboundEmail.status == InboundEmailStatus(status_filter))
    total = len(list((await session.execute(total_stmt)).scalars().all()))
    response.headers["x-total-count"] = str(total)

    return [_email_to_list(r) for r in rows]


@router.get("/{email_id}", response_model=InboundEmailDetail)
async def get_email(
    email_id: str,
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> InboundEmailDetail:
    email = await session.get(InboundEmail, email_id)
    if email is None or email.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="not_found")
    att_rows = list(
        (
            await session.execute(
                select(InboundAttachment).where(InboundAttachment.inbound_email_id == email.id)
            )
        )
        .scalars()
        .all()
    )
    base = _email_to_list(email)
    return InboundEmailDetail(
        **base.model_dump(),
        in_reply_to=email.in_reply_to,
        cc_addresses=email.cc_addresses,
        raw_body_text=email.raw_body_text,
        raw_body_html=email.raw_body_html,
        headers=email.headers,
        raw_storage_url=email.raw_storage_url,
        attachments=[
            InboundAttachmentRead(
                id=a.id,
                filename=a.filename,
                content_type=a.content_type,
                size_bytes=a.size_bytes,
                sha256=a.sha256,
                storage_url=a.storage_url,
                scanned_at=a.scanned_at,
            )
            for a in att_rows
        ],
    )


@router.post("/{email_id}/retry", response_model=InboundRetryResponse)
async def retry_email(
    email_id: str,
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> InboundRetryResponse:
    email = await session.get(InboundEmail, email_id)
    if email is None or email.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="not_found")
    try:
        updated = await inbound_email_service.retry_routing(
            session, tenant_id=tenant_id, email_id=email_id
        )
    except inbound_email_service.InboundIngestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InboundRetryResponse(
        id=updated.id, status=updated.status.value, routing_error=updated.routing_error
    )


@router.post("/{email_id}/quarantine", response_model=InboundRetryResponse)
async def quarantine_email(
    email_id: str,
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> InboundRetryResponse:
    email = await session.get(InboundEmail, email_id)
    if email is None or email.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="not_found")
    updated = await inbound_email_service.quarantine(
        session, tenant_id=tenant_id, email_id=email_id
    )
    return InboundRetryResponse(
        id=updated.id, status=updated.status.value, routing_error=updated.routing_error
    )


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


@router.get("/rules", response_model=list[InboundRuleRead])
async def list_rules(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[InboundRuleRead]:
    stmt = (
        select(InboundRoutingRule)
        .where(InboundRoutingRule.tenant_id == tenant_id)
        .order_by(InboundRoutingRule.priority.asc(), InboundRoutingRule.created_at.asc())
    )
    return [_rule_to_read(r) for r in (await session.execute(stmt)).scalars().all()]


@router.post("/rules", response_model=InboundRuleRead, status_code=201)
async def create_rule(
    payload: InboundRuleCreate,
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> InboundRuleRead:
    rule = InboundRoutingRule(
        tenant_id=tenant_id,
        name=payload.name,
        priority=payload.priority,
        match_from_domain=payload.match_from_domain,
        match_subject_regex=payload.match_subject_regex,
        match_attachment_kind=payload.match_attachment_kind,
        action=InboundRuleAction(payload.action),
        action_params=payload.action_params,
        active=payload.active,
    )
    session.add(rule)
    await session.flush()
    await session.commit()
    return _rule_to_read(rule)


@router.patch("/rules/{rule_id}", response_model=InboundRuleRead)
async def update_rule(
    rule_id: str,
    payload: InboundRuleUpdate,
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> InboundRuleRead:
    rule = await session.get(InboundRoutingRule, rule_id)
    if rule is None or rule.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="not_found")
    data = payload.model_dump(exclude_unset=True)
    if "action" in data:
        rule.action = InboundRuleAction(data.pop("action"))
    for k, v in data.items():
        setattr(rule, k, v)
    await session.flush()
    await session.commit()
    return _rule_to_read(rule)


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: str,
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    rule = await session.get(InboundRoutingRule, rule_id)
    if rule is None or rule.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="not_found")
    await session.execute(
        delete(InboundRoutingRule).where(InboundRoutingRule.id == rule_id)
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/rules/reorder", response_model=list[InboundRuleRead])
async def reorder_rules(
    payload: InboundRuleReorder,
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[InboundRuleRead]:
    stmt = select(InboundRoutingRule).where(
        InboundRoutingRule.tenant_id == tenant_id,
        InboundRoutingRule.id.in_(payload.order),
    )
    rules = {r.id: r for r in (await session.execute(stmt)).scalars().all()}
    if len(rules) != len(payload.order):
        raise HTTPException(status_code=400, detail="unknown_rule_id_in_order")
    for index, rid in enumerate(payload.order):
        # Re-number priorities sparsely so manual edits remain easy.
        rules[rid].priority = (index + 1) * 10
    await session.flush()
    await session.commit()

    refreshed = select(InboundRoutingRule).where(
        InboundRoutingRule.tenant_id == tenant_id
    ).order_by(InboundRoutingRule.priority.asc())
    return [_rule_to_read(r) for r in (await session.execute(refreshed)).scalars().all()]
