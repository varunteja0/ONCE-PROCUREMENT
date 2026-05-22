"""L3.6 — Onboarding state machine model.

One row per tenant. Tracks the current step of the self-serve wizard, the
list of completed steps (with timestamps), and a JSON blob for per-step
draft inputs so a user can resume after a refresh.

The state machine itself lives in
:mod:`app.services.onboarding_service` — this module is intentionally a
dumb persistence layer.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OnboardingStep(str, enum.Enum):
    """Ordered self-serve onboarding steps. Order matters — see
    :func:`app.services.onboarding_service.STEP_ORDER`."""

    START = "start"
    EMAIL_PENDING = "email_pending"
    EMAIL_VERIFIED = "email_verified"
    PROFILE = "profile"
    PLAN = "plan"
    PORTAL = "portal"
    SUPPLIER = "supplier"
    SUBMISSION = "submission"
    DONE = "done"


class OnboardingState(Base):
    """Per-tenant onboarding progress.

    ``tenant_id`` is the primary key (1:1 with tenants) — there is exactly
    one onboarding journey per tenant.
    """

    __tablename__ = "onboarding_states"

    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    current_step: Mapped[OnboardingStep] = mapped_column(
        Enum(OnboardingStep, name="onboarding_step", native_enum=False, length=32),
        nullable=False,
        default=OnboardingStep.START,
    )
    completed_steps: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    skipped_steps: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    step_data_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    company_profile_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    primary_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


__all__ = ["OnboardingState", "OnboardingStep"]
