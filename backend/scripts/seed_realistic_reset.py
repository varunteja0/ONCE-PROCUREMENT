"""Idempotent reset for ``seed_realistic.py``.

Deletes **only** the rows whose IDs were emitted by the realistic seed
(under the current ``SEED_MARKER``). Rows created by humans through the
real app (or by other seeds) are never touched.

Strategy
--------
The realistic seed assigns every primary key as ``uuid5(NS, "{marker}|{kind}|{ord}")``.
The reset script computes exactly the same UUID space and issues bulk
``DELETE … WHERE id IN (…)`` statements in dependency order so the
``RESTRICT`` foreign key between ``submission_receipts`` and
``consent_records`` is satisfied. We deliberately do *not* rely on
``ON DELETE CASCADE`` because the receipt→consent FK is ``RESTRICT`` —
cascading from the tenant would surface as an error on Postgres.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = Path(__file__).resolve().parent
for _p in (_BACKEND_ROOT, _SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _seed_data import SEED_MARKER  # noqa: E402
from _seed_data.generators import DeterministicIds  # noqa: E402
from _seed_data.portals import PORTAL_SEEDS  # noqa: E402
from sqlalchemy import delete  # noqa: E402

import app.db as app_db  # noqa: E402
from app.models import (  # noqa: E402
    AcordForm,
    AuditLog,
    CertificateOfInsurance,
    ConsentRecord,
    EOCertificate,
    LossRun,
    Portal,
    ProducerLicense,
    RiskSchedule,
    SigningKey,
    SubmissionReceipt,
    Supplier,
    SupplierSubmission,
    Tenant,
    TenantUser,
    User,
)
from app.utils.logging import get_logger  # noqa: E402

logger = get_logger("seed_realistic_reset")

_TENANT_SLUG = "demo-specialty-mga"
_USER_NICKS = ("owner", "admin", "ops1", "ops2")
_DEFAULT_SEED = int(os.environ.get("SEED_SECRET", "42"))


def _id_space() -> dict[str, list[str]]:
    """Compute every deterministic ID the seed would emit (upper bound)."""

    ids = DeterministicIds()
    return {
        "tenant": [ids.of("tenant", _TENANT_SLUG)],
        "user": [ids.of("user", n) for n in _USER_NICKS],
        "tenant_user": [ids.of("tenant_user", n) for n in _USER_NICKS],
        "portal": [ids.of("portal", s.platform.value) for s in PORTAL_SEEDS],
        "signing_key": [ids.of("signing_key", "default-1")],
        # The numeric series below are over-provisioned. DELETE WHERE IN is
        # a no-op for IDs that don't exist, so it's safe to delete the
        # full computed set even if the latest seed run created fewer rows.
        "supplier": [ids.of("supplier", i) for i in range(2000)],
        "consent": [ids.of("consent", i) for i in range(2000)]
        + [ids.of("consent_synthetic", i) for i in range(2000)],
        "coi": [ids.of("coi", i) for i in range(2000)],
        "license": [ids.of("license", i) for i in range(2000)],
        "eo": [ids.of("eo", i) for i in range(2000)],
        "acord": [ids.of("acord", i) for i in range(2000)],
        "schedule": [ids.of("schedule", i) for i in range(2000)],
        "loss": [ids.of("loss", i) for i in range(2000)],
        "submission": [ids.of("submission", i) for i in range(2000)],
        "receipt": [ids.of("receipt", i) for i in range(2000)],
        "audit": [ids.of("audit", i) for i in range(2000)],
    }


# Dependency-ordered tuples: (Model, key_name in _id_space).
_DELETE_ORDER: tuple[tuple[type, str], ...] = (
    (AuditLog, "audit"),
    (SubmissionReceipt, "receipt"),
    (SupplierSubmission, "submission"),
    (AcordForm, "acord"),
    (RiskSchedule, "schedule"),
    (LossRun, "loss"),
    (EOCertificate, "eo"),
    (ProducerLicense, "license"),
    (CertificateOfInsurance, "coi"),
    (ConsentRecord, "consent"),
    (Supplier, "supplier"),
    (TenantUser, "tenant_user"),
    (Tenant, "tenant"),
    (User, "user"),
    (SigningKey, "signing_key"),
    (Portal, "portal"),
)


async def reset(*, seed_secret: int = _DEFAULT_SEED) -> dict[str, int]:
    """Delete every row whose ID was emitted by the realistic seed."""

    space = _id_space()
    removed: dict[str, int] = {}

    async with app_db.AsyncSessionLocal() as session:
        for model, key in _DELETE_ORDER:
            id_chunk = space[key]
            if not id_chunk:
                continue
            # Chunk by 500 to keep SQL parameter counts modest on SQLite.
            total = 0
            for start in range(0, len(id_chunk), 500):
                chunk = id_chunk[start : start + 500]
                result = await session.execute(
                    delete(model).where(model.id.in_(chunk))  # type: ignore[attr-defined]
                )
                total += result.rowcount or 0
            removed[model.__tablename__] = total
        await session.commit()

    logger.info(
        "seed_realistic_reset_complete",
        marker=SEED_MARKER,
        seed_secret=seed_secret,
        **removed,
    )
    return removed


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Delete only the rows created by seed_realistic.py.")
    p.add_argument("--seed", type=int, default=_DEFAULT_SEED, help="SEED_SECRET (matches seed run).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        removed = asyncio.run(reset(seed_secret=args.seed))
    except Exception:  # noqa: BLE001
        logger.exception("seed_realistic_reset_failed")
        return 1
    print("Reset removed:")
    for table, n in removed.items():
        print(f"  {table:<32s} {n:>6}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
