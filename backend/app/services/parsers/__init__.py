"""L3.7 — Streaming parsers for bulk imports."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from app.services.parsers.csv_parser import iter_csv_rows
from app.services.parsers.xlsx_parser import iter_xlsx_rows

__all__ = [
    "iter_rows",
    "iter_csv_rows",
    "iter_xlsx_rows",
    "ALLOWED_EXTENSIONS",
    "detect_format",
]


ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".csv", ".xlsx", ".xls"})


def detect_format(filename: str, content_type: str | None = None) -> str:
    """Return ``"csv"`` or ``"xlsx"`` based on filename / content-type."""

    ext = Path(filename).suffix.lower()
    if ext == ".csv":
        return "csv"
    if ext in {".xlsx", ".xls"}:
        return "xlsx"
    if content_type:
        ct = content_type.lower()
        if "csv" in ct or ct == "text/plain":
            return "csv"
        if "sheet" in ct or "excel" in ct:
            return "xlsx"
    raise ValueError(
        f"Unsupported import file type: {filename!r} (content_type={content_type!r})"
    )


def iter_rows(path: str | Path, *, filename: str | None = None) -> Iterator[dict[str, str]]:
    """Auto-detect format and yield rows from ``path``."""

    p = Path(path)
    fmt = detect_format(filename or p.name)
    if fmt == "csv":
        yield from iter_csv_rows(p)
    else:
        yield from iter_xlsx_rows(p)
