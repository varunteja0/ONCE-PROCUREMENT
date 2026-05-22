"""RFC-6238 TOTP helpers + recovery-code utilities for cockpit MFA.

Pure stdlib + ``pyotp`` + ``segno``. No network, no clock skew beyond the
configured ``valid_window`` (TOTP step ±N). All output is plain text /
SVG strings — persistence is the caller's responsibility.

Why this module exists separately from :mod:`app.services.operator_auth`:
keep the auth flow lean and let MFA primitives be unit-tested in
isolation (no DB, no FastAPI).
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import string
from urllib.parse import quote

import pyotp
import segno

__all__ = [
    "generate_secret",
    "verify_code",
    "provisioning_uri",
    "provisioning_qr_svg",
    "generate_recovery_codes",
    "hash_recovery_code",
    "RECOVERY_CODE_LENGTH",
    "RECOVERY_CODE_COUNT",
]


# Ambiguous glyphs removed (0/O, 1/I) so codes printed for humans cannot be
# misread off a screen or sheet of paper.
_RECOVERY_ALPHABET: str = "".join(
    c for c in (string.ascii_uppercase + string.digits) if c not in {"0", "O", "1", "I"}
)

RECOVERY_CODE_LENGTH: int = 10
RECOVERY_CODE_COUNT: int = 10


def generate_secret() -> str:
    """Return a fresh 32-character base32 TOTP secret (160 bits of entropy).

    ``secrets.token_bytes(20)`` → 20 bytes → exactly 32 base32 chars with
    no padding. Compatible with every TOTP authenticator app.
    """

    raw = secrets.token_bytes(20)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def verify_code(secret: str, code: str, *, valid_window: int = 1) -> bool:
    """Verify a 6-digit TOTP code against ``secret``.

    Returns ``False`` (never raises) on any malformed input, empty code,
    or verification failure. ``valid_window=1`` accepts ±1 30-second
    step to tolerate small clock drift.
    """

    if not secret or not isinstance(secret, str):
        return False
    if not code or not isinstance(code, str):
        return False
    normalized = code.strip()
    if len(normalized) != 6 or not normalized.isdigit():
        return False
    try:
        totp = pyotp.TOTP(secret)
        return bool(totp.verify(normalized, valid_window=valid_window))
    except Exception:
        return False


def provisioning_uri(
    secret: str,
    *,
    account_name: str,
    issuer: str = "Once Cockpit",
) -> str:
    """Return an ``otpauth://`` URI suitable for QR enrollment.

    Both ``account_name`` and ``issuer`` are percent-encoded so spaces /
    ``@`` / unicode survive the round-trip through Google Authenticator,
    1Password, etc.
    """

    if not secret:
        raise ValueError("secret must be a non-empty base32 string")
    if not account_name:
        raise ValueError("account_name must be a non-empty string")

    label = f"{quote(issuer)}:{quote(account_name)}"
    query = (
        f"secret={secret}"
        f"&issuer={quote(issuer)}"
        f"&algorithm=SHA1"
        f"&digits=6"
        f"&period=30"
    )
    return f"otpauth://totp/{label}?{query}"


def provisioning_qr_svg(uri: str) -> str:
    """Render an SVG QR code (string) for a provisioning URI.

    Pure-Python via ``segno`` — no Pillow, no ImageMagick. The returned
    string is safe to embed directly in an HTML response.
    """

    if not uri:
        raise ValueError("uri must be a non-empty string")
    qr = segno.make(uri, error="m")
    import io

    buf = io.BytesIO()
    qr.save(buf, kind="svg", xmldecl=False, svgns=True, scale=4)
    return buf.getvalue().decode("utf-8")


def generate_recovery_codes(n: int = RECOVERY_CODE_COUNT) -> list[str]:
    """Generate ``n`` unique, human-readable recovery codes.

    Each code is :data:`RECOVERY_CODE_LENGTH` characters from a
    deliberately unambiguous alphabet (no ``0/O``, no ``1/I``). Returned
    plaintext — the caller MUST hash via :func:`hash_recovery_code`
    before persisting.
    """

    if n <= 0:
        raise ValueError("n must be positive")
    out: set[str] = set()
    # Bounded retry loop — collisions in a ~30-char alphabet over 10 chars
    # are astronomically unlikely but cheap to guard against.
    while len(out) < n:
        out.add(
            "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(RECOVERY_CODE_LENGTH))
        )
    return sorted(out)


def hash_recovery_code(code: str) -> str:
    """Deterministic sha256-hex of a recovery code.

    Codes are stored only as their hash; verification re-hashes the
    submitted value and compares. ``code`` is upper-cased and stripped of
    dashes / whitespace so users can type ``ABCD-EF12-34`` or
    ``abcdef1234`` interchangeably.
    """

    if not code:
        raise ValueError("code must be a non-empty string")
    normalized = code.strip().upper().replace("-", "").replace(" ", "")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
