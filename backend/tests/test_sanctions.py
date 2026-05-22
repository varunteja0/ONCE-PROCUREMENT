"""Tests for the in-memory OFAC sanctions cache and matching logic."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services import sanctions_service
from app.services.sanctions_service import SanctionsEntry

pytestmark = pytest.mark.asyncio


def _inject(entries: list[SanctionsEntry]) -> None:
    cache = sanctions_service.get_cache()
    cache.replace(entries, source_url=None, source_path=None)
    cache.loaded_at = datetime.now(UTC)


async def test_is_sanctioned_returns_false_by_default() -> None:
    assert sanctions_service.is_sanctioned("ACME CORP", "12-3456789") is False


async def test_is_sanctioned_matches_synthetic_name_entry() -> None:
    _inject(
        [
            SanctionsEntry(
                source="TEST",
                sdn_id="TEST-1",
                name="ACME CORP",
                name_lower="acme corp",
                sdn_type="entity",
                program="TESTING",
                raw_ein=None,
            )
        ]
    )

    assert sanctions_service.is_sanctioned("ACME CORP", "00-0000000") is True
    # Case-insensitive substring match.
    assert sanctions_service.is_sanctioned("Acme Corp Holdings", None) is True
    # Non-matching name does not register.
    assert sanctions_service.is_sanctioned("Zebra Holdings", None) is False


async def test_is_sanctioned_ein_match_wins_over_name_miss() -> None:
    _inject(
        [
            SanctionsEntry(
                source="TEST",
                sdn_id="TEST-2",
                name="Totally Unrelated Name Ltd",
                name_lower="totally unrelated name ltd",
                sdn_type="entity",
                program="TESTING",
                raw_ein="123456789",
            )
        ]
    )

    # The EIN matches even though the legal name doesn't appear in the cache.
    assert sanctions_service.is_sanctioned("ACME CORP", "12-3456789") is True
    # Different EIN with non-matching name → no match.
    assert sanctions_service.is_sanctioned("ACME CORP", "99-9999999") is False


async def test_empty_inputs_do_not_match() -> None:
    _inject(
        [
            SanctionsEntry(
                source="TEST",
                sdn_id="TEST-3",
                name="Sample Entity",
                name_lower="sample entity",
                sdn_type="entity",
                program="TESTING",
                raw_ein="555555555",
            )
        ]
    )

    assert sanctions_service.is_sanctioned("", None) is False
    assert sanctions_service.is_sanctioned("", "") is False
