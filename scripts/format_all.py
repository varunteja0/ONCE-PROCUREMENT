"""Format every supported file in the repo.

Runs (in order, skipping any that aren't installed):
  - ruff format       (Python in backend/, verifier/, scripts/)
  - ruff check --fix  (autofixes lint where possible)
  - prettier --write  (JSON, MD, YAML, CSS, TS/TSX/JS via npx)
  - eslint --fix      (frontend/, extension/)

Returns non-zero only if a formatter that *is* installed exits with an error.
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
    dim,
    header,
    run,
    which,
    yellow,
)

SCRIPTS_DIR = Path(__file__).resolve().parent
PY_PATHS = [BACKEND, VERIFIER, SCRIPTS_DIR]
JS_PATHS = [FRONTEND, EXTENSION]


def _ruff(*args: str) -> int:
    ruff = which("ruff")
    if not ruff:
        print(f"  {yellow('-')} ruff not installed, skipping")
        return 0
    paths = [str(p) for p in PY_PATHS if p.exists()]
    cp = run([ruff, *args, *paths])
    return cp.returncode


def _prettier() -> int:
    npx = which("npx")
    if not npx:
        print(f"  {yellow('-')} npx not installed, skipping prettier")
        return 0
    cp = run(
        [npx, "--yes", "prettier", "--write", "--log-level=warn",
         "**/*.{json,jsonc,md,yml,yaml,css,scss}",
         "--ignore-path", ".gitignore"],
        cwd=ROOT,
    )
    return cp.returncode


def _eslint_fix(dir_: Path) -> int:
    if not (dir_ / "package.json").exists():
        return 0
    npx = which("npx")
    if not npx:
        return 0
    cp = run([npx, "eslint", ".", "--fix", "--max-warnings=999"], cwd=dir_)
    if cp.returncode != 0:
        print(f"  {yellow('!')} eslint --fix in {dir_.name} returned {cp.returncode}")
    return cp.returncode


def main() -> int:
    print(bold(cyan("format_all -- ruff + prettier + eslint --fix")))
    rcs: list[int] = []

    header("Python: ruff format + ruff check --fix")
    rcs.append(_ruff("format"))
    rcs.append(_ruff("check", "--fix"))

    header("Web: prettier --write")
    rcs.append(_prettier())

    header("Web: eslint --fix")
    for d in JS_PATHS:
        rcs.append(_eslint_fix(d))

    failed = sum(1 for r in rcs if r not in (0, None))
    if failed:
        print(f"\n{FAIL} {failed} formatter(s) reported errors. Output above.")
        return 1
    print(f"\n{OK} Repo formatted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
