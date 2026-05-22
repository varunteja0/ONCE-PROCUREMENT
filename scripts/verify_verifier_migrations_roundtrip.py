"""One-off round-trip verifier for the two Phase 6.1 verifier-API migrations.

Closes verification gate #4 from /memories/session/plan.md:

    "alembic upgrade head on fresh SQLite + Postgres; alembic downgrade -1
     is a true inverse (drops indexes + table)."

This script runs the SQLite portion (Postgres requires a live DB, see
docs/RUNBOOK.md for the manual procedure). It:

    1. Creates a fresh temp SQLite file.
    2. Runs ``alembic upgrade head`` and asserts that
       ``verifier_api_keys`` + ``verifier_api_key_usage`` exist with the
       expected columns, the unique constraint on ``key_prefix``, and the
       composite uniqueness on (api_key_id, period_month).
    3. Downgrades stepwise back to the pre-verifier revision
       (``20260522_01_soc2_evidence``) and asserts both tables are gone.
    4. Upgrades to head again and re-checks the tables come back.
    5. Cleans up the temp DB.

Run from the repo root:
    .\\backend\\.venv\\Scripts\\python.exe .\\scripts\\verify_verifier_migrations_roundtrip.py
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
PY = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
PRE_VERIFIER_REV = "20260522_01_soc2_evidence"


def run_alembic(args: list[str], db_url: str) -> str:
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    result = subprocess.run(
        [str(PY), "-m", "alembic", *args],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(f"alembic {' '.join(args)} failed (rc={result.returncode})")
    return (result.stdout or "") + (result.stderr or "")


def table_exists(db_path: Path, name: str) -> bool:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
    return row is not None


def list_columns(db_path: Path, table: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def has_unique_on(db_path: Path, table: str, columns: tuple[str, ...]) -> bool:
    """Return True if SQLite has a UNIQUE index on exactly ``columns`` (any order)."""
    with sqlite3.connect(db_path) as conn:
        indexes = conn.execute(f"PRAGMA index_list({table})").fetchall()
        wanted = set(columns)
        for _, idx_name, is_unique, *_ in indexes:
            if not is_unique:
                continue
            idx_cols = {
                row[2] for row in conn.execute(f"PRAGMA index_info({idx_name})").fetchall()
            }
            if idx_cols == wanted:
                return True
    return False


def assert_tables_present(db_path: Path) -> None:
    assert table_exists(db_path, "verifier_api_keys"), "verifier_api_keys missing"
    assert table_exists(db_path, "verifier_api_key_usage"), "verifier_api_key_usage missing"

    expected_keys_cols = {
        "id", "tenant_id", "name", "key_prefix", "key_hash",
        "monthly_call_cap", "last_used_at", "created_at",
        "created_by_operator_id", "revoked_at",
    }
    cols = list_columns(db_path, "verifier_api_keys")
    missing = expected_keys_cols - cols
    assert not missing, f"verifier_api_keys missing columns: {missing}"

    expected_usage_cols = {"id", "api_key_id", "period_month", "count", "updated_at"}
    cols = list_columns(db_path, "verifier_api_key_usage")
    missing = expected_usage_cols - cols
    assert not missing, f"verifier_api_key_usage missing columns: {missing}"

    assert has_unique_on(db_path, "verifier_api_keys", ("key_prefix",)), \
        "UNIQUE(key_prefix) not enforced on verifier_api_keys"
    assert has_unique_on(
        db_path, "verifier_api_key_usage", ("api_key_id", "period_month")
    ), "UNIQUE(api_key_id, period_month) not enforced on verifier_api_key_usage"


def assert_tables_absent(db_path: Path) -> None:
    assert not table_exists(db_path, "verifier_api_keys"), \
        "verifier_api_keys still present after downgrade"
    assert not table_exists(db_path, "verifier_api_key_usage"), \
        "verifier_api_key_usage still present after downgrade"


def main() -> int:
    if not PY.exists():
        print(f"backend venv not found at {PY}", file=sys.stderr)
        return 2

    tmp_db = Path(tempfile.gettempdir()) / "once_verifier_migrations_roundtrip.db"
    tmp_db.unlink(missing_ok=True)
    db_url = f"sqlite+aiosqlite:///{tmp_db.as_posix()}"
    print(f"Using temp DB: {tmp_db}")

    try:
        print("\n[1/4] alembic upgrade head ...")
        run_alembic(["upgrade", "head"], db_url)
        assert_tables_present(tmp_db)
        print("    OK - both tables present with expected schema")

        print(f"\n[2/4] alembic downgrade {PRE_VERIFIER_REV} ...")
        run_alembic(["downgrade", PRE_VERIFIER_REV], db_url)
        assert_tables_absent(tmp_db)
        print("    OK - both tables dropped")

        print("\n[3/4] alembic upgrade head (re-apply) ...")
        run_alembic(["upgrade", "head"], db_url)
        assert_tables_present(tmp_db)
        print("    OK - both tables re-created")

        print("\n[4/4] cleanup")
        try:
            tmp_db.unlink(missing_ok=True)
            print("    OK")
        except PermissionError:
            print("    skipped (file locked by Windows, will be cleaned next run)")

        print("\nPASS: verifier migrations are reversible on SQLite")
        return 0
    finally:
        try:
            tmp_db.unlink(missing_ok=True)
        except PermissionError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
