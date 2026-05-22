from __future__ import annotations

import types

import httpx
import pytest

from app.services.slack_notifier import (
    SlackNotifier,
    build_drift_payload,
    build_persistent_failure_payload,
    build_recovery_payload,
)


def _capture_post(monkeypatch: pytest.MonkeyPatch) -> dict:
    captured: dict = {}

    class _Resp:
        status_code = 200
        text = "ok"

    def _post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _Resp()

    monkeypatch.setattr("app.services.slack_notifier.httpx.post", _post)
    return captured


def test_disabled_when_webhook_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.slack_notifier.httpx.post",
        lambda *a, **k: pytest.fail("httpx.post should not be called"),
    )
    n = SlackNotifier(webhook_url="", channel="#x")
    assert n.enabled is False
    assert (
        n.notify(title="t", severity="critical", body_lines=["b"]) is False
    )


def test_notify_posts_to_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_post(monkeypatch)
    n = SlackNotifier(webhook_url="http://hooks.example/abc", channel="#x")
    assert n.notify(title="Hello", severity="critical", body_lines=["b"]) is True
    assert captured["url"] == "http://hooks.example/abc"
    header_text = captured["json"]["attachments"][0]["blocks"][0]["text"]["text"]
    assert header_text.startswith(":rotating_light:")


def test_notify_returns_false_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _post(url, json, timeout):
        raise httpx.RequestError("boom", request=httpx.Request("POST", "http://x"))

    monkeypatch.setattr("app.services.slack_notifier.httpx.post", _post)
    n = SlackNotifier(webhook_url="http://x", channel="#x")
    assert n.notify(title="t", severity="critical", body_lines=["b"]) is False


def test_notify_returns_false_on_non_2xx(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.SimpleNamespace(status_code=500, text="oops")
    monkeypatch.setattr(
        "app.services.slack_notifier.httpx.post",
        lambda url, json, timeout: fake,
    )
    n = SlackNotifier(webhook_url="http://x", channel="#x")
    assert n.notify(title="t", severity="warning", body_lines=["b"]) is False


def test_build_drift_payload_shape() -> None:
    payload = build_drift_payload(
        platform="amtrust",
        error="selector_drift",
        submitter="AmTrustSubmitter",
        duration_sec=1.23,
    )
    assert set(payload.keys()) == {
        "title",
        "severity",
        "body_lines",
        "fields",
        "mention_here",
    }
    assert payload["severity"] == "critical"
    assert payload["mention_here"] is True
    assert "amtrust" in payload["title"]


def test_build_recovery_payload_includes_downtime_minutes() -> None:
    payload = build_recovery_payload(
        platform="markel", submitter="MarkelSubmitter", downtime_sec=120.0
    )
    assert "2.0 min" in "\n".join(payload["body_lines"])


def test_build_persistent_failure_payload_includes_count() -> None:
    payload = build_persistent_failure_payload(
        platform="amtrust",
        error="timeout",
        submitter="AmTrustSubmitter",
        consecutive_failures=4,
        duration_sec=1.0,
    )
    assert "4x" in payload["title"] or "4" in payload["title"]


def test_payload_truncates_long_body(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_post(monkeypatch)
    n = SlackNotifier(webhook_url="http://x", channel="#x")
    n.notify(title="t", severity="warning", body_lines=["x" * 5000])
    section_text = captured["json"]["attachments"][0]["blocks"][1]["text"]["text"]
    assert len(section_text) <= 2900


@pytest.mark.parametrize(
    "severity,color",
    [
        ("critical", "#dc2626"),
        ("warning", "#ea580c"),
        ("info", "#10b981"),
    ],
)
def test_severity_color_mapping(
    monkeypatch: pytest.MonkeyPatch, severity: str, color: str
) -> None:
    captured = _capture_post(monkeypatch)
    n = SlackNotifier(webhook_url="http://x", channel="#x")
    n.notify(title="t", severity=severity, body_lines=["b"])  # type: ignore[arg-type]
    assert captured["json"]["attachments"][0]["color"] == color
