"""structlog processor that scrubs secrets from log events.

Used as a processor in the ``structlog`` pipeline (see
``app.utils.logging``).  It is intentionally exposed as a *function* so it can
also be applied to dict-shaped payloads from anywhere in the codebase (e.g.
audit log metadata).

Design notes:

* **Fail-open for logging, fail-closed for secrets**: if the regex pass
  raises (e.g. exotic Unicode triggers a bug) we still return the event with
  key-based redaction applied — the worst case is a value we did not scrub,
  but we **never** crash the logger.
* **Whitelist by key**: ``username``, ``user_id``, ``tenant_id``,
  ``request_id``, ``trace_id``, ``service``, ``level``, ``timestamp``,
  ``event``, ``message``, ``status_code``, ``method``, ``path``,
  ``duration_ms``, ``ip``, ``ip_address`` are considered safe and pass
  through.
* **Email**: emails are partially redacted (``ab***@example.com``).
* **Recursion**: walks nested dicts and list values to any depth.  A
  recursion guard caps depth at 16 to defeat hostile cycles.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, MutableMapping
from typing import Any

__all__ = [
    "REDACTED",
    "SENSITIVE_KEYS",
    "WHITELIST_KEYS",
    "redact_secrets",
    "redact_event_dict",
    "structlog_redactor",
]


REDACTED: str = "[REDACTED]"

# Keys whose value is always redacted (substring match, case-insensitive).
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "passphrase",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "set-cookie",
        "private_key",
        "signing_key",
        "client_secret",
        "aws_secret",
        "aws_secret_access_key",
        "stripe_key",
        "stripe_secret_key",
        "stripe_publishable_key",
        "database_url",
        "credit_card",
        "card_number",
        "ssn",
        "ein",
        "session_id",
        "refresh_token",
        "access_token",
        "jwt",
    }
)

# Keys that always bypass redaction even if they appear to match a sensitive
# substring (e.g. ``user_id`` would otherwise be flagged by ``id`` rules).
WHITELIST_KEYS: frozenset[str] = frozenset(
    {
        "username",
        "user_id",
        "tenant_id",
        "request_id",
        "trace_id",
        "span_id",
        "service",
        "level",
        "timestamp",
        "event",
        "message",
        "status_code",
        "method",
        "path",
        "duration_ms",
        "ip",
        "ip_address",
        "logger",
    }
)

# Heuristic value-pattern redaction.
# Tightened to reduce false positives on normal IDs / hashes used elsewhere.
_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # AWS access key IDs (AKIA / ASIA / etc.)
    re.compile(r"\bA(?:KIA|SIA|GPA|IDA|ROA|IPA|NPA|NVA)[0-9A-Z]{16}\b"),
    # AWS secret access keys (40 char base64-ish)
    re.compile(r"\b[A-Za-z0-9/+=]{40}\b"),
    # JWTs (three base64url segments).
    re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b"),
    # Generic "very long opaque token" — be conservative (>= 48 chars).
    re.compile(r"\b[A-Za-z0-9_\-]{48,}\b"),
)

_EMAIL_RE = re.compile(r"^([^@\s]+)@([^@\s]+)$")
_MAX_DEPTH = 16


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    if lowered in WHITELIST_KEYS:
        return False
    for needle in SENSITIVE_KEYS:
        if needle in lowered:
            return True
    return False


def _redact_email(value: str) -> str:
    match = _EMAIL_RE.match(value)
    if not match:
        return value
    local, domain = match.group(1), match.group(2)
    prefix = local[:3] if len(local) > 3 else local[:1]
    return f"{prefix}***@{domain}"


def _redact_value_regex(value: str) -> str:
    try:
        for pattern in _VALUE_PATTERNS:
            value = pattern.sub(REDACTED, value)
    except Exception:  # pragma: no cover - defensive: never break logging
        return value
    return value


def _walk(node: Any, *, depth: int = 0, key_hint: str | None = None) -> Any:
    if depth > _MAX_DEPTH:
        return REDACTED
    if isinstance(node, MutableMapping):
        out: dict[Any, Any] = {}
        for k, v in node.items():
            k_str = str(k)
            if _is_sensitive_key(k_str):
                out[k] = REDACTED
            else:
                out[k] = _walk(v, depth=depth + 1, key_hint=k_str)
        return out
    if isinstance(node, list | tuple):
        rebuilt = [_walk(item, depth=depth + 1, key_hint=key_hint) for item in node]
        return type(node)(rebuilt) if isinstance(node, tuple) else rebuilt
    if isinstance(node, set | frozenset):
        return type(node)(_walk(item, depth=depth + 1, key_hint=key_hint) for item in node)
    if isinstance(node, str):
        # Whitelisted-key emails get partial redaction; everything else gets
        # the regex sweep.
        if key_hint and key_hint.lower() == "email":
            return _redact_email(node)
        return _redact_value_regex(node)
    return node


def redact_secrets(payload: Any) -> Any:
    """Public helper: deep-copy ``payload`` with secrets replaced."""

    return _walk(payload, depth=0)


def redact_event_dict(event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Apply redaction to a structlog event_dict and return a new dict."""

    return _walk(event_dict, depth=0)


def structlog_redactor(_logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """structlog processor signature."""

    try:
        return _walk(event_dict, depth=0)
    except Exception:  # pragma: no cover - never break logging
        return event_dict


# Quiet unused-import warnings from type checkers in lean envs.
_ = Iterable
