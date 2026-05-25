"""Shared SlowAPI Limiter singleton.

The Limiter must be a module-level object so route decorators like
``@limiter.limit("5/minute")`` can attach metadata at import time, and
``app.state.limiter`` (set in :mod:`app.main`) can point at the same
instance the ``SlowAPIMiddleware`` consults.

Optional: when ``RATELIMIT_STORAGE_URI`` is set (e.g. ``redis://...``)
the limiter persists across processes. With no URI it falls back to
in-process memory — fine for single-worker dev, never enough for
production. The CI gate in ``app.main`` warns at boot if a production
deployment is missing the storage URI.
"""

from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

__all__ = ["limiter"]


_storage_uri = (os.environ.get("RATELIMIT_STORAGE_URI") or "").strip() or None


limiter: Limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],
    storage_uri=_storage_uri,
)
