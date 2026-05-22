"""Tests for app.middleware.secrets_redaction."""

from __future__ import annotations

from app.middleware.secrets_redaction import (
    REDACTED,
    redact_event_dict,
    redact_secrets,
    structlog_redactor,
)


class TestKeyBasedRedaction:
    def test_password_key_redacted(self) -> None:
        out = redact_event_dict({"event": "x", "password": "hunter2"})
        assert out["password"] == REDACTED
        assert out["event"] == "x"

    def test_authorization_key_redacted(self) -> None:
        out = redact_event_dict({"Authorization": "Bearer abc"})
        assert out["Authorization"] == REDACTED

    def test_nested_dict_redacted(self) -> None:
        out = redact_event_dict(
            {
                "user": {
                    "id": "u_1",
                    "credentials": {"api_key": "k_secret", "username": "alice"},
                }
            }
        )
        assert out["user"]["credentials"]["api_key"] == REDACTED
        assert out["user"]["credentials"]["username"] == "alice"

    def test_list_of_dicts_walked(self) -> None:
        out = redact_event_dict(
            {"items": [{"token": "abc"}, {"safe": "ok"}]}
        )
        assert out["items"][0]["token"] == REDACTED
        assert out["items"][1]["safe"] == "ok"

    def test_signing_key_substring_match(self) -> None:
        out = redact_event_dict({"receipt_signing_key": "PEM..."})
        assert out["receipt_signing_key"] == REDACTED


class TestWhitelist:
    def test_user_id_not_redacted(self) -> None:
        out = redact_event_dict({"user_id": "abc-123"})
        assert out["user_id"] == "abc-123"

    def test_tenant_id_not_redacted(self) -> None:
        out = redact_event_dict({"tenant_id": "tnt_1"})
        assert out["tenant_id"] == "tnt_1"

    def test_email_partially_redacted(self) -> None:
        out = redact_event_dict({"email": "alice@example.com"})
        # local part shortened to 3 chars + ***
        assert out["email"].endswith("@example.com")
        assert "***" in out["email"]
        assert "alice@example.com" not in out["email"]


class TestRegexRedaction:
    def test_aws_access_key_redacted(self) -> None:
        out = redact_secrets("user passed AKIAIOSFODNN7EXAMPLE today")
        assert "AKIAIOSFODNN7EXAMPLE" not in out
        assert REDACTED in out

    def test_jwt_redacted(self) -> None:
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghij"
        out = redact_secrets(f"token={jwt}")
        assert jwt not in out
        assert REDACTED in out

    def test_short_strings_not_redacted(self) -> None:
        # ordinary words should pass through untouched
        out = redact_secrets("hello world this is fine")
        assert out == "hello world this is fine"


class TestProcessorSignature:
    def test_structlog_processor_callable(self) -> None:
        out = structlog_redactor(None, "info", {"password": "x", "event": "login"})
        assert out["password"] == REDACTED
        assert out["event"] == "login"

    def test_processor_never_raises_on_weird_input(self) -> None:
        # Force a recursion-style structure — should still return something.
        ev: dict = {"event": "x"}
        ev["self"] = ev  # cyclic
        out = structlog_redactor(None, "info", ev)
        assert "event" in out
