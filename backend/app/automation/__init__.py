from __future__ import annotations

from app.automation.base import BaseSubmitter, SubmitterOutcome
from app.automation.detector import detect_portal, is_risky

__all__ = [
    "BaseSubmitter",
    "SubmitterOutcome",
    "detect_portal",
    "is_risky",
]
