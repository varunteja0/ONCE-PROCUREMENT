"""L3.9 — Spam-score stub.

A real deployment plugs this into rspamd / SpamAssassin via HTTP. For
now we emit a deterministic heuristic 0.0..1.0 so the rest of the
pipeline can branch on score without depending on an external service.

The score is intentionally CONSERVATIVE — false positives starve the
pitch surface (broker-forwarded quotes look spammy to naive scorers).
Anything ≥ 0.9 should be quarantined; the orchestrator owns that
decision.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

__all__ = ["score_spam", "QUARANTINE_THRESHOLD"]


QUARANTINE_THRESHOLD: float = 0.9

_SPAM_KEYWORDS: tuple[str, ...] = (
    "viagra",
    "bitcoin",
    "free money",
    "click here now",
    "act fast",
    "100% guaranteed",
    "nigerian prince",
    "lottery winner",
)


def _kw_hits(text: str) -> int:
    if not text:
        return 0
    lowered = text.lower()
    return sum(1 for kw in _SPAM_KEYWORDS if kw in lowered)


def score_spam(
    *,
    from_address: str,
    subject: str | None,
    body_text: str | None,
    headers: Mapping[str, object] | None = None,
) -> float:
    """Return a float 0..1 — higher = spammier."""

    score = 0.0

    hits = _kw_hits(subject or "") + _kw_hits(body_text or "")
    score += min(0.6, hits * 0.2)

    # All-caps subject is mildly suspicious.
    if subject and len(subject) > 8 and subject == subject.upper():
        score += 0.1

    # Bare numeric local-part + free-mail TLD looks like a bot.
    if re.match(r"^\d{6,}@", from_address or ""):
        score += 0.2

    # Header signal: explicit X-Spam-Flag=YES
    if headers:
        for key, value in headers.items():
            if str(key).lower() == "x-spam-flag" and str(value).strip().lower() == "yes":
                score = max(score, 0.95)

    return min(1.0, round(score, 3))
