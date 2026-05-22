"""Diagnostic for the Once dev environment.

Runs a battery of independent checks (toolchain versions, container
runtime, free ports, env vars, disk space, repo layout) and prints a
colored summary. Exit code 0 iff every *required* check passes —
warnings never block.

Each check has:
    id        e.g. ``DOC.PY.VER``
    category  ``required`` | ``recommended``
    result    ``ok`` | ``warn`` | ``fail``
    fix       human-readable hint with the exact command to run

Pure stdlib, cross-platform safe.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Force UTF-8 stdout on Windows so box-drawing / check-mark glyphs don't
# blow up on the default cp1252 console.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    FAIL,
    OK,
    ROOT,
    WARN,
    bold,
    cyan,
    dim,
    green,
    header,
    red,
    which,
    yellow,
)

# ── Required versions ────────────────────────────────────────────────────
REQ_PYTHON = (3, 12)
REQ_NODE = 20
REQ_DISK_GB = 5

# Ports the demo stack binds. Anything listening here on 127.0.0.1 will
# collide with `make up`.
REQUIRED_PORTS: list[tuple[int, str]] = [
    (5173, "frontend (vite)"),
    (8000, "backend (uvicorn)"),
    (8080, "verifier"),
    (5432, "postgres"),
    (6379, "redis"),
    (8081, "nginx fixture portal"),
    (8082, "nginx fixture portal"),
    (8083, "nginx fixture portal"),
    (8084, "nginx fixture portal"),
    (8085, "nginx fixture portal"),
]

REQUIRED_PATHS = ["backend", "frontend", "extension", "verifier"]


# ── Result dataclass ─────────────────────────────────────────────────────
@dataclass
class Check:
    id: str
    label: str
    category: str  # "required" | "recommended"
    result: str = "ok"  # "ok" | "warn" | "fail"
    detail: str = ""
    fix: str = ""
    extras: list[str] = field(default_factory=list)

    def render(self) -> None:
        icon = {"ok": OK, "warn": WARN, "fail": FAIL}[self.result]
        line = f"  {icon} [{self.id}] {self.label}"
        if self.detail:
            line += "  " + dim(self.detail)
        print(line)
        for extra in self.extras:
            print("      " + dim(extra))
        if self.fix and self.result != "ok":
            print("      " + yellow("fix: ") + self.fix)


# ── Subprocess helpers ───────────────────────────────────────────────────
def _run(cmd: list[str], timeout: int = 5) -> subprocess.CompletedProcess:
    """Run a subprocess with a hard timeout. Never raises on non-zero exit."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        cp = subprocess.CompletedProcess(cmd, 124, "", str(exc))
        return cp


def _version_tuple(s: str) -> tuple[int, ...]:
    m = re.search(r"(\d+(?:\.\d+){1,2})", s or "")
    return tuple(int(p) for p in m.group(1).split(".")) if m else ()


# ── Individual checks ────────────────────────────────────────────────────
def check_python() -> Check:
    v = sys.version_info
    c = Check("DOC.PY.VER", "Python interpreter", "required")
    c.detail = f"found {v.major}.{v.minor}.{v.micro} (need >= {REQ_PYTHON[0]}.{REQ_PYTHON[1]})"
    if (v.major, v.minor) < REQ_PYTHON:
        c.result = "fail"
        c.fix = f"install Python {REQ_PYTHON[0]}.{REQ_PYTHON[1]}+ from https://www.python.org/downloads/"
    return c


def check_node() -> Check:
    c = Check("DOC.NODE.VER", "Node.js", "required")
    node = which("node")
    if not node:
        c.result = "fail"
        c.detail = "not on PATH"
        c.fix = f"install Node {REQ_NODE}+ from https://nodejs.org/ (or use nvm)"
        return c
    cp = _run([node, "--version"])
    ver = _version_tuple(cp.stdout)
    c.detail = f"found {cp.stdout.strip()} (need >= {REQ_NODE})"
    if not ver or ver[0] < REQ_NODE:
        c.result = "fail"
        c.fix = f"upgrade Node to {REQ_NODE}+ (e.g. `nvm install {REQ_NODE} && nvm use {REQ_NODE}`)"
    return c


def check_npm() -> Check:
    c = Check("DOC.NPM.PRESENT", "npm", "required")
    npm = which("npm")
    if not npm:
        c.result = "fail"
        c.detail = "not on PATH"
        c.fix = "npm ships with Node — reinstall Node from https://nodejs.org/"
        return c
    cp = _run([npm, "--version"])
    c.detail = f"found {cp.stdout.strip()}"
    return c


def check_git() -> Check:
    c = Check("DOC.GIT.PRESENT", "git", "recommended")
    g = which("git")
    if not g:
        c.result = "warn"
        c.detail = "not on PATH"
        c.fix = "install git from https://git-scm.com/downloads"
        return c
    cp = _run([g, "--version"])
    c.detail = cp.stdout.strip()
    return c


def check_docker_cli() -> Check:
    c = Check("DOC.DOCKER.CLI", "Docker CLI", "required")
    docker = which("docker")
    if not docker:
        c.result = "fail"
        c.detail = "not on PATH"
        c.fix = "install Docker Desktop from https://docs.docker.com/get-docker/"
        return c
    cp = _run([docker, "--version"])
    c.detail = cp.stdout.strip() or "(version unknown)"
    return c


def check_docker_daemon() -> Check:
    c = Check("DOC.DOCKER.DAEMON", "Docker daemon", "required")
    docker = which("docker")
    if not docker:
        c.result = "fail"
        c.detail = "docker CLI not installed"
        c.fix = "install Docker Desktop and start it"
        return c
    cp = _run([docker, "info", "--format", "{{.ServerVersion}}"], timeout=5)
    if cp.returncode != 0 or not cp.stdout.strip():
        c.result = "fail"
        c.detail = "daemon not responding (timed out or refused)"
        if os.name == "nt":
            c.fix = "start Docker Desktop and wait for the whale icon to stop animating"
        else:
            c.fix = "start the Docker daemon (`sudo systemctl start docker` on Linux, Docker Desktop on macOS)"
        return c
    c.detail = f"server {cp.stdout.strip()}"
    return c


def check_docker_compose() -> Check:
    c = Check("DOC.DOCKER.COMPOSE", "Docker Compose v2", "required")
    docker = which("docker")
    if not docker:
        c.result = "fail"
        c.detail = "docker CLI not installed"
        c.fix = "install Docker Desktop (includes Compose v2)"
        return c
    cp = _run([docker, "compose", "version", "--short"])
    if cp.returncode != 0 or not cp.stdout.strip():
        c.result = "fail"
        c.detail = "`docker compose` not available"
        c.fix = "upgrade Docker Desktop to a version that bundles Compose v2"
        return c
    c.detail = f"v{cp.stdout.strip()}"
    return c


def check_playwright_deps() -> Check:
    """Best-effort — never fails."""
    c = Check("DOC.PLAYWRIGHT.DEPS", "Playwright system deps", "recommended")
    venv_py = ROOT / "backend" / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    if not venv_py.exists():
        c.result = "warn"
        c.detail = "backend venv not yet created"
        c.fix = "run `make setup` to bootstrap the venv and install Playwright"
        return c
    cp = _run([str(venv_py), "-c", "import playwright; print(playwright.__version__)"])
    if cp.returncode != 0:
        c.result = "warn"
        c.detail = "playwright Python package not installed"
        c.fix = "run `make setup`"
        return c
    c.detail = f"playwright {cp.stdout.strip()}"
    # Check chromium is installed (best-effort: cache dir presence).
    cp2 = _run([str(venv_py), "-m", "playwright", "install", "--dry-run", "chromium"], timeout=15)
    out = (cp2.stdout or "") + (cp2.stderr or "")
    if cp2.returncode != 0:
        c.result = "warn"
        c.detail += " (chromium check skipped)"
        c.fix = "run `python -m playwright install --with-deps chromium`"
    elif "downloading" in out.lower() or "will download" in out.lower():
        c.result = "warn"
        c.detail += " — chromium browser not yet downloaded"
        c.fix = "run `python -m playwright install --with-deps chromium`"
    else:
        c.detail += " — chromium present"
    return c


# ── Ports ─────────────────────────────────────────────────────────────────
def _pid_holding_port(port: int) -> str | None:
    """Best-effort PID lookup for a process listening on ``port``."""
    try:
        if os.name == "nt":
            cp = _run(["netstat", "-ano", "-p", "TCP"], timeout=3)
            for line in (cp.stdout or "").splitlines():
                parts = line.split()
                # State LISTENING in column 4, local addr in column 2.
                if len(parts) >= 5 and parts[3].upper() == "LISTENING":
                    local = parts[1]
                    if local.endswith(f":{port}") or local.endswith(f"]:{port}"):
                        return parts[4]
        else:
            lsof = which("lsof")
            if lsof:
                cp = _run([lsof, "-iTCP", f"-i:{port}", "-sTCP:LISTEN", "-t"], timeout=3)
                pid = (cp.stdout or "").strip().splitlines()
                if pid:
                    return pid[0]
    except Exception:
        return None
    return None


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.25)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except (ConnectionRefusedError, socket.timeout):
            return False
        except OSError:
            return False


def check_ports() -> list[Check]:
    out: list[Check] = []
    for port, label in REQUIRED_PORTS:
        cid = f"DOC.PORT.{port}"
        c = Check(cid, f"port :{port}", "required")
        c.detail = label
        if _port_in_use(port):
            c.result = "warn"  # often it's our own container; warn, don't fail.
            pid = _pid_holding_port(port)
            if pid:
                c.detail += f"  -- in use by PID {pid}"
                if os.name == "nt":
                    c.fix = f"`taskkill /PID {pid} /F` to free it, or `make down` if it's our stack"
                else:
                    c.fix = f"`kill {pid}` to free it, or `make down` if it's our stack"
            else:
                c.detail += "  -- in use (process unknown)"
                if os.name == "nt":
                    c.fix = f"`netstat -ano | findstr :{port}` to find the PID"
                else:
                    c.fix = f"`lsof -i :{port}` to find the PID"
        out.append(c)
    return out


# ── Repo layout ──────────────────────────────────────────────────────────
def check_repo_paths() -> Check:
    c = Check("DOC.REPO.LAYOUT", "repo subdirectories", "required")
    missing = [p for p in REQUIRED_PATHS if not (ROOT / p).is_dir()]
    if missing:
        c.result = "fail"
        c.detail = "missing: " + ", ".join(missing)
        c.fix = "re-clone the repo; expected directories were not found"
    else:
        c.detail = "all present: " + ", ".join(REQUIRED_PATHS)
    return c


# ── Disk ─────────────────────────────────────────────────────────────────
def check_disk() -> Check:
    c = Check("DOC.DISK.FREE", "free disk space", "required")
    usage = shutil.disk_usage(str(ROOT))
    free_gb = usage.free / 1024**3
    c.detail = f"{free_gb:.1f} GB free on repo volume (need >= {REQ_DISK_GB})"
    if free_gb < REQ_DISK_GB:
        c.result = "fail"
        c.fix = "free disk space; Docker images + Playwright browsers need ~5 GB"
    return c


# ── OneDrive warning ─────────────────────────────────────────────────────
def check_onedrive() -> Check:
    c = Check("DOC.FS.ONEDRIVE", "filesystem speed", "recommended")
    path_str = str(ROOT)
    if "OneDrive" in path_str or "iCloud" in path_str or "Dropbox" in path_str:
        c.result = "warn"
        which_sync = "OneDrive" if "OneDrive" in path_str else ("iCloud" if "iCloud" in path_str else "Dropbox")
        c.detail = f"repo lives under {which_sync} — file syncs will slow npm/pip writes"
        c.fix = "move the repo to a non-synced path (e.g. `~/dev/once-procurement`) for faster builds"
    else:
        c.detail = "repo is on a non-synced path"
    return c


# ── Main ─────────────────────────────────────────────────────────────────
SECTIONS: list[tuple[str, list]] = []


def main() -> int:
    print(bold(cyan(f"Once dev doctor  ({platform.system()} {platform.release()})")))
    print(dim(f"  repo: {ROOT}"))

    all_checks: list[Check] = []

    header("Toolchain")
    for c in (check_python(), check_node(), check_npm(), check_git()):
        c.render()
        all_checks.append(c)

    header("Container runtime")
    for c in (check_docker_cli(), check_docker_daemon(), check_docker_compose()):
        c.render()
        all_checks.append(c)

    header("Browsers / automation")
    c = check_playwright_deps()
    c.render()
    all_checks.append(c)

    header("Repository")
    c = check_repo_paths()
    c.render()
    all_checks.append(c)

    header("Ports")
    for c in check_ports():
        c.render()
        all_checks.append(c)

    header("Disk space")
    c = check_disk()
    c.render()
    all_checks.append(c)

    header("Filesystem")
    c = check_onedrive()
    c.render()
    all_checks.append(c)

    # ── Summary ──────────────────────────────────────────────────────
    header("Summary")
    n_ok = sum(1 for c in all_checks if c.result == "ok")
    n_warn = sum(1 for c in all_checks if c.result == "warn")
    n_fail = sum(1 for c in all_checks if c.result == "fail" and c.category == "required")
    n_fail_rec = sum(1 for c in all_checks if c.result == "fail" and c.category == "recommended")

    parts = [
        green(f"✓ {n_ok} ok"),
        yellow(f"⚠ {n_warn} warnings"),
        red(f"✗ {n_fail} failures"),
    ]
    if n_fail_rec:
        parts.append(dim(f"({n_fail_rec} recommended)"))
    line = "  " + "  ·  ".join(parts)
    print(line)

    if n_fail:
        print()
        print(red("  Doctor: required checks failed — fix the items above before running `make setup`."))
        print(dim("  See docs/TROUBLESHOOTING.md for deeper help."))
        return 1

    print()
    if n_warn:
        print(yellow("  Doctor: ready (with warnings). Safe to run ") + cyan("make setup") + yellow("."))
    else:
        print(green("  Doctor: all green. Ready to run ") + cyan("make setup") + green("."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
