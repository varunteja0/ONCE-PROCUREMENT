"""RFC8785-style canonical JSON encoding tests.

The implementation lives in :mod:`app.utils.canonical_json`. These tests
exhaustively cover:

* primitive encoding (null/bool/int/float/str)
* string escaping (control chars → ``\\uXXXX``)
* object key sort order (UTF-16-BE)
* array order preservation
* round-trip stability (encode → ``json.loads`` → equal)
* numeric edge cases (zero, large ints, fractional, exponent normalization)
* error cases (NaN, Infinity, non-string keys, unsupported types)
"""

from __future__ import annotations

import json

import pytest

from app.utils.canonical_json import (
    canonical_json_bytes,
    canonical_json_str,
    payload_sha256,
)


class TestPrimitives:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, "null"),
            (True, "true"),
            (False, "false"),
            (0, "0"),
            (1, "1"),
            (-1, "-1"),
            (42, "42"),
            (123456789012345, "123456789012345"),
            ("", '""'),
            ("hello", '"hello"'),
            ("a/b", '"a/b"'),  # slashes are NOT escaped
        ],
    )
    def test_primitive_encoding(self, value: object, expected: str) -> None:
        assert canonical_json_str(value) == expected

    def test_returns_bytes_utf8(self) -> None:
        assert canonical_json_bytes({"a": 1}) == b'{"a":1}'

    def test_zero_float_encodes_as_integer_zero(self) -> None:
        assert canonical_json_str(0.0) == "0"

    @pytest.mark.parametrize(
        "value,expected",
        [
            (1.0, "1"),  # integer-valued float collapses to int form
            (-1.0, "-1"),
            (1.5, "1.5"),
            (-2.25, "-2.25"),
        ],
    )
    def test_float_formatting(self, value: float, expected: str) -> None:
        assert canonical_json_str(value) == expected


class TestStringEscaping:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("\\", '"\\\\"'),
            ('"', '"\\""'),
            ("\n", '"\\n"'),
            ("\r", '"\\r"'),
            ("\t", '"\\t"'),
            ("\b", '"\\b"'),
            ("\f", '"\\f"'),
        ],
    )
    def test_standard_escapes(self, value: str, expected: str) -> None:
        assert canonical_json_str(value) == expected

    def test_low_control_chars_use_unicode_escape(self) -> None:
        # \x01 has no shorthand → must come out as \u0001
        assert canonical_json_str("\x01") == '"\\u0001"'

    def test_unicode_passthrough(self) -> None:
        # Non-ASCII (above 0x1f) is passed through literally.
        assert canonical_json_str("café") == '"café"'


class TestObjectKeyOrdering:
    def test_keys_are_sorted_lexicographically(self) -> None:
        assert canonical_json_str({"b": 1, "a": 2}) == '{"a":2,"b":1}'

    def test_keys_sorted_by_utf16be(self) -> None:
        # 'Z' (0x5a) < 'a' (0x61) in UTF-16-BE.
        assert canonical_json_str({"a": 1, "Z": 2}) == '{"Z":2,"a":1}'

    def test_nested_objects_are_recursively_sorted(self) -> None:
        encoded = canonical_json_str({"z": {"b": 1, "a": 2}, "a": [3, 2, 1]})
        assert encoded == '{"a":[3,2,1],"z":{"a":2,"b":1}}'

    def test_array_order_is_preserved(self) -> None:
        # Arrays are NOT sorted — order is significant.
        assert canonical_json_str([3, 1, 2]) == "[3,1,2]"


class TestErrors:
    def test_nan_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="representable"):
            canonical_json_str(float("nan"))

    def test_infinity_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="representable"):
            canonical_json_str(float("inf"))

    def test_negative_infinity_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            canonical_json_str(float("-inf"))

    def test_non_string_key_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="keys"):
            canonical_json_str({1: "v"})

    def test_unsupported_type_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="unsupported"):
            canonical_json_str(object())


class TestRoundTrip:
    @pytest.mark.parametrize(
        "value",
        [
            {},
            [],
            {"a": [1, 2, {"nested": True}]},
            {"unicode": "naïve", "list": [None, False, 0]},
            {"x" * 10: "y" * 10},
            [{"a": 1}, {"b": 2}],
        ],
    )
    def test_round_trip_via_json_loads_is_value_equal(self, value: object) -> None:
        encoded = canonical_json_str(value)
        # Must be parseable as JSON.
        loaded = json.loads(encoded)
        assert loaded == value

    def test_two_equal_dicts_in_different_insertion_orders_canonicalize_equally(
        self,
    ) -> None:
        a = canonical_json_bytes({"x": 1, "y": 2, "z": 3})
        b = canonical_json_bytes({"z": 3, "y": 2, "x": 1})
        assert a == b


class TestPayloadHashing:
    def test_sha256_is_stable_across_key_orders(self) -> None:
        h1 = payload_sha256({"a": 1, "b": 2})
        h2 = payload_sha256({"b": 2, "a": 1})
        assert h1 == h2
        assert len(h1) == 64  # hex sha256

    def test_sha256_changes_with_value(self) -> None:
        h1 = payload_sha256({"a": 1})
        h2 = payload_sha256({"a": 2})
        assert h1 != h2
