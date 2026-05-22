"""Tiny shared helpers for dev scripts. Pure stdlib, no third-party deps."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

# ── Repo layout ───────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
EXTENSION = ROOT / "extension"
VERIFIER = ROOT / "verifier"
ONCETAX = ROOT / "oncetax"
COV_DIR = ROOT / ".cov"

# ── ANSI colors (auto-disabled when not a TTY or NO_COLOR is set) ─────────
_USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def green(t: str) -> str:
    return _c("32", t)


def red(t: str) -> str:
    return _c("31", t)


def yellow(t: str) -> str:
    return _c("33", t)


def cyan(t: str) -> str:
    return _c("36", t)


def bold(t: str) -> str:
    return _c("1", t)


def dim(t: str) -> str:
    return _c("2", t)


# ── Status icons ──────────────────────────────────────────────────────────
OK = green("✓")
FAIL = red("✗")
WARN = yellow("!")


def header(title: str) -> None:
    print()
    print(bold(cyan(f"── {title} " + "─" * max(0, 60 - len(title)))))


def which(cmd: str) -> str | None:
    """Locate a command on PATH; on Windows also try .exe / .cmd / .bat."""
    found = shutil.which(cmd)
    if found:
        return found
    if os.name == "nt":
        for ext in (".exe", ".cmd", ".bat"):
            found = shutil.which(cmd + ext)
            if found:
                return found
    return None


def run(
    cmd: "list[str] | str",
    *,
    cwd: Path | None = None,
    check: bool = False,
    capture: bool = False,
    env: "dict[str, str] | None" = None,
) -> subprocess.CompletedProcess:
    """Run a subprocess with sensible defaults; honors shell=True for strings."""
    shell = isinstance(cmd, str)
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=check,
        shell=shell,
        text=True,
        capture_output=capture,
        env={**os.environ, **(env or {})},
    )


def step(label: str, ok: bool, detail: str = "") -> None:
    icon = OK if ok else FAIL
    line = f"  {icon} {label}"
    if detail:
        line += "  " + dim(detail)
    print(line)


def section_counts(results: Iterable[bool]) -> tuple[int, int]:
    total = 0
    passed = 0
    for r in results:
        total += 1
        if r:
            passed += 1
    return passed, total
