"""Tests for pagination utilities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Column, DateTime, String, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.schemas.common import Cursor, Page
from app.utils.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    decode_cursor,
    encode_cursor,
    normalize_limit,
    normalize_offset,
    paginate,
)


class _Base(DeclarativeBase):
    pass


class _Item(_Base):
    __tablename__ = "items"
    id = Column(String(36), primary_key=True)
    name = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False)


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    sm = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
    async with sm() as s:
        base_time = datetime(2025, 1, 1, tzinfo=UTC).replace(tzinfo=None)
        for i in range(25):
            s.add(
                _Item(
                    id=f"id-{i:02d}",
                    name=f"name-{i:02d}",
                    created_at=base_time + timedelta(minutes=i),
                )
            )
        await s.commit()
    async with sm() as s:
        yield s
    await engine.dispose()


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


class TestNormalizeLimit:
    def test_default_when_none(self) -> None:
        assert normalize_limit(None) == DEFAULT_LIMIT

    def test_default_when_empty_string(self) -> None:
        assert normalize_limit("") == DEFAULT_LIMIT

    def test_accepts_valid_int(self) -> None:
        assert normalize_limit(25) == 25

    def test_accepts_string_int(self) -> None:
        assert normalize_limit("25") == 25

    def test_rejects_below_one(self) -> None:
        with pytest.raises(ValueError):
            normalize_limit(0)

    def test_rejects_negative(self) -> None:
        with pytest.raises(ValueError):
            normalize_limit(-1)

    def test_rejects_above_max(self) -> None:
        with pytest.raises(ValueError):
            normalize_limit(MAX_LIMIT + 1)

    def test_rejects_non_numeric(self) -> None:
        with pytest.raises(ValueError):
            normalize_limit("twenty")


class TestNormalizeOffset:
    def test_default_when_none(self) -> None:
        assert normalize_offset(None) == 0

    def test_accepts_zero(self) -> None:
        assert normalize_offset(0) == 0

    def test_rejects_negative(self) -> None:
        with pytest.raises(ValueError):
            normalize_offset(-1)

    def test_rejects_non_numeric(self) -> None:
        with pytest.raises(ValueError):
            normalize_offset("nope")


# ---------------------------------------------------------------------------
# Cursor round-trip
# ---------------------------------------------------------------------------


class TestCursorEncoding:
    def test_round_trip(self) -> None:
        c = Cursor(created_at="2025-01-15T12:00:00Z", id="abc", direction="next")
        encoded = encode_cursor(c)
        decoded = decode_cursor(encoded)
        assert decoded == c

    def test_encoded_form_is_opaque_base64(self) -> None:
        c = Cursor(created_at="2025-01-15T12:00:00Z", id="abc")
        encoded = encode_cursor(c)
        # No padding, urlsafe — must not contain '=' or '+' or '/'.
        assert "=" not in encoded
        assert "+" not in encoded
        assert "/" not in encoded

    def test_decode_rejects_garbage(self) -> None:
        with pytest.raises(ValueError):
            decode_cursor("!!!not-base64!!!")

    def test_decode_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            decode_cursor("")

    def test_decode_rejects_non_object_payload(self) -> None:
        import base64

        encoded = base64.urlsafe_b64encode(b'"just-a-string"').rstrip(b"=").decode()
        with pytest.raises(ValueError):
            decode_cursor(encoded)


# ---------------------------------------------------------------------------
# Offset pagination
# ---------------------------------------------------------------------------


class TestOffsetPagination:
    async def test_returns_total_and_items(self, session: AsyncSession) -> None:
        stmt = select(_Item).order_by(_Item.created_at)
        page = await paginate(session, stmt, mode="offset", limit=10, offset=0)
        assert isinstance(page, Page)
        assert page.total == 25
        assert len(page.items) == 10
        assert page.limit == 10
        assert page.offset == 0
        assert page.next_cursor is None

    async def test_offset_skips_rows(self, session: AsyncSession) -> None:
        stmt = select(_Item).order_by(_Item.created_at)
        page = await paginate(session, stmt, mode="offset", limit=10, offset=20)
        assert len(page.items) == 5

    async def test_default_limit_applied(self, session: AsyncSession) -> None:
        stmt = select(_Item).order_by(_Item.created_at)
        page = await paginate(session, stmt, mode="offset")
        assert page.limit == DEFAULT_LIMIT
        assert len(page.items) == 25  # all fit under default

    async def test_caps_limit(self, session: AsyncSession) -> None:
        stmt = select(_Item).order_by(_Item.created_at)
        with pytest.raises(ValueError):
            await paginate(session, stmt, mode="offset", limit=MAX_LIMIT + 1)


# ---------------------------------------------------------------------------
# Cursor pagination
# ---------------------------------------------------------------------------


class TestCursorPagination:
    async def test_first_page_emits_next_cursor(self, session: AsyncSession) -> None:
        stmt = select(_Item)
        page = await paginate(
            session,
            stmt,
            mode="cursor",
            limit=10,
            cursor=None,
            id_column=_Item.id,
            created_at_column=_Item.created_at,
        )
        assert page.total is None
        assert page.limit == 10
        assert len(page.items) == 10
        assert page.next_cursor is not None
        assert page.prev_cursor is None

    async def test_next_cursor_walks_forward(self, session: AsyncSession) -> None:
        stmt = select(_Item)
        first = await paginate(
            session,
            stmt,
            mode="cursor",
            limit=10,
            id_column=_Item.id,
            created_at_column=_Item.created_at,
        )
        second = await paginate(
            session,
            stmt,
            mode="cursor",
            limit=10,
            cursor=first.next_cursor,
            id_column=_Item.id,
            created_at_column=_Item.created_at,
        )
        first_ids = {row.id for row in first.items}
        second_ids = {row.id for row in second.items}
        assert first_ids.isdisjoint(second_ids)
        assert second.prev_cursor is not None

    async def test_end_of_stream_emits_no_next_cursor(self, session: AsyncSession) -> None:
        stmt = select(_Item)
        page = await paginate(
            session,
            stmt,
            mode="cursor",
            limit=100,
            id_column=_Item.id,
            created_at_column=_Item.created_at,
        )
        assert page.next_cursor is None

    async def test_cursor_mode_requires_columns(self, session: AsyncSession) -> None:
        stmt = select(_Item)
        with pytest.raises(ValueError):
            await paginate(session, stmt, mode="cursor", limit=10)


class TestModeValidation:
    async def test_unknown_mode_raises(self, session: AsyncSession) -> None:
        stmt = select(_Item)
        with pytest.raises(ValueError):
            await paginate(session, stmt, mode="banana", limit=10)
