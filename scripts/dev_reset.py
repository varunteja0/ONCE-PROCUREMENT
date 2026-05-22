"""Nuke local dev data and re-seed from scratch.

WHAT THIS DOES (in order):
  1. `docker compose down -v` -- drops Postgres + Redis volumes.
  2. `docker compose up -d db redis` -- fresh DB and cache.
  3. Waits for Postgres to accept connections (<= 60s).
  4. `alembic upgrade head` inside backend.
  5. `python scripts/seed_demo_tenant.py` if present.

USAGE:
    python scripts/dev_reset.py              # interactive confirmation
    python scripts/dev_reset.py --yes        # skip confirmation
    python scripts/dev_reset.py --no-seed    # migrate but skip seed

Destructive. Pure stdlib.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    BACKEND,
    FAIL,
    OK,
    ROOT,
    bold,
    cyan,
    dim,
    header,
    red,
    run,
    which,
    yellow,
)


def confirm(prompt: str) -> bool:
    try:
        ans = input(f"{prompt} [y/N] ").strip().lower()
    except EOFError:
        return False
    return ans in {"y", "yes"}


def wait_for_postgres(host: str = "127.0.0.1", port: int = 5432, timeout: int = 60) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            try:
                s.connect((host, port))
                return True
            except OSError:
                time.sleep(1)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Reset local Once dev data.")
    ap.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    ap.add_argument("--no-seed", action="store_true", help="Skip seed step.")
    args = ap.parse_args()

    print(bold(red("!  This will DELETE local Postgres and Redis volumes.")))
    print(dim("   (Source code and your .env are untouched.)"))
    if not args.yes and not confirm("Continue?"):
        print("Aborted.")
        return 1

    docker = which("docker")
    if not docker:
        print(f"{FAIL} docker not on PATH")
        return 2

    header("Stopping containers and removing volumes")
    cp = run([docker, "compose", "down", "-v"], cwd=ROOT)
    if cp.returncode != 0:
        print(f"{FAIL} docker compose down failed")
        return cp.returncode

    header("Starting db + redis")
    cp = run([docker, "compose", "up", "-d", "db", "redis"], cwd=ROOT)
    if cp.returncode != 0:
        return cp.returncode

    header("Waiting for Postgres")
    if not wait_for_postgres():
        print(f"{FAIL} postgres not reachable after 60s")
        return 1
    print(f"  {OK} postgres accepting connections")

    header("Applying migrations")
    venv_py = BACKEND / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    if venv_py.exists():
        cp = run([str(venv_py), "-m", "alembic", "upgrade", "head"], cwd=BACKEND)
    else:
        cp = run(["alembic", "upgrade", "head"], cwd=BACKEND)
    if cp.returncode != 0:
        print(f"{FAIL} alembic upgrade head failed")
        return cp.returncode

    if not args.no_seed:
        header("Seeding demo tenant")
        seed = ROOT / "scripts" / "seed_demo_tenant.py"
        if seed.exists():
            interp = str(venv_py) if venv_py.exists() else sys.executable
            cp = run([interp, str(seed)], cwd=ROOT)
            if cp.returncode != 0:
                print(f"{yellow('!')} seed script returned {cp.returncode} (continuing)")
        else:
            print(f"  {yellow('!')} scripts/seed_demo_tenant.py not present yet -- skipping")

    print(f"\n{OK} Reset complete. Next: {cyan('make up')} to launch the rest of the stack.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
