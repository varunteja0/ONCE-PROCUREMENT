"""Unit tests for :mod:`app.services.mfa_totp` — no DB, no FastAPI."""

from __future__ import annotations

import base64
import re

import pyotp
import pytest
from freezegun import freeze_time

from app.services import mfa_totp


def test_generate_secret_is_32_char_base32() -> None:
    secret = mfa_totp.generate_secret()
    assert isinstance(secret, str)
    assert len(secret) == 32
    # base32 alphabet only, no padding
    assert re.fullmatch(r"[A-Z2-7]{32}", secret)
    # round-trips through base32 decoding (20 raw bytes)
    decoded = base64.b32decode(secret)
    assert len(decoded) == 20


def test_generate_secret_is_unique_per_call() -> None:
    secrets_seen = {mfa_totp.generate_secret() for _ in range(50)}
    assert len(secrets_seen) == 50


def test_verify_code_accepts_live_code() -> None:
    secret = mfa_totp.generate_secret()
    code = pyotp.TOTP(secret).now()
    assert mfa_totp.verify_code(secret, code) is True


def test_verify_code_rejects_wrong_code() -> None:
    secret = mfa_totp.generate_secret()
    live = pyotp.TOTP(secret).now()
    wrong = "000000" if live != "000000" else "111111"
    assert mfa_totp.verify_code(secret, wrong) is False


def test_verify_code_rejects_empty_and_nondigit() -> None:
    secret = mfa_totp.generate_secret()
    assert mfa_totp.verify_code(secret, "") is False
    assert mfa_totp.verify_code(secret, None) is False  # type: ignore[arg-type]
    assert mfa_totp.verify_code(secret, "abcdef") is False
    assert mfa_totp.verify_code(secret, "12345") is False  # too short
    assert mfa_totp.verify_code(secret, "1234567") is False  # too long


def test_verify_code_rejects_when_secret_missing() -> None:
    assert mfa_totp.verify_code("", "123456") is False
    assert mfa_totp.verify_code(None, "123456") is False  # type: ignore[arg-type]


def test_verify_code_strips_whitespace() -> None:
    secret = mfa_totp.generate_secret()
    code = pyotp.TOTP(secret).now()
    assert mfa_totp.verify_code(secret, f"  {code}  ") is True


def test_verify_code_handles_garbage_secret() -> None:
    # Non-base32 secret — pyotp raises; we must swallow and return False.
    assert mfa_totp.verify_code("!!!not-base32!!!", "123456") is False


def test_verify_code_accepts_previous_step_within_window() -> None:
    secret = mfa_totp.generate_secret()
    totp = pyotp.TOTP(secret)
    with freeze_time("2026-06-01T12:00:00Z") as frozen:
        code = totp.now()
        frozen.tick(delta=31)  # advance one full 30s step
        assert mfa_totp.verify_code(secret, code, valid_window=1) is True


def test_verify_code_rejects_outside_window() -> None:
    secret = mfa_totp.generate_secret()
    totp = pyotp.TOTP(secret)
    with freeze_time("2026-06-01T12:00:00Z") as frozen:
        code = totp.now()
        frozen.tick(delta=120)  # 4 steps later → outside ±1
        assert mfa_totp.verify_code(secret, code, valid_window=1) is False


def test_provisioning_uri_shape() -> None:
    secret = "JBSWY3DPEHPK3PXP"
    uri = mfa_totp.provisioning_uri(secret, account_name="ops@once.dev", issuer="Once Cockpit")
    assert uri.startswith("otpauth://totp/")
    assert "secret=JBSWY3DPEHPK3PXP" in uri
    assert "issuer=Once%20Cockpit" in uri
    assert "ops%40once.dev" in uri
    assert "digits=6" in uri
    assert "period=30" in uri


def test_provisioning_uri_rejects_empty_inputs() -> None:
    with pytest.raises(ValueError):
        mfa_totp.provisioning_uri("", account_name="x")
    with pytest.raises(ValueError):
        mfa_totp.provisioning_uri("ABC", account_name="")


def test_provisioning_qr_svg_is_valid_svg() -> None:
    uri = mfa_totp.provisioning_uri(mfa_totp.generate_secret(), account_name="ops@once.dev")
    svg = mfa_totp.provisioning_qr_svg(uri)
    assert isinstance(svg, str)
    assert "<svg" in svg
    assert "</svg>" in svg


def test_provisioning_qr_svg_rejects_empty() -> None:
    with pytest.raises(ValueError):
        mfa_totp.provisioning_qr_svg("")


def test_generate_recovery_codes_default_count_and_shape() -> None:
    codes = mfa_totp.generate_recovery_codes()
    assert len(codes) == mfa_totp.RECOVERY_CODE_COUNT
    for c in codes:
        assert len(c) == mfa_totp.RECOVERY_CODE_LENGTH
        # No ambiguous characters
        assert not set(c) & {"0", "O", "1", "I"}
        # Only uppercase + digits from the safe alphabet
        assert re.fullmatch(r"[A-HJ-NP-Z2-9]{10}", c)


def test_generate_recovery_codes_are_unique() -> None:
    codes = mfa_totp.generate_recovery_codes(10)
    assert len(set(codes)) == 10


def test_generate_recovery_codes_custom_n() -> None:
    codes = mfa_totp.generate_recovery_codes(5)
    assert len(codes) == 5


def test_generate_recovery_codes_rejects_zero() -> None:
    with pytest.raises(ValueError):
        mfa_totp.generate_recovery_codes(0)


def test_hash_recovery_code_deterministic() -> None:
    a = mfa_totp.hash_recovery_code("ABCDEF2345")
    b = mfa_totp.hash_recovery_code("ABCDEF2345")
    assert a == b
    assert len(a) == 64  # sha256 hex


def test_hash_recovery_code_normalizes_case_and_dashes() -> None:
    a = mfa_totp.hash_recovery_code("ABCDEF2345")
    b = mfa_totp.hash_recovery_code("abcdef2345")
    c = mfa_totp.hash_recovery_code("ABCD-EF23-45")
    d = mfa_totp.hash_recovery_code("  abcd ef2345  ")
    assert a == b == c == d


def test_hash_recovery_code_rejects_empty() -> None:
    with pytest.raises(ValueError):
        mfa_totp.hash_recovery_code("")
