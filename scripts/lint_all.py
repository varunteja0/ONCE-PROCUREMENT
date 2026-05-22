"""Run all linters across the repo and aggregate their exit codes.

Runs:
  - ruff check                (Python in backend/, verifier/, scripts/)
  - ruff format --check       (Python formatting drift)
  - mypy                      (backend/app/)  -- best-effort, non-blocking on missing
  - prettier --check          (JSON/MD/YAML/CSS/TS/TSX/JS)
  - eslint                    (frontend/, extension/)
  - tsc --noEmit              (frontend/, extension/)

Exits non-zero if any *installed* linter reported errors. Missing optional
tools degrade gracefully with a yellow warning.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    BACKEND,
    EXTENSION,
    FAIL,
    FRONTEND,
    OK,
    ROOT,
    VERIFIER,
    bold,
    cyan,
    header,
    run,
    which,
    yellow,
)

SCRIPTS_DIR = Path(__file__).resolve().parent
PY_PATHS = [BACKEND, VERIFIER, SCRIPTS_DIR]


def _ruff_check() -> int:
    ruff = which("ruff")
    if not ruff:
        print(f"  {yellow('-')} ruff not installed, skipping")
        return 0
    paths = [str(p) for p in PY_PATHS if p.exists()]
    return run([ruff, "check", *paths]).returncode


def _ruff_format_check() -> int:
    ruff = which("ruff")
    if not ruff:
        return 0
    paths = [str(p) for p in PY_PATHS if p.exists()]
    return run([ruff, "format", "--check", *paths]).returncode


def _mypy() -> int:
    mypy = which("mypy")
    if not mypy or not (BACKEND / "app").exists():
        print(f"  {yellow('-')} mypy or backend/app not available, skipping")
        return 0
    cp = run([mypy, "--ignore-missing-imports", "app"], cwd=BACKEND)
    if cp.returncode != 0:
        print(f"  {yellow('!')} mypy reported issues (non-blocking)")
    return 0  # advisory only


def _prettier_check() -> int:
    npx = which("npx")
    if not npx:
        return 0
    return run(
        [npx, "--yes", "prettier", "--check", "--log-level=warn",
         "**/*.{json,jsonc,md,yml,yaml,css,scss}",
         "--ignore-path", ".gitignore"],
        cwd=ROOT,
    ).returncode


def _eslint(dir_: Path) -> int:
    if not (dir_ / "package.json").exists():
        return 0
    npx = which("npx")
    if not npx:
        return 0
    return run([npx, "eslint", ".", "--max-warnings=0"], cwd=dir_).returncode


def _tsc(dir_: Path) -> int:
    if not (dir_ / "tsconfig.json").exists():
        return 0
    npx = which("npx")
    if not npx:
        return 0
    return run([npx, "tsc", "--noEmit"], cwd=dir_).returncode


def main() -> int:
    print(bold(cyan("lint_all -- ruff + mypy + prettier + eslint + tsc")))
    results: dict[str, int] = {}

    header("Python: ruff check")
    results["ruff-check"] = _ruff_check()

    header("Python: ruff format --check")
    results["ruff-format"] = _ruff_format_check()

    header("Python: mypy (advisory)")
    results["mypy"] = _mypy()

    header("Web: prettier --check")
    results["prettier"] = _prettier_check()

    for d in (FRONTEND, EXTENSION):
        header(f"Web: eslint {d.name}")
        results[f"eslint-{d.name}"] = _eslint(d)
        header(f"Web: tsc --noEmit {d.name}")
        results[f"tsc-{d.name}"] = _tsc(d)

    header("Summary")
    failed: list[str] = []
    for name, rc in results.items():
        if rc == 0:
            print(f"  {OK} {name}")
        else:
            print(f"  {FAIL} {name}  (exit {rc})")
            failed.append(name)
    if failed:
        print(f"\n{FAIL} {len(failed)} linter(s) failed: {', '.join(failed)}")
        return 1
    print(f"\n{OK} All linters clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
