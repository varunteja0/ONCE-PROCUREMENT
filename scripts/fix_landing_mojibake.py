"""One-shot mojibake fix for landing/index.html; safe to delete after running."""

from __future__ import annotations

import pathlib

landing_path = pathlib.Path(__file__).resolve().parent.parent / "landing" / "index.html"
raw_bytes = landing_path.read_bytes()
fixed = raw_bytes

# Double-encoded UTF-8 mojibake sequences seen in the file.
double_encoded = {
    b"\xc3\xa2\xe2\x82\xac\xe2\x80\x9d": "\u2014",
    b"\xc3\xa2\xe2\x82\xac\xe2\x84\xa2": "\u2019",
    b"\xc3\xa2\xe2\x82\xac\xc2\xa6": "\u2026",
    b"\xc3\x82\xc2\xb7": "\u00b7",
    b"\xc3\x82\xc2\xa9": "\u00a9",
    b"\xc3\xa2\xe2\x80\xa0\xe2\x80\x99": "\u2192",
    b"\xc3\xa2\xc5\x93\xe2\x80\x9c": "\u2713",
    b"\xc3\xb0\xc5\xb8\xe2\x80\x9c\xe2\x80\xa6": "\U0001f4c5",
}
single_encoded = {
    b"\xe2\x80\x94": "\u2014",
    b"\xe2\x80\x99": "\u2019",
    b"\xe2\x80\x98": "\u2018",
    b"\xe2\x80\xa6": "\u2026",
    b"\xc2\xb7": "\u00b7",
    b"\xc2\xa9": "\u00a9",
    b"\xe2\x86\x92": "\u2192",
}

for bad_bytes, replacement in double_encoded.items():
    fixed = fixed.replace(bad_bytes, replacement.encode("utf-8"))
for bad_bytes, replacement in single_encoded.items():
    fixed = fixed.replace(bad_bytes, replacement.encode("utf-8"))

# Url / email / cal-link replacements
fixed = fixed.replace(b"founders@getonce.com", b"varun@onceidentity.com")
fixed = fixed.replace(
    b'data-cal-link="once/demo"',
    b'data-cal-link="varun-once/discovery"',
)

landing_path.write_bytes(fixed)
leftover = sum(
    fixed.count(marker) for marker in (b"\xc3\xa2", b"\xc3\x82", b"\xc3\xb0")
)
if leftover:
    raise SystemExit(f"leftover mojibake markers: {leftover}")
