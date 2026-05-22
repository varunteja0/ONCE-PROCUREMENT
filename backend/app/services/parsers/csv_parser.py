"""L3.7 — Streaming CSV parser with encoding auto-detection.

Uses stdlib :mod:`csv` for RFC 4180 quoting / embedded newlines and
:mod:`chardet` to sniff encoding (UTF-8 / UTF-8-BOM / Windows-1252 are
the three flavours we routinely see from Excel exports).
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path
from typing import IO

import chardet

__all__ = ["iter_csv_rows", "sniff_encoding", "sniff_dialect"]


_ENCODING_SNIFF_BYTES: int = 64 * 1024
_DIALECT_SNIFF_BYTES: int = 8 * 1024


def sniff_encoding(path: Path) -> str:
    """Return the most likely text encoding for ``path``.

    UTF-8 BOM → ``"utf-8-sig"``. Low-confidence guesses fall back to
    ``"utf-8"`` if the head is valid UTF-8, otherwise to ``cp1252``
    (the most common Windows/Excel export encoding). ``ascii`` /
    Latin-1 / Windows-1252 are normalised to ``cp1252`` (a strict
    superset of the other two).
    """

    with path.open("rb") as fh:
        head = fh.read(_ENCODING_SNIFF_BYTES)
    if head.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    guess = chardet.detect(head) or {}
    enc = (guess.get("encoding") or "").lower()
    confidence = float(guess.get("confidence") or 0.0)
    if enc in {"ascii", "iso-8859-1", "windows-1252"}:
        return "cp1252"
    if enc and confidence >= 0.5:
        return enc
    # Low confidence or no guess — pick based on whether head is valid UTF-8.
    try:
        head.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1252"


def sniff_dialect(sample: str) -> csv.Dialect | type[csv.Dialect]:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.excel


def _normalize_header(name: str | None) -> str:
    if name is None:
        return ""
    return name.replace("\ufeff", "").strip().lower()


def iter_csv_rows(path: Path) -> Iterator[dict[str, str]]:
    """Yield one ``{header: value}`` dict per data row (streaming)."""

    encoding = sniff_encoding(path)
    with path.open("r", encoding=encoding, newline="") as fh:
        yield from _iter_from_textio(fh)


def _iter_from_textio(fh: IO[str]) -> Iterator[dict[str, str]]:
    sample = fh.read(_DIALECT_SNIFF_BYTES)
    fh.seek(0)
    dialect = sniff_dialect(sample) if sample else csv.excel
    reader = csv.reader(fh, dialect=dialect)
    try:
        header_row = next(reader)
    except StopIteration:
        return
    headers = [_normalize_header(h) for h in header_row]
    width = len(headers)
    for raw in reader:
        if not raw:
            continue
        if all((cell or "").strip() == "" for cell in raw):
            continue
        if len(raw) < width:
            raw = list(raw) + [""] * (width - len(raw))
        out: dict[str, str] = {}
        for idx, header in enumerate(headers):
            if not header:
                continue
            cell = raw[idx] if idx < len(raw) else ""
            out[header] = "" if cell is None else str(cell)
        yield out
