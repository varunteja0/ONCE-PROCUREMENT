"""Static data tables used by ``seed_realistic.py``.

All modules in this package must be **pure data** — no I/O, no DB access, no
randomness. The random/seed plumbing lives in :mod:`generators` and the
orchestration in :mod:`backend.scripts.seed_realistic`.
"""

from __future__ import annotations

SEED_MARKER: str = "L3-2-realistic-v1"
"""Tag attached to every row created by the realistic seed.

The reset script keys off this exact string to know which rows are safe to
delete. Bump the suffix (``-v2``, ``-v3``…) when the schema or population
materially changes so old data can be reset independently of new data.
"""

__all__ = ["SEED_MARKER"]
