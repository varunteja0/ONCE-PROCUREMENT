"""Byte-exact parity between backend signing canonical-JSON and the
public verifier's canonical-JSON.

The signing path in :mod:`app.services.receipt_signer` computes the
signature over ``app.utils.canonical_json.canonical_json_bytes(payload)``.
The public verifier at ``verifier/app/canonical.py`` re-derives the same
bytes during verification. If the two encoders ever drift, every receipt
ever signed becomes unverifiable.

This test loads the verifier's encoder via direct file import (it is
intentionally NOT a Python package — it ships as a standalone service)
and asserts byte-exact parity across a deliberately tricky set of
payloads.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from app.utils.canonical_json import canonical_json_bytes as backend_bytes
from app.utils.canonical_json import payload_sha256 as backend_sha256

# --- Load verifier's canonical encoder by file path -----------------------
_VERIFIER_CANONICAL = (
    Path(__file__).resolve().parents[2] / "verifier" / "app" / "canonical.py"
)
_spec = importlib.util.spec_from_file_location(
    "_verifier_canonical_under_test", _VERIFIER_CANONICAL
)
assert _spec is not None and _spec.loader is not None, (
    f"could not import verifier canonical encoder at {_VERIFIER_CANONICAL}"
)
_verifier_canonical = importlib.util.module_from_spec(_spec)
sys.modules["_verifier_canonical_under_test"] = _verifier_canonical
_spec.loader.exec_module(_verifier_canonical)
verifier_bytes = _verifier_canonical.canonical_json_bytes
verifier_sha256 = _verifier_canonical.payload_sha256


# --- 20+ tricky payloads --------------------------------------------------
_PAYLOADS: list[object] = [
    # 1. empty containers
    {},
    [],
    # 2. primitives at top level
    None,
    True,
    False,
    0,
    -0,
    42,
    -42,
    0.0,
    1.5,
    -2.25,
    "",
    "hello",
    # 3. unicode keys (latin-1, cyrillic, CJK)
    {"café": 1, "naïve": 2},
    {"Привет": "мир", "你好": "世界"},
    # 4. mixed UTF-16 sort order (uppercase < lowercase)
    {"Z": 1, "a": 2, "A": 3, "b": 4},
    # 5. nested objects + arrays
    {"outer": {"b": [1, 2, 3], "a": {"deep": "value"}}},
    # 6. arrays preserve order
    [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5],
    # 7. heterogeneous array
    [None, True, False, 0, "x", {"k": "v"}, [1, [2, [3]]]],
    # 8. control-char escapes
    {"line\nbreak": "tab\there", "bell": "\x07"},
    # 9. quotes and backslashes
    {"q": '"', "bs": "\\", "both": '"\\'},
    # 10. large integer (must not become float / exponent)
    {"big": 123456789012345},
    # 11. integer-valued floats collapse to int form
    {"i": 1.0, "j": -1.0},
    # 12. signed-zero is encoded as "0"
    {"zero": 0.0, "neg_zero": -0.0},
    # 13. boolean differentiated from int
    {"true": True, "one": 1, "false": False, "zero": 0},
    # 14. tuple-as-array equivalence
    {"t": (1, 2, 3)},
    # 15. duplicate keys via dict (last wins, by JSON semantics)
    {"k": 1, "k": 2},  # noqa: F601 - intentional
    # 16. key that is the empty string
    {"": "empty_key", "x": "value"},
    # 17. deeply nested
    {"a": {"b": {"c": {"d": {"e": {"f": "leaf"}}}}}},
    # 18. realistic receipt-style payload
    {
        "receipt_id": "rcpt_01HW0",
        "tenant_id": "tnt_abc",
        "supplier_id": "sup_def",
        "portal": "amtrust",
        "submission_id": "sub_xyz",
        "submitted_at": "2026-05-23T12:34:56Z",
        "payload_hash": "a" * 64,
        "tos_version_hash": "b" * 64,
        "consent_record_id": "csnt_123",
    },
    # 19. control char range
    {"ctrl_" + chr(i): chr(i) for i in (1, 7, 8, 9, 10, 13, 31)},
    # 20. mixed numbers (small fractional)
    {"a": 0.1, "b": 0.2, "c": 0.3},
    # 21. negative fractional
    [-1.5, -2.5, -3.75],
    # 22. wide ascii printable
    {chr(c): c for c in range(33, 127) if chr(c) != "\\" and chr(c) != '"'},
]


@pytest.mark.parametrize(
    "payload", _PAYLOADS, ids=[f"case_{i:02d}" for i in range(len(_PAYLOADS))]
)
def test_canonical_bytes_parity(payload: object) -> None:
    """Backend and verifier MUST produce byte-identical canonical JSON."""

    assert backend_bytes(payload) == verifier_bytes(payload)


@pytest.mark.parametrize(
    "payload", _PAYLOADS, ids=[f"case_{i:02d}" for i in range(len(_PAYLOADS))]
)
def test_payload_sha256_parity(payload: object) -> None:
    """SHA-256 of the canonical bytes must match across the two encoders."""

    assert backend_sha256(payload) == verifier_sha256(payload)


def test_key_order_invariance_across_implementations() -> None:
    """Re-ordering input keys must not change either encoder's output."""

    a = {"x": 1, "y": 2, "z": 3, "nested": {"a": [1, 2], "b": None}}
    b = {"nested": {"b": None, "a": [1, 2]}, "z": 3, "y": 2, "x": 1}
    assert backend_bytes(a) == backend_bytes(b) == verifier_bytes(a) == verifier_bytes(b)
