"""Pagination helpers — offset & cursor.

Two paginations modes are supported by the public API:

* **Offset** — ``?limit=50&offset=0``. Stable, easy to reason about, but
  pages drift if the underlying ordering changes. Capped at
  :data:`MAX_LIMIT`.
* **Cursor** — ``?limit=50&cursor=<opaque>``. Cursor encodes
  ``(created_at, id)`` of the boundary row so subsequent pages are
  consistent under inserts at the tail.

The cursor wire format is base64-urlsafe JSON. Clients MUST treat it as
opaque (we may change the encoding without notice).

The :func:`paginate` helper executes a SQLAlchemy ``Select`` in the
requested mode and returns a :class:`~app.schemas.common.Page` populated
with the appropriate fields.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.common import Cursor, Page

__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "PaginationParams",
    "encode_cursor",
    "decode_cursor",
    "normalize_limit",
    "normalize_offset",
    "paginate",
]


DEFAULT_LIMIT: int = 50
MAX_LIMIT: int = 200


class PaginationParams(BaseModel):
    """Normalized pagination query parameters."""

    mode: str = "offset"
    limit: int = DEFAULT_LIMIT
    offset: int | None = 0
    cursor: str | None = None


# ---------------------------------------------------------------------------
# Cursor encoding
# ---------------------------------------------------------------------------


def encode_cursor(cursor: Cursor) -> str:
    """Encode a :class:`Cursor` into the opaque wire format."""

    raw = json.dumps(
        {
            "created_at": cursor.created_at,
            "id": cursor.id,
            "direction": cursor.direction,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode_cursor(value: str) -> Cursor:
    """Decode the opaque wire format into a :class:`Cursor`.

    Raises :class:`ValueError` for malformed input — routes should turn that
    into a 400 ``invalid_cursor`` Problem response.
    """

    if not isinstance(value, str) or not value:
        raise ValueError("cursor must be a non-empty string")
    padded = value + "=" * (-len(value) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid cursor: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("cursor payload must be an object")
    try:
        return Cursor(
            created_at=str(payload["created_at"]),
            id=str(payload["id"]),
            direction=str(payload.get("direction", "next")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid cursor fields: {exc}") from exc


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def normalize_limit(value: Any, *, default: int = DEFAULT_LIMIT, maximum: int = MAX_LIMIT) -> int:
    """Coerce / clamp ``limit`` to a valid range.

    Raises :class:`ValueError` for out-of-range / negative input so callers
    can return a 422 with a precise error.
    """

    if value is None or value == "":
        return default
    try:
        n = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer") from exc
    if n < 1:
        raise ValueError("limit must be >= 1")
    if n > maximum:
        raise ValueError(f"limit must be <= {maximum}")
    return n


def normalize_offset(value: Any, *, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        n = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("offset must be an integer") from exc
    if n < 0:
        raise ValueError("offset must be >= 0")
    return n


# ---------------------------------------------------------------------------
# Async paginator
# ---------------------------------------------------------------------------


async def paginate(
    session: AsyncSession,
    stmt: Select[Any],
    *,
    mode: str = "offset",
    limit: int = DEFAULT_LIMIT,
    offset: int | None = 0,
    cursor: str | None = None,
    id_column: Any = None,
    created_at_column: Any = None,
) -> Page[Any]:
    """Execute ``stmt`` paginated in the requested mode.

    Offset mode requires ``limit`` and (optionally) ``offset``; emits
    ``total`` via a separate ``COUNT(*)`` derived query.

    Cursor mode requires ``id_column`` and ``created_at_column`` so the
    function can apply the cursor filter and produce next/prev cursors.
    """

    limit = normalize_limit(limit)
    mode_normalized = mode.lower().strip() if mode else "offset"

    if mode_normalized == "offset":
        offset_value = normalize_offset(offset)
        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await session.execute(total_stmt)).scalar_one() or 0)
        page_stmt = stmt.limit(limit).offset(offset_value)
        rows: Sequence[Any] = (await session.execute(page_stmt)).scalars().all()
        return Page(
            items=list(rows),
            total=total,
            limit=limit,
            offset=offset_value,
        )

    if mode_normalized != "cursor":
        raise ValueError(f"unknown pagination mode: {mode!r}")

    if id_column is None or created_at_column is None:
        raise ValueError(
            "cursor mode requires id_column and created_at_column"
        )

    page_stmt = stmt
    if cursor:
        boundary = decode_cursor(cursor)
        # The cursor's ``created_at`` is an ISO-8601 string. If the underlying
        # column is a ``DateTime``, coerce so SQLAlchemy binds the right type
        # (string comparison against a TEXT-encoded DateTime column gives the
        # wrong answer because the ISO ``T`` separator sorts after the SPACE
        # separator SQLite stores).
        boundary_created_at: Any = boundary.created_at
        col_type = getattr(created_at_column, "type", None)
        py_type = getattr(col_type, "python_type", None) if col_type is not None else None
        if py_type is not None:
            try:
                from datetime import date, datetime

                if py_type in (datetime,):
                    boundary_created_at = datetime.fromisoformat(
                        boundary.created_at.replace("Z", "+00:00")
                    )
                elif py_type in (date,):
                    boundary_created_at = date.fromisoformat(boundary.created_at)
            except (ValueError, TypeError):
                pass
        # Composite key compare: created_at descending, id descending as tiebreaker.
        page_stmt = page_stmt.where(
            (created_at_column < boundary_created_at)
            | (
                (created_at_column == boundary_created_at)
                & (id_column < boundary.id)
            )
        )
    page_stmt = page_stmt.order_by(created_at_column.desc(), id_column.desc()).limit(limit + 1)
    rows = (await session.execute(page_stmt)).scalars().all()

    has_next = len(rows) > limit
    items = list(rows[:limit])
    next_cursor: str | None = None
    prev_cursor: str | None = None
    if has_next and items:
        tail = items[-1]
        next_cursor = encode_cursor(
            Cursor(
                created_at=getattr(tail, created_at_column.key).isoformat()
                if hasattr(getattr(tail, created_at_column.key), "isoformat")
                else str(getattr(tail, created_at_column.key)),
                id=str(getattr(tail, id_column.key)),
                direction="next",
            )
        )
    if cursor and items:
        head = items[0]
        prev_cursor = encode_cursor(
            Cursor(
                created_at=getattr(head, created_at_column.key).isoformat()
                if hasattr(getattr(head, created_at_column.key), "isoformat")
                else str(getattr(head, created_at_column.key)),
                id=str(getattr(head, id_column.key)),
                direction="prev",
            )
        )
    return Page(
        items=items,
        total=None,
        limit=limit,
        offset=None,
        next_cursor=next_cursor,
        prev_cursor=prev_cursor,
    )
