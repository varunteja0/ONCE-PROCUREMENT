"""Realistic 3-month transcript seed for the Demo Specialty MGA tenant.

Run directly::

    python backend/scripts/seed_realistic.py            # default 50 suppliers, 90 days
    python backend/scripts/seed_realistic.py --seed 99  # override SEED_SECRET
    python backend/scripts/seed_realistic.py --dry-run  # counts only, no writes
    python backend/scripts/seed_realistic.py --reset    # delegate to reset script

Determinism contract
--------------------
Every row's primary key is a UUID v5 derived from
``(SEED_MARKER, kind, ordinal)`` — same inputs ⇒ same UUIDs ⇒ idempotent
``INSERT … ON CONFLICT DO NOTHING`` style behavior via a pre-flight
existence check. The ``SEED_SECRET`` integer is mixed into the FEIN /
phone / dollar amounts but never into a PK, so reseeding under a new
secret reuses the same tenant/users/suppliers rows.

Reset contract
--------------
Only rows whose tenant / user / portal IDs were emitted by this script
(under the current ``SEED_MARKER``) are removed. User-created data is
never touched. See ``seed_realistic_reset.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import os
import sys
import time as _time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Make `app.*` importable when running as a bare script.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = Path(__file__).resolve().parent
for _p in (_BACKEND_ROOT, _SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from random import Random  # noqa: E402

from _seed_data import SEED_MARKER  # noqa: E402
from _seed_data.coi_templates import LICENSE_STATES  # noqa: E402
from _seed_data.generators import (  # noqa: E402
    DeterministicIds,
    business_day_datetimes,
    deterministic_signing_seed,
    make_acord,
    make_coi,
    make_consent_signed_text,
    make_eo,
    make_license,
    make_loss_run,
    make_risk_schedule,
    make_supplier,
    submission_payload,
)
from _seed_data.narratives import (  # noqa: E402
    AUDIT_EVENT_TEMPLATES,
    FAILURE_NARRATIVES,
    RUNNING_NARRATIVES,
)
from _seed_data.portals import PORTAL_SEEDS  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)
from passlib.context import CryptContext  # noqa: E402, F401  # kept for parity with rest of app
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

import app.db as app_db  # noqa: E402
from app.models import (  # noqa: E402
    AcordForm,
    AuditLog,
    Base,
    CertificateOfInsurance,
    ConsentRecord,
    ConsentScope,
    EOCertificate,
    LossRun,
    Portal,
    ProducerLicense,
    RiskSchedule,
    SigningKey,
    SubmissionReceipt,
    SubmissionStatus,
    Supplier,
    SupplierSubmission,
    Tenant,
    TenantUser,
    User,
)
from app.utils.canonical_json import canonical_json_bytes, payload_sha256  # noqa: E402
from app.utils.crypto import derive_public_pem, sign  # noqa: E402
from app.utils.logging import get_logger  # noqa: E402

logger = get_logger("seed_realistic")

_PWD = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=4)


def _hash_demo_password(plaintext: str) -> str:
    """Bcrypt-hash a demo password.

    Uses ``bcrypt`` directly (skipping passlib's runtime backend detection
    which trips a ``ValueError: password cannot be longer than 72 bytes`` on
    newer bcrypt + passlib combinations). The output is still a standard
    ``$2b$`` hash compatible with the rest of the app's verification path.
    """
    import bcrypt as _bcrypt

    payload = plaintext.encode("utf-8")[:72]
    return _bcrypt.hashpw(payload, _bcrypt.gensalt(rounds=4)).decode("ascii")
_TENANT_SLUG = "demo-specialty-mga"
_TENANT_NAME = "Demo Specialty MGA"
_TOS_VERSION_HASH = hashlib.sha256(
    f"once-tos-v1|{SEED_MARKER}".encode()
).hexdigest()
_DEFAULT_SEED = int(os.environ.get("SEED_SECRET", "42"))


# ---------------------------------------------------------------------------
# Targets — these mirror the mission spec; tests assert against them.
# ---------------------------------------------------------------------------

# Failure-kind distribution within the failed bucket.
_FAILURE_MIX = (
    ("captcha", 0.35),
    ("auth_failed", 0.25),
    ("selector_drift", 0.20),
    ("timeout", 0.15),
    ("network", 0.05),
)

# Top-level status mix across all submissions.
_STATUS_MIX = (
    (SubmissionStatus.COMPLETED, 0.72),
    (SubmissionStatus.QUEUED, 0.16),
    (SubmissionStatus.FAILED, 0.08),
    (SubmissionStatus.RUNNING, 0.04),
)


# ---------------------------------------------------------------------------
# Counts / config dataclass
# ---------------------------------------------------------------------------


def _bucket(rng: Random) -> str:
    """Size bucket distribution: 60% small, 30% mid, 10% large."""

    r = rng.random()
    if r < 0.60:
        return "small"
    if r < 0.90:
        return "mid"
    return "large"


def _weighted_pick(rng: Random, mix: tuple[tuple[Any, float], ...]) -> Any:
    r = rng.random()
    cum = 0.0
    for value, weight in mix:
        cum += weight
        if r < cum:
            return value
    return mix[-1][0]


def _stable_uuid_seed(seed_secret: int) -> int:
    """Hash SEED_MARKER + seed_secret into the 64-bit Random() init value."""

    raw = f"{SEED_MARKER}|{seed_secret}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


# ---------------------------------------------------------------------------
# Existence check (idempotency gate)
# ---------------------------------------------------------------------------


async def _tenant_exists(session: AsyncSession, tenant_id: str) -> bool:
    result = await session.execute(select(Tenant.id).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Core seed
# ---------------------------------------------------------------------------


async def seed(  # noqa: PLR0915 — single linear orchestrator on purpose
    *,
    seed_secret: int = _DEFAULT_SEED,
    n_suppliers: int = 50,
    n_days: int = 90,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Insert (or skip) the full realistic seed; return a counts summary."""

    start = _time.perf_counter()
    rng = Random(_stable_uuid_seed(seed_secret))  # noqa: S311 - deterministic demo seed, not crypto
    ids = DeterministicIds()

    now = datetime.now(tz=UTC)
    today = now.date()

    counts: dict[str, int] = {}

    # ------------------------------------------------------------------ ids
    tenant_id = ids.of("tenant", _TENANT_SLUG)
    user_specs = [
        ("owner", "Sam Owens", "owner"),
        ("admin", "Riley Admin", "admin"),
        ("ops1", "Jordan Ops", "ops"),
        ("ops2", "Casey Ops", "ops"),
    ]
    user_ids = {nick: ids.of("user", nick) for nick, *_ in user_specs}
    owner_id = user_ids["owner"]

    # Portals (global rows — IDs deterministic by platform value).
    portal_ids: dict[str, str] = {
        seed_def.platform.value: ids.of("portal", seed_def.platform.value)
        for seed_def in PORTAL_SEEDS
    }
    supported_portal_values = [
        s.platform.value for s in PORTAL_SEEDS if s.is_supported
    ]

    # ------------------------------------------------------------------ dry-run
    if dry_run:
        # Compute & return the projected counts without touching the DB.
        counts = _project_counts(n_suppliers=n_suppliers, n_days=n_days)
        elapsed = _time.perf_counter() - start
        counts["__elapsed_sec__"] = round(elapsed, 3)
        counts["__random_state_hash__"] = _rng_fingerprint(rng)
        logger.info("seed_realistic_dry_run", **{k: v for k, v in counts.items() if not k.startswith("__")})
        _print_summary(counts, dry_run=True)
        return counts

    async with app_db.AsyncSessionLocal() as session:
        # Idempotency: if the tenant already exists under this marker, exit.
        if await _tenant_exists(session, tenant_id):
            logger.info(
                "seed_realistic_skip_existing",
                tenant_id=tenant_id,
                marker=SEED_MARKER,
            )
            elapsed = _time.perf_counter() - start
            return {
                "__skipped__": True,
                "__elapsed_sec__": round(elapsed, 3),
                "__random_state_hash__": _rng_fingerprint(rng),
            }

        # ------------------------------------------------------------ signing key
        # Stash the deterministic Ed25519 public key so signed receipts can be
        # verified later. We never persist the private half — that lives in
        # ``settings`` (or is regenerated from ``seed_secret`` on demand).
        priv_seed = deterministic_signing_seed(seed_secret)
        private_key = Ed25519PrivateKey.from_private_bytes(priv_seed)
        public_pem = derive_public_pem(private_key)
        signing_key_id = ids.of("signing_key", "default-1")

        existing_key = (
            await session.execute(select(SigningKey).where(SigningKey.id == signing_key_id))
        ).scalar_one_or_none()
        if existing_key is None:
            session.add(
                SigningKey(
                    id=signing_key_id,
                    algorithm="ed25519",
                    public_key_pem=public_pem,
                    description=f"Realistic seed key ({SEED_MARKER})",
                )
            )

        # ------------------------------------------------------------ tenant + users
        session.add(
            Tenant(
                id=tenant_id,
                name=_TENANT_NAME,
                slug=_TENANT_SLUG,
                plan="growth",
                is_active=True,
            )
        )
        counts["tenants"] = 1

        hashed_pw = _hash_demo_password(f"DemoPass!{seed_secret}")
        for nick, full_name, role in user_specs:
            session.add(
                User(
                    id=user_ids[nick],
                    email=f"{nick}@example.com",
                    hashed_password=hashed_pw,
                    full_name=full_name,
                    is_active=True,
                )
            )
            session.add(
                TenantUser(
                    id=ids.of("tenant_user", nick),
                    tenant_id=tenant_id,
                    user_id=user_ids[nick],
                    role=role,
                )
            )
        counts["users"] = len(user_specs)
        counts["tenant_users"] = len(user_specs)

        # ------------------------------------------------------------ portals
        for seed_def in PORTAL_SEEDS:
            pid = portal_ids[seed_def.platform.value]
            existing = (
                await session.execute(select(Portal).where(Portal.id == pid))
            ).scalar_one_or_none()
            if existing is not None:
                continue
            session.add(
                Portal(
                    id=pid,
                    platform=seed_def.platform,
                    display_name=seed_def.display_name,
                    base_url=seed_def.base_url,
                    is_supported=seed_def.is_supported,
                    risky=seed_def.risky,
                    notes=f"[seed:{SEED_MARKER}] {seed_def.notes}",
                )
            )
        counts["portals"] = len(PORTAL_SEEDS)

        await session.flush()

        # ------------------------------------------------------------ suppliers
        supplier_rows: list[dict[str, Any]] = []
        for i in range(n_suppliers):
            spec = make_supplier(rng, ordinal=i, size_bucket=_bucket(rng))
            sid = ids.of("supplier", i)
            session.add(
                Supplier(
                    id=sid,
                    tenant_id=tenant_id,
                    **spec,
                )
            )
            supplier_rows.append({"id": sid, "ordinal": i, **spec})
            if (i + 1) % 200 == 0:
                await session.flush()
        counts["suppliers"] = n_suppliers
        await session.flush()

        # ------------------------------------------------------------ consents
        # 35 of the 50 suppliers (the ones that "ever submitted") get consent.
        n_consents = min(35, n_suppliers)
        consent_for: dict[str, str] = {}
        for i in range(n_consents):
            supplier = supplier_rows[i]
            granted_at = now.replace(microsecond=0) - _delta_days(rng, 5, 85)
            cid = ids.of("consent", i)
            session.add(
                ConsentRecord(
                    id=cid,
                    tenant_id=tenant_id,
                    supplier_id=supplier["id"],
                    scope=ConsentScope.SUBMIT_ON_BEHALF,
                    portal_ids_json=list(portal_ids.values())[:5],
                    granted_at=granted_at,
                    granted_by_user_id=owner_id,
                    signed_text=make_consent_signed_text(
                        supplier_name=supplier["legal_name"],
                        granted_at=granted_at,
                        portal_names=supported_portal_values[:5],
                    ),
                    signature_b64=base64.b64encode(
                        sign(
                            private_key,
                            canonical_json_bytes(
                                {"supplier_id": supplier["id"], "granted_at": granted_at.isoformat()}
                            ),
                        )
                    ).decode("ascii"),
                )
            )
            consent_for[supplier["id"]] = cid
        counts["consent_records"] = n_consents
        await session.flush()

        # ------------------------------------------------------------ COIs (120)
        n_cois = 120
        # 18 expiring within 30 days, 6 already expired, rest active.
        coi_buckets = (
            ["expiring_soon"] * 18 + ["expired"] * 6 + ["active"] * (n_cois - 24)
        )
        for j, bucket in enumerate(coi_buckets):
            supplier = supplier_rows[j % n_suppliers]
            spec = make_coi(rng, supplier_id=supplier["id"], today=today, bucket=bucket)
            session.add(
                CertificateOfInsurance(
                    id=ids.of("coi", j),
                    tenant_id=tenant_id,
                    uploaded_by_user_id=owner_id,
                    **spec,
                )
            )
            if (j + 1) % 200 == 0:
                await session.flush()
        counts["certificates_of_insurance"] = n_cois
        await session.flush()

        # ------------------------------------------------------------ producer licenses (80 / 12 states)
        n_licenses = 80
        # Ensure every state in LICENSE_STATES appears at least once.
        forced_states = list(LICENSE_STATES)
        remaining = n_licenses - len(forced_states)
        chosen_states = forced_states + [
            rng.choice(LICENSE_STATES) for _ in range(remaining)
        ]
        for j, state in enumerate(chosen_states):
            supplier = supplier_rows[j % n_suppliers]
            spec = make_license(
                rng,
                supplier_id=supplier["id"],
                supplier_name=supplier["legal_name"],
                state=state,
                today=today,
            )
            session.add(
                ProducerLicense(
                    id=ids.of("license", j),
                    tenant_id=tenant_id,
                    **spec,
                )
            )
        counts["producer_licenses"] = n_licenses
        await session.flush()

        # ------------------------------------------------------------ E&O (35)
        n_eo = 35
        for j in range(n_eo):
            supplier = supplier_rows[j % n_suppliers]
            spec = make_eo(
                rng,
                supplier_id=supplier["id"],
                supplier_name=supplier["legal_name"],
                today=today,
            )
            session.add(
                EOCertificate(id=ids.of("eo", j), tenant_id=tenant_id, **spec)
            )
        counts["eo_certificates"] = n_eo

        # ------------------------------------------------------------ ACORD forms (60)
        n_acord = 60
        for j in range(n_acord):
            supplier = supplier_rows[j % n_suppliers]
            spec = make_acord(
                rng,
                supplier_id=supplier["id"],
                supplier_name=supplier["legal_name"],
                today=today,
            )
            session.add(AcordForm(id=ids.of("acord", j), tenant_id=tenant_id, **spec))
        counts["acord_forms"] = n_acord

        # ------------------------------------------------------------ risk schedules (45)
        n_schedules = 45
        for j in range(n_schedules):
            supplier = supplier_rows[j % n_suppliers]
            spec = make_risk_schedule(rng, supplier_id=supplier["id"], today=today)
            session.add(
                RiskSchedule(id=ids.of("schedule", j), tenant_id=tenant_id, **spec)
            )
        counts["risk_schedules"] = n_schedules

        # ------------------------------------------------------------ loss runs (200)
        n_loss = 200
        for j in range(n_loss):
            supplier = supplier_rows[j % n_suppliers]
            spec = make_loss_run(rng, supplier_id=supplier["id"], today=today)
            session.add(
                LossRun(id=ids.of("loss", j), tenant_id=tenant_id, **spec)
            )
            if (j + 1) % 200 == 0:
                await session.flush()
        counts["loss_runs"] = n_loss
        await session.flush()

        # ------------------------------------------------------------ submissions (800)
        n_submissions = 800
        # Cluster timestamps on business days.
        timestamps = business_day_datetimes(
            rng, count=n_submissions, days=n_days, now=now
        )
        # Track which submissions are completed (need receipts) and which are
        # failed (need a narrative).
        completed_indices: list[int] = []
        failed_specs: list[tuple[int, str]] = []

        for j in range(n_submissions):
            supplier = supplier_rows[j % n_suppliers]
            consent_id = consent_for.get(supplier["id"])  # may be None
            portal_value = supported_portal_values[j % len(supported_portal_values)]
            portal_id = portal_ids[portal_value]
            submitted_at = timestamps[j] if j < len(timestamps) else now
            status = _weighted_pick(rng, _STATUS_MIX)

            payload = submission_payload(
                rng,
                supplier_name=supplier["legal_name"],
                portal=portal_value,
                submitted_at=submitted_at,
            )

            last_error: str | None = None
            failure_kind: str | None = None
            claimed_at = started_at = completed_at = None
            attempt_count = 0
            result_json: dict[str, Any] | None = None

            if status == SubmissionStatus.COMPLETED:
                claimed_at = submitted_at
                started_at = submitted_at
                completed_at = submitted_at
                attempt_count = 1
                result_json = {"_seed_marker": SEED_MARKER, "ok": True}
                completed_indices.append(j)
            elif status == SubmissionStatus.FAILED:
                failure_kind = _weighted_pick(rng, _FAILURE_MIX)
                pool = FAILURE_NARRATIVES[failure_kind]
                last_error = pool[j % len(pool)]
                claimed_at = submitted_at
                started_at = submitted_at
                completed_at = submitted_at
                attempt_count = rng.randint(1, 3)
                failed_specs.append((j, failure_kind))
                result_json = {
                    "_seed_marker": SEED_MARKER,
                    "ok": False,
                    "error_kind": failure_kind,
                }
            elif status == SubmissionStatus.RUNNING:
                claimed_at = submitted_at
                started_at = submitted_at
                attempt_count = 1
                last_error = RUNNING_NARRATIVES[j % len(RUNNING_NARRATIVES)]
            # QUEUED → no timestamps yet

            sub_id = ids.of("submission", j)
            session.add(
                SupplierSubmission(
                    id=sub_id,
                    tenant_id=tenant_id,
                    supplier_id=supplier["id"],
                    portal_id=portal_id,
                    status=status,
                    payload_json=payload,
                    result_json=result_json,
                    attempt_count=attempt_count,
                    last_error=last_error,
                    claimed_at=claimed_at,
                    started_at=started_at,
                    completed_at=completed_at,
                    consent_record_id=consent_id,
                )
            )
            if (j + 1) % 200 == 0:
                await session.flush()
        counts["supplier_submissions"] = n_submissions
        await session.flush()

        # ------------------------------------------------------------ receipts (576)
        # One per completed submission. Need consent for each.
        # The first 12 are deliberately tampered (mutated payload_hash).
        # If a completed submission has no consent (supplier ordinal >= 35),
        # we synthesize a consent record on the fly so the FK holds.
        receipt_count = 0
        tampered_target = 12
        for k, j in enumerate(completed_indices):
            supplier = supplier_rows[j % n_suppliers]
            portal_value = supported_portal_values[j % len(supported_portal_values)]
            submitted_at = timestamps[j] if j < len(timestamps) else now
            sub_id = ids.of("submission", j)
            payload = submission_payload(
                rng,  # rng state advances deterministically
                supplier_name=supplier["legal_name"],
                portal=portal_value,
                submitted_at=submitted_at,
            )
            payload_hash = payload_sha256(payload)
            consent_id = consent_for.get(supplier["id"])
            if consent_id is None:
                # Synthetic consent for the long-tail suppliers.
                consent_id = ids.of("consent_synthetic", j)
                session.add(
                    ConsentRecord(
                        id=consent_id,
                        tenant_id=tenant_id,
                        supplier_id=supplier["id"],
                        scope=ConsentScope.SUBMIT_ON_BEHALF,
                        portal_ids_json=[portal_ids[portal_value]],
                        granted_at=submitted_at,
                        granted_by_user_id=owner_id,
                        signed_text=make_consent_signed_text(
                            supplier_name=supplier["legal_name"],
                            granted_at=submitted_at,
                            portal_names=[portal_value],
                        ),
                        signature_b64=base64.b64encode(
                            sign(
                                private_key,
                                canonical_json_bytes(
                                    {
                                        "supplier_id": supplier["id"],
                                        "granted_at": submitted_at.isoformat(),
                                    }
                                ),
                            )
                        ).decode("ascii"),
                    )
                )
                consent_for[supplier["id"]] = consent_id

            receipt_id = ids.of("receipt", k)
            public_payload = {
                "receipt_id": receipt_id,
                "tenant_id": tenant_id,
                "supplier_id": supplier["id"],
                "portal": portal_value,
                "submission_id": sub_id,
                "submitted_at": submitted_at.isoformat(),
                "payload_hash": payload_hash,
                "tos_version_hash": _TOS_VERSION_HASH,
                "consent_record_id": consent_id,
            }
            signature = sign(private_key, canonical_json_bytes(public_payload))
            signature_b64 = base64.b64encode(signature).decode("ascii")

            # Tamper the first ``tampered_target`` receipts by flipping a hex
            # digit inside ``payload_hash``. The signature remains the
            # original — verification will fail.
            if k < tampered_target:
                tampered_hash = ("0" if payload_hash[0] != "0" else "f") + payload_hash[1:]
                public_payload["payload_hash"] = tampered_hash

            session.add(
                SubmissionReceipt(
                    id=receipt_id,
                    submission_id=sub_id,
                    tenant_id=tenant_id,
                    supplier_id=supplier["id"],
                    portal_platform=portal_value,
                    submitted_at=submitted_at,
                    payload_hash=public_payload["payload_hash"],
                    tos_version_hash=_TOS_VERSION_HASH,
                    consent_record_id=consent_id,
                    signing_key_id=signing_key_id,
                    signature_b64=signature_b64,
                    public_payload_json=public_payload,
                )
            )
            receipt_count += 1
            if receipt_count % 200 == 0:
                await session.flush()

        counts["submission_receipts"] = receipt_count
        counts["consent_records"] = len(consent_for)
        await session.flush()

        # ------------------------------------------------------------ audit log
        # ~3 entries per supplier — gives the audit page real density.
        audit_n = n_suppliers * 3
        for j in range(audit_n):
            template_action, template_msg = AUDIT_EVENT_TEMPLATES[
                j % len(AUDIT_EVENT_TEMPLATES)
            ]
            actor_nick = user_specs[j % len(user_specs)][0]
            supplier = supplier_rows[j % n_suppliers]
            occurred_at = now - _delta_days(rng, 1, n_days)
            session.add(
                AuditLog(
                    id=ids.of("audit", j),
                    tenant_id=tenant_id,
                    actor_user_id=user_ids[actor_nick],
                    action=template_action,
                    resource_type="supplier",
                    resource_id=supplier["id"],
                    metadata_json={
                        "_seed_marker": SEED_MARKER,
                        "message": template_msg.format(
                            actor=actor_nick, resource=supplier["legal_name"]
                        ),
                    },
                    ip_address="198.51.100.42",
                    occurred_at=occurred_at,
                )
            )
            if (j + 1) % 200 == 0:
                await session.flush()
        counts["audit_logs"] = audit_n

        await session.commit()

    elapsed = _time.perf_counter() - start
    counts["__elapsed_sec__"] = round(elapsed, 3)
    counts["__random_state_hash__"] = _rng_fingerprint(rng)
    counts["__seed_marker__"] = SEED_MARKER
    counts["__seed_secret__"] = seed_secret
    logger.info("seed_realistic_complete", **{k: v for k, v in counts.items() if not k.startswith("__")})
    _print_summary(counts, dry_run=False)
    return counts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _delta_days(rng: Random, lo: int, hi: int):
    from datetime import timedelta

    return timedelta(days=rng.randint(lo, hi), seconds=rng.randint(0, 86_399))


def _rng_fingerprint(rng: Random) -> str:
    """Return a stable hex digest of the RNG state — used by tests."""

    state = rng.getstate()
    flat = repr(state).encode("utf-8")
    return hashlib.sha256(flat).hexdigest()[:16]


def _project_counts(*, n_suppliers: int, n_days: int) -> dict[str, int]:
    """Compute the counts a real run *would* insert — no DB access."""

    n_submissions = 800
    n_completed = int(round(n_submissions * 0.72))
    return {
        "tenants": 1,
        "users": 4,
        "tenant_users": 4,
        "portals": len(PORTAL_SEEDS),
        "suppliers": n_suppliers,
        "consent_records": min(35, n_suppliers),
        "certificates_of_insurance": 120,
        "producer_licenses": 80,
        "eo_certificates": 35,
        "acord_forms": 60,
        "risk_schedules": 45,
        "loss_runs": 200,
        "supplier_submissions": n_submissions,
        "submission_receipts": n_completed,
        "audit_logs": n_suppliers * 3,
    }


def _print_summary(counts: dict[str, Any], *, dry_run: bool) -> None:
    label = "PROJECTED" if dry_run else "INSERTED"
    print()
    print(f"+-- Seed summary ({label}) " + "-" * 36 + "+")
    for k, v in counts.items():
        if k.startswith("__"):
            continue
        print(f"|  {k:<32s} {v:>10}                  |")
    print("+" + "-" * 58 + "+")
    for k in ("__elapsed_sec__", "__random_state_hash__", "__seed_marker__", "__seed_secret__"):
        if k in counts:
            label_k = k.strip("_")
            print(f"|  {label_k:<32s} {str(counts[k]):>10}                  |")
    print("+" + "-" * 58 + "+")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Realistic 3-month transcript seed for Once.")
    p.add_argument("--seed", type=int, default=_DEFAULT_SEED, help="SEED_SECRET integer (default 42)")
    p.add_argument("--suppliers", type=int, default=50, help="Number of suppliers (default 50)")
    p.add_argument("--days", type=int, default=90, help="Submission window in days (default 90)")
    p.add_argument("--dry-run", action="store_true", help="Print counts only; no DB writes.")
    p.add_argument("--reset", action="store_true", help="Delegate to seed_realistic_reset before seeding.")
    return p.parse_args(argv)


async def _async_main(args: argparse.Namespace) -> dict[str, Any]:
    if args.reset:
        from seed_realistic_reset import reset as do_reset

        await do_reset(seed_secret=args.seed)

    # Ensure schema exists (no-op on prod migrated DB; useful for fresh sqlite).
    async with app_db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return await seed(
        seed_secret=args.seed,
        n_suppliers=args.suppliers,
        n_days=args.days,
        dry_run=args.dry_run,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        logger.warning("seed_realistic_interrupted")
        return 130
    except Exception:  # noqa: BLE001
        logger.exception("seed_realistic_failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
