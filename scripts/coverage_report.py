"""Combined coverage report across backend + frontend + extension + verifier.

Runs each suite with coverage enabled, then prints a single table:

    component    stmts    covered    pct
    -----------  -------  ---------  ------
    backend      1234     987        80.0%
    verifier     210      199        94.8%
    frontend     876      702        80.1%
    extension    540      421        78.0%
    -----------  -------  ---------  ------
    TOTAL        2860     2309       80.7%

Exits non-zero if combined coverage is below the threshold (default 75%).

Pure stdlib (parses JSON output from coverage / vitest --reporter=json).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    BACKEND,
    COV_DIR,
    EXTENSION,
    FAIL,
    FRONTEND,
    OK,
    VERIFIER,
    bold,
    cyan,
    dim,
    header,
    red,
    run,
    which,
    yellow,
)


def _ensure_cov_dir() -> None:
    COV_DIR.mkdir(parents=True, exist_ok=True)


def _venv_py(d: Path) -> Path:
    return d / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")


def _python_for(d: Path) -> str:
    p = _venv_py(d)
    if p.exists():
        return str(p)
    p = _venv_py(BACKEND)  # verifier shares backend venv per dev_setup
    if p.exists():
        return str(p)
    return sys.executable


def run_backend() -> tuple[int, int] | None:
    if not BACKEND.exists():
        return None
    out = COV_DIR / "backend.json"
    py = _python_for(BACKEND)
    cp = run(
        [py, "-m", "pytest", "-q", "--cov=app", f"--cov-report=json:{out}", "--cov-report=term-missing:skip-covered"],
        cwd=BACKEND,
    )
    if cp.returncode != 0:
        print(f"  {yellow('!')} backend pytest exited {cp.returncode}; continuing")
    return _parse_coverage_py(out)


def run_verifier() -> tuple[int, int] | None:
    if not VERIFIER.exists():
        return None
    out = COV_DIR / "verifier.json"
    py = _python_for(VERIFIER)
    cp = run(
        [py, "-m", "pytest", "-q", "--cov=app", f"--cov-report=json:{out}"],
        cwd=VERIFIER,
    )
    if cp.returncode != 0:
        print(f"  {yellow('!')} verifier pytest exited {cp.returncode}; continuing")
    return _parse_coverage_py(out)


def run_npm_coverage(dir_: Path, name: str) -> tuple[int, int] | None:
    if not (dir_ / "package.json").exists():
        return None
    npm = which("npm")
    if not npm:
        return None
    out = COV_DIR / f"{name}.json"
    # Try `npm run coverage` first; fall back to vitest direct.
    cp = run([npm, "run", "coverage", "--silent"], cwd=dir_)
    if cp.returncode != 0:
        npx = which("npx")
        if npx:
            run([npx, "vitest", "run", "--coverage", "--coverage.reporter=json-summary", f"--coverage.reportsDirectory={out.parent / (name + '-cov')}"], cwd=dir_)
    return _parse_coverage_js(dir_, out, name)


def _parse_coverage_py(path: Path) -> tuple[int, int]:
    if not path.exists():
        return (0, 0)
    data = json.loads(path.read_text(encoding="utf-8"))
    totals: dict[str, Any] = data.get("totals", {})
    stmts = int(totals.get("num_statements", 0))
    covered = int(totals.get("covered_lines", 0))
    return covered, stmts


def _parse_coverage_js(dir_: Path, out_json: Path, name: str) -> tuple[int, int]:
    # vitest v8 writes coverage-summary.json under coverage/ by default
    for candidate in (
        out_json,
        dir_ / "coverage" / "coverage-summary.json",
        COV_DIR / f"{name}-cov" / "coverage-summary.json",
    ):
        if candidate.exists():
            data = json.loads(candidate.read_text(encoding="utf-8"))
            total = data.get("total", {})
            if total and "statements" in total:
                s = total["statements"]
                return int(s.get("covered", 0)), int(s.get("total", 0))
    return (0, 0)


def _fmt_pct(covered: int, stmts: int) -> str:
    if stmts == 0:
        return "  n/a"
    return f"{(covered / stmts * 100):5.1f}%"


def main() -> int:
    ap = argparse.ArgumentParser(description="Combined Once coverage report.")
    ap.add_argument("--threshold", type=float, default=75.0, help="Fail if combined %% < threshold (default 75).")
    ap.add_argument("--skip-js", action="store_true")
    ap.add_argument("--skip-py", action="store_true")
    args = ap.parse_args()

    _ensure_cov_dir()
    print(bold(cyan("Once coverage report")))

    results: dict[str, tuple[int, int] | None] = {}
    if not args.skip_py:
        header("Backend (pytest --cov)")
        results["backend"] = run_backend()
        header("Verifier (pytest --cov)")
        results["verifier"] = run_verifier()
    if not args.skip_js:
        header("Frontend (vitest --coverage)")
        results["frontend"] = run_npm_coverage(FRONTEND, "frontend")
        header("Extension (vitest --coverage)")
        results["extension"] = run_npm_coverage(EXTENSION, "extension")

    header("Combined report")
    print(f"  {'component':<12} {'stmts':>8} {'covered':>10} {'pct':>8}")
    print(f"  {'-' * 12} {'-' * 8} {'-' * 10} {'-' * 8}")
    total_stmts = 0
    total_cov = 0
    for name, val in results.items():
        if val is None:
            print(f"  {name:<12} {'-':>8} {'-':>10} {dim('skipped'):>8}")
            continue
        cov, stmts = val
        total_stmts += stmts
        total_cov += cov
        print(f"  {name:<12} {stmts:>8} {cov:>10} {_fmt_pct(cov, stmts):>8}")
    print(f"  {'-' * 12} {'-' * 8} {'-' * 10} {'-' * 8}")
    pct = (total_cov / total_stmts * 100) if total_stmts else 0
    print(f"  {'TOTAL':<12} {total_stmts:>8} {total_cov:>10} {_fmt_pct(total_cov, total_stmts):>8}")

    if pct < args.threshold and total_stmts > 0:
        print(f"\n{red(f'Coverage {pct:.1f}% below threshold {args.threshold:.1f}%.')}")
        return 1
    print(f"\n{OK} Coverage {pct:.1f}% meets threshold {args.threshold:.1f}%.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
