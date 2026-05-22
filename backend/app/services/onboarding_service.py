"""L3.6 — Self-serve onboarding state machine.

State flow::

    START
      └─ EMAIL_PENDING
           └─ EMAIL_VERIFIED
                └─ PROFILE  (↔ START allowed for re-edit)
                     └─ PLAN
                          └─ PORTAL
                               └─ SUPPLIER
                                    └─ SUBMISSION
                                         └─ DONE

* All forward transitions are **idempotent** — submitting the same step
  twice is a no-op, never an error, so a retried POST never breaks the
  flow.
* Only ``PLAN``, ``PORTAL``, ``SUPPLIER``, ``SUBMISSION`` are skippable.
* Once ``DONE`` is reached the row is frozen.

The session token / endpoints live in
:mod:`app.api.v1.onboarding` — this module is pure domain logic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OnboardingState, OnboardingStep
from app.utils.logging import get_logger

__all__ = [
    "STEP_ORDER",
    "SKIPPABLE_STEPS",
    "is_forward_transition",
    "create_state",
    "get_state",
    "advance_to",
    "skip_step",
    "mark_completed",
    "OnboardingStateError",
]


_logger = get_logger(__name__)


STEP_ORDER: tuple[OnboardingStep, ...] = (
    OnboardingStep.START,
    OnboardingStep.EMAIL_PENDING,
    OnboardingStep.EMAIL_VERIFIED,
    OnboardingStep.PROFILE,
    OnboardingStep.PLAN,
    OnboardingStep.PORTAL,
    OnboardingStep.SUPPLIER,
    OnboardingStep.SUBMISSION,
    OnboardingStep.DONE,
)


SKIPPABLE_STEPS: frozenset[OnboardingStep] = frozenset(
    {
        OnboardingStep.PLAN,
        OnboardingStep.PORTAL,
        OnboardingStep.SUPPLIER,
        OnboardingStep.SUBMISSION,
    }
)


# The only backward arrow allowed is PROFILE -> START (re-edit).
_BACKWARD_ALLOWED: frozenset[tuple[OnboardingStep, OnboardingStep]] = frozenset(
    {(OnboardingStep.PROFILE, OnboardingStep.START)}
)


def _step_index(step: OnboardingStep) -> int:
    return STEP_ORDER.index(step)


def is_forward_transition(current: OnboardingStep, target: OnboardingStep) -> bool:
    return _step_index(target) > _step_index(current)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class OnboardingStateError(HTTPException):
    """HTTP 409 — invalid step transition."""

    def __init__(self, *, current: OnboardingStep, target: OnboardingStep) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "invalid_onboarding_transition",
                "message": (
                    f"Cannot transition onboarding from {current.value!r} to "
                    f"{target.value!r}."
                ),
                "current_step": current.value,
                "target_step": target.value,
            },
        )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_state(
    session: AsyncSession,
    *,
    tenant_id: str,
    primary_user_id: str | None = None,
    initial_step: OnboardingStep = OnboardingStep.EMAIL_PENDING,
) -> OnboardingState:
    """Idempotently create the per-tenant onboarding row.

    If a row already exists for ``tenant_id`` it is returned unchanged.
    """

    existing = await get_state(session, tenant_id=tenant_id, allow_missing=True)
    if existing is not None:
        return existing

    state = OnboardingState(
        tenant_id=tenant_id,
        current_step=initial_step,
        primary_user_id=primary_user_id,
        completed_steps={OnboardingStep.START.value: _utcnow().isoformat()},
        skipped_steps={},
        step_data_json={},
    )
    session.add(state)
    await session.flush()
    _logger.info(
        "onboarding_state_created",
        tenant_id=tenant_id,
        initial_step=initial_step.value,
    )
    return state


async def get_state(
    session: AsyncSession,
    *,
    tenant_id: str,
    allow_missing: bool = False,
) -> OnboardingState | None:
    stmt = select(OnboardingState).where(OnboardingState.tenant_id == tenant_id)
    result = await session.execute(stmt)
    state = result.scalar_one_or_none()
    if state is None and not allow_missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "onboarding_state_not_found",
                "message": "No onboarding session for this tenant.",
            },
        )
    return state


def _mark_completed(state: OnboardingState, step: OnboardingStep) -> None:
    # Note: SQLAlchemy doesn't detect in-place dict mutation on JSON
    # columns unless the dict is reassigned.
    completed = dict(state.completed_steps or {})
    completed[step.value] = _utcnow().isoformat()
    state.completed_steps = completed
    state.last_activity_at = _utcnow()


def _mark_skipped(state: OnboardingState, step: OnboardingStep) -> None:
    skipped = dict(state.skipped_steps or {})
    skipped[step.value] = _utcnow().isoformat()
    state.skipped_steps = skipped


async def advance_to(
    session: AsyncSession,
    *,
    tenant_id: str,
    target: OnboardingStep,
    step_data: dict[str, Any] | None = None,
) -> OnboardingState:
    """Forward-advance the state to ``target``.

    Idempotent: if ``current_step >= target`` we still record ``step_data``
    but do not move backwards (unless the transition is explicitly
    allowed in :data:`_BACKWARD_ALLOWED`).
    """

    state = await get_state(session, tenant_id=tenant_id)
    if state is None:  # pragma: no cover - get_state raises unless allow_missing=True
        raise RuntimeError("onboarding state missing")
    current = state.current_step

    if current == OnboardingStep.DONE and target != OnboardingStep.DONE:
        raise OnboardingStateError(current=current, target=target)

    is_backward = _step_index(target) < _step_index(current)
    if is_backward and (current, target) not in _BACKWARD_ALLOWED:
        raise OnboardingStateError(current=current, target=target)

    if step_data:
        merged = dict(state.step_data_json or {})
        merged.update(step_data)
        state.step_data_json = merged

    # Idempotent forward: stay at higher step but record completion of `target`.
    new_step = target if _step_index(target) >= _step_index(current) else target
    state.current_step = new_step
    _mark_completed(state, target)
    await session.flush()
    _logger.info(
        "onboarding_state_advanced",
        tenant_id=tenant_id,
        from_step=current.value,
        to_step=new_step.value,
    )
    return state


async def skip_step(
    session: AsyncSession,
    *,
    tenant_id: str,
    step: OnboardingStep,
) -> OnboardingState:
    if step not in SKIPPABLE_STEPS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "step_not_skippable",
                "message": f"Step {step.value!r} cannot be skipped.",
            },
        )
    state = await get_state(session, tenant_id=tenant_id)
    if state is None:  # pragma: no cover - get_state raises unless allow_missing=True
        raise RuntimeError("onboarding state missing")

    if state.current_step == OnboardingStep.DONE:
        raise OnboardingStateError(current=state.current_step, target=step)

    _mark_skipped(state, step)
    # Advance to the next step after the skipped one.
    idx = _step_index(step)
    next_step = STEP_ORDER[min(idx + 1, len(STEP_ORDER) - 1)]
    # Idempotent: never move backwards.
    if _step_index(next_step) > _step_index(state.current_step):
        state.current_step = next_step
    state.last_activity_at = _utcnow()
    await session.flush()
    _logger.info(
        "onboarding_step_skipped",
        tenant_id=tenant_id,
        step=step.value,
        advanced_to=state.current_step.value,
    )
    return state


async def mark_completed(
    session: AsyncSession, *, tenant_id: str
) -> OnboardingState:
    """Finalize the onboarding journey."""

    state = await get_state(session, tenant_id=tenant_id)
    if state is None:  # pragma: no cover - get_state raises unless allow_missing=True
        raise RuntimeError("onboarding state missing")
    if state.current_step == OnboardingStep.DONE:
        return state
    state.current_step = OnboardingStep.DONE
    state.completed_at = _utcnow()
    _mark_completed(state, OnboardingStep.DONE)
    await session.flush()
    _logger.info("onboarding_completed", tenant_id=tenant_id)
    return state
