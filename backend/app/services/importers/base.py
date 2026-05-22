"""L3.7 — Base protocol for entity importers.

An importer is the entity-specific glue between the generic parsing /
orchestration layer and a single SQLAlchemy model. Subclasses declare:

* the user-visible column metadata (so the UI mapper can render it);
* alias maps (so we accept ``company`` / ``supplier`` / ``account_name``
  for the canonical ``name`` field);
* per-row validation + normalisation;
* a chunked insert that handles dedupe vs the DB.

The orchestrator in :mod:`app.services.import_service` calls these
methods — never the parsers directly — so adding a new entity type is
purely "subclass + register".
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

__all__ = [
    "ColumnSpec",
    "RowError",
    "ValidatedRow",
    "BaseImporter",
]


@dataclass(slots=True)
class ColumnSpec:
    """One column declared by an importer."""

    field: str
    required: bool
    aliases: tuple[str, ...]
    description: str
    example: str | None = None


@dataclass(slots=True)
class RowError:
    row_number: int
    column: str | None
    value: str | None
    error_code: str
    error_message: str


@dataclass(slots=True)
class ValidatedRow:
    """Result of ``validate_row`` — exactly one of ``data`` / ``errors`` is meaningful."""

    row_number: int
    data: dict[str, Any] | None = None
    errors: list[RowError] = field(default_factory=list)
    dedupe_key: str | None = None  # e.g. normalized FEIN; powers in-file dedupe

    @property
    def ok(self) -> bool:
        return not self.errors


class BaseImporter(abc.ABC):
    """Subclass per entity. Register in :mod:`app.services.importers`."""

    entity_type: str  # matches ``ImportEntityType.value``
    columns: tuple[ColumnSpec, ...] = ()

    # ---------- introspection helpers (shared) -----------------------------

    @classmethod
    def required_columns(cls) -> tuple[ColumnSpec, ...]:
        return tuple(c for c in cls.columns if c.required)

    @classmethod
    def optional_columns(cls) -> tuple[ColumnSpec, ...]:
        return tuple(c for c in cls.columns if not c.required)

    @classmethod
    def alias_map(cls) -> dict[str, str]:
        """Reverse-index: any accepted alias → canonical ``field`` name."""

        out: dict[str, str] = {}
        for spec in cls.columns:
            out[spec.field] = spec.field
            for alias in spec.aliases:
                out[alias.lower()] = spec.field
        return out

    @classmethod
    def remap_row(
        cls,
        row: dict[str, str],
        user_mapping: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Rewrite raw headers to canonical field names.

        ``user_mapping`` (source_header → canonical_field) takes
        precedence over the built-in alias map.
        """

        aliases = cls.alias_map()
        out: dict[str, str] = {}
        for key, value in row.items():
            k = (key or "").strip().lower()
            if not k:
                continue
            target: str | None = None
            if user_mapping and k in user_mapping:
                target = user_mapping[k]
            elif k in aliases:
                target = aliases[k]
            if target is not None:
                out[target] = value
        return out

    @classmethod
    def missing_required_columns(
        cls,
        header_set: set[str],
        user_mapping: dict[str, str] | None = None,
    ) -> list[str]:
        """Return required canonical fields not satisfied by the headers.

        The user mapping (if any) can satisfy a requirement even when no
        alias matches the source header.
        """

        aliases = cls.alias_map()
        present: set[str] = set()
        for header in header_set:
            h = (header or "").strip().lower()
            if not h:
                continue
            if user_mapping and h in user_mapping:
                present.add(user_mapping[h])
            elif h in aliases:
                present.add(aliases[h])
        return [c.field for c in cls.required_columns() if c.field not in present]

    # ---------- abstract per-entity hooks ----------------------------------

    @abc.abstractmethod
    def validate_row(
        self,
        row: dict[str, str],
        row_number: int,
    ) -> ValidatedRow:
        """Validate + normalise a single row in isolation (no DB access)."""

    @abc.abstractmethod
    async def insert_batch(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        rows: list[ValidatedRow],
        on_duplicate: str,
    ) -> dict[str, int]:
        """Insert (or update / skip) up to ``import_chunk_size`` rows.

        Returns counts: ``{"inserted": n, "updated": n, "skipped": n,
        "errors": n}``. Implementations MUST detect duplicate-vs-DB
        conflicts and turn them into row errors when ``on_duplicate ==
        "error"``.
        """

    @abc.abstractmethod
    async def existing_dedupe_keys(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        keys: list[str],
    ) -> set[str]:
        """Return the subset of ``keys`` already present in the DB."""
