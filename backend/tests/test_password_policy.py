"""Tests for app.utils.password_policy."""

from __future__ import annotations

import pytest

from app.utils.password_policy import (
    MIN_LENGTH,
    PasswordPolicyResult,
    validate_password,
)


class TestLength:
    def test_short_rejected(self) -> None:
        r = validate_password("Aa1!short")
        assert r.valid is False
        assert any("too_short" in reason for reason in r.reasons)

    def test_exact_min_with_categories_accepted(self) -> None:
        # 12 chars, 4 categories, not in common list
        r = validate_password("Zx9!quokka@7")
        assert r.valid is True, r.reasons


class TestCategories:
    def test_only_two_categories_rejected(self) -> None:
        r = validate_password("aaaaaaaaaaaa1")
        assert r.valid is False
        assert "password_needs_more_character_categories" in r.reasons or any(
            "category" in reason or "categories" in reason for reason in r.reasons
        )

    def test_three_categories_accepted(self) -> None:
        r = validate_password("ZebraQuokka1X")
        assert r.valid is True, r.reasons


class TestCommonPasswords:
    @pytest.mark.parametrize(
        "pw",
        ["Password1234", "Qwerty1!abcd", "Letmein12!abc"],
    )
    def test_common_substring_rejected(self, pw: str) -> None:
        r = validate_password(pw)
        assert r.valid is False
        assert any("common" in reason for reason in r.reasons)


class TestIdentityChecks:
    def test_password_equals_email_rejected(self) -> None:
        r = validate_password("alice@example.com1", email="alice@example.com")
        assert r.valid is False
        assert any("email" in reason for reason in r.reasons)

    def test_password_contains_tenant_rejected(self) -> None:
        r = validate_password("AcmeMGA-Quokka9!", tenant_name="Acme MGA")
        assert r.valid is False
        assert any("tenant" in reason for reason in r.reasons)

    def test_password_contains_user_name_rejected(self) -> None:
        r = validate_password("Smithington9!Zx", full_name="Bob Smithington")
        assert r.valid is False
        assert any("user_name" in reason or "name" in reason for reason in r.reasons)


class TestSequenceAndRuns:
    def test_repeated_run_rejected(self) -> None:
        r = validate_password("Zx!aaaaQuokka9")
        assert r.valid is False

    def test_simple_sequence_rejected(self) -> None:
        r = validate_password("Zx!abcdeQuokk9")
        assert r.valid is False


class TestResultShape:
    def test_valid_result_has_empty_reasons(self) -> None:
        r = validate_password("Zx9!quokka@7")
        assert isinstance(r, PasswordPolicyResult)
        assert r.valid is True
        assert r.reasons == []
        assert r.first_reason is None

    def test_min_length_constant_is_twelve(self) -> None:
        assert MIN_LENGTH == 12
