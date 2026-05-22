"""Once dev scripts package.

Each module in this package is a self-contained, stdlib-only CLI that supports
the local developer workflow (setup, diagnostics, reset, formatting, linting,
combined coverage). They are invoked from the Makefile / tasks.ps1 and may
also be run directly:

    python scripts/dev_doctor.py
    python scripts/format_all.py
"""

from __future__ import annotations

__all__: list[str] = []
