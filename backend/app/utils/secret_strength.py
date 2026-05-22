"""SECRET_KEY / JWT_SECRET_KEY strength validation.

Used at app boot to refuse-to-start in production when configured secrets
are too short or too predictable.  In development we degrade to a warning
so contributors aren't blocked.

Entropy estimate uses the Shannon entropy of the byte distribution times the
length of the key, which is the standard back-of-envelope number used by
crypto libraries.  A strong random 32-char base64 secret comfortably exceeds
the 128-bit threshold.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

__all__ = [
    "SecretStrengthResult",
    "evaluate_secret",
    "MIN_LENGTH",
    "MIN_ENTROPY_BITS",
    "WEAK_PLACEHOLDERS",
]


MIN_LENGTH: int = 32
MIN_ENTROPY_BITS: float = 128.0

WEAK_PLACEHOLDERS: frozenset[str] = frozenset(
    {
        "", "changeme", "change-me", "changeme!", "placeholder", "secret",
        "your-secret-here", "todo", "tbd", "supersecret", "topsecret",
        "password", "test", "dev", "development",
    }
)


@dataclass(slots=True, frozen=True)
class SecretStrengthResult:
    name: str
    strong: bool
    length: int
    entropy_bits: float
    reasons: tuple[str, ...]

    @property
    def label(self) -> str:
        return "strong" if self.strong else "weak"


def _shannon_entropy_bits(value: str) -> float:
    if not value:
        return 0.0
    counts = Counter(value)
    total = float(len(value))
    per_char = -sum((c / total) * math.log2(c / total) for c in counts.values())
    return per_char * total


def evaluate_secret(name: str, value: str | None) -> SecretStrengthResult:
    """Score a secret. Returns ``strong=True`` only when **all** checks pass."""

    reasons: list[str] = []
    candidate = (value or "").strip()
    length = len(candidate)
    entropy = _shannon_entropy_bits(candidate)

    if length == 0:
        reasons.append("empty")
    if length < MIN_LENGTH:
        reasons.append(f"too_short_min_{MIN_LENGTH}")
    if candidate.lower() in WEAK_PLACEHOLDERS:
        reasons.append("placeholder_value")
    if entropy < MIN_ENTROPY_BITS:
        reasons.append(f"entropy_below_{int(MIN_ENTROPY_BITS)}_bits")

    return SecretStrengthResult(
        name=name,
        strong=not reasons,
        length=length,
        entropy_bits=round(entropy, 2),
        reasons=tuple(reasons),
    )
