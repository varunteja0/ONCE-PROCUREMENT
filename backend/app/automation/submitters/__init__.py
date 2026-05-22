from __future__ import annotations

from app.automation.base import BaseSubmitter
from app.models.portal import PortalPlatform

# Define the registry BEFORE importing submitter modules so each module's
# import-time `from app.automation.submitters import SUBMITTER_REGISTRY` works.
SUBMITTER_REGISTRY: dict[PortalPlatform, type[BaseSubmitter]] = {}

# Self-registering submitters (each module assigns itself into SUBMITTER_REGISTRY
# at import time — see CONTRACTS.md §12, agent 09 spec).
from app.automation.submitters import (  # noqa: E402,F401  (import-for-side-effects)
    amtrust,
    applied_epic,
    markel,
    sircon,
    vertafore_ams360,
)
from app.automation.submitters.applied_epic import AppliedEpicSubmitter  # noqa: E402

# Belt-and-suspenders: ensure Applied Epic is registered even if its module
# self-registration path changes in the future.
SUBMITTER_REGISTRY.setdefault(PortalPlatform.APPLIED_EPIC, AppliedEpicSubmitter)


def get_submitter_class(platform: PortalPlatform) -> type[BaseSubmitter] | None:
    """Return the submitter class for ``platform`` or None if unsupported."""
    return SUBMITTER_REGISTRY.get(platform)


# Backwards-compatible alias used by app.services.submission_pipeline.
def get_submitter(platform: PortalPlatform) -> type[BaseSubmitter] | None:
    return get_submitter_class(platform)


__all__ = [
    "SUBMITTER_REGISTRY",
    "AppliedEpicSubmitter",
    "get_submitter_class",
    "get_submitter",
]
