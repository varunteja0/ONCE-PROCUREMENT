"""Slack incoming-webhook notifier (Phase 4 portal-drift alerting).

A tiny, dependency-light wrapper around ``httpx.post`` that delivers a
structured Slack Block-Kit payload to the configured incoming webhook. The
module is intentionally side-effect-free at import time:

* If :env:`SLACK_WEBHOOK_URL` is empty the notifier becomes a no-op (returns
  ``False`` and structlog-logs ``slack_notifier_disabled``). This keeps local
  dev and CI quiet while leaving the production wiring identical.

* All HTTP failures are swallowed and logged — Slack outages MUST NOT crash
  the Celery smoke-test beat task.

Severities follow the operator runbook:

* ``critical`` — red bar, ``@here`` mention (selector drift, captcha block).
* ``warning``  — orange bar (transient timeout, persistent failure).
* ``info``     — green bar (recovery / pass-after-fail).

The shape of the outgoing payload is deliberately stable; the unit test in
``backend/tests/test_slack_notifier.py`` snapshots it so changes are visible
in code review.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from app.config import settings
from app.utils.logging import get_logger

__all__ = [
    "Severity",
    "SlackNotifier",
    "build_drift_payload",
    "build_recovery_payload",
    "build_persistent_failure_payload",
    "get_default_notifier",
]

_logger = get_logger(__name__)

Severity = Literal["critical", "warning", "info"]

_SEVERITY_COLOR: dict[Severity, str] = {
    "critical": "#dc2626",
    "warning": "#ea580c",
    "info": "#10b981",
}

_SEVERITY_EMOJI: dict[Severity, str] = {
    "critical": ":rotating_light:",
    "warning": ":warning:",
    "info": ":white_check_mark:",
}


class SlackNotifier:
    """Posts Block-Kit messages to a Slack incoming webhook."""

    def __init__(
        self,
        *,
        webhook_url: str | None = None,
        channel: str | None = None,
        timeout_sec: float = 5.0,
    ) -> None:
        self.webhook_url: str = (webhook_url if webhook_url is not None else settings.slack_webhook_url)
        self.channel: str = channel or settings.slack_alert_channel
        self.timeout_sec: float = timeout_sec

    @property
    def enabled(self) -> bool:
        return bool(self.webhook_url)

    def notify(
        self,
        *,
        title: str,
        severity: Severity,
        body_lines: list[str],
        fields: dict[str, str] | None = None,
        mention_here: bool = False,
    ) -> bool:
        """Send a Slack message. Returns True on 2xx, False otherwise/disabled."""

        if not self.enabled:
            _logger.info(
                "slack_notifier_disabled",
                title=title,
                severity=severity,
            )
            return False

        payload = self._build_payload(
            title=title,
            severity=severity,
            body_lines=body_lines,
            fields=fields or {},
            mention_here=mention_here,
        )
        try:
            response = httpx.post(
                self.webhook_url,
                json=payload,
                timeout=self.timeout_sec,
            )
        except httpx.HTTPError as exc:
            _logger.warning(
                "slack_notifier_http_error",
                title=title,
                severity=severity,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return False

        if response.status_code >= 400:
            _logger.warning(
                "slack_notifier_non_2xx",
                title=title,
                severity=severity,
                status=response.status_code,
                body=response.text[:200],
            )
            return False

        _logger.info(
            "slack_notifier_delivered",
            title=title,
            severity=severity,
            status=response.status_code,
        )
        return True

    def _build_payload(
        self,
        *,
        title: str,
        severity: Severity,
        body_lines: list[str],
        fields: dict[str, str],
        mention_here: bool,
    ) -> dict[str, Any]:
        emoji = _SEVERITY_EMOJI[severity]
        color = _SEVERITY_COLOR[severity]
        ts_iso = datetime.now(UTC).isoformat()

        header_text = f"{emoji} {title}"
        body_text = "\n".join(body_lines) if body_lines else "_(no detail)_"
        if mention_here:
            body_text = "<!here>\n" + body_text

        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": header_text[:150], "emoji": True},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": body_text[:2900]},
            },
        ]

        if fields:
            blocks.append(
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*{k}*\n{v}"[:2000]}
                        for k, v in fields.items()
                    ][:10],
                }
            )

        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Once portal-drift monitor · {ts_iso}",
                    }
                ],
            }
        )

        return {
            "channel": self.channel,
            "username": "Once portal-monitor",
            "icon_emoji": ":lock:",
            "attachments": [
                {
                    "color": color,
                    "blocks": blocks,
                }
            ],
        }


# ---------------------------------------------------------------------------
# Payload builders shared by the smoke-test task and ad-hoc callers.
# ---------------------------------------------------------------------------


def build_drift_payload(
    *,
    platform: str,
    error: str | None,
    submitter: str,
    duration_sec: float,
) -> dict[str, Any]:
    """Return kwargs for :meth:`SlackNotifier.notify` when a portal newly fails."""

    return {
        "title": f"Portal DRIFT detected — {platform}",
        "severity": "critical",
        "body_lines": [
            f"*{platform}* smoke-test transitioned PASS → FAIL.",
            "Operator action required: confirm selector update, push hotfix, "
            "and re-arm submitter.",
        ],
        "fields": {
            "Submitter": submitter,
            "Error": (error or "(no error string)")[:500],
            "Duration": f"{duration_sec:.2f}s",
        },
        "mention_here": True,
    }


def build_persistent_failure_payload(
    *,
    platform: str,
    error: str | None,
    submitter: str,
    consecutive_failures: int,
    duration_sec: float,
) -> dict[str, Any]:
    return {
        "title": f"Portal still failing — {platform} ({consecutive_failures}x)",
        "severity": "warning",
        "body_lines": [
            f"*{platform}* smoke-test still failing after "
            f"{consecutive_failures} consecutive runs.",
        ],
        "fields": {
            "Submitter": submitter,
            "Error": (error or "(no error string)")[:500],
            "Duration": f"{duration_sec:.2f}s",
        },
        "mention_here": False,
    }


def build_recovery_payload(
    *,
    platform: str,
    submitter: str,
    downtime_sec: float,
) -> dict[str, Any]:
    return {
        "title": f"Portal RECOVERED — {platform}",
        "severity": "info",
        "body_lines": [
            f"*{platform}* smoke-test is passing again.",
            f"Approximate downtime: {downtime_sec / 60:.1f} min.",
        ],
        "fields": {"Submitter": submitter},
        "mention_here": False,
    }


_default_notifier: SlackNotifier | None = None


def get_default_notifier() -> SlackNotifier:
    """Return a process-wide cached notifier built from current settings."""

    global _default_notifier
    if _default_notifier is None:
        _default_notifier = SlackNotifier()
    return _default_notifier
