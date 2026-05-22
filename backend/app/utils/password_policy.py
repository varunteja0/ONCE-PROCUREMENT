"""Password-strength policy without heavyweight deps.

Why not zxcvbn?  It ships a >700 KB dictionary file and pulls in C
extensions.  For an MGA-facing API this is overkill — a focused policy
catches the bulk of real-world bad passwords (length + categories +
top-N list + identity-related checks) without the dependency surface.

Policy:

* Minimum 12 chars (rejects everything below).
* Must contain at least 3 of {uppercase, lowercase, digit, special}.
* Must not be one of the hardcoded top-100 most-common passwords (case-
  insensitive substring match against the password's "core").
* Must not equal the user's email (case-insensitive) or its local part.
* Must not contain the tenant name (case-insensitive, if provided).
* Must not contain more than 3 identical chars in a row (``aaaaaa``).
* Must not be a simple ascending/descending sequence (``123456``,
  ``abcdef``).

Existing user passwords are **not** migrated; this is documented as a
deferred item in ``SECURITY.md``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

__all__ = [
    "PasswordPolicyResult",
    "validate_password",
    "MIN_LENGTH",
    "COMMON_PASSWORDS",
]


MIN_LENGTH: int = 12
_MAX_LENGTH: int = 256
_MIN_CATEGORIES: int = 3

# Top-100 most-common passwords (deduped, lowercase). Sourced from the
# publicly-published SecLists "10k Most Common" top of the long tail.
# Embedded inline so the policy works in air-gapped envs.
COMMON_PASSWORDS: frozenset[str] = frozenset(
    {
        "123456", "password", "12345678", "qwerty", "123456789", "12345",
        "1234", "111111", "1234567", "dragon", "123123", "baseball",
        "abc123", "football", "monkey", "letmein", "shadow", "master",
        "666666", "qwertyuiop", "123321", "mustang", "1234567890",
        "michael", "654321", "pussy", "superman", "1qaz2wsx", "7777777",
        "121212", "000000", "qazwsx", "123qwe", "killer", "trustno1",
        "jordan", "jennifer", "zxcvbnm", "asdfgh", "hunter", "buster",
        "soccer", "harley", "batman", "andrew", "tigger", "sunshine",
        "iloveyou", "2000", "charlie", "robert", "thomas", "hockey",
        "ranger", "daniel", "starwars", "klaster", "112233", "george",
        "computer", "michelle", "jessica", "pepper", "1111", "zxcvbn",
        "555555", "11111111", "131313", "freedom", "777777", "pass",
        "maggie", "159753", "aaaaaa", "ginger", "princess", "joshua",
        "cheese", "amanda", "summer", "love", "ashley", "nicole",
        "chelsea", "biteme", "matthew", "access", "yankees", "987654321",
        "dallas", "austin", "thunder", "taylor", "matrix", "william",
        "corvette", "hello", "martin", "heather", "secret", "fucker",
        "merlin", "diamond", "1234qwer",
    }
)


@dataclass(slots=True)
class PasswordPolicyResult:
    valid: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def first_reason(self) -> str | None:
        return self.reasons[0] if self.reasons else None


def _categories(password: str) -> int:
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any((not c.isalnum()) and (not c.isspace()) for c in password)
    return sum((has_upper, has_lower, has_digit, has_special))


def _has_long_run(password: str, *, run: int = 4) -> bool:
    if len(password) < run:
        return False
    streak = 1
    prev = password[0]
    for c in password[1:]:
        if c == prev:
            streak += 1
            if streak >= run:
                return True
        else:
            streak = 1
            prev = c
    return False


def _is_sequence(password: str, *, length: int = 5) -> bool:
    if len(password) < length:
        return False
    ascending = 1
    descending = 1
    for i in range(1, len(password)):
        diff = ord(password[i]) - ord(password[i - 1])
        ascending = ascending + 1 if diff == 1 else 1
        descending = descending + 1 if diff == -1 else 1
        if ascending >= length or descending >= length:
            return True
    return False


def _contains_token(password: str, tokens: Iterable[str]) -> str | None:
    lowered = password.lower()
    for token in tokens:
        token_norm = (token or "").strip().lower()
        if len(token_norm) >= 4 and token_norm in lowered:
            return token_norm
    return None


def validate_password(
    password: str,
    *,
    email: str | None = None,
    tenant_name: str | None = None,
    full_name: str | None = None,
) -> PasswordPolicyResult:
    """Run the full policy and return a structured result."""

    reasons: list[str] = []

    if not isinstance(password, str):
        return PasswordPolicyResult(valid=False, reasons=["password_not_string"])

    if len(password) < MIN_LENGTH:
        reasons.append(f"password_too_short_min_{MIN_LENGTH}")
    if len(password) > _MAX_LENGTH:
        reasons.append(f"password_too_long_max_{_MAX_LENGTH}")

    if _categories(password) < _MIN_CATEGORIES:
        reasons.append("password_needs_more_character_categories")

    lowered = password.lower().strip()
    if lowered in COMMON_PASSWORDS:
        reasons.append("password_is_common")
    else:
        # Catch trivial wrappers like " Password123" -> still recognise.
        for common in COMMON_PASSWORDS:
            if len(common) >= 6 and common in lowered:
                reasons.append("password_contains_common_substring")
                break

    if email:
        email_norm = email.strip().lower()
        if email_norm and email_norm in lowered:
            reasons.append("password_contains_email")
        local_part = email_norm.split("@", 1)[0] if "@" in email_norm else email_norm
        if local_part and len(local_part) >= 4 and local_part in lowered:
            reasons.append("password_contains_email_local_part")

    if tenant_name:
        candidates: list[str] = [tenant_name]
        candidates.extend(tenant_name.split())
        # Also try a whitespace-stripped variant ("Acme MGA" -> "acmemga")
        candidates.append("".join(tenant_name.split()))
        match = _contains_token(password, candidates)
        if match:
            reasons.append("password_contains_tenant_name")

    if full_name:
        parts = [p for p in full_name.replace(",", " ").split() if len(p) >= 4]
        match = _contains_token(password, parts)
        if match:
            reasons.append("password_contains_user_name")

    if _has_long_run(password, run=4):
        reasons.append("password_has_repeated_run")

    if _is_sequence(password, length=5):
        reasons.append("password_is_sequence")

    # De-duplicate while preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            deduped.append(r)

    return PasswordPolicyResult(valid=not deduped, reasons=deduped)
