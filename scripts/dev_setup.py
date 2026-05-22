"""One-shot environment bootstrapper for the Once repo.

    python scripts/dev_setup.py                # full bootstrap (idempotent)
    python scripts/dev_setup.py --dry-run      # print what would happen, do nothing
    python scripts/dev_setup.py --check        # delegate to dev_doctor.py
    python scripts/dev_setup.py --skip-doctor  # skip the pre-flight doctor
    python scripts/dev_setup.py --skip-npm     # skip npm installs
    python scripts/dev_setup.py --skip-playwright
    python scripts/dev_setup.py --skip-precommit

Re-running this script when everything is already set up is a near no-op.

Pure stdlib + subprocess. Cross-platform.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
import venv
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    BACKEND,
    EXTENSION,
    FAIL,
    FRONTEND,
    OK,
    ONCETAX,
    ROOT,
    VERIFIER,
    WARN,
    bold,
    cyan,
    dim,
    green,
    header,
    red,
    run,
    which,
    yellow,
)


DRY_RUN = False  # set by main(); checked by every side-effecting helper.


def _say(msg: str) -> None:
    print(f"  {cyan('+')} {msg}")


def _dry(msg: str) -> None:
    print(f"  {dim('· dry-run:')} {msg}")


# ── venv helpers ─────────────────────────────────────────────────────────
def _venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")


def create_venv(venv_dir: Path) -> Path:
    py = _venv_python(venv_dir)
    if py.exists():
        print(f"  {OK} venv already exists: {dim(str(venv_dir))}")
        return py
    if DRY_RUN:
        _dry(f"create venv at {venv_dir}")
        return py
    _say(f"creating venv at {venv_dir}")
    venv.create(venv_dir, with_pip=True, clear=False, symlinks=os.name != "nt")
    return py


def pip_install(py: Path, *reqs: str) -> int:
    cmd = [str(py), "-m", "pip", "install", "--quiet", "--upgrade", *reqs]
    if DRY_RUN:
        _dry(" ".join(cmd))
        return 0
    cp = run(cmd)
    return cp.returncode


# ── Pre-flight: doctor ───────────────────────────────────────────────────
def preflight_doctor() -> bool:
    header("Pre-flight: dev_doctor")
    if DRY_RUN:
        _dry("python scripts/dev_doctor.py")
        return True
    from dev_doctor import main as doctor_main  # noqa: WPS433

    rc = doctor_main()
    if rc != 0:
        print()
        print(red("  Doctor reported required failures. Fix them, then re-run setup."))
        return False
    return True


# ── Phases ───────────────────────────────────────────────────────────────
def setup_backend() -> bool:
    if not BACKEND.exists():
        print(f"  {FAIL} backend/ not found")
        return False
    py = create_venv(BACKEND / ".venv")
    if pip_install(py, "pip") != 0:
        return False
    req = BACKEND / "requirements.txt"
    dev_req = BACKEND / "requirements-dev.txt"
    if req.exists() and pip_install(py, "-r", str(req)) != 0:
        return False
    if dev_req.exists():
        pip_install(py, "-r", str(dev_req))
    pip_install(py, "ruff", "black", "mypy", "pytest", "pytest-cov", "pre-commit")
    return True


def setup_verifier() -> bool:
    if not VERIFIER.exists():
        print(f"  {yellow('-')} verifier/ not found, skipping")
        return True
    req = VERIFIER / "requirements.txt"
    if not req.exists():
        return True
    py = _venv_python(BACKEND / ".venv")
    if not py.exists() and not DRY_RUN:
        print(f"  {FAIL} backend venv missing — run setup_backend first")
        return False
    return pip_install(py, "-r", str(req)) == 0


def setup_npm(target: Path, name: str) -> bool:
    if not target.exists():
        print(f"  {yellow('-')} {target} not found, skipping")
        return True
    npm = which("npm")
    if not npm:
        print(f"  {FAIL} npm not found on PATH")
        return False
    has_lock = (target / "package-lock.json").exists()
    if has_lock:
        # Idempotent fast path: if node_modules looks fresh relative to the
        # lockfile, skip. (Heuristic: node_modules/.package-lock.json exists.)
        cache = target / "node_modules" / ".package-lock.json"
        lock = target / "package-lock.json"
        if cache.exists() and cache.stat().st_mtime >= lock.stat().st_mtime:
            print(f"  {OK} {name}: node_modules up-to-date with lockfile")
            return True
        cmd = [npm, "ci", "--no-audit", "--no-fund"]
    else:
        cmd = [npm, "install", "--no-audit", "--no-fund"]
    if DRY_RUN:
        _dry(f"({name}) " + " ".join(cmd))
        return True
    cp = run(cmd, cwd=target)
    return cp.returncode == 0


def setup_playwright() -> bool:
    py = _venv_python(BACKEND / ".venv")
    if not py.exists() and not DRY_RUN:
        print(f"  {FAIL} backend venv missing")
        return False
    pip_install(py, "playwright")
    # Demo only needs chromium — save ~1GB by skipping webkit/firefox.
    cmd = [str(py), "-m", "playwright", "install", "--with-deps", "chromium"]
    if DRY_RUN:
        _dry(" ".join(cmd))
        return True
    cp = run(cmd)
    if cp.returncode != 0:
        # --with-deps requires root on Linux; retry without it as a fallback.
        print(f"  {yellow('!')} `playwright install --with-deps` failed; retrying without --with-deps")
        cp = run([str(py), "-m", "playwright", "install", "chromium"])
    return cp.returncode == 0


def setup_precommit() -> bool:
    py = _venv_python(BACKEND / ".venv")
    if not py.exists() and not DRY_RUN:
        return False
    cmd = [str(py), "-m", "pre_commit", "install"]
    if DRY_RUN:
        _dry(" ".join(cmd))
        return True
    cp = run(cmd, cwd=ROOT)
    if cp.returncode != 0:
        print(f"  {yellow('!')} pre-commit install returned {cp.returncode}")
        return False
    return True


# ── Env file copies ──────────────────────────────────────────────────────
_ENV_TARGETS = [
    (ROOT, "root"),
    (BACKEND, "backend"),
    (FRONTEND, "frontend"),
    (EXTENSION, "extension"),
    (ONCETAX, "oncetax"),
]


def copy_env_examples() -> bool:
    ok = True
    leftover_warnings: list[str] = []
    for base, label in _ENV_TARGETS:
        src = base / ".env.example"
        dst = base / ".env"
        if not src.exists():
            continue  # subproject has no template — nothing to copy
        if dst.exists():
            print(f"  {OK} {label}: .env already present (left untouched)")
        else:
            if DRY_RUN:
                _dry(f"cp {src} {dst}")
            else:
                shutil.copyfile(src, dst)
                print(f"  {OK} {label}: created .env from .env.example")
        # Scan for leftover CHANGE_ME placeholders.
        target = dst if dst.exists() else src
        try:
            content = target.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(content.splitlines(), 1):
            if "CHANGE_ME" in line and not line.lstrip().startswith("#"):
                leftover_warnings.append(f"{label}/.env:{lineno}: {line.strip()}")
    if leftover_warnings:
        print(f"  {WARN} {len(leftover_warnings)} CHANGE_ME placeholder(s) still present:")
        for w in leftover_warnings[:10]:
            print("      " + dim(w))
        if len(leftover_warnings) > 10:
            print("      " + dim(f"... and {len(leftover_warnings) - 10} more"))
    return ok


# ── Alembic on local sqlite (for unit tests) ─────────────────────────────
def setup_alembic_sqlite() -> bool:
    py = _venv_python(BACKEND / ".venv")
    if not py.exists() and not DRY_RUN:
        print(f"  {WARN} backend venv missing — skipping alembic")
        return True
    alembic_ini = BACKEND / "alembic.ini"
    if not alembic_ini.exists():
        print(f"  {yellow('-')} backend/alembic.ini not found, skipping")
        return True
    # Use an in-repo sqlite so unit tests don't need Postgres.
    sqlite_url = "sqlite:///" + str((BACKEND / "dev.sqlite").as_posix())
    env = dict(os.environ)
    env["DATABASE_URL"] = sqlite_url
    cmd = [str(py), "-m", "alembic", "upgrade", "head"]
    if DRY_RUN:
        _dry(f"DATABASE_URL={sqlite_url} " + " ".join(cmd))
        return True
    cp = run(cmd, cwd=BACKEND, env=env)
    if cp.returncode != 0:
        print(f"  {WARN} alembic upgrade against sqlite failed (non-fatal for unit tests)")
        return True
    print(f"  {OK} alembic upgraded local sqlite ({sqlite_url})")
    print(f"      {dim('after `make up`, run `make migrate` to upgrade the Postgres dev database.')}")
    return True


# ── Phase runner ─────────────────────────────────────────────────────────
def _phase(label: str, fn) -> tuple[str, bool, float]:
    header(label)
    t0 = time.monotonic()
    try:
        ok = bool(fn())
    except Exception as exc:  # noqa: BLE001
        print(f"  {FAIL} unhandled exception: {exc}")
        ok = False
    elapsed = time.monotonic() - t0
    print(f"  {dim(f'({elapsed:.1f}s)')}")
    return label, ok, elapsed


def main() -> int:
    global DRY_RUN  # noqa: PLW0603

    ap = argparse.ArgumentParser(description="Bootstrap the Once dev environment.")
    ap.add_argument("--check", action="store_true", help="Run dev_doctor.py instead and exit.")
    ap.add_argument("--dry-run", action="store_true", help="Print what would happen; touch nothing.")
    ap.add_argument("--skip-doctor", action="store_true", help="Skip the pre-flight doctor.")
    ap.add_argument("--skip-npm", action="store_true")
    ap.add_argument("--skip-playwright", action="store_true")
    ap.add_argument("--skip-precommit", action="store_true")
    args = ap.parse_args()

    if args.check:
        from dev_doctor import main as doctor_main  # noqa: WPS433

        return doctor_main()

    DRY_RUN = bool(args.dry_run)

    title = "Once dev setup — this may take a few minutes on first run"
    if DRY_RUN:
        title += "  [DRY RUN]"
    print(bold(cyan(title)))

    if not args.skip_doctor:
        if not preflight_doctor():
            return 1

    phases: list[tuple[str, bool, float]] = []

    phases.append(_phase("Copy .env templates", copy_env_examples))
    phases.append(_phase("Backend venv + dependencies", setup_backend))
    phases.append(_phase("Verifier dependencies", setup_verifier))
    if not args.skip_npm:
        phases.append(_phase("frontend  (npm ci)", lambda: setup_npm(FRONTEND, "frontend")))
        phases.append(_phase("extension (npm ci)", lambda: setup_npm(EXTENSION, "extension")))
        phases.append(_phase("oncetax   (npm ci)", lambda: setup_npm(ONCETAX, "oncetax")))
    if not args.skip_playwright:
        phases.append(_phase("Playwright (chromium + system deps)", setup_playwright))
    phases.append(_phase("Alembic upgrade (local sqlite)", setup_alembic_sqlite))
    if not args.skip_precommit:
        phases.append(_phase("pre-commit hooks", setup_precommit))

    # ── Summary ──────────────────────────────────────────────────────
    header("Summary")
    total = 0.0
    failed: list[str] = []
    for label, ok, elapsed in phases:
        total += elapsed
        icon = OK if ok else FAIL
        print(f"  {icon} {label:<42} {dim(f'{elapsed:>6.1f}s')}")
        if not ok:
            failed.append(label)

    print(f"\n  {dim(f'total: {total:.1f}s')}")
    if failed:
        print(f"\n{FAIL} {len(failed)} phase(s) failed: {', '.join(failed)}")
        print(dim("  -> run `python scripts/dev_doctor.py` for diagnostics."))
        return 1
    print()
    if DRY_RUN:
        print(green("  Dry run complete — re-run without --dry-run to apply."))
    else:
        print(green("  Setup complete. Try: ") + cyan("make demo") + green("  (or ") + cyan(".\\tasks.ps1 demo") + green(" on Windows)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
